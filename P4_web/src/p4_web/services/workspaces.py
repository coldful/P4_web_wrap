import shutil
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from p4_web.persistence.models import FileObject, ProjectVersion
from p4_web.storage import StorageBackend


async def materialize_version_workspace(
    session: AsyncSession,
    storage: StorageBackend,
    version: ProjectVersion,
    workspace_dir: Path,
) -> Path:
    """Recreate a project version as a local folder for a runner.

    Runners must operate on immutable version contents, not on the user's mutable
    local project directory. The returned path is the project root inside the job
    workspace.
    """

    project_dir = workspace_dir / "project"
    if project_dir.exists():
        shutil.rmtree(project_dir)
    project_dir.mkdir(parents=True, exist_ok=True)

    result = await session.execute(
        select(FileObject).where(FileObject.version_id == version.id).order_by(FileObject.path)
    )
    for file_object in result.scalars().all():
        target = project_dir / file_object.path
        storage.copy_to_path(file_object.storage_key, target)
    return project_dir
