from dataclasses import dataclass, field
from pathlib import Path
from typing import Protocol

from p4_web.domain.enums import ArtifactKind, JobKind


@dataclass(frozen=True)
class RunnerContext:
    job_id: str
    project_id: str
    version_id: str
    kind: JobKind
    parameters: dict
    workspace_dir: Path
    legacy_p4_app_path: Path | None = None


@dataclass(frozen=True)
class ArtifactSpec:
    kind: ArtifactKind
    path: str
    content_type: str | None = None
    data: bytes | None = None
    local_path: Path | None = None


@dataclass(frozen=True)
class RunnerResult:
    logs: list[str] = field(default_factory=list)
    artifacts: list[ArtifactSpec] = field(default_factory=list)


class RunnerExecutionError(RuntimeError):
    def __init__(self, message: str, logs: list[str] | None = None) -> None:
        super().__init__(message)
        self.logs = logs or []


class RunnerPort(Protocol):
    async def run(self, context: RunnerContext) -> RunnerResult:
        ...
