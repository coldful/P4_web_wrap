from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from p4_web.api.dependencies import actor_id_dep, db_session, settings_dep, storage_dep
from p4_web.api.schemas import JobCreate, JobLogsRead, JobRead
from p4_web.core.config import Settings
from p4_web.persistence.database import SessionLocal
from p4_web.services import jobs as job_service
from p4_web.services.projects import ConflictError, NotFoundError
from p4_web.storage import StorageBackend

router = APIRouter(prefix="/jobs", tags=["jobs"])


@router.post("", response_model=JobRead, status_code=202)
async def create_job(
    payload: JobCreate,
    background_tasks: BackgroundTasks,
    session: AsyncSession = Depends(db_session),
    settings: Settings = Depends(settings_dep),
    storage: StorageBackend = Depends(storage_dep),
    actor_id: str = Depends(actor_id_dep),
) -> JobRead:
    try:
        job = await job_service.create_job(session, payload, actor_id)
    except NotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ConflictError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc

    if payload.run_async:
        background_tasks.add_task(job_service.run_job, SessionLocal, job.id, settings, storage)
    else:
        await job_service.run_job(SessionLocal, job.id, settings, storage)
        job = await job_service.get_job(session, job.id)
    return job


@router.get("/{job_id}", response_model=JobRead)
async def get_job(
    job_id: str,
    session: AsyncSession = Depends(db_session),
) -> JobRead:
    try:
        return await job_service.get_job(session, job_id)
    except NotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get("/{job_id}/logs", response_model=JobLogsRead)
async def get_job_logs(
    job_id: str,
    cursor: int | None = Query(default=None, ge=0),
    limit: int = Query(default=200, ge=1, le=1000),
    session: AsyncSession = Depends(db_session),
) -> JobLogsRead:
    try:
        await job_service.get_job(session, job_id)
    except NotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    logs, next_cursor = await job_service.list_job_logs(session, job_id, cursor, limit)
    return JobLogsRead(items=logs, next_cursor=next_cursor)


@router.post("/{job_id}/cancel", response_model=JobRead)
async def cancel_job(
    job_id: str,
    session: AsyncSession = Depends(db_session),
) -> JobRead:
    try:
        return await job_service.cancel_job(session, job_id)
    except NotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

