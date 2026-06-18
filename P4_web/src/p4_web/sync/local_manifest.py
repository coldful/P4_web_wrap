import hashlib
from dataclasses import asdict, dataclass
from pathlib import Path

from p4_web.domain.enums import FileRole


@dataclass(frozen=True)
class ManifestItem:
    path: str
    sha256: str
    size_bytes: int
    mtime_ns: int
    role: FileRole

    def to_dict(self) -> dict:
        data = asdict(self)
        data["role"] = self.role.value
        return data


def compute_manifest(root: Path) -> list[ManifestItem]:
    root = root.resolve()
    if not root.is_dir():
        raise ValueError(f"Manifest root is not a directory: {root}")
    items: list[ManifestItem] = []
    for path in sorted(root.rglob("*")):
        if not path.is_file() or _is_ignored(path, root):
            continue
        rel = path.relative_to(root).as_posix()
        stat = path.stat()
        items.append(
            ManifestItem(
                path=rel,
                sha256=_sha256(path),
                size_bytes=stat.st_size,
                mtime_ns=stat.st_mtime_ns,
                role=infer_file_role(rel),
            )
        )
    return items


def infer_file_role(path: str) -> FileRole:
    lower = path.lower()
    name = Path(lower).name
    if name.endswith((".proj.xls", ".proj.xlsx", ".proj.xlsm")):
        return FileRole.PROJECT_SHEET
    if name.endswith("_keyseq.txt") or name == "keyseq.txt":
        return FileRole.KEYSEQ
    if name.endswith("_langsel.txt"):
        return FileRole.LANGUAGE_SELECTION
    if lower.endswith(".xml"):
        return FileRole.SOURCE_XML
    if lower.endswith((".png", ".jpg", ".jpeg", ".gif", ".bmp", ".svg", ".eps", ".pdf")):
        return FileRole.IMAGE
    if name in {"configuration.xml", "configuration.py", "sconstruct"}:
        return FileRole.CONFIG
    return FileRole.OTHER


def _sha256(path: Path) -> str:
    sha = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            sha.update(chunk)
    return sha.hexdigest()


def _is_ignored(path: Path, root: Path) -> bool:
    rel_parts = path.relative_to(root).parts
    return any(part in {".git", "__pycache__", ".pytest_cache"} for part in rel_parts)

