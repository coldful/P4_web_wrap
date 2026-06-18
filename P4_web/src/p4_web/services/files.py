from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from p4_web.persistence.models import FileObject


async def list_version_files(session: AsyncSession, version_id: str) -> list[FileObject]:
    result = await session.execute(
        select(FileObject).where(FileObject.version_id == version_id).order_by(FileObject.path)
    )
    return list(result.scalars().all())

