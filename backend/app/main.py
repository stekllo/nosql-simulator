"""Точка входа FastAPI-приложения NoSQL Simulator."""
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.auth    import router as auth_router
from app.api.builder import router as builder_router
from app.api.courses import router as courses_router
from app.api.health  import router as health_router
from app.api.me      import router as me_router
from app.api.tasks   import router as tasks_router
from app.api.teacher import router as teacher_router
from app.core.config import settings
from app.db.migrations import run_migrations_on_startup

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(_: FastAPI):
    """Lifecycle-обработчик: автоматические миграции при старте.

    Если RUN_MIGRATIONS_ON_STARTUP=true (по умолчанию), на каждом старте
    backend выполняет `alembic upgrade head` с retry — это значит:
      - после первого `docker compose up` БД сразу готова к работе
      - после ребута VPS контейнер сам подтягивает свежие миграции
      - ручной `alembic upgrade head` больше не нужен

    Если что-то идёт не так — миграция кидает RuntimeError, и FastAPI
    не стартует. Это намеренно: лучше упасть на старте, чем работать
    с неполной БД и плодить странные ошибки в рантайме.
    """
    if settings.RUN_MIGRATIONS_ON_STARTUP:
        await run_migrations_on_startup()
    else:
        logger.info(
            "Skipping migrations on startup "
            "(RUN_MIGRATIONS_ON_STARTUP=false)."
        )
    yield
    # Тут можно было бы добавить cleanup, но движок SQLAlchemy
    # сам корректно закроется при остановке процесса.


app = FastAPI(
    title       = "NoSQL Simulator API",
    version     = "0.8.0",
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

app.include_router(health_router,  prefix="/health",  tags=["health"])
app.include_router(auth_router,    prefix="/auth",    tags=["auth"])
app.include_router(courses_router, prefix="/courses", tags=["courses"])
app.include_router(tasks_router,   prefix="/tasks",   tags=["tasks"])
app.include_router(me_router,      prefix="/me",      tags=["me"])
app.include_router(builder_router, prefix="/builder", tags=["builder"])
app.include_router(teacher_router, prefix="/teacher", tags=["teacher"])


@app.get("/", include_in_schema=False)
async def root():
    return {"name": settings.APP_NAME, "version": "0.8.0", "docs": "/docs"}
