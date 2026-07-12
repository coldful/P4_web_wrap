from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from p4_web.api.dependencies import db_session, settings_dep, storage_dep
from p4_web.api.schemas import DeliveryStatusAdvanceRead, VersionRead
from p4_web.core.config import Settings
from p4_web.services import delivery_status as delivery_status_service
from p4_web.services import projects as project_service
from p4_web.services.delivery_status import DeliveryStatusError, LegacyRunnerUnavailableError
from p4_web.services.projects import NotFoundError
from p4_web.storage import StorageBackend

router = APIRouter(prefix="/versions", tags=["versions"])


@router.get("/{version_id}", response_model=VersionRead)
async def get_version(
    version_id: str,
    session: AsyncSession = Depends(db_session),
    storage: StorageBackend = Depends(storage_dep),
) -> VersionRead:
    try:
        version = await project_service.get_version(session, version_id)
        return project_service.enrich_version_for_legacy_delivery(version, storage)
    except NotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/{version_id}/delivery-status/advance", response_model=DeliveryStatusAdvanceRead)
async def advance_delivery_status(
    version_id: str,
    session: AsyncSession = Depends(db_session),
    storage: StorageBackend = Depends(storage_dep),
    settings: Settings = Depends(settings_dep),
) -> DeliveryStatusAdvanceRead:
    try:
        version = await delivery_status_service.advance_delivery_status(
            session,
            storage,
            settings,
            version_id,
        )
    except NotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except LegacyRunnerUnavailableError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except DeliveryStatusError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    delivery_state = version.manifest.get("delivery_state")
    if not isinstance(delivery_state, dict):
        delivery_state = {}
    return DeliveryStatusAdvanceRead(version=version, delivery_state=delivery_state)
