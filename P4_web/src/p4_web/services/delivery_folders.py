from __future__ import annotations

import re
import shutil
from pathlib import Path

from p4_web.services.delivery_state import DELIVERY_STATUS_STAGE_COUNT, normalize_delivery_status

DELIVERY_STAGE_FOLDERS: dict[int, tuple[str, ...]] = {
    1: ("001",),
    2: ("002",),
    3: ("003",),
    4: ("pdf", "sap", "004"),
    5: ("005",),
}
DELIVERY_STAGE_ALL_PDF_COPY_FOLDERS = ("pdf",)
DELIVERY_STAGE_KORREKTUR_SUBFOLDERS: dict[int, str] = {
    2: "Korrekturexemplar_1",
    3: "Korrekturexemplar_2",
}


class DeliveryFolderError(Exception):
    pass


def get_folder_stage_for_advance(current_status: int, next_status: int) -> int | None:
    current_status = normalize_delivery_status(current_status, default=0) or 0
    next_status = normalize_delivery_status(next_status, default=0) or 0
    if current_status >= 1:
        return current_status
    if next_status >= 1:
        return next_status
    return None


def compute_next_delivery_status(current_status: int) -> int:
    current_status = normalize_delivery_status(current_status, default=0) or 0
    if current_status >= DELIVERY_STATUS_STAGE_COUNT:
        return 0
    return current_status + 1


def ensure_delivery_stage_folders(
    project_root: Path,
    stage: int,
    metadata: dict[str, str],
) -> None:
    stage = normalize_delivery_status(stage, default=0) or 0
    if stage <= 0:
        return

    for folder_name in DELIVERY_STAGE_FOLDERS.get(stage, ()):
        folder_path = project_root / folder_name
        _ensure_directory(folder_path)
        if re.fullmatch(r"\d{3}", folder_name):
            _copy_current_xml_to_folder(project_root, folder_path, metadata)
            korrektur_subfolder = DELIVERY_STAGE_KORREKTUR_SUBFOLDERS.get(stage)
            if korrektur_subfolder:
                _copy_first_project_pdf_to_korrektur_subfolder(folder_path, korrektur_subfolder)
        if folder_name in DELIVERY_STAGE_ALL_PDF_COPY_FOLDERS:
            _copy_project_pdfs_to_folder(project_root, folder_path)


def apply_delivery_status_advance_side_effects(
    project_root: Path,
    metadata: dict[str, str],
) -> int:
    current_status = normalize_delivery_status(metadata.get("delivery_status"), default=0) or 0
    next_status = compute_next_delivery_status(current_status)
    folder_stage = get_folder_stage_for_advance(current_status, next_status)
    if folder_stage:
        ensure_delivery_stage_folders(project_root, folder_stage, metadata)
    return next_status


def resolve_delivery_source_xml(project_root: Path, metadata: dict[str, str]) -> Path | None:
    trunk_or_branch = str(metadata.get("trunk_or_branch", "")).strip().lower()
    if trunk_or_branch == "branch":
        candidate = metadata.get("branch_xml") or metadata.get("trunk_xml")
    else:
        candidate = metadata.get("trunk_xml") or metadata.get("branch_xml")
    if candidate:
        path = Path(str(candidate))
        if not path.is_absolute():
            path = project_root / path
        if path.is_file():
            return path

    xml_files = sorted(
        path
        for path in project_root.glob("*.xml")
        if path.is_file() and path.name.lower() not in {"configuration.xml"}
    )
    return xml_files[0] if xml_files else None


def _ensure_directory(path: Path) -> None:
    if path.is_dir():
        return
    if path.exists():
        raise DeliveryFolderError(f"Can't create directory '{path}': file already exists")
    path.mkdir(parents=True, exist_ok=False)


def _copy_current_xml_to_folder(
    project_root: Path,
    folder_path: Path,
    metadata: dict[str, str],
) -> None:
    source_xml = resolve_delivery_source_xml(project_root, metadata)
    if source_xml is None:
        return
    destination = folder_path / source_xml.name
    shutil.copy2(source_xml, destination)


def _project_pdfs(project_root: Path) -> list[Path]:
    return sorted(
        (
            path
            for path in project_root.iterdir()
            if path.is_file() and path.suffix.lower() == ".pdf"
        ),
        key=lambda path: path.name.lower(),
    )


def _copy_project_pdfs_to_folder(project_root: Path, folder_path: Path) -> None:
    for source_pdf in _project_pdfs(project_root):
        shutil.copy2(source_pdf, folder_path / source_pdf.name)


def _copy_first_project_pdf_to_korrektur_subfolder(folder_path: Path, subfolder_name: str) -> None:
    project_pdfs = _project_pdfs(folder_path.parent)
    if not project_pdfs:
        return
    subfolder_path = folder_path / subfolder_name
    _ensure_directory(subfolder_path)
    shutil.copy2(project_pdfs[0], subfolder_path / f"{subfolder_name}.pdf")
