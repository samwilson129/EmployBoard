from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app import __version__
from app.api.routes import admin, companies, health, jobs, sources, stats
from app.config import get_settings
from app.database.connection import SessionLocal, dispose_engine
from app.database.seed import seed_companies
from app.logging_config import configure_logging
from app.services.ingestion_service import run_scheduled_sync
from app.services.description_cache_service import run_cache_maintenance

logger = logging.getLogger(__name__)
settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    configure_logging(settings.log_level)
    logger.info(
        "Starting %s %s (environment=%s, database=%s)",
        settings.app_name,
        __version__,
        settings.environment,
        settings.redacted_database_url,
    )

    if settings.seed_on_startup:
        try:
            async with SessionLocal() as session:
                result = await seed_companies(session)
            logger.info("Company registry seeded: %s", result)
        except Exception:  # noqa: BLE001 - startup should report, not crash
            logger.exception("Company registry seed failed")

    scheduler: AsyncIOScheduler | None = None
    if settings.enable_scheduler:
        scheduler = AsyncIOScheduler(timezone="UTC")
        scheduler.add_job(
            run_scheduled_sync,
            "interval",
            hours=settings.sync_interval_hours,
            args=[SessionLocal, settings],
            id="employboard-ingestion",
            replace_existing=True,
            max_instances=1,
            coalesce=True,
            misfire_grace_time=3600,
        )
        scheduler.add_job(
            run_cache_maintenance,
            "interval",
            hours=settings.cache_maintenance_interval_hours,
            args=[SessionLocal, settings],
            id="employboard-description-cache-maintenance",
            replace_existing=True,
            max_instances=1,
            coalesce=True,
            misfire_grace_time=3600,
        )
        scheduler.start()
        logger.info(
            "In-process ingestion scheduler started (every %s hours)",
            settings.sync_interval_hours,
        )
    app.state.scheduler = scheduler

    yield

    if scheduler is not None:
        scheduler.shutdown(wait=False)
    await dispose_engine()
    logger.info("Shutdown complete")


app = FastAPI(
    title="EmployBoard API",
    version=__version__,
    description=(
        "Public job aggregation API. Normalizes postings from configured public "
        "ATS providers into one schema."
    ),
    lifespan=lifespan,
)

origins = settings.cors_origin_list
allow_all = "*" in origins
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"] if allow_all else origins,
    allow_credentials=False,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["*"],
)

app.include_router(jobs.router, prefix="/api")
app.include_router(companies.router, prefix="/api")
app.include_router(sources.router, prefix="/api")
app.include_router(stats.router, prefix="/api")
app.include_router(health.router, prefix="/api")
app.include_router(admin.router, prefix="/api")


@app.get("/", tags=["meta"])
async def root() -> dict[str, str]:
    return {
        "name": "EmployBoard API",
        "tagline": "Every job. Every source. One board.",
        "version": __version__,
        "docs": "/docs",
        "health": "/api/health",
        "jobs": "/api/jobs",
    }
