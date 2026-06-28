import json
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


async def test_xsl_fo_stores_pdf_artifact_from_workspace_output_dir(
    tmp_path: Path,
) -> None:
    source_project = tmp_path / "local_project"
    source_project.mkdir()
    (source_project / "demo.proj.xlsm").write_bytes(b"project sheet")
    (source_project / "001").mkdir()
    (source_project / "001" / "source.xml").write_text("<root/>", encoding="utf-8")

    legacy_dir = tmp_path / "legacy"
    legacy_dir.mkdir()
    fake_runner = legacy_dir / "fake_xsl_fo.py"
    fake_runner.write_text(
        "\n".join(
            [
                "import json",
                "import os",
                "from pathlib import Path",
                "params = json.loads(os.environ['P4_WEB_JOB_PARAMETERS'])",
                "output_dir = Path(params['output_dir'])",
                "output_dir.mkdir(parents=True, exist_ok=True)",
                "pdf_file = output_dir / 'demo_xslfo.pdf'",
                "pdf_file.write_bytes(b'%PDF-1.4\\n% generated\\n')",
                "print(f'RESULT {pdf_file}')",
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
                    kind=JobKind.XSL_FO,
                    parameters={"language": "de"},
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
        assert [artifact.kind for artifact in artifacts] == [ArtifactKind.PDF]
        assert artifacts[0].path == "demo_xslfo.pdf"
        stored_pdf = storage.resolve_local_path(artifacts[0].storage_key)
        assert stored_pdf is not None
        assert stored_pdf.read_bytes().startswith(b"%PDF-1.4")
        exported_params = None
        for message in logs:
            if "P4_WEB_JOB_PARAMETERS" in message:
                exported_params = message
        assert any("RESULT" in message for message in logs)
    finally:
        await engine.dispose()
