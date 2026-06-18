from fastapi import APIRouter, Depends

from p4_web.api.dependencies import settings_dep
from p4_web.api.schemas import HealthRead
from p4_web.core.config import Settings

router = APIRouter(tags=["health"])


@router.get("/health", response_model=HealthRead)
async def health(settings: Settings = Depends(settings_dep)) -> HealthRead:
    return HealthRead(status="ok", app=settings.app_name, environment=settings.environment)

