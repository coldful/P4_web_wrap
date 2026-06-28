from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse
from sqlalchemy.ext.asyncio import AsyncSession

from p4_web.api.dependencies import db_session, storage_dep
from p4_web.api.file_responses import stored_object_response
from p4_web.api.schemas import ArtifactRead
from p4_web.services import artifacts as artifact_service
from p4_web.services.projects import NotFoundError
from p4_web.storage import StorageBackend

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


@router.get("/artifacts/{artifact_id}/content", response_class=FileResponse)
async def get_artifact_content(
    artifact_id: str,
    session: AsyncSession = Depends(db_session),
    storage: StorageBackend = Depends(storage_dep),
) -> FileResponse:
    try:
        artifact = await artifact_service.get_artifact(session, artifact_id)
    except NotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return stored_object_response(
        storage,
        storage_key=artifact.storage_key,
        logical_path=artifact.path,
        content_type=artifact.content_type,
        download=False,
    )


@router.get("/artifacts/{artifact_id}/download", response_class=FileResponse)
async def download_artifact(
    artifact_id: str,
    session: AsyncSession = Depends(db_session),
    storage: StorageBackend = Depends(storage_dep),
) -> FileResponse:
    try:
        artifact = await artifact_service.get_artifact(session, artifact_id)
    except NotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return stored_object_response(
        storage,
        storage_key=artifact.storage_key,
        logical_path=artifact.path,
        content_type=artifact.content_type,
        download=True,
    )
