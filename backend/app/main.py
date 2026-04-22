"""Точка входа FastAPI-приложения NoSQL Simulator."""
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.health import router as health_router
from app.core.config import settings


@asynccontextmanager
async def lifespan(_: FastAPI):
    """Стартовая и завершающая инициализация приложения."""
    # На старте: установить соединения, прогнать миграции и т. п.
    # На остановке: закрыть соединения.
    yield


app = FastAPI(
    title       = "NoSQL Simulator API",
    version     = "0.1.0",
    description = "Backend для обучающего симулятора NoSQL баз данных",
    lifespan    = lifespan,
)

# CORS: фронтенд во время разработки запущен на другом порту.
app.add_middleware(
    CORSMiddleware,
    allow_origins     = ["http://localhost:3000"],
    allow_credentials = True,
    allow_methods     = ["*"],
    allow_headers     = ["*"],
)

# Маршруты.
app.include_router(health_router, prefix="/health", tags=["health"])


@app.get("/", include_in_schema=False)
async def root():
    """Корневой эндпоинт — быстрая проверка, что приложение поднялось."""
    return {
        "name":    settings.APP_NAME,
        "version": "0.1.0",
        "docs":    "/docs",
    }
