from copy import deepcopy
import re
import zipfile
from pathlib import Path
from xml.etree import ElementTree as ET

from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from p4_web.api.schemas import ProjectCopyRequest, ProjectCreate, VersionCreate
from p4_web.core.slug import slugify
from p4_web.domain.enums import JobStatus, VersionStatus
from p4_web.persistence.models import (
    Approval,
    Artifact,
    FileObject,
    Job,
    JobLog,
    Project,
    ProjectVersion,
)
from p4_web.storage import StorageBackend

LEGACY_DELIVERY_STEPS = [
    {"id": "new", "label": "Captured"},
    {"id": "in_work", "label": "In Work"},
    {"id": "freigegeben", "label": "Released"},
    {"id": "in_translation", "label": "In Translation"},
    {"id": "closed", "label": "Closed"},
]

_RE_ROW_DIGITS = re.compile(r"\d+")


class NotFoundError(Exception):
    pass


class ConflictError(Exception):
    pass


ACTIVE_JOB_STATUSES = {
    JobStatus.QUEUED,
    JobStatus.RUNNING,
    JobStatus.CANCEL_REQUESTED,
}


async def create_project(
    session: AsyncSession,
    data: ProjectCreate,
    actor_id: str | None = None,
) -> Project:
    base_slug = data.slug or slugify(data.name)
    slug = base_slug
    suffix = 2
    while await _slug_exists(session, slug):
        slug = f"{base_slug}-{suffix}"
        suffix += 1

    project = Project(
        name=data.name,
        slug=slug,
        description=data.description,
        default_client=data.default_client,
        local_path_hint=data.local_path_hint,
        owner_user_id=actor_id,
    )
    session.add(project)
    await session.commit()
    await session.refresh(project)
    return project


async def list_projects(session: AsyncSession) -> list[Project]:
    result = await session.execute(select(Project).order_by(Project.updated_at.desc()))
    return list(result.scalars().all())


async def get_project(session: AsyncSession, project_id: str) -> Project:
    project = await session.get(Project, project_id)
    if project is None:
        raise NotFoundError("Project not found")
    return project


async def copy_project(
    session: AsyncSession,
    storage: StorageBackend,
    project_id: str,
    data: ProjectCopyRequest,
    actor_id: str | None = None,
) -> Project:
    source_project = await get_project(session, project_id)
    await _ensure_no_active_jobs(session, project_id)

    base_slug = data.slug or slugify(data.name or f"{source_project.name} copy")
    slug = await _unique_slug(session, base_slug)
    description = data.description if data.description is not None else source_project.description
    project = Project(
        name=data.name or f"{source_project.name} copy",
        slug=slug,
        description=description,
        default_client=source_project.default_client,
        local_path_hint=None,
        lifecycle=source_project.lifecycle,
        owner_user_id=actor_id,
    )
    session.add(project)
    await session.flush()

    source_versions = await _project_versions_ascending(session, source_project.id)
    version_map: dict[str, ProjectVersion] = {}
    pending_base_links: list[tuple[ProjectVersion, ProjectVersion]] = []

    for source_version in source_versions:
        version = ProjectVersion(
            project_id=project.id,
            version_number=source_version.version_number,
            label=source_version.label,
            status=VersionStatus.DRAFT,
            snapshot_prefix=f"projects/{project.id}/versions/{source_version.version_number}",
            manifest=deepcopy(source_version.manifest),
            base_version_id=None,
            created_by_user_id=actor_id,
        )
        session.add(version)
        await session.flush()
        version_map[source_version.id] = version
        pending_base_links.append((source_version, version))

        await _copy_version_files(session, storage, source_version, version)
        await _copy_version_artifacts(session, storage, source_version, version, project.id)

    for source_version, copied_version in pending_base_links:
        if source_version.base_version_id in version_map:
            copied_version.base_version_id = version_map[source_version.base_version_id].id

    await session.commit()
    await session.refresh(project)
    return project


async def delete_project(
    session: AsyncSession,
    storage: StorageBackend,
    project_id: str,
) -> None:
    project = await get_project(session, project_id)
    await _ensure_no_active_jobs(session, project_id)

    storage.delete_prefix(f"projects/{project.id}")

    version_ids = select(ProjectVersion.id).where(ProjectVersion.project_id == project_id)
    job_ids = select(Job.id).where(Job.project_id == project_id)
    await session.execute(delete(JobLog).where(JobLog.job_id.in_(job_ids)))
    await session.execute(delete(Artifact).where(Artifact.project_id == project_id))
    await session.execute(delete(Approval).where(Approval.version_id.in_(version_ids)))
    await session.execute(delete(FileObject).where(FileObject.version_id.in_(version_ids)))
    await session.execute(delete(Job).where(Job.project_id == project_id))
    await session.execute(delete(ProjectVersion).where(ProjectVersion.project_id == project_id))
    await session.execute(delete(Project).where(Project.id == project_id))
    await session.commit()


async def create_version(
    session: AsyncSession,
    project_id: str,
    data: VersionCreate,
    actor_id: str | None = None,
) -> ProjectVersion:
    project = await get_project(session, project_id)
    next_number = await _next_version_number(session, project_id)
    snapshot_prefix = f"projects/{project.id}/versions/{next_number}"
    version = ProjectVersion(
        project_id=project.id,
        version_number=next_number,
        label=data.label,
        manifest=data.manifest,
        snapshot_prefix=snapshot_prefix,
        base_version_id=data.base_version_id,
        created_by_user_id=actor_id,
    )
    session.add(version)
    await session.commit()
    await session.refresh(version)
    return version


async def list_versions(session: AsyncSession, project_id: str) -> list[ProjectVersion]:
    await get_project(session, project_id)
    result = await session.execute(
        select(ProjectVersion)
        .where(ProjectVersion.project_id == project_id)
        .order_by(ProjectVersion.version_number.desc())
    )
    return list(result.scalars().all())


async def get_version(session: AsyncSession, version_id: str) -> ProjectVersion:
    version = await session.get(ProjectVersion, version_id)
    if version is None:
        raise NotFoundError("Project version not found")
    return version


def enrich_version_for_legacy_delivery(version: ProjectVersion, storage: StorageBackend) -> ProjectVersion:
    manifest = deepcopy(version.manifest or {})
    files = manifest.get("files")
    if not isinstance(files, list):
        files = []
        manifest["files"] = files

    metadata = manifest.get("project_sheet_metadata")
    if not isinstance(metadata, dict):
        metadata = _extract_project_sheet_metadata(version, storage, files)
        if metadata:
            manifest["project_sheet_metadata"] = metadata

    manifest["legacy_delivery"] = _build_legacy_delivery_payload(files, metadata or {})
    version.manifest = manifest
    return version


async def _slug_exists(session: AsyncSession, slug: str) -> bool:
    result = await session.execute(select(Project.id).where(Project.slug == slug))
    return result.scalar_one_or_none() is not None


async def _unique_slug(session: AsyncSession, base_slug: str) -> str:
    slug = base_slug
    suffix = 2
    while await _slug_exists(session, slug):
        slug = f"{base_slug}-{suffix}"
        suffix += 1
    return slug


async def _next_version_number(session: AsyncSession, project_id: str) -> int:
    result = await session.execute(
        select(func.max(ProjectVersion.version_number)).where(
            ProjectVersion.project_id == project_id
        )
    )
    current = result.scalar_one_or_none()
    return int(current or 0) + 1


async def _project_versions_ascending(
    session: AsyncSession,
    project_id: str,
) -> list[ProjectVersion]:
    result = await session.execute(
        select(ProjectVersion)
        .where(ProjectVersion.project_id == project_id)
        .order_by(ProjectVersion.version_number)
    )
    return list(result.scalars().all())


async def _copy_version_files(
    session: AsyncSession,
    storage: StorageBackend,
    source_version: ProjectVersion,
    version: ProjectVersion,
) -> None:
    result = await session.execute(
        select(FileObject)
        .where(FileObject.version_id == source_version.id)
        .order_by(FileObject.path)
    )
    for source_file in result.scalars().all():
        storage_key = f"{version.snapshot_prefix}/files/{source_file.path}"
        stored = storage.copy_object(
            source_file.storage_key,
            storage_key,
            source_file.content_type,
        )
        session.add(
            FileObject(
                version_id=version.id,
                path=source_file.path,
                storage_key=stored.key,
                sha256=stored.sha256,
                size_bytes=stored.size_bytes,
                content_type=stored.content_type,
                role=source_file.role,
            )
        )


async def _copy_version_artifacts(
    session: AsyncSession,
    storage: StorageBackend,
    source_version: ProjectVersion,
    version: ProjectVersion,
    project_id: str,
) -> None:
    result = await session.execute(
        select(Artifact).where(Artifact.version_id == source_version.id).order_by(Artifact.path)
    )
    for source_artifact in result.scalars().all():
        storage_key = f"{version.snapshot_prefix}/artifacts/{source_artifact.path}"
        stored = storage.copy_object(
            source_artifact.storage_key,
            storage_key,
            source_artifact.content_type,
        )
        session.add(
            Artifact(
                project_id=project_id,
                version_id=version.id,
                job_id=None,
                kind=source_artifact.kind,
                path=source_artifact.path,
                storage_key=stored.key,
                sha256=stored.sha256,
                size_bytes=stored.size_bytes,
                content_type=stored.content_type,
            )
        )


async def _ensure_no_active_jobs(session: AsyncSession, project_id: str) -> None:
    result = await session.execute(
        select(Job.id)
        .where(Job.project_id == project_id, Job.status.in_(ACTIVE_JOB_STATUSES))
        .limit(1)
    )
    if result.scalar_one_or_none() is not None:
        raise ConflictError("Project has active jobs")


def _extract_project_sheet_metadata(
    version: ProjectVersion,
    storage: StorageBackend,
    files: list[dict],
) -> dict[str, str]:
    project_sheet = next(
        (
            item
            for item in files
            if str(item.get("role", "")).lower() == "project_sheet"
            and isinstance(item.get("path"), str)
        ),
        None,
    )
    if not project_sheet:
        return {}

    relative_path = str(project_sheet.get("path", "")).strip("/")
    if not relative_path:
        return {}
    local_path = storage.resolve_local_path(f"{version.snapshot_prefix}/files/{relative_path}")
    if not local_path:
        return {}
    return _read_project_sheet_keyvals(local_path)


def _read_project_sheet_keyvals(path: Path) -> dict[str, str]:
    if path.suffix.lower() not in {".xlsx", ".xlsm"}:
        return {}
    try:
        with zipfile.ZipFile(path) as archive:
            shared_strings = _read_shared_strings(archive)
            values: dict[str, str] = {}
            worksheet_names = sorted(
                name
                for name in archive.namelist()
                if name.startswith("xl/worksheets/") and name.endswith(".xml")
            )
            for worksheet_name in worksheet_names:
                root = ET.fromstring(archive.read(worksheet_name))
                namespace = {"main": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}
                for row in root.findall(".//main:sheetData/main:row", namespace):
                    row_values: dict[str, str] = {}
                    for cell in row.findall("main:c", namespace):
                        ref = cell.attrib.get("r", "")
                        column = _RE_ROW_DIGITS.sub("", ref)
                        if not column:
                            continue
                        row_values[column] = _xlsx_cell_value(cell, shared_strings, namespace)
                    key = str(row_values.get("A", "")).strip()
                    if not key:
                        continue
                    values[key.lower()] = str(row_values.get("B", "")).strip()
            return values
    except (OSError, ValueError, zipfile.BadZipFile, ET.ParseError):
        return {}


def _read_shared_strings(archive: zipfile.ZipFile) -> list[str]:
    try:
        raw = archive.read("xl/sharedStrings.xml")
    except KeyError:
        return []
    root = ET.fromstring(raw)
    namespace = {"main": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}
    return [
        "".join(node.text or "" for node in item.findall(".//main:t", namespace))
        for item in root.findall("main:si", namespace)
    ]


def _xlsx_cell_value(cell: ET.Element, shared_strings: list[str], namespace: dict[str, str]) -> str:
    cell_type = cell.attrib.get("t", "")
    if cell_type == "inlineStr":
        return "".join(node.text or "" for node in cell.findall(".//main:t", namespace))
    value_node = cell.find("main:v", namespace)
    value = value_node.text if value_node is not None and value_node.text is not None else ""
    if cell_type == "s":
        try:
            return shared_strings[int(value)]
        except (ValueError, IndexError):
            return ""
    return value


def _build_legacy_delivery_payload(files: list[dict], metadata: dict[str, str]) -> dict[str, object]:
    stage = _legacy_delivery_stage(files, metadata)
    configured = _as_boolean(metadata.get("project_configured"))
    source_xml = _source_xml_from_metadata(metadata)
    return {
        "stage": stage,
        "configured": configured,
        "source_xml": source_xml,
        "steps": LEGACY_DELIVERY_STEPS,
    }


def _legacy_delivery_stage(files: list[dict], metadata: dict[str, str]) -> str:
    if not any(str(item.get("role", "")).lower() == "project_sheet" for item in files):
        return "error"

    has_ok_pdf = any(_is_ok_pdf(item) for item in files)
    has_lang_xml = any(_is_language_xml(item) for item in files)
    configured = _as_boolean(metadata.get("project_configured"))
    source_xml = _source_xml_from_metadata(metadata)
    has_lang_export = configured and _has_translation_export(files, source_xml)

    if has_ok_pdf:
        if has_lang_export:
            return "in_translation"
        if has_lang_xml:
            return "closed"
        return "freigegeben"
    if configured:
        return "in_work"
    return "new"


def _source_xml_from_metadata(metadata: dict[str, str]) -> str | None:
    trunk_or_branch = str(metadata.get("trunk_or_branch", "")).strip().lower()
    if trunk_or_branch == "branch":
        return metadata.get("branch_xml") or metadata.get("trunk_xml")
    return metadata.get("trunk_xml") or metadata.get("branch_xml")


def _as_boolean(value: object) -> bool:
    if isinstance(value, str):
        return value.strip().lower() not in {
            "",
            "0",
            "false",
            "falsch",
            "no",
            "nein",
            "-",
            "off",
            "aus",
            "none",
        }
    return bool(value)


def _file_path(item: dict) -> str:
    return str(item.get("path", "")).replace("\\", "/")


def _is_ok_pdf(item: dict) -> bool:
    path = _file_path(item).lower()
    name = Path(path).name
    return name.endswith(".pdf") and name.startswith("o.k._")


def _is_language_xml(item: dict) -> bool:
    path = _file_path(item).lower()
    name = Path(path).name
    if not name.endswith(".xml"):
        return False
    stem = Path(name).stem
    return len(stem) >= 3 and stem[-3] == "_" and stem[-2:] != "de"


def _has_translation_export(files: list[dict], source_xml: str | None) -> bool:
    if not source_xml:
        return False
    source_prefix = Path(str(source_xml).replace("\\", "/")).stem + "_"
    for item in files:
        parts = [part for part in _file_path(item).split("/") if part]
        if not parts:
            continue
        directory = parts[0]
        lower = directory.lower()
        if lower[-18:-2] != "target_language_":
            continue
        prefix = directory[:-18]
        if prefix and prefix != source_prefix:
            continue
        return True
    return False
