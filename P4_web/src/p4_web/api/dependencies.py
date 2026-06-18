from collections.abc import AsyncIterator

from sqlalchemy.ext.asyncio import AsyncSession

from p4_web.core.config import Settings, get_settings
from p4_web.persistence.database import get_session
from p4_web.services.storage_factory import build_storage
from p4_web.storage import StorageBackend


async def db_session() -> AsyncIterator[AsyncSession]:
    async for session in get_session():
        yield session


def settings_dep() -> Settings:
    return get_settings()


def storage_dep() -> StorageBackend:
    return build_storage(get_settings())


def actor_id_dep() -> str:
    return get_settings().default_actor_id

