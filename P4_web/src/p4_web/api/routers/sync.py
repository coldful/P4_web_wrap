from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from sqlalchemy.ext.asyncio import AsyncSession

from p4_web.api.dependencies import actor_id_dep, db_session, settings_dep, storage_dep
from p4_web.api.schemas import LocalImportRead
from p4_web.core.config import Settings
from p4_web.services.projects import NotFoundError
from p4_web.services.sync_import import import_uploaded_folder
from p4_web.storage import StorageBackend

router = APIRouter(prefix="/sync", tags=["sync"])


@router.post("/import-upload", response_model=LocalImportRead, status_code=201)
async def import_upload(
    files: list[UploadFile] = File(...),
    project_id: str | None = Form(default=None),
    project_name: str | None = Form(default=None),
    label: str | None = Form(default=None),
    session: AsyncSession = Depends(db_session),
    storage: StorageBackend = Depends(storage_dep),
    settings: Settings = Depends(settings_dep),
    actor_id: str = Depends(actor_id_dep),
) -> LocalImportRead:
    try:
        project, version = await import_uploaded_folder(
            session=session,
            storage=storage,
            settings=settings,
            uploads=files,
            project_id=project_id,
            project_name=project_name,
            label=label,
            actor_id=actor_id,
        )
        return LocalImportRead(project=project, version=version)
    except NotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except (OSError, ValueError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
