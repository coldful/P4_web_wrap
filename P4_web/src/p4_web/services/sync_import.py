import shutil
import tempfile
from pathlib import Path

from fastapi import UploadFile

from sqlalchemy.ext.asyncio import AsyncSession

from p4_web.api.schemas import ProjectCreate, VersionCreate
from p4_web.core.config import Settings
from p4_web.persistence.models import FileObject, Project, ProjectVersion
from p4_web.services.projects import create_project, create_version, get_project
from p4_web.storage import StorageBackend
from p4_web.sync import compute_manifest


async def import_uploaded_folder(
    session: AsyncSession,
    storage: StorageBackend,
    settings: Settings,
    uploads: list[UploadFile],
    project_id: str | None = None,
    project_name: str | None = None,
    label: str | None = None,
    actor_id: str | None = None,
) -> tuple[Project, ProjectVersion]:
    normalized = [_normalize_upload_path(upload.filename or "") for upload in uploads]
    if not normalized:
        raise ValueError("No files were uploaded")

    relative_paths, root_name = _strip_common_upload_root(normalized)
    temp_root = Path(
        tempfile.mkdtemp(prefix="upload-import-", dir=str(settings.workspace_root.resolve()))
    )
    try:
        for upload, relative_path in zip(uploads, relative_paths, strict=True):
            target = temp_root / relative_path
            target.parent.mkdir(parents=True, exist_ok=True)
            with target.open("wb") as handle:
                while True:
                    chunk = await upload.read(1024 * 1024)
                    if not chunk:
                        break
                    handle.write(chunk)
            await upload.close()

        if project_id:
            project = await get_project(session, project_id)
        else:
            name = project_name or root_name or temp_root.name
            project = await create_project(
                session,
                ProjectCreate(name=name),
                actor_id=actor_id,
            )

        version = await import_workspace_version(
            session=session,
            storage=storage,
            root=temp_root,
            project_id=project.id,
            label=label or "manual import",
            actor_id=actor_id,
            root_name=root_name,
        )
        await session.refresh(project)
        return project, version
    finally:
        shutil.rmtree(temp_root, ignore_errors=True)


async def import_workspace_version(
    session: AsyncSession,
    storage: StorageBackend,
    root: Path,
    project_id: str,
    label: str | None = None,
    base_version_id: str | None = None,
    actor_id: str | None = None,
    root_name: str | None = None,
    exclude_paths: set[str] | None = None,
) -> ProjectVersion:
    root = root.resolve()
    excluded = {path.strip("/") for path in (exclude_paths or set())}
    manifest_items = [
        item for item in compute_manifest(root) if item.path not in excluded
    ]

    manifest = {
        "root_name": root_name or root.name,
        "files": [item.to_dict() for item in manifest_items],
    }
    version = await create_version(
        session,
        project_id,
        VersionCreate(
            label=label,
            base_version_id=base_version_id,
            manifest=manifest,
        ),
        actor_id=actor_id,
    )

    for item in manifest_items:
        source = root / item.path
        storage_key = f"{version.snapshot_prefix}/files/{item.path}"
        stored = storage.put_file(storage_key, source)
        session.add(
            FileObject(
                version_id=version.id,
                path=item.path,
                storage_key=stored.key,
                sha256=stored.sha256,
                size_bytes=stored.size_bytes,
                content_type=stored.content_type,
                role=item.role,
            )
        )

    await session.commit()
    await session.refresh(version)
    return version


def _normalize_upload_path(value: str) -> Path:
    clean = value.strip().replace("\\", "/").lstrip("/")
    path = Path(clean)
    parts = [part for part in path.parts if part not in ("", ".")]
    if not parts:
        raise ValueError("Uploaded file is missing a valid relative path")
    if any(part == ".." for part in parts):
        raise ValueError(f"Unsafe uploaded path: {value}")
    return Path(*parts)


def _strip_common_upload_root(paths: list[Path]) -> tuple[list[Path], str | None]:
    first_parts = [path.parts[0] for path in paths if len(path.parts) >= 2]
    root_name = None
    if first_parts and len(first_parts) == len(paths) and len(set(first_parts)) == 1:
        root_name = first_parts[0]
        stripped = [Path(*path.parts[1:]) for path in paths]
        if all(path.parts for path in stripped):
            return stripped, root_name
    return paths, root_name
