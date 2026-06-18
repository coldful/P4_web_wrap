from functools import lru_cache
from pathlib import Path
from typing import Annotated

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict


def discover_legacy_p4_app_path() -> Path:
    current = Path(__file__).resolve()
    for parent in current.parents:
        candidate = parent / "P4_app" / "interface.py"
        if candidate.is_file():
            return candidate.parent
    return Path("../../P4_app")


class Settings(BaseSettings):
    """Runtime settings for API, workers, storage, and legacy adapters."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_prefix="P4_WEB_",
        extra="ignore",
    )

    app_name: str = "P4 Web"
    environment: str = "local"
    database_url: str = "sqlite+aiosqlite:///./var/p4_web.db"
    cors_origins: Annotated[list[str], NoDecode] = Field(
        default_factory=lambda: ["http://localhost:8000"]
    )

    storage_backend: str = "local"
    local_storage_root: Path = Path("./var/storage")
    workspace_root: Path = Path("./var/workspaces")

    legacy_p4_app_path: Path = Field(default_factory=discover_legacy_p4_app_path)
    enable_legacy_runner: bool = False
    legacy_python_executable: str = "python2.7"
    legacy_runner_command: str | None = None
    legacy_runner_timeout_seconds: int = 3600
    legacy_pdf_artifact_globs: Annotated[list[str], NoDecode] = Field(
        default_factory=lambda: ["*.pdf", "**/*.pdf"]
    )

    default_actor_id: str = "local-admin"

    @field_validator("cors_origins", "legacy_pdf_artifact_globs", mode="before")
    @classmethod
    def parse_csv_list(cls, value: object) -> list[str] | object:
        if isinstance(value, str):
            return [item.strip() for item in value.split(",") if item.strip()]
        return value

    def ensure_local_dirs(self) -> None:
        self.local_storage_root.mkdir(parents=True, exist_ok=True)
        self.workspace_root.mkdir(parents=True, exist_ok=True)


@lru_cache
def get_settings() -> Settings:
    settings = Settings()
    settings.ensure_local_dirs()
    return settings
