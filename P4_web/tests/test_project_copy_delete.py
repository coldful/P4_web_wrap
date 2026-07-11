from pathlib import Path

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from p4_web.api.schemas import ProjectCopyRequest
from p4_web.domain.enums import ArtifactKind, FileRole
from p4_web.persistence.database import Base
from p4_web.persistence.models import Artifact, FileObject, ProjectVersion
from p4_web.services.projects import NotFoundError, copy_project, delete_project, get_project
from p4_web.storage.local import LocalStorage

from .conftest import import_project_version


async def test_copy_project_creates_server_copy_and_delete_keeps_local_files(
    tmp_path: Path,
) -> None:
    source_project = tmp_path / "local_project"
    source_project.mkdir()
    (source_project / "demo.proj.xlsm").write_bytes(b"project sheet")
    (source_project / "source.xml").write_text("<root/>", encoding="utf-8")

    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path / 'test.db'}")
    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)

    storage = LocalStorage(tmp_path / "storage")

    try:
        async with session_factory() as session:
            project, version = await import_project_version(
                session=session,
                storage=storage,
                root=source_project,
                project_name="Imported",
                label="initial import",
            )
            stored = storage.put_bytes(
                f"{version.snapshot_prefix}/artifacts/out.pdf",
                b"%PDF-1.4\n",
                "application/pdf",
            )
            session.add(
                Artifact(
                    project_id=project.id,
                    version_id=version.id,
                    kind=ArtifactKind.PDF,
                    path="out.pdf",
                    storage_key=stored.key,
                    sha256=stored.sha256,
                    size_bytes=stored.size_bytes,
                    content_type=stored.content_type,
                )
            )
            await session.commit()

            copied = await copy_project(
                session,
                storage,
                project.id,
                ProjectCopyRequest(name="Imported server copy"),
            )

            copied_versions = await session.execute(
                select(ProjectVersion).where(ProjectVersion.project_id == copied.id)
            )
            copied_version = copied_versions.scalar_one()
            copied_files = await session.execute(
                select(FileObject).where(FileObject.version_id == copied_version.id)
            )
            copied_artifacts = await session.execute(
                select(Artifact).where(Artifact.project_id == copied.id)
            )
            copied_file_rows = list(copied_files.scalars().all())
            copied_artifact_rows = list(copied_artifacts.scalars().all())

            assert copied.local_path_hint is None
            assert copied_version.status.value == "draft"
            assert {row.role for row in copied_file_rows} == {
                FileRole.PROJECT_SHEET,
                FileRole.SOURCE_XML,
            }
            assert len(copied_artifact_rows) == 1
            assert copied_artifact_rows[0].job_id is None
            assert storage.resolve_local_path(copied_file_rows[0].storage_key) is not None
            assert storage.resolve_local_path(copied_artifact_rows[0].storage_key) is not None

            await delete_project(session, storage, project.id)

            with pytest.raises(NotFoundError, match="Project not found"):
                await get_project(session, project.id)

            assert source_project.exists()
            assert (source_project / "demo.proj.xlsm").exists()
            assert storage.resolve_local_path(
                f"projects/{project.id}/versions/{version.version_number}/files/source.xml"
            ) is None
            assert await get_project(session, copied.id)
    finally:
        await engine.dispose()
