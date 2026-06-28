from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse
from sqlalchemy.ext.asyncio import AsyncSession

from p4_web.api.dependencies import db_session
from p4_web.api.dependencies import storage_dep
from p4_web.api.file_responses import stored_object_response
from p4_web.api.schemas import FileObjectRead
from p4_web.services import files as file_service
from p4_web.services.projects import NotFoundError
from p4_web.storage import StorageBackend

router = APIRouter(prefix="/versions", tags=["files"])


@router.get("/{version_id}/files", response_model=list[FileObjectRead])
async def list_version_files(
    version_id: str,
    session: AsyncSession = Depends(db_session),
) -> list[FileObjectRead]:
    return await file_service.list_version_files(session, version_id)


@router.get("/{version_id}/files/{file_id}/content", response_class=FileResponse)
async def get_version_file_content(
    version_id: str,
    file_id: str,
    session: AsyncSession = Depends(db_session),
    storage: StorageBackend = Depends(storage_dep),
) -> FileResponse:
    try:
        file_object = await file_service.get_version_file(session, version_id, file_id)
    except NotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return stored_object_response(
        storage,
        storage_key=file_object.storage_key,
        logical_path=file_object.path,
        content_type=file_object.content_type,
        download=False,
    )


@router.get("/{version_id}/files/{file_id}/download", response_class=FileResponse)
async def download_version_file(
    version_id: str,
    file_id: str,
    session: AsyncSession = Depends(db_session),
    storage: StorageBackend = Depends(storage_dep),
) -> FileResponse:
    try:
        file_object = await file_service.get_version_file(session, version_id, file_id)
    except NotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return stored_object_response(
        storage,
        storage_key=file_object.storage_key,
        logical_path=file_object.path,
        content_type=file_object.content_type,
        download=True,
    )
