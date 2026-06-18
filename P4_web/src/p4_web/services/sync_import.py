from pathlib import Path

from sqlalchemy.ext.asyncio import AsyncSession

from p4_web.api.schemas import ProjectCreate, VersionCreate
from p4_web.persistence.models import FileObject, Project, ProjectVersion
from p4_web.services.projects import create_project, create_version, get_project
from p4_web.storage import StorageBackend
from p4_web.sync import compute_manifest


async def import_local_folder(
    session: AsyncSession,
    storage: StorageBackend,
    root: Path,
    project_id: str | None = None,
    project_name: str | None = None,
    label: str | None = None,
    actor_id: str | None = None,
) -> tuple[Project, ProjectVersion]:
    root = root.resolve()
    if project_id:
        project = await get_project(session, project_id)
    else:
        name = project_name or root.name
        project = await create_project(
            session,
            ProjectCreate(name=name, local_path_hint=str(root)),
            actor_id=actor_id,
        )

    version = await import_workspace_version(
        session=session,
        storage=storage,
        root=root,
        project_id=project.id,
        label=label or "manual import",
        actor_id=actor_id,
    )
    await session.refresh(project)
    return project, version


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
