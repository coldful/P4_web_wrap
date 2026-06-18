from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from p4_web.api.routers import approvals, artifacts, files, health, jobs, projects, sync, versions
from p4_web.core.config import get_settings
from p4_web.persistence.database import init_db


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    await init_db()
    yield


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(title=settings.app_name, lifespan=lifespan)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    api_prefix = "/api"
    app.include_router(health.router, prefix=api_prefix)
    app.include_router(projects.router, prefix=api_prefix)
    app.include_router(sync.router, prefix=api_prefix)
    app.include_router(versions.router, prefix=api_prefix)
    app.include_router(files.router, prefix=api_prefix)
    app.include_router(jobs.router, prefix=api_prefix)
    app.include_router(artifacts.router, prefix=api_prefix)
    app.include_router(approvals.router, prefix=api_prefix)
    return app


app = create_app()
