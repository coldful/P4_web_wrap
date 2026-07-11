import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

async def import_project_version(
    session,
    storage,
    root: Path,
    *,
    project_name: str,
    label: str,
):
    from p4_web.api.schemas import ProjectCreate
    from p4_web.services.projects import create_project
    from p4_web.services.sync_import import import_workspace_version

    project = await create_project(session, ProjectCreate(name=project_name))
    version = await import_workspace_version(
        session=session,
        storage=storage,
        root=root,
        project_id=project.id,
        label=label,
    )
    await session.refresh(project)
    return project, version
