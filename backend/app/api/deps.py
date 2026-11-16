from app.core.config import get_settings
from app.integrations.storage import LocalDiskStorage, StorageBackend


def get_storage() -> StorageBackend:
    return LocalDiskStorage(get_settings().storage_root)
