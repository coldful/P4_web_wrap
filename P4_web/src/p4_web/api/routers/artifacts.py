from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from p4_web.api.dependencies import db_session
from p4_web.api.schemas import ArtifactRead
from p4_web.services import artifacts as artifact_service

router = APIRouter(tags=["artifacts"])


@router.get("/projects/{project_id}/artifacts", response_model=list[ArtifactRead])
async def list_project_artifacts(
    project_id: str,
    session: AsyncSession = Depends(db_session),
) -> list[ArtifactRead]:
    return await artifact_service.list_project_artifacts(session, project_id)


@router.get("/versions/{version_id}/artifacts", response_model=list[ArtifactRead])
async def list_version_artifacts(
    version_id: str,
    session: AsyncSession = Depends(db_session),
) -> list[ArtifactRead]:
    return await artifact_service.list_version_artifacts(session, version_id)

