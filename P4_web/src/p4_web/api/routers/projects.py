from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy.ext.asyncio import AsyncSession

from p4_web.api.dependencies import actor_id_dep, db_session, storage_dep
from p4_web.api.schemas import (
    ProjectCopyRequest,
    ProjectCreate,
    ProjectRead,
    VersionCreate,
    VersionRead,
)
from p4_web.services import projects as project_service
from p4_web.services.projects import ConflictError, NotFoundError
from p4_web.storage import StorageBackend

router = APIRouter(prefix="/projects", tags=["projects"])


@router.post("", response_model=ProjectRead, status_code=201)
async def create_project(
    payload: ProjectCreate,
    session: AsyncSession = Depends(db_session),
    actor_id: str = Depends(actor_id_dep),
) -> ProjectRead:
    return await project_service.create_project(session, payload, actor_id)


@router.get("", response_model=list[ProjectRead])
async def list_projects(session: AsyncSession = Depends(db_session)) -> list[ProjectRead]:
    return await project_service.list_projects(session)


@router.get("/{project_id}", response_model=ProjectRead)
async def get_project(
    project_id: str,
    session: AsyncSession = Depends(db_session),
) -> ProjectRead:
    try:
        return await project_service.get_project(session, project_id)
    except NotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/{project_id}/copy", response_model=ProjectRead, status_code=201)
async def copy_project(
    project_id: str,
    payload: ProjectCopyRequest,
    session: AsyncSession = Depends(db_session),
    storage: StorageBackend = Depends(storage_dep),
    actor_id: str = Depends(actor_id_dep),
) -> ProjectRead:
    try:
        return await project_service.copy_project(session, storage, project_id, payload, actor_id)
    except NotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ConflictError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except (OSError, ValueError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.delete("/{project_id}", status_code=204)
async def delete_project(
    project_id: str,
    session: AsyncSession = Depends(db_session),
    storage: StorageBackend = Depends(storage_dep),
) -> Response:
    try:
        await project_service.delete_project(session, storage, project_id)
    except NotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ConflictError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except (OSError, ValueError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return Response(status_code=204)


@router.post("/{project_id}/versions", response_model=VersionRead, status_code=201)
async def create_version(
    project_id: str,
    payload: VersionCreate,
    session: AsyncSession = Depends(db_session),
    actor_id: str = Depends(actor_id_dep),
) -> VersionRead:
    try:
        return await project_service.create_version(session, project_id, payload, actor_id)
    except NotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get("/{project_id}/versions", response_model=list[VersionRead])
async def list_versions(
    project_id: str,
    session: AsyncSession = Depends(db_session),
) -> list[VersionRead]:
    try:
        return await project_service.list_versions(session, project_id)
    except NotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
