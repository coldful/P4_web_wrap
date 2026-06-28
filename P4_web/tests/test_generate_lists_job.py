import shlex
import sys
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from p4_web.api.schemas import JobCreate
from p4_web.core.config import Settings
from p4_web.domain.enums import FileRole, JobKind, JobStatus
from p4_web.persistence.database import Base
from p4_web.persistence.models import FileObject, JobLog, ProjectVersion
from p4_web.services.jobs import create_job, get_job, run_job
from p4_web.services.sync_import import import_local_folder
from p4_web.storage.local import LocalStorage


async def test_generate_lists_creates_new_version_from_workspace_changes(
    tmp_path: Path,
) -> None:
    source_project = tmp_path / "local_project"
    source_project.mkdir()
    (source_project / "demo.proj.xlsm").write_bytes(b"project sheet")
    (source_project / "001").mkdir()
    (source_project / "001" / "source.xml").write_text("<root>original</root>", encoding="utf-8")

    legacy_dir = tmp_path / "legacy"
    legacy_dir.mkdir()
    fake_runner = legacy_dir / "fake_generate_lists.py"
    fake_runner.write_text(
        "\n".join(
            [
                "from pathlib import Path",
                "import sys",
                "project = Path(sys.argv[1])",
                "source = project / '001' / 'source.xml'",
                "target = project / '001' / 'source_with_lists.xml'",
                "target.write_text('<root>with lists</root>', encoding='utf-8')",
                "print('generated lists')",
                "print(f'RESULT {target}')",
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
            original_version_id = version.id
            job = await create_job(
                session,
                JobCreate(
                    project_id=project.id,
                    version_id=version.id,
                    kind=JobKind.GENERATE_LISTS,
                    parameters={"language": "de", "version_label": "lists generated"},
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
            logs_result = await session.execute(
                select(JobLog).where(JobLog.job_id == job_id).order_by(JobLog.sequence)
            )
            logs = [row.message for row in logs_result.scalars().all()]

        assert job.status == JobStatus.SUCCEEDED
        assert job.parameters["produced_version_number"] == 2
        assert len(versions) == 2
        assert versions[1].base_version_id == original_version_id
        assert versions[1].label == "lists generated"
        assert [row.path for row in files] == [
            "001/source.xml",
            "001/source_with_lists.xml",
            "demo.proj.xlsm",
        ]
        assert any(row.role == FileRole.SOURCE_XML for row in files)
        generated_xml = storage.resolve_local_path(
            f"{versions[1].snapshot_prefix}/files/001/source_with_lists.xml"
        )
        assert generated_xml is not None
        assert generated_xml.read_text(encoding="utf-8") == "<root>with lists</root>"
        assert not (source_project / "001" / "source_with_lists.xml").exists()
        assert any("Created version #2." in message for message in logs)
        assert any("generated lists" in message for message in logs)
    finally:
        await engine.dispose()
