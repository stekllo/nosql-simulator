"""Точка входа FastAPI-приложения NoSQL Simulator."""
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.auth    import router as auth_router
from app.api.courses import router as courses_router
from app.api.health  import router as health_router
from app.core.config import settings


@asynccontextmanager
async def lifespan(_: FastAPI):
    yield


app = FastAPI(
    title       = "NoSQL Simulator API",
    version     = "0.4.0",
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


@app.get("/", include_in_schema=False)
async def root():
    return {"name": settings.APP_NAME, "version": "0.4.0", "docs": "/docs"}
