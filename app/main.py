from __future__ import annotations

from contextlib import asynccontextmanager

from apscheduler.schedulers.background import BackgroundScheduler
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlmodel import Session

from app.api.v1.router import api_router
from app.core.config import get_settings
from app.core.logging import configure_logging
from app.db.init_db import create_db_and_tables
from app.db.session import engine
from app.services.sync_service import SyncService


settings = get_settings()
configure_logging()
_scheduler: BackgroundScheduler | None = None



def run_scheduled_sync() -> None:
    with Session(engine) as session:
        SyncService(session).sync_all_enabled_sources()


@asynccontextmanager
async def lifespan(_: FastAPI):
    global _scheduler
    create_db_and_tables()
    if settings.scheduler_enabled:
        _scheduler = BackgroundScheduler(timezone=settings.timezone)
        _scheduler.add_job(
            run_scheduled_sync,
            trigger="interval",
            minutes=settings.scheduler_interval_minutes,
            id="knowledge-source-sync",
            replace_existing=True,
        )
        _scheduler.start()
    yield
    if _scheduler and _scheduler.running:
        _scheduler.shutdown(wait=False)


app = FastAPI(title=settings.app_name, lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(api_router, prefix=settings.api_v1_prefix)


@app.get("/")
def root() -> dict[str, str]:
    return {"message": settings.app_name, "docs": "/docs"}


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
