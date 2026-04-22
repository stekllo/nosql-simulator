"""Точка входа FastAPI-приложения NoSQL Simulator."""
import logging
from contextlib import asynccontextmanager

from alembic import command
from alembic.config import Config as AlembicConfig
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.health import router as health_router
from app.core.config import settings

logger = logging.getLogger(__name__)


def _run_migrations() -> None:
    """Прогоняем Alembic-миграции при старте контейнера."""
    cfg = AlembicConfig("alembic.ini")
    cfg.set_main_option("sqlalchemy.url", settings.DATABASE_URL)
    command.upgrade(cfg, "head")


@asynccontextmanager
async def lifespan(_: FastAPI):
    """Стартовая и завершающая инициализация приложения."""
    logger.info("Running Alembic migrations...")
    try:
        _run_migrations()
        logger.info("Migrations done")
    except Exception as err:
        # На первом старте Postgres может быть ещё не готов — это логируем,
        # не падаем: Docker рестартнёт контейнер через depends_on/healthcheck.
        logger.warning("Migration step failed: %s", err)

    yield


app = FastAPI(
    title       = "NoSQL Simulator API",
    version     = "0.1.0",
    description = "Backend для обучающего симулятора NoSQL баз данных",
    lifespan    = lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins     = ["http://localhost:3000"],
    allow_credentials = True,
    allow_methods     = ["*"],
    allow_headers     = ["*"],
)

app.include_router(health_router, prefix="/health", tags=["health"])


@app.get("/", include_in_schema=False)
async def root():
    return {
        "name":    settings.APP_NAME,
        "version": "0.1.0",
        "docs":    "/docs",
    }
