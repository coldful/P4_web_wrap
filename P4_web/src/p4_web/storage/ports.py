from dataclasses import dataclass
from pathlib import Path
from typing import Protocol


@dataclass(frozen=True)
class StoredObject:
    key: str
    sha256: str
    size_bytes: int
    content_type: str | None = None


class StorageBackend(Protocol):
    def put_bytes(self, key: str, data: bytes, content_type: str | None = None) -> StoredObject:
        ...

    def put_file(self, key: str, path: Path, content_type: str | None = None) -> StoredObject:
        ...

    def resolve_local_path(self, key: str) -> Path | None:
        ...

    def copy_to_path(self, key: str, target: Path) -> None:
        ...

    def copy_object(
        self,
        source_key: str,
        target_key: str,
        content_type: str | None = None,
    ) -> StoredObject:
        ...

    def delete_prefix(self, prefix: str) -> None:
        ...
