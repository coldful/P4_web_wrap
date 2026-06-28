import mimetypes
from pathlib import Path

from fastapi import HTTPException
from fastapi.responses import FileResponse

from p4_web.storage import StorageBackend


def stored_object_response(
    storage: StorageBackend,
    *,
    storage_key: str,
    logical_path: str,
    content_type: str | None = None,
    download: bool = False,
) -> FileResponse:
    local_path = storage.resolve_local_path(storage_key)
    if local_path is None or not local_path.is_file():
        raise HTTPException(status_code=404, detail="Stored file not found")

    filename = Path(logical_path).name or "download"
    safe_filename = filename.replace("\\", "_").replace('"', "_")
    media_type = content_type or mimetypes.guess_type(filename)[0] or "application/octet-stream"
    disposition = "attachment" if download else "inline"
    return FileResponse(
        local_path,
        media_type=media_type,
        headers={"Content-Disposition": f'{disposition}; filename="{safe_filename}"'},
    )
