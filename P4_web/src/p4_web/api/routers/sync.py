from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from p4_web.api.dependencies import actor_id_dep, db_session, storage_dep
from p4_web.api.schemas import LocalImportRead, LocalImportRequest
from p4_web.services.projects import NotFoundError
from p4_web.services.sync_import import import_local_folder
from p4_web.storage import StorageBackend

router = APIRouter(prefix="/sync", tags=["sync"])


@router.post("/import-local", response_model=LocalImportRead, status_code=201)
async def import_local(
    payload: LocalImportRequest,
    session: AsyncSession = Depends(db_session),
    storage: StorageBackend = Depends(storage_dep),
    actor_id: str = Depends(actor_id_dep),
) -> LocalImportRead:
    try:
        project, version = await import_local_folder(
            session=session,
            storage=storage,
            root=Path(payload.path),
            project_id=payload.project_id,
            project_name=payload.project_name,
            label=payload.label,
            actor_id=actor_id,
        )
        return LocalImportRead(project=project, version=version)
    except NotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except (OSError, ValueError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
