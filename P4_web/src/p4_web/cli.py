import asyncio
from pathlib import Path

import typer
from rich.console import Console
from rich.table import Table

from p4_web.persistence.database import init_db
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


if __name__ == "__main__":
    app()
