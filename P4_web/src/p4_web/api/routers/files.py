from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from p4_web.api.dependencies import db_session
from p4_web.api.schemas import FileObjectRead
from p4_web.services import files as file_service

router = APIRouter(prefix="/versions", tags=["files"])


@router.get("/{version_id}/files", response_model=list[FileObjectRead])
async def list_version_files(
    version_id: str,
    session: AsyncSession = Depends(db_session),
) -> list[FileObjectRead]:
    return await file_service.list_version_files(session, version_id)

