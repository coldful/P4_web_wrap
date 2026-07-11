from io import BytesIO
from pathlib import Path

from fastapi import UploadFile
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from p4_web.core.config import Settings
from p4_web.persistence.database import Base
from p4_web.persistence.models import FileObject
from p4_web.services.sync_import import import_uploaded_folder
from p4_web.storage.local import LocalStorage


async def test_import_uploaded_folder_strips_selected_root_and_cleans_temp_workspace(
    tmp_path: Path,
) -> None:
    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path / 'test.db'}")
    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)

    storage = LocalStorage(tmp_path / "storage")
    settings = Settings(
        workspace_root=tmp_path / "workspaces",
        local_storage_root=tmp_path / "storage",
    )
    settings.ensure_local_dirs()

    uploads = [
        UploadFile(filename="DemoProject/demo.proj.xlsm", file=BytesIO(b"project-sheet")),
        UploadFile(filename="DemoProject/source.xml", file=BytesIO(b"<root/>")),
        UploadFile(filename="DemoProject/sub/data.txt", file=BytesIO(b"payload")),
    ]

    try:
        async with session_factory() as session:
            project, version = await import_uploaded_folder(
                session=session,
                storage=storage,
                settings=settings,
                uploads=uploads,
                label="browser import",
            )

            files = await session.execute(
                select(FileObject).where(FileObject.version_id == version.id)
            )
            file_rows = list(files.scalars().all())

            assert project.name == "DemoProject"
            assert project.local_path_hint is None
            assert version.label == "browser import"
            assert version.manifest["root_name"] == "DemoProject"
            assert {row.path for row in file_rows} == {
                "demo.proj.xlsm",
                "source.xml",
                "sub/data.txt",
            }
            assert not any(
                item["path"].startswith("DemoProject/") for item in version.manifest["files"]
            )
            assert list(settings.workspace_root.iterdir()) == []
    finally:
        await engine.dispose()
