"""Health-check для всех зависимых сервисов.

Возвращает статус каждой СУБД и брокера. Удобно для отладки и для
проверки в CI, что окружение правильно поднято.
"""
import asyncio
import logging
from typing import Literal

from fastapi import APIRouter
from motor.motor_asyncio import AsyncIOMotorClient
from pydantic import BaseModel
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy import text

from app.core.config import settings

logger = logging.getLogger(__name__)
router = APIRouter()


class ServiceStatus(BaseModel):
    name:   str
    status: Literal["ok", "down"]
    detail: str | None = None


class HealthResponse(BaseModel):
    status:   Literal["ok", "degraded"]
    services: list[ServiceStatus]


# ---------- Чекеры ----------

async def _check_postgres() -> ServiceStatus:
    try:
        engine = create_async_engine(settings.DATABASE_URL, pool_pre_ping=True)
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        await engine.dispose()
        return ServiceStatus(name="postgres", status="ok")
    except Exception as e:
        return ServiceStatus(name="postgres", status="down", detail=str(e)[:200])


async def _check_mongo() -> ServiceStatus:
    try:
        client = AsyncIOMotorClient(settings.MONGO_URL, serverSelectionTimeoutMS=2000)
        await client.admin.command("ping")
        client.close()
        return ServiceStatus(name="mongo", status="ok")
    except Exception as e:
        return ServiceStatus(name="mongo", status="down", detail=str(e)[:200])


async def _check_redis_sandbox() -> ServiceStatus:
    try:
        r = Redis.from_url(settings.REDIS_SANDBOX_URL, socket_connect_timeout=2)
        await r.ping()
        await r.close()
        return ServiceStatus(name="redis-sandbox", status="ok")
    except Exception as e:
        return ServiceStatus(name="redis-sandbox", status="down", detail=str(e)[:200])


async def _check_redis_broker() -> ServiceStatus:
    try:
        r = Redis.from_url(settings.REDIS_BROKER_URL, socket_connect_timeout=2)
        await r.ping()
        await r.close()
        return ServiceStatus(name="redis-broker", status="ok")
    except Exception as e:
        return ServiceStatus(name="redis-broker", status="down", detail=str(e)[:200])


# Cassandra и Neo4j подымаются медленно — проверим тоже,
# но не валим итоговый статус, если они ещё стартуют.
async def _check_cassandra() -> ServiceStatus:
    # Драйвер cassandra-driver — синхронный, гоняем в thread.
    def _ping():
        from cassandra.cluster import Cluster
        from cassandra.policies import DCAwareRoundRobinPolicy

        cluster = Cluster(
            [settings.CASSANDRA_HOST],
            connect_timeout=2,
            load_balancing_policy=DCAwareRoundRobinPolicy(local_dc="datacenter1"),
            protocol_version=4,
        )
        session = cluster.connect()
        session.execute("SELECT release_version FROM system.local")
        cluster.shutdown()

    try:
        await asyncio.wait_for(asyncio.to_thread(_ping), timeout=5)
        return ServiceStatus(name="cassandra", status="ok")
    except Exception as e:
        return ServiceStatus(name="cassandra", status="down", detail=str(e)[:200])


async def _check_neo4j() -> ServiceStatus:
    try:
        from neo4j import AsyncGraphDatabase

        user, password = settings.NEO4J_AUTH.split(":", 1)
        driver = AsyncGraphDatabase.driver(settings.NEO4J_URL, auth=(user, password))
        async with driver.session() as session:
            await session.run("RETURN 1")
        await driver.close()
        return ServiceStatus(name="neo4j", status="ok")
    except Exception as e:
        return ServiceStatus(name="neo4j", status="down", detail=str(e)[:200])


# ---------- Эндпоинт ----------

@router.get("", response_model=HealthResponse)
async def health() -> HealthResponse:
    """Возвращает статус всех зависимых сервисов."""
    services = await asyncio.gather(
        _check_postgres(),
        _check_mongo(),
        _check_redis_sandbox(),
        _check_redis_broker(),
        _check_cassandra(),
        _check_neo4j(),
        return_exceptions=False,
    )
    overall = "ok" if all(s.status == "ok" for s in services) else "degraded"
    return HealthResponse(status=overall, services=services)
