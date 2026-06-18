from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from p4_web.persistence.models import Artifact


async def list_project_artifacts(session: AsyncSession, project_id: str) -> list[Artifact]:
    result = await session.execute(
        select(Artifact)
        .where(Artifact.project_id == project_id)
        .order_by(Artifact.created_at.desc())
    )
    return list(result.scalars().all())


async def list_version_artifacts(session: AsyncSession, version_id: str) -> list[Artifact]:
    result = await session.execute(
        select(Artifact)
        .where(Artifact.version_id == version_id)
        .order_by(Artifact.created_at.desc())
    )
    return list(result.scalars().all())
