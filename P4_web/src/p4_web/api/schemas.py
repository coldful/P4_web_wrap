from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from p4_web.domain.enums import (
    ApprovalStatus,
    ArtifactKind,
    FileRole,
    JobKind,
    JobStatus,
    ProjectLifecycle,
    VersionStatus,
)


class OrmModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class ProjectCreate(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    slug: str | None = Field(default=None, max_length=255)
    description: str | None = None
    default_client: str | None = Field(default=None, max_length=128)
    local_path_hint: str | None = None


class ProjectCopyRequest(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=255)
    slug: str | None = Field(default=None, max_length=255)
    description: str | None = None


class ProjectRead(OrmModel):
    id: str
    name: str
    slug: str
    description: str | None
    default_client: str | None
    local_path_hint: str | None
    lifecycle: ProjectLifecycle
    created_at: datetime
    updated_at: datetime


class FileManifestItem(BaseModel):
    path: str
    sha256: str
    size_bytes: int
    role: FileRole = FileRole.OTHER
    content_type: str | None = None


class VersionCreate(BaseModel):
    label: str | None = None
    base_version_id: str | None = None
    manifest: dict[str, Any] = Field(default_factory=dict)


class VersionRead(OrmModel):
    id: str
    project_id: str
    version_number: int
    label: str | None
    status: VersionStatus
    snapshot_prefix: str
    manifest: dict[str, Any]
    base_version_id: str | None
    created_at: datetime
    updated_at: datetime


class FileObjectRead(OrmModel):
    id: str
    version_id: str
    path: str
    storage_key: str
    sha256: str
    size_bytes: int
    content_type: str | None
    role: FileRole
    created_at: datetime


class JobCreate(BaseModel):
    project_id: str
    version_id: str
    kind: JobKind
    parameters: dict[str, Any] = Field(default_factory=dict)
    run_async: bool = True


class JobRead(OrmModel):
    id: str
    project_id: str
    version_id: str
    kind: JobKind
    status: JobStatus
    parameters: dict[str, Any]
    progress_current: int
    progress_total: int
    error_message: str | None
    started_at: datetime | None
    finished_at: datetime | None
    created_at: datetime
    updated_at: datetime


class JobLogRead(OrmModel):
    id: int
    job_id: str
    sequence: int
    level: str
    message: str
    created_at: datetime


class JobLogsRead(BaseModel):
    items: list[JobLogRead]
    next_cursor: int | None


class ArtifactRead(OrmModel):
    id: str
    project_id: str
    version_id: str
    job_id: str | None
    kind: ArtifactKind
    path: str
    storage_key: str
    sha256: str
    size_bytes: int
    content_type: str | None
    created_at: datetime
    updated_at: datetime


class ApprovalRead(OrmModel):
    id: str
    project_id: str
    version_id: str
    status: ApprovalStatus
    comment: str | None
    submitted_at: datetime
    decided_at: datetime | None
    created_at: datetime
    updated_at: datetime


class ApprovalDecision(BaseModel):
    comment: str | None = None


class HealthRead(BaseModel):
    status: str
    app: str
    environment: str


class SyncManifestItem(BaseModel):
    path: str
    sha256: str
    size_bytes: int
    mtime_ns: int
    role: FileRole = FileRole.OTHER


class SyncManifestRead(BaseModel):
    root: str
    files: list[SyncManifestItem]


class LocalImportRequest(BaseModel):
    path: str
    project_id: str | None = None
    project_name: str | None = None
    label: str | None = None


class LocalImportRead(BaseModel):
    project: ProjectRead
    version: VersionRead
