import asyncio
from pathlib import Path

import typer
from rich.console import Console
from rich.table import Table

from p4_web.core.config import get_settings
from p4_web.persistence.database import SessionLocal, init_db
from p4_web.services.storage_factory import build_storage
from p4_web.services.sync_import import import_local_folder
from p4_web.sync import compute_manifest

app = typer.Typer(help="P4 Web operational CLI.")
sync_app = typer.Typer(help="Manual local sync commands.")
app.add_typer(sync_app, name="sync")
console = Console()


@app.command("init-db")
def init_database() -> None:
    """Create database tables for local development."""

    asyncio.run(init_db())
    console.print("[green]Database initialized.[/green]")


@sync_app.command("scan")
def scan_folder(root: Path) -> None:
    """Print a local folder manifest without uploading it."""

    items = compute_manifest(root)
    table = Table(title=f"Manifest: {root}")
    table.add_column("Role")
    table.add_column("Size", justify="right")
    table.add_column("SHA256")
    table.add_column("Path")
    for item in items:
        table.add_row(item.role.value, str(item.size_bytes), item.sha256[:16], item.path)
    console.print(table)


@sync_app.command("import-local")
def import_local(
    root: Path,
    project_id: str | None = typer.Option(None, help="Existing project id."),
    project_name: str | None = typer.Option(None, help="Name for a new project."),
    label: str | None = typer.Option(None, help="Version label."),
) -> None:
    """Upload a local folder into storage as a new draft version."""

    asyncio.run(_import_local(root, project_id, project_name, label))


@app.command("import-local")
def import_local_alias(
    root: Path,
    project_id: str | None = typer.Option(None, help="Existing project id."),
    project_name: str | None = typer.Option(None, help="Name for a new project."),
    label: str | None = typer.Option(None, help="Version label."),
) -> None:
    """Alias for `p4web sync import-local`."""

    asyncio.run(_import_local(root, project_id, project_name, label))


async def _import_local(
    root: Path,
    project_id: str | None,
    project_name: str | None,
    label: str | None,
) -> None:
    settings = get_settings()
    storage = build_storage(settings)
    async with SessionLocal() as session:
        project, version = await import_local_folder(
            session=session,
            storage=storage,
            root=root,
            project_id=project_id,
            project_name=project_name,
            label=label,
            actor_id=settings.default_actor_id,
        )
    console.print(
        f"[green]Imported[/green] project={project.id} version={version.id} "
        f"number={version.version_number}"
    )


if __name__ == "__main__":
    app()
