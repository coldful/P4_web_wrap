import shlex
import sys
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from p4_web.api.schemas import JobCreate
from p4_web.core.config import Settings
from p4_web.domain.enums import ArtifactKind, JobKind, JobStatus
from p4_web.persistence.database import Base
from p4_web.persistence.models import Artifact, JobLog
from p4_web.services.jobs import create_job, get_job, run_job
from p4_web.services.sync_import import import_local_folder
from p4_web.storage.local import LocalStorage


async def test_generate_pdf_job_materializes_version_and_stores_pdf_artifact(
    tmp_path: Path,
) -> None:
    source_project = tmp_path / "local_project"
    source_project.mkdir()
    (source_project / "demo.proj.xlsm").write_bytes(b"project sheet")
    (source_project / "001").mkdir()
    (source_project / "001" / "source.xml").write_text("<root/>", encoding="utf-8")

    legacy_dir = tmp_path / "legacy"
    legacy_dir.mkdir()
    fake_runner = legacy_dir / "fake_generate_pdf.py"
    fake_runner.write_text(
        "\n".join(
            [
                "from pathlib import Path",
                "import sys",
                "project = Path(sys.argv[1])",
                "assert (project / 'demo.proj.xlsm').exists()",
                "assert (project / '001' / 'source.xml').exists()",
                "(project / 'pdf').mkdir(exist_ok=True)",
                "(project / 'pdf' / 'generated.pdf').write_bytes(b'%PDF-1.4\\n% generated\\n')",
                "print('generated pdf')",
            ]
        ),
        encoding="utf-8",
    )

    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path / 'test.db'}")
    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)

    storage = LocalStorage(tmp_path / "storage")
    settings = Settings(
        database_url=f"sqlite+aiosqlite:///{tmp_path / 'test.db'}",
        local_storage_root=tmp_path / "storage",
        workspace_root=tmp_path / "workspaces",
        enable_legacy_runner=True,
        legacy_p4_app_path=legacy_dir,
        legacy_python_executable=sys.executable,
        legacy_runner_command=(
            f"{shlex.quote(sys.executable)} {shlex.quote(str(fake_runner))} "
            "{project_path}"
        ),
        legacy_pdf_artifact_globs=["**/*.pdf"],
    )
    settings.ensure_local_dirs()

    try:
        async with session_factory() as session:
            project, version = await import_local_folder(
                session=session,
                storage=storage,
                root=source_project,
                project_name="Imported",
                label="initial import",
            )
            job = await create_job(
                session,
                JobCreate(
                    project_id=project.id,
                    version_id=version.id,
                    kind=JobKind.GENERATE_PDF,
                    parameters={"language": "de", "project_path": str(source_project)},
                    run_async=False,
                ),
            )
            job_id = job.id

        await run_job(session_factory, job_id, settings, storage)

        async with session_factory() as session:
            job = await get_job(session, job_id)
            artifact_result = await session.execute(
                select(Artifact).where(Artifact.job_id == job_id)
            )
            artifacts = list(artifact_result.scalars().all())
            log_result = await session.execute(
                select(JobLog).where(JobLog.job_id == job_id).order_by(JobLog.sequence)
            )
            logs = [row.message for row in log_result.scalars().all()]

        assert job.status == JobStatus.SUCCEEDED
        assert job.error_message is None
        assert [artifact.kind for artifact in artifacts] == [ArtifactKind.PDF]
        assert artifacts[0].path == "pdf/generated.pdf"
        assert artifacts[0].content_type == "application/pdf"
        stored_pdf = storage.resolve_local_path(artifacts[0].storage_key)
        assert stored_pdf is not None
        assert stored_pdf.read_bytes().startswith(b"%PDF-1.4")
        assert not (source_project / "pdf" / "generated.pdf").exists()
        assert any("Workspace prepared:" in message for message in logs)
        assert any("generated pdf" in message for message in logs)
    finally:
        await engine.dispose()
