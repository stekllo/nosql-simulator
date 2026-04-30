"""Изолированная Neo4j-sandbox и выполнение Cypher-скриптов.

Архитектура изоляции
--------------------

Neo4j Community Edition не поддерживает множественные базы данных, поэтому
изоляция через keyspace (как у Cassandra) недоступна. Решение — **транзакция
с rollback**:

  1. Открываем сессию.
  2. Начинаем транзакцию.
  3. Выполняем preload (от преподавателя).
  4. Выполняем команды студента, читаем результат последней.
  5. **rollback()** — все изменения исчезают.

Преимущество: что бы студент ни сделал (создал узлы, удалил данные), это
не попадает в БД. Даже если он не использует никакие метки — rollback
откатывает всё.

Дополнительно — глобальный asyncio.Lock сериализует выполнение между
параллельными студентами, чтобы транзакции не пересекались по
блокировкам.
"""
from __future__ import annotations

import asyncio
import logging
import time
from dataclasses import dataclass
from datetime import date, datetime, time as dtime
from decimal import Decimal
from typing import Any

from neo4j import AsyncGraphDatabase
from neo4j.exceptions import ClientError, CypherSyntaxError, Neo4jError
from neo4j.time import Date as Neo4jDate
from neo4j.time import DateTime as Neo4jDateTime
from neo4j.time import Time as Neo4jTime

from app.sandbox.cypher_parser import (
    CypherParseError, ParsedCypherStatement, parse_cypher_script,
)

logger = logging.getLogger(__name__)

QUERY_TIMEOUT_SEC = 10.0
PRELOAD_TIMEOUT   = 10.0

# Глобальный лок: Neo4j Community — single-database, и rollback-транзакции
# на одной БД могут конфликтовать по блокировкам узлов между параллельными
# студентами. Сериализуем выполнение проверок.
_runner_lock = asyncio.Lock()


@dataclass
class ExecutionResult:
    """Тот же контракт, что у других runner'ов."""
    ok:          bool
    duration_ms: int
    result:      Any | None = None
    error:       str | None = None


# ---------- Нормализация значений Neo4j → JSON-совместимый вид ----------

def _normalize(value: Any) -> Any:
    """Приводит значения Neo4j к JSON-совместимому виду.

    Neo4j возвращает свои типы для дат/времени, узлов, связей и путей.
    Чтобы compare_to_any_reference корректно сравнивал, приводим всё к
    плоским dict/list/str/int.
    """
    if value is None:
        return None
    # Дата/время Neo4j (свои классы из neo4j.time).
    if isinstance(value, (Neo4jDateTime, Neo4jDate, Neo4jTime)):
        return value.iso_format()
    # Узел: {labels: [...], properties: {...}, id: int}
    if hasattr(value, "labels") and hasattr(value, "items"):
        # Это neo4j.graph.Node
        return {
            "labels":     sorted(value.labels),
            "properties": {k: _normalize(v) for k, v in dict(value).items()},
        }
    # Связь: {type: ..., properties: {...}}
    if hasattr(value, "type") and hasattr(value, "items") and hasattr(value, "start_node"):
        # Это neo4j.graph.Relationship
        return {
            "type":       value.type,
            "properties": {k: _normalize(v) for k, v in dict(value).items()},
        }
    # Путь: список чередующихся узлов и связей
    if hasattr(value, "nodes") and hasattr(value, "relationships"):
        return {
            "nodes":         [_normalize(n) for n in value.nodes],
            "relationships": [_normalize(r) for r in value.relationships],
        }
    # Стандартные Python-типы.
    if isinstance(value, (set, frozenset)):
        try:
            return sorted(_normalize(v) for v in value)
        except TypeError:
            return [_normalize(v) for v in value]
    if isinstance(value, (list, tuple)):
        return [_normalize(v) for v in value]
    if isinstance(value, dict):
        return {str(_normalize(k)): _normalize(v) for k, v in value.items()}
    if isinstance(value, (datetime, date, dtime)):
        return value.isoformat()
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, bytes):
        try:
            return value.decode("utf-8")
        except UnicodeDecodeError:
            return value.hex()
    return value


def _record_to_dict(record: Any) -> dict[str, Any]:
    """Преобразует neo4j Record в dict {column: normalized_value}."""
    return {key: _normalize(record[key]) for key in record.keys()}


# ---------- Выполнение скрипта ----------

async def execute_cypher_script(
    uri:        str,
    auth:       tuple[str, str],
    fixture:    dict,
    query_text: str,
) -> ExecutionResult:
    """Выполняет Cypher-скрипт студента в транзакции с откатом.

    Контракт совместим с mongo_runner / redis_runner / cassandra_runner.
    """
    start = time.perf_counter()

    # 1. Парсинг.
    try:
        statements = parse_cypher_script(query_text)
    except CypherParseError as err:
        return ExecutionResult(
            ok=False,
            duration_ms=int((time.perf_counter() - start) * 1000),
            error=str(err),
        )

    preload: list[str] = list(fixture.get("preload", []))

    async with _runner_lock:
        driver = AsyncGraphDatabase.driver(uri, auth=auth)
        try:
            try:
                last_result = await asyncio.wait_for(
                    _execute_in_transaction(driver, preload, statements),
                    timeout=QUERY_TIMEOUT_SEC + PRELOAD_TIMEOUT,
                )
            except asyncio.TimeoutError:
                return ExecutionResult(
                    ok=False,
                    duration_ms=int((QUERY_TIMEOUT_SEC + PRELOAD_TIMEOUT) * 1000),
                    error=f"Превышено время ожидания (~{int(QUERY_TIMEOUT_SEC + PRELOAD_TIMEOUT)} сек)",
                )
            except CypherSyntaxError as err:
                return ExecutionResult(
                    ok=False,
                    duration_ms=int((time.perf_counter() - start) * 1000),
                    error=f"Ошибка синтаксиса Cypher: {err}",
                )
            except (ClientError, Neo4jError) as err:
                return ExecutionResult(
                    ok=False,
                    duration_ms=int((time.perf_counter() - start) * 1000),
                    error=f"Ошибка Neo4j: {err}",
                )
            except Exception as err:
                logger.exception("Cypher execution error")
                return ExecutionResult(
                    ok=False,
                    duration_ms=int((time.perf_counter() - start) * 1000),
                    error=f"{type(err).__name__}: {err}",
                )
        finally:
            await driver.close()

    return ExecutionResult(
        ok=True,
        duration_ms=int((time.perf_counter() - start) * 1000),
        result=_normalize(last_result),
    )


async def _execute_in_transaction(
    driver,
    preload:    list[str],
    statements: list[ParsedCypherStatement],
) -> Any:
    """Открывает сессию + транзакцию, выполняет всё, делает rollback.

    Возвращает результат последней команды студента.
    """
    async with driver.session() as session:
        tx = await session.begin_transaction()
        try:
            # Preload.
            for raw in preload:
                stmt = raw.strip().rstrip(";").strip()
                if not stmt:
                    continue
                await tx.run(stmt)

            # Скрипт студента.
            last_result: Any = None
            for st in statements:
                try:
                    cursor = await tx.run(st.text)
                    records = [r async for r in cursor]
                except CypherSyntaxError as err:
                    raise CypherSyntaxError(f"Строка {st.line}: {err}") from err

                if records:
                    last_result = [_record_to_dict(r) for r in records]
                else:
                    # Команды без явного RETURN ничего не отдают.
                    # Различаем по верба: если был RETURN — значит результат
                    # просто пуст (None или []).
                    if st.verb in ("RETURN", "MATCH", "OPTIONAL", "WITH", "UNWIND"):
                        # Команды чтения — пустой результат это [].
                        last_result = []
                    else:
                        last_result = None
            return last_result
        finally:
            # Принципиально важно: откатываем транзакцию,
            # никаких commit'ов в песочнице не бывает.
            try:
                await tx.rollback()
            except Exception as exc:
                logger.warning("Failed to rollback Neo4j sandbox transaction: %s", exc)
