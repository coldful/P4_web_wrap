from p4_web.core.config import Settings
from p4_web.storage import LocalStorage, StorageBackend


def build_storage(settings: Settings) -> StorageBackend:
    if settings.storage_backend != "local":
        raise NotImplementedError(f"Storage backend is not implemented: {settings.storage_backend}")
    return LocalStorage(settings.local_storage_root)

