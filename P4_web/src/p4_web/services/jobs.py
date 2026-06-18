from pathlib import Path

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from p4_web.api.schemas import JobCreate
from p4_web.core.config import Settings
from p4_web.core.time import utcnow
from p4_web.domain.enums import JobKind, JobStatus
from p4_web.persistence.models import Artifact, Job, JobLog, ProjectVersion
from p4_web.runners import (
    DryRunRunner,
    LegacyP4Runner,
    RunnerContext,
    RunnerExecutionError,
    RunnerPort,
)
from p4_web.services.projects import ConflictError, NotFoundError, get_project, get_version
from p4_web.services.sync_import import import_workspace_version
from p4_web.services.workspaces import materialize_version_workspace
from p4_web.storage import StorageBackend

VERSION_PRODUCING_JOB_KINDS = {
    JobKind.PACK_MODULES,
    JobKind.UNPACK_MODULES,
}


async def create_job(
    session: AsyncSession,
    data: JobCreate,
    actor_id: str | None = None,
) -> Job:
    project = await get_project(session, data.project_id)
    version = await get_version(session, data.version_id)
    if version.project_id != project.id:
        raise ConflictError("Version does not belong to project")

    job = Job(
        project_id=project.id,
        version_id=version.id,
        kind=data.kind,
        parameters=data.parameters,
        requested_by_user_id=actor_id,
    )
    session.add(job)
    await session.commit()
    await session.refresh(job)
    return job


async def get_job(session: AsyncSession, job_id: str) -> Job:
    job = await session.get(Job, job_id)
    if job is None:
        raise NotFoundError("Job not found")
    return job


async def list_job_logs(
    session: AsyncSession,
    job_id: str,
    cursor: int | None = None,
    limit: int = 200,
) -> tuple[list[JobLog], int | None]:
    stmt = select(JobLog).where(JobLog.job_id == job_id).order_by(JobLog.sequence).limit(limit)
    if cursor is not None:
        stmt = stmt.where(JobLog.sequence > cursor)
    result = await session.execute(stmt)
    logs = list(result.scalars().all())
    next_cursor = logs[-1].sequence if logs else cursor
    return logs, next_cursor


async def cancel_job(session: AsyncSession, job_id: str) -> Job:
    job = await get_job(session, job_id)
    if job.status in {JobStatus.QUEUED, JobStatus.RUNNING}:
        job.status = JobStatus.CANCEL_REQUESTED
        await session.commit()
        await session.refresh(job)
    return job


async def run_job(
    session_factory: async_sessionmaker[AsyncSession],
    job_id: str,
    settings: Settings,
    storage: StorageBackend,
) -> None:
    async with session_factory() as session:
        job = await get_job(session, job_id)
        if job.status == JobStatus.CANCEL_REQUESTED:
            job.status = JobStatus.CANCELED
            job.finished_at = utcnow()
            await session.commit()
            return

        job.status = JobStatus.RUNNING
        job.started_at = utcnow()
        job.progress_total = 100
        job.progress_current = 5
        await session.commit()
        await append_job_log(session, job.id, "info", "Job started.")

        try:
            version = await session.get(ProjectVersion, job.version_id)
            if version is None:
                raise NotFoundError("Project version not found")
            runner = build_runner(settings)
            workspace_dir = _workspace_dir(settings.workspace_root, job.id)
            workspace_dir.mkdir(parents=True, exist_ok=True)
            project_path = await materialize_version_workspace(
                session,
                storage,
                version,
                workspace_dir,
            )
            parameters = dict(job.parameters)
            parameters["project_path"] = str(project_path)
            context = RunnerContext(
                job_id=job.id,
                project_id=job.project_id,
                version_id=job.version_id,
                kind=job.kind,
                parameters=parameters,
                workspace_dir=workspace_dir,
                legacy_p4_app_path=settings.legacy_p4_app_path,
            )
            await append_job_log(session, job.id, "info", f"Workspace prepared: {project_path}")
            job.progress_current = 25
            await session.commit()
            result = await runner.run(context)
            job.progress_current = 60
            await session.commit()

            for message in result.logs:
                await append_job_log(session, job.id, "info", message)
            target_version = version
            if job.kind in VERSION_PRODUCING_JOB_KINDS:
                target_version = await import_workspace_version(
                    session=session,
                    storage=storage,
                    root=project_path,
                    project_id=job.project_id,
                    label=_result_version_label(job),
                    base_version_id=version.id,
                    actor_id=job.requested_by_user_id,
                    root_name=_manifest_root_name(version, project_path),
                    exclude_paths={spec.path.strip("/") for spec in result.artifacts},
                )
                job.parameters = {
                    **dict(job.parameters),
                    "produced_version_id": target_version.id,
                    "produced_version_number": target_version.version_number,
                }
                job.progress_current = 85
                await append_job_log(
                    session,
                    job.id,
                    "info",
                    f"Created version #{target_version.version_number}.",
                )
            job.progress_current = 95
            await session.commit()
            for spec in result.artifacts:
                if spec.data is not None:
                    key = f"{target_version.snapshot_prefix}/artifacts/{spec.path}"
                    stored = storage.put_bytes(key, spec.data, spec.content_type)
                elif spec.local_path is not None:
                    key = f"{target_version.snapshot_prefix}/artifacts/{spec.path}"
                    stored = storage.put_file(key, spec.local_path, spec.content_type)
                else:
                    continue
                artifact = Artifact(
                    project_id=job.project_id,
                    version_id=target_version.id,
                    job_id=job.id,
                    kind=spec.kind,
                    path=spec.path,
                    storage_key=stored.key,
                    sha256=stored.sha256,
                    size_bytes=stored.size_bytes,
                    content_type=stored.content_type,
                )
                session.add(artifact)

            job.status = JobStatus.SUCCEEDED
            job.progress_current = 100
            job.finished_at = utcnow()
            await append_job_log(session, job.id, "info", "Job completed successfully.")
            await session.commit()
        except RunnerExecutionError as exc:
            for message in exc.logs:
                await append_job_log(session, job.id, "error", message)
            job.status = JobStatus.FAILED
            job.error_message = str(exc)
            job.finished_at = utcnow()
            await session.commit()
        except Exception as exc:
            job.status = JobStatus.FAILED
            job.error_message = str(exc)
            job.finished_at = utcnow()
            await append_job_log(session, job.id, "error", str(exc))
            await session.commit()


async def append_job_log(
    session: AsyncSession,
    job_id: str,
    level: str,
    message: str,
) -> JobLog:
    result = await session.execute(
        select(func.max(JobLog.sequence)).where(JobLog.job_id == job_id)
    )
    next_sequence = int(result.scalar_one_or_none() or 0) + 1
    row = JobLog(job_id=job_id, sequence=next_sequence, level=level, message=message)
    session.add(row)
    await session.commit()
    await session.refresh(row)
    return row


def build_runner(settings: Settings) -> RunnerPort:
    if settings.enable_legacy_runner:
        return LegacyP4Runner(
            python_executable=settings.legacy_python_executable,
            command_template=settings.legacy_runner_command,
            timeout_seconds=settings.legacy_runner_timeout_seconds,
            pdf_artifact_globs=settings.legacy_pdf_artifact_globs,
        )
    return DryRunRunner()


def _workspace_dir(root: Path, job_id: str) -> Path:
    return root / job_id


def _result_version_label(job: Job) -> str:
    value = str(job.parameters.get("version_label") or "").strip()
    if value:
        return value
    return job.kind.value.replace("_", " ")


def _manifest_root_name(version: ProjectVersion, project_path: Path) -> str:
    root_name = version.manifest.get("root_name")
    if isinstance(root_name, str) and root_name.strip():
        return root_name
    return project_path.name
