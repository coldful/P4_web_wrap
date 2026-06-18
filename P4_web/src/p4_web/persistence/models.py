import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import BigInteger, DateTime, Enum, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.types import JSON

from p4_web.core.time import utcnow
from p4_web.domain.enums import (
    ApprovalStatus,
    ArtifactKind,
    FileRole,
    JobKind,
    JobStatus,
    ProjectLifecycle,
    ResourcePackageKind,
    VersionStatus,
)
from p4_web.persistence.database import Base


def uuid_str() -> str:
    return str(uuid.uuid4())


def json_type() -> JSON:
    return JSON().with_variant(JSONB, "postgresql")


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utcnow,
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utcnow,
        onupdate=utcnow,
        nullable=False,
    )


class User(Base, TimestampMixin):
    __tablename__ = "users"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    display_name: Mapped[str] = mapped_column(String(255), nullable=False)
    access_level: Mapped[str] = mapped_column(String(64), default="full_access", nullable=False)


class Project(Base, TimestampMixin):
    __tablename__ = "projects"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid_str)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    slug: Mapped[str] = mapped_column(String(255), unique=True, index=True, nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    default_client: Mapped[str | None] = mapped_column(String(128))
    local_path_hint: Mapped[str | None] = mapped_column(Text)
    lifecycle: Mapped[ProjectLifecycle] = mapped_column(
        Enum(ProjectLifecycle),
        default=ProjectLifecycle.ACTIVE,
        nullable=False,
    )
    owner_user_id: Mapped[str | None] = mapped_column(ForeignKey("users.id"))

    versions: Mapped[list["ProjectVersion"]] = relationship(
        back_populates="project",
        cascade="all, delete-orphan",
        order_by="ProjectVersion.version_number",
    )
    jobs: Mapped[list["Job"]] = relationship(back_populates="project")
    artifacts: Mapped[list["Artifact"]] = relationship(back_populates="project")


class ProjectVersion(Base, TimestampMixin):
    __tablename__ = "project_versions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid_str)
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id"), nullable=False, index=True)
    version_number: Mapped[int] = mapped_column(Integer, nullable=False)
    label: Mapped[str | None] = mapped_column(String(255))
    status: Mapped[VersionStatus] = mapped_column(
        Enum(VersionStatus),
        default=VersionStatus.DRAFT,
        nullable=False,
    )
    snapshot_prefix: Mapped[str] = mapped_column(Text, nullable=False)
    manifest: Mapped[dict[str, Any]] = mapped_column(json_type(), default=dict, nullable=False)
    base_version_id: Mapped[str | None] = mapped_column(ForeignKey("project_versions.id"))
    created_by_user_id: Mapped[str | None] = mapped_column(ForeignKey("users.id"))

    project: Mapped[Project] = relationship(back_populates="versions")
    files: Mapped[list["FileObject"]] = relationship(
        back_populates="version",
        cascade="all, delete-orphan",
    )
    jobs: Mapped[list["Job"]] = relationship(back_populates="version")
    artifacts: Mapped[list["Artifact"]] = relationship(back_populates="version")
    approvals: Mapped[list["Approval"]] = relationship(
        back_populates="version",
        cascade="all, delete-orphan",
    )


class FileObject(Base, TimestampMixin):
    __tablename__ = "file_objects"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid_str)
    version_id: Mapped[str] = mapped_column(
        ForeignKey("project_versions.id"),
        nullable=False,
        index=True,
    )
    path: Mapped[str] = mapped_column(Text, nullable=False)
    storage_key: Mapped[str] = mapped_column(Text, nullable=False)
    sha256: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    size_bytes: Mapped[int] = mapped_column(BigInteger, nullable=False)
    content_type: Mapped[str | None] = mapped_column(String(255))
    role: Mapped[FileRole] = mapped_column(Enum(FileRole), default=FileRole.OTHER, nullable=False)

    version: Mapped[ProjectVersion] = relationship(back_populates="files")


class Job(Base, TimestampMixin):
    __tablename__ = "jobs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid_str)
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id"), nullable=False, index=True)
    version_id: Mapped[str] = mapped_column(
        ForeignKey("project_versions.id"),
        nullable=False,
        index=True,
    )
    kind: Mapped[JobKind] = mapped_column(Enum(JobKind), nullable=False)
    status: Mapped[JobStatus] = mapped_column(
        Enum(JobStatus),
        default=JobStatus.QUEUED,
        nullable=False,
        index=True,
    )
    parameters: Mapped[dict[str, Any]] = mapped_column(json_type(), default=dict, nullable=False)
    progress_current: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    progress_total: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    error_message: Mapped[str | None] = mapped_column(Text)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    requested_by_user_id: Mapped[str | None] = mapped_column(ForeignKey("users.id"))

    project: Mapped[Project] = relationship(back_populates="jobs")
    version: Mapped[ProjectVersion] = relationship(back_populates="jobs")
    logs: Mapped[list["JobLog"]] = relationship(
        back_populates="job",
        cascade="all, delete-orphan",
        order_by="JobLog.sequence",
    )
    artifacts: Mapped[list["Artifact"]] = relationship(back_populates="job")


class JobLog(Base):
    __tablename__ = "job_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    job_id: Mapped[str] = mapped_column(ForeignKey("jobs.id"), nullable=False, index=True)
    sequence: Mapped[int] = mapped_column(Integer, nullable=False)
    level: Mapped[str] = mapped_column(String(32), default="info", nullable=False)
    message: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utcnow,
        nullable=False,
    )

    job: Mapped[Job] = relationship(back_populates="logs")


class Artifact(Base, TimestampMixin):
    __tablename__ = "artifacts"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid_str)
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id"), nullable=False, index=True)
    version_id: Mapped[str] = mapped_column(
        ForeignKey("project_versions.id"),
        nullable=False,
        index=True,
    )
    job_id: Mapped[str | None] = mapped_column(ForeignKey("jobs.id"), index=True)
    kind: Mapped[ArtifactKind] = mapped_column(Enum(ArtifactKind), nullable=False)
    path: Mapped[str] = mapped_column(Text, nullable=False)
    storage_key: Mapped[str] = mapped_column(Text, nullable=False)
    sha256: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    size_bytes: Mapped[int] = mapped_column(BigInteger, nullable=False)
    content_type: Mapped[str | None] = mapped_column(String(255))

    project: Mapped[Project] = relationship(back_populates="artifacts")
    version: Mapped[ProjectVersion] = relationship(back_populates="artifacts")
    job: Mapped[Job | None] = relationship(back_populates="artifacts")


class Approval(Base, TimestampMixin):
    __tablename__ = "approvals"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid_str)
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id"), nullable=False, index=True)
    version_id: Mapped[str] = mapped_column(
        ForeignKey("project_versions.id"),
        nullable=False,
        index=True,
    )
    status: Mapped[ApprovalStatus] = mapped_column(
        Enum(ApprovalStatus),
        default=ApprovalStatus.PENDING,
        nullable=False,
    )
    comment: Mapped[str | None] = mapped_column(Text)
    submitted_by_user_id: Mapped[str | None] = mapped_column(ForeignKey("users.id"))
    reviewed_by_user_id: Mapped[str | None] = mapped_column(ForeignKey("users.id"))
    submitted_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utcnow,
        nullable=False,
    )
    decided_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    version: Mapped[ProjectVersion] = relationship(back_populates="approvals")


class ResourcePackage(Base, TimestampMixin):
    __tablename__ = "resource_packages"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid_str)
    kind: Mapped[ResourcePackageKind] = mapped_column(Enum(ResourcePackageKind), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    version: Mapped[str | None] = mapped_column(String(128))
    storage_key: Mapped[str] = mapped_column(Text, nullable=False)
    manifest: Mapped[dict[str, Any]] = mapped_column(json_type(), default=dict, nullable=False)
    is_active: Mapped[bool] = mapped_column(default=True, nullable=False)
