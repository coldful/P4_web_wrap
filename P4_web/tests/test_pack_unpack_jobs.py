import shlex
import sys
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from p4_web.api.schemas import JobCreate
from p4_web.core.config import Settings
from p4_web.domain.enums import ArtifactKind, JobKind, JobStatus
from p4_web.persistence.database import Base
from p4_web.persistence.models import Artifact, FileObject, JobLog, ProjectVersion
from p4_web.services.jobs import create_job, get_job, run_job
from p4_web.services.sync_import import import_local_folder
from p4_web.storage.local import LocalStorage


async def test_pack_modules_creates_new_version_and_stores_report_artifact(
    tmp_path: Path,
) -> None:
    source_project = tmp_path / "local_project"
    source_project.mkdir()
    (source_project / "demo.proj.xlsm").write_bytes(b"project sheet")
    (source_project / "001").mkdir()
    (source_project / "001" / "source.xml").write_text("<root>original</root>", encoding="utf-8")

    legacy_dir = tmp_path / "legacy"
    legacy_dir.mkdir()
    fake_runner = legacy_dir / "fake_pack.py"
    fake_runner.write_text(
        "\n".join(
            [
                "from pathlib import Path",
                "import sys",
                "project = Path(sys.argv[1])",
                "schema = sys.argv[2]",
                "assert schema == 'proced.xsd'",
                "source = project / '001' / 'source.xml'",
                "source.write_text('<root schema=\"proced.xsd\">packed</root>', encoding='utf-8')",
                "(project / 'TextModules').mkdir(exist_ok=True)",
                (
                    "(project / 'TextModules' / 'packed-module.xml')"
                    ".write_text('<module/>', encoding='utf-8')"
                ),
                "(project / 'packed.txt').write_text('packed ok\\n', encoding='utf-8')",
                "print('packed modules')",
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
            "{project_path} {schema}"
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
            original_version_id = version.id
            job = await create_job(
                session,
                JobCreate(
                    project_id=project.id,
                    version_id=version.id,
                    kind=JobKind.PACK_MODULES,
                    parameters={
                        "language": "de",
                        "schema": "proced.xsd",
                        "version_label": "packed modules",
                    },
                    run_async=False,
                ),
            )
            job_id = job.id

        await run_job(session_factory, job_id, settings, storage)

        async with session_factory() as session:
            job = await get_job(session, job_id)
            versions_result = await session.execute(
                select(ProjectVersion)
                .where(ProjectVersion.project_id == job.project_id)
                .order_by(ProjectVersion.version_number)
            )
            versions = list(versions_result.scalars().all())
            files_result = await session.execute(
                select(FileObject)
                .where(FileObject.version_id == job.parameters["produced_version_id"])
                .order_by(FileObject.path)
            )
            files = list(files_result.scalars().all())
            artifacts_result = await session.execute(
                select(Artifact)
                .where(Artifact.job_id == job_id)
                .order_by(Artifact.path)
            )
            artifacts = list(artifacts_result.scalars().all())
            logs_result = await session.execute(
                select(JobLog).where(JobLog.job_id == job_id).order_by(JobLog.sequence)
            )
            logs = [row.message for row in logs_result.scalars().all()]

        assert job.status == JobStatus.SUCCEEDED
        assert job.parameters["produced_version_number"] == 2
        assert len(versions) == 2
        assert versions[1].id == job.parameters["produced_version_id"]
        assert versions[1].base_version_id == original_version_id
        assert versions[1].label == "packed modules"
        assert [row.path for row in files] == [
            "001/source.xml",
            "TextModules/packed-module.xml",
            "demo.proj.xlsm",
        ]
        assert [artifact.kind for artifact in artifacts] == [ArtifactKind.REPORT]
        assert artifacts[0].path == "packed.txt"
        assert artifacts[0].version_id == versions[1].id

        original_xml = storage.resolve_local_path(
            f"{versions[0].snapshot_prefix}/files/001/source.xml"
        )
        packed_xml = storage.resolve_local_path(
            f"{versions[1].snapshot_prefix}/files/001/source.xml"
        )
        packed_report = storage.resolve_local_path(artifacts[0].storage_key)

        assert original_xml is not None
        assert packed_xml is not None
        assert packed_report is not None
        assert original_xml.read_text(encoding="utf-8") == "<root>original</root>"
        assert "proced.xsd" in packed_xml.read_text(encoding="utf-8")
        assert packed_report.read_text(encoding="utf-8") == "packed ok\n"
        assert not (source_project / "packed.txt").exists()
        assert any("Created version #2." in message for message in logs)
        assert any("packed modules" in message for message in logs)
    finally:
        await engine.dispose()
