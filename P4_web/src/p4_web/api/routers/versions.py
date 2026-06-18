from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from p4_web.api.dependencies import db_session
from p4_web.api.schemas import VersionRead
from p4_web.services import projects as project_service
from p4_web.services.projects import NotFoundError

router = APIRouter(prefix="/versions", tags=["versions"])


@router.get("/{version_id}", response_model=VersionRead)
async def get_version(
    version_id: str,
    session: AsyncSession = Depends(db_session),
) -> VersionRead:
    try:
        return await project_service.get_version(session, version_id)
    except NotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

