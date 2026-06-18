from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from p4_web.api.dependencies import actor_id_dep, db_session
from p4_web.api.schemas import ApprovalDecision, ApprovalRead
from p4_web.services import approvals as approval_service
from p4_web.services.projects import NotFoundError

router = APIRouter(prefix="/versions", tags=["approvals"])


@router.post("/{version_id}/submit", response_model=ApprovalRead, status_code=201)
async def submit_version(
    version_id: str,
    payload: ApprovalDecision,
    session: AsyncSession = Depends(db_session),
    actor_id: str = Depends(actor_id_dep),
) -> ApprovalRead:
    try:
        return await approval_service.submit_version(session, version_id, payload, actor_id)
    except NotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/{version_id}/approve", response_model=ApprovalRead)
async def approve_version(
    version_id: str,
    payload: ApprovalDecision,
    session: AsyncSession = Depends(db_session),
    actor_id: str = Depends(actor_id_dep),
) -> ApprovalRead:
    try:
        return await approval_service.approve_version(session, version_id, payload, actor_id)
    except NotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/{version_id}/reject", response_model=ApprovalRead)
async def reject_version(
    version_id: str,
    payload: ApprovalDecision,
    session: AsyncSession = Depends(db_session),
    actor_id: str = Depends(actor_id_dep),
) -> ApprovalRead:
    try:
        return await approval_service.reject_version(session, version_id, payload, actor_id)
    except NotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

