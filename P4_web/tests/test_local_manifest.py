from pathlib import Path

from p4_web.domain.enums import FileRole
from p4_web.sync.local_manifest import compute_manifest, infer_file_role


def test_infer_file_roles() -> None:
    assert infer_file_role("demo.proj.xlsm") == FileRole.PROJECT_SHEET
    assert infer_file_role("demo_keyseq.txt") == FileRole.KEYSEQ
    assert infer_file_role("demo_langsel.txt") == FileRole.LANGUAGE_SELECTION
    assert infer_file_role("source.xml") == FileRole.SOURCE_XML
    assert infer_file_role("image.bmp") == FileRole.IMAGE


def test_compute_manifest_skips_git_and_hashes_files(tmp_path: Path) -> None:
    (tmp_path / "demo.proj.xlsm").write_text("project", encoding="utf-8")
    (tmp_path / "source.xml").write_text("<root/>", encoding="utf-8")
    (tmp_path / ".git").mkdir()
    (tmp_path / ".git" / "ignored").write_text("ignored", encoding="utf-8")

    manifest = compute_manifest(tmp_path)

    assert [item.path for item in manifest] == ["demo.proj.xlsm", "source.xml"]
    assert manifest[0].sha256
    assert manifest[0].role == FileRole.PROJECT_SHEET
    assert manifest[1].role == FileRole.SOURCE_XML

