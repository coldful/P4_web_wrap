import asyncio

from p4_web.core.config import get_settings
from p4_web.persistence.database import SessionLocal
from p4_web.services.jobs import run_job
from p4_web.services.storage_factory import build_storage


async def run_one(job_id: str) -> None:
    settings = get_settings()
    storage = build_storage(settings)
    await run_job(SessionLocal, job_id, settings, storage)


def run_one_sync(job_id: str) -> None:
    asyncio.run(run_one(job_id))

