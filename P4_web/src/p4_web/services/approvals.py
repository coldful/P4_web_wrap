from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from p4_web.api.schemas import ApprovalDecision
from p4_web.core.time import utcnow
from p4_web.domain.enums import ApprovalStatus, VersionStatus
from p4_web.persistence.models import Approval
from p4_web.services.projects import NotFoundError, get_version


async def submit_version(
    session: AsyncSession,
    version_id: str,
    decision: ApprovalDecision,
    actor_id: str | None = None,
) -> Approval:
    version = await get_version(session, version_id)
    version.status = VersionStatus.SUBMITTED
    approval = Approval(
        project_id=version.project_id,
        version_id=version.id,
        status=ApprovalStatus.PENDING,
        comment=decision.comment,
        submitted_by_user_id=actor_id,
    )
    session.add(approval)
    await session.commit()
    await session.refresh(approval)
    return approval


async def approve_version(
    session: AsyncSession,
    version_id: str,
    decision: ApprovalDecision,
    actor_id: str | None = None,
) -> Approval:
    approval = await _latest_approval(session, version_id)
    version = await get_version(session, version_id)
    version.status = VersionStatus.APPROVED
    approval.status = ApprovalStatus.APPROVED
    approval.comment = decision.comment or approval.comment
    approval.reviewed_by_user_id = actor_id
    approval.decided_at = utcnow()
    await session.commit()
    await session.refresh(approval)
    return approval


async def reject_version(
    session: AsyncSession,
    version_id: str,
    decision: ApprovalDecision,
    actor_id: str | None = None,
) -> Approval:
    approval = await _latest_approval(session, version_id)
    version = await get_version(session, version_id)
    version.status = VersionStatus.REJECTED
    approval.status = ApprovalStatus.REJECTED
    approval.comment = decision.comment or approval.comment
    approval.reviewed_by_user_id = actor_id
    approval.decided_at = utcnow()
    await session.commit()
    await session.refresh(approval)
    return approval


async def _latest_approval(session: AsyncSession, version_id: str) -> Approval:
    result = await session.execute(
        select(Approval)
        .where(Approval.version_id == version_id)
        .order_by(Approval.created_at.desc())
        .limit(1)
    )
    approval = result.scalar_one_or_none()
    if approval is None:
        raise NotFoundError("Approval request not found")
    return approval
