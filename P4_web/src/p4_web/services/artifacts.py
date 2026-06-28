from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from p4_web.persistence.models import Artifact
from p4_web.services.projects import NotFoundError


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


async def get_artifact(session: AsyncSession, artifact_id: str) -> Artifact:
    artifact = await session.get(Artifact, artifact_id)
    if artifact is None:
        raise NotFoundError("Artifact not found")
    return artifact
