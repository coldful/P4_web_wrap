import hashlib
import shutil
from pathlib import Path

from p4_web.storage.ports import StoredObject


class LocalStorage:
    """Local filesystem storage adapter for development and tests."""

    def __init__(self, root: Path) -> None:
        self.root = root
        self.root.mkdir(parents=True, exist_ok=True)

    def _path_for_key(self, key: str) -> Path:
        clean_key = key.strip().replace("\\", "/").lstrip("/")
        if ".." in Path(clean_key).parts:
            raise ValueError(f"Unsafe storage key: {key}")
        return self.root / clean_key

    def put_bytes(self, key: str, data: bytes, content_type: str | None = None) -> StoredObject:
        path = self._path_for_key(key)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
        return StoredObject(
            key=key,
            sha256=hashlib.sha256(data).hexdigest(),
            size_bytes=len(data),
            content_type=content_type,
        )

    def put_file(self, key: str, path: Path, content_type: str | None = None) -> StoredObject:
        target = self._path_for_key(key)
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(path, target)
        sha = hashlib.sha256()
        size = 0
        with target.open("rb") as handle:
            for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                sha.update(chunk)
                size += len(chunk)
        return StoredObject(
            key=key,
            sha256=sha.hexdigest(),
            size_bytes=size,
            content_type=content_type,
        )

    def resolve_local_path(self, key: str) -> Path | None:
        path = self._path_for_key(key)
        return path if path.exists() else None

    def copy_to_path(self, key: str, target: Path) -> None:
        source = self._path_for_key(key)
        if not source.exists():
            raise FileNotFoundError(f"Stored object not found: {key}")
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, target)

    def copy_object(
        self,
        source_key: str,
        target_key: str,
        content_type: str | None = None,
    ) -> StoredObject:
        source = self._path_for_key(source_key)
        if not source.exists():
            raise FileNotFoundError(f"Stored object not found: {source_key}")
        return self.put_file(target_key, source, content_type)

    def delete_prefix(self, prefix: str) -> None:
        clean_prefix = prefix.strip().replace("\\", "/").lstrip("/")
        if not clean_prefix:
            raise ValueError("Refusing to delete empty storage prefix")
        target = self._path_for_key(clean_prefix)
        if target.is_file():
            target.unlink()
            return
        if target.is_dir():
            shutil.rmtree(target)
