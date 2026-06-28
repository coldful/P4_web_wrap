from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from p4_web.persistence.models import FileObject
from p4_web.services.projects import NotFoundError


async def list_version_files(session: AsyncSession, version_id: str) -> list[FileObject]:
    result = await session.execute(
        select(FileObject).where(FileObject.version_id == version_id).order_by(FileObject.path)
    )
    return list(result.scalars().all())


async def get_version_file(session: AsyncSession, version_id: str, file_id: str) -> FileObject:
    result = await session.execute(
        select(FileObject).where(
            FileObject.id == file_id,
            FileObject.version_id == version_id,
        )
    )
    file_object = result.scalar_one_or_none()
    if file_object is None:
        raise NotFoundError("File not found")
    return file_object
