"""Диспатчер выполнения запросов: выбирает runner по db_type задания.

Вынесено отдельно от api/tasks.py, чтобы:
  - api/tasks.py не знал детали клиентов разных СУБД
  - добавление нового NoSQL-runner'а сводилось к добавлению одной ветки

Контракт всех runner'ов одинаковый: возвращают ExecutionResult с полями
ok / duration_ms / result / error. Сравнение и подсчёт баллов делаются
в api/tasks.py, не здесь.
"""
from __future__ import annotations

from motor.motor_asyncio import AsyncIOMotorClient

from app.core.config import settings
from app.models import NoSQLType
from app.sandbox.cassandra_runner import ExecutionResult as CassandraResult
from app.sandbox.cassandra_runner import execute_cql_script
from app.sandbox.mongo_runner import ExecutionResult as MongoResult
from app.sandbox.mongo_runner import execute_mql
from app.sandbox.neo4j_runner import ExecutionResult as Neo4jResult
from app.sandbox.neo4j_runner import execute_cypher_script
from app.sandbox.redis_runner import ExecutionResult as RedisResult
from app.sandbox.redis_runner import execute_redis_script

# Универсальный тип результата (структуры идентичны, см. модули runner'ов).
SandboxResult = MongoResult | RedisResult | CassandraResult | Neo4jResult


# Cassandra использует стандартный native-protocol порт.
CASSANDRA_PORT = 9042


def _parse_neo4j_auth(auth_str: str) -> tuple[str, str]:
    """Разбирает строку 'login:password' в кортеж для драйвера."""
    if ":" not in auth_str:
        return (auth_str, "")
    login, _, password = auth_str.partition(":")
    return (login, password)


async def execute_for_task(
    db_type:    NoSQLType,
    fixture:    dict,
    query_text: str,
) -> SandboxResult:
    """Выполняет запрос в соответствующей песочнице.

    Для DOCUMENT (MongoDB)  — Motor + ephemeral database.
    Для KEY_VALUE (Redis)   — redis-py async + FLUSHDB до/после.
    Для COLUMN (Cassandra)  — cassandra-driver + ephemeral keyspace.
    Для GRAPH (Neo4j)       — neo4j async + транзакция с rollback.
    Остальные типы (MIXED) пока не реализованы (501).
    """
    if db_type == NoSQLType.DOCUMENT:
        client = AsyncIOMotorClient(settings.MONGO_URL, serverSelectionTimeoutMS=3000)
        try:
            return await execute_mql(client, fixture, query_text)
        finally:
            client.close()

    if db_type == NoSQLType.KEY_VALUE:
        return await execute_redis_script(
            settings.REDIS_SANDBOX_URL,
            fixture,
            query_text,
        )

    if db_type == NoSQLType.COLUMN:
        return await execute_cql_script(
            cluster_hosts=[settings.CASSANDRA_HOST],
            cluster_port=CASSANDRA_PORT,
            fixture=fixture,
            query_text=query_text,
        )

    if db_type == NoSQLType.GRAPH:
        return await execute_cypher_script(
            uri=settings.NEO4J_URL,
            auth=_parse_neo4j_auth(settings.NEO4J_AUTH),
            fixture=fixture,
            query_text=query_text,
        )

    # MIXED — пока нет.
    raise NotImplementedError(
        f"Runner для типа {db_type.value!r} ещё не реализован"
    )


def is_supported(db_type: NoSQLType) -> bool:
    """True, если для этого типа есть runner."""
    return db_type in (
        NoSQLType.DOCUMENT, NoSQLType.KEY_VALUE,
        NoSQLType.COLUMN,   NoSQLType.GRAPH,
    )
