from copy import deepcopy

from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from p4_web.api.schemas import ProjectCopyRequest, ProjectCreate, VersionCreate
from p4_web.core.slug import slugify
from p4_web.domain.enums import JobStatus, VersionStatus
from p4_web.persistence.models import (
    Approval,
    Artifact,
    FileObject,
    Job,
    JobLog,
    Project,
    ProjectVersion,
)
from p4_web.storage import StorageBackend


class NotFoundError(Exception):
    pass


class ConflictError(Exception):
    pass


ACTIVE_JOB_STATUSES = {
    JobStatus.QUEUED,
    JobStatus.RUNNING,
    JobStatus.CANCEL_REQUESTED,
}


async def create_project(
    session: AsyncSession,
    data: ProjectCreate,
    actor_id: str | None = None,
) -> Project:
    base_slug = data.slug or slugify(data.name)
    slug = base_slug
    suffix = 2
    while await _slug_exists(session, slug):
        slug = f"{base_slug}-{suffix}"
        suffix += 1

    project = Project(
        name=data.name,
        slug=slug,
        description=data.description,
        default_client=data.default_client,
        local_path_hint=data.local_path_hint,
        owner_user_id=actor_id,
    )
    session.add(project)
    await session.commit()
    await session.refresh(project)
    return project


async def list_projects(session: AsyncSession) -> list[Project]:
    result = await session.execute(select(Project).order_by(Project.updated_at.desc()))
    return list(result.scalars().all())


async def get_project(session: AsyncSession, project_id: str) -> Project:
    project = await session.get(Project, project_id)
    if project is None:
        raise NotFoundError("Project not found")
    return project


async def copy_project(
    session: AsyncSession,
    storage: StorageBackend,
    project_id: str,
    data: ProjectCopyRequest,
    actor_id: str | None = None,
) -> Project:
    source_project = await get_project(session, project_id)
    await _ensure_no_active_jobs(session, project_id)

    base_slug = data.slug or slugify(data.name or f"{source_project.name} copy")
    slug = await _unique_slug(session, base_slug)
    description = data.description if data.description is not None else source_project.description
    project = Project(
        name=data.name or f"{source_project.name} copy",
        slug=slug,
        description=description,
        default_client=source_project.default_client,
        local_path_hint=None,
        lifecycle=source_project.lifecycle,
        owner_user_id=actor_id,
    )
    session.add(project)
    await session.flush()

    source_versions = await _project_versions_ascending(session, source_project.id)
    version_map: dict[str, ProjectVersion] = {}
    pending_base_links: list[tuple[ProjectVersion, ProjectVersion]] = []

    for source_version in source_versions:
        version = ProjectVersion(
            project_id=project.id,
            version_number=source_version.version_number,
            label=source_version.label,
            status=VersionStatus.DRAFT,
            snapshot_prefix=f"projects/{project.id}/versions/{source_version.version_number}",
            manifest=deepcopy(source_version.manifest),
            base_version_id=None,
            created_by_user_id=actor_id,
        )
        session.add(version)
        await session.flush()
        version_map[source_version.id] = version
        pending_base_links.append((source_version, version))

        await _copy_version_files(session, storage, source_version, version)
        await _copy_version_artifacts(session, storage, source_version, version, project.id)

    for source_version, copied_version in pending_base_links:
        if source_version.base_version_id in version_map:
            copied_version.base_version_id = version_map[source_version.base_version_id].id

    await session.commit()
    await session.refresh(project)
    return project


async def delete_project(
    session: AsyncSession,
    storage: StorageBackend,
    project_id: str,
) -> None:
    project = await get_project(session, project_id)
    await _ensure_no_active_jobs(session, project_id)

    storage.delete_prefix(f"projects/{project.id}")

    version_ids = select(ProjectVersion.id).where(ProjectVersion.project_id == project_id)
    job_ids = select(Job.id).where(Job.project_id == project_id)
    await session.execute(delete(JobLog).where(JobLog.job_id.in_(job_ids)))
    await session.execute(delete(Artifact).where(Artifact.project_id == project_id))
    await session.execute(delete(Approval).where(Approval.version_id.in_(version_ids)))
    await session.execute(delete(FileObject).where(FileObject.version_id.in_(version_ids)))
    await session.execute(delete(Job).where(Job.project_id == project_id))
    await session.execute(delete(ProjectVersion).where(ProjectVersion.project_id == project_id))
    await session.execute(delete(Project).where(Project.id == project_id))
    await session.commit()


async def create_version(
    session: AsyncSession,
    project_id: str,
    data: VersionCreate,
    actor_id: str | None = None,
) -> ProjectVersion:
    project = await get_project(session, project_id)
    next_number = await _next_version_number(session, project_id)
    snapshot_prefix = f"projects/{project.id}/versions/{next_number}"
    version = ProjectVersion(
        project_id=project.id,
        version_number=next_number,
        label=data.label,
        manifest=data.manifest,
        snapshot_prefix=snapshot_prefix,
        base_version_id=data.base_version_id,
        created_by_user_id=actor_id,
    )
    session.add(version)
    await session.commit()
    await session.refresh(version)
    return version


async def list_versions(session: AsyncSession, project_id: str) -> list[ProjectVersion]:
    await get_project(session, project_id)
    result = await session.execute(
        select(ProjectVersion)
        .where(ProjectVersion.project_id == project_id)
        .order_by(ProjectVersion.version_number.desc())
    )
    return list(result.scalars().all())


async def get_version(session: AsyncSession, version_id: str) -> ProjectVersion:
    version = await session.get(ProjectVersion, version_id)
    if version is None:
        raise NotFoundError("Project version not found")
    return version


async def _slug_exists(session: AsyncSession, slug: str) -> bool:
    result = await session.execute(select(Project.id).where(Project.slug == slug))
    return result.scalar_one_or_none() is not None


async def _unique_slug(session: AsyncSession, base_slug: str) -> str:
    slug = base_slug
    suffix = 2
    while await _slug_exists(session, slug):
        slug = f"{base_slug}-{suffix}"
        suffix += 1
    return slug


async def _next_version_number(session: AsyncSession, project_id: str) -> int:
    result = await session.execute(
        select(func.max(ProjectVersion.version_number)).where(
            ProjectVersion.project_id == project_id
        )
    )
    current = result.scalar_one_or_none()
    return int(current or 0) + 1


async def _project_versions_ascending(
    session: AsyncSession,
    project_id: str,
) -> list[ProjectVersion]:
    result = await session.execute(
        select(ProjectVersion)
        .where(ProjectVersion.project_id == project_id)
        .order_by(ProjectVersion.version_number)
    )
    return list(result.scalars().all())


async def _copy_version_files(
    session: AsyncSession,
    storage: StorageBackend,
    source_version: ProjectVersion,
    version: ProjectVersion,
) -> None:
    result = await session.execute(
        select(FileObject)
        .where(FileObject.version_id == source_version.id)
        .order_by(FileObject.path)
    )
    for source_file in result.scalars().all():
        storage_key = f"{version.snapshot_prefix}/files/{source_file.path}"
        stored = storage.copy_object(
            source_file.storage_key,
            storage_key,
            source_file.content_type,
        )
        session.add(
            FileObject(
                version_id=version.id,
                path=source_file.path,
                storage_key=stored.key,
                sha256=stored.sha256,
                size_bytes=stored.size_bytes,
                content_type=stored.content_type,
                role=source_file.role,
            )
        )


async def _copy_version_artifacts(
    session: AsyncSession,
    storage: StorageBackend,
    source_version: ProjectVersion,
    version: ProjectVersion,
    project_id: str,
) -> None:
    result = await session.execute(
        select(Artifact).where(Artifact.version_id == source_version.id).order_by(Artifact.path)
    )
    for source_artifact in result.scalars().all():
        storage_key = f"{version.snapshot_prefix}/artifacts/{source_artifact.path}"
        stored = storage.copy_object(
            source_artifact.storage_key,
            storage_key,
            source_artifact.content_type,
        )
        session.add(
            Artifact(
                project_id=project_id,
                version_id=version.id,
                job_id=None,
                kind=source_artifact.kind,
                path=source_artifact.path,
                storage_key=stored.key,
                sha256=stored.sha256,
                size_bytes=stored.size_bytes,
                content_type=stored.content_type,
            )
        )


async def _ensure_no_active_jobs(session: AsyncSession, project_id: str) -> None:
    result = await session.execute(
        select(Job.id)
        .where(Job.project_id == project_id, Job.status.in_(ACTIVE_JOB_STATUSES))
        .limit(1)
    )
    if result.scalar_one_or_none() is not None:
        raise ConflictError("Project has active jobs")
