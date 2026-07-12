from pathlib import Path

import pytest

from p4_web.services.delivery_folders import (
    apply_delivery_status_advance_side_effects,
    ensure_delivery_stage_folders,
    get_folder_stage_for_advance,
)


@pytest.fixture
def project_dir(tmp_path: Path) -> Path:
    root = tmp_path / "project"
    root.mkdir()
    xml_path = root / "source.xml"
    xml_path.write_text("<root/>", encoding="utf-8")
    for pdf_name in ("first.pdf", "second.PDF"):
        (root / pdf_name).write_text(pdf_name, encoding="utf-8")
    return root


def test_stage_one_creates_numeric_backup_folder_and_copies_xml(project_dir: Path) -> None:
    ensure_delivery_stage_folders(project_dir, 1, {"trunk_xml": "source.xml"})

    backup_dir = project_dir / "001"
    assert backup_dir.is_dir()
    assert (backup_dir / "source.xml").is_file()


def test_stage_two_copies_single_pdf_with_korrekturexemplar_name(project_dir: Path) -> None:
    ensure_delivery_stage_folders(project_dir, 2, {"trunk_xml": "source.xml"})

    backup_dir = project_dir / "002"
    korrektur_pdf = backup_dir / "Korrekturexemplar_1" / "Korrekturexemplar_1.pdf"
    assert backup_dir.is_dir()
    assert (backup_dir / "source.xml").is_file()
    assert korrektur_pdf.is_file()
    assert not (project_dir / "Korrekturexemplar_1").exists()


def test_stage_three_copies_single_pdf_with_korrekturexemplar_name(project_dir: Path) -> None:
    ensure_delivery_stage_folders(project_dir, 3, {"trunk_xml": "source.xml"})

    backup_dir = project_dir / "003"
    korrektur_pdf = backup_dir / "Korrekturexemplar_2" / "Korrekturexemplar_2.pdf"
    assert backup_dir.is_dir()
    assert (backup_dir / "source.xml").is_file()
    assert korrektur_pdf.is_file()
    assert not (project_dir / "Korrekturexemplar_2").exists()


def test_stage_four_copies_all_pdfs_to_pdf_folder(project_dir: Path) -> None:
    ensure_delivery_stage_folders(project_dir, 4, {"trunk_xml": "source.xml"})

    pdf_dir = project_dir / "pdf"
    assert pdf_dir.is_dir()
    assert (pdf_dir / "first.pdf").is_file()
    assert (pdf_dir / "second.PDF").is_file()


def test_folder_stage_for_advance_matches_indicator_position() -> None:
    assert get_folder_stage_for_advance(0, 1) == 1
    assert get_folder_stage_for_advance(1, 2) == 1
    assert get_folder_stage_for_advance(2, 3) == 2
    assert get_folder_stage_for_advance(3, 4) == 3
    assert get_folder_stage_for_advance(4, 5) == 4
    assert get_folder_stage_for_advance(5, 0) == 5


def test_apply_delivery_status_advance_side_effects_from_zero(project_dir: Path) -> None:
    next_status = apply_delivery_status_advance_side_effects(project_dir, {"delivery_status": "0"})

    assert next_status == 1
    assert (project_dir / "001" / "source.xml").is_file()


def test_apply_delivery_status_advance_side_effects_wraps_to_zero(project_dir: Path) -> None:
    for stage in (1, 2, 3, 4):
        ensure_delivery_stage_folders(project_dir, stage, {"trunk_xml": "source.xml"})

    next_status = apply_delivery_status_advance_side_effects(project_dir, {"delivery_status": "5"})

    assert next_status == 0
    assert (project_dir / "005").is_dir()
