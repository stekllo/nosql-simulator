"""Изолированная Cassandra-sandbox и выполнение CQL-скриптов студента.

Архитектура изоляции
--------------------

В отличие от Redis (где DB всего одна и приходится сериализовать через лок),
у Cassandra есть **keyspace** — полноценный namespace для таблиц. Поэтому
каждая проверка получает свой свежий keyspace `sandbox_<uuid>`, а в `finally`
он удаляется (`DROP KEYSPACE`). Это даёт настоящую параллельную изоляцию —
несколько студентов могут проверять решения одновременно.

Структура fixture
-----------------

Для Cassandra fixture — это объект вида:

    {
      "preload": [
        "CREATE TABLE users (id int PRIMARY KEY, name text);",
        "INSERT INTO users (id, name) VALUES (1, 'Anna');",
        "INSERT INTO users (id, name) VALUES (2, 'Bob');"
      ]
    }

Команды preload выполняются перед скриптом студента (без проверки whitelist —
это код преподавателя). Перед preload автоматически создаётся keyspace и
выполняется `USE <keyspace>`, поэтому в preload писать `CREATE KEYSPACE` или
`USE` не нужно.

Возврат результата
------------------

Возвращается результат **последнего** statement'а. Для SELECT это список
строк (каждая — dict {column_name: value}). Для INSERT/UPDATE/DELETE/CREATE/
DROP/USE — None (CQL не возвращает данные у write-команд).

Структуры данных Cassandra (set, list, map, UUID, timestamp, decimal) приводятся
в JSON-совместимый вид для сравнения с эталоном:
  - set      → отсортированный list (если элементы сравнимы)
  - frozenset → то же
  - UUID     → str
  - datetime → ISO-строка
  - Decimal  → str (точность не теряется)
  - bytes    → hex-строка
"""
from __future__ import annotations

import asyncio
import logging
import time
import uuid
from dataclasses import dataclass
from datetime import date, datetime, time as dtime
from decimal import Decimal
from typing import Any

from cassandra.cluster import Cluster
from cassandra.query import SimpleStatement
from cassandra import InvalidRequest, OperationTimedOut
# cassandra-driver возвращает свои собственные коллекционные классы для CQL-типов
# set<>, list<>, map<> — они НЕ наследуются от стандартных set/list/dict, поэтому
# их приходится распознавать явно. Иначе Pydantic упадёт на сериализации ответа.
from cassandra.util import SortedSet, OrderedMap, OrderedMapSerializedKey

from app.sandbox.cql_parser import (
    CQLParseError, ParsedStatement, parse_cql_script,
)

logger = logging.getLogger(__name__)

QUERY_TIMEOUT_SEC = 10.0
PRELOAD_TIMEOUT   = 10.0


@dataclass
class ExecutionResult:
    """Тот же контракт, что у mongo_runner / redis_runner."""
    ok:          bool
    duration_ms: int
    result:      Any | None = None
    error:       str | None = None


# ---------- Нормализация значений для сравнения ----------

def _normalize(value: Any) -> Any:
    """Приводит значения Cassandra к JSON-совместимому виду.

    Cassandra возвращает Python-объекты разных типов (UUID, datetime, Decimal,
    set, list, dict). Чтобы compare_to_any_reference нормально сработал,
    приводим всё к строкам/числам/спискам/dict.

    Особенность: cassandra-driver возвращает CQL-коллекции в виде своих
    собственных классов из cassandra.util:
      - set<T>     → SortedSet (НЕ наследник set!)
      - map<K,V>   → OrderedMap / OrderedMapSerializedKey (НЕ наследники dict!)
      - list<T>    → list (стандартный)
    Эти классы Pydantic не умеет сериализовать, поэтому распознаём их первыми.
    """
    if value is None:
        return None
    # ---- Cassandra-специфичные коллекции (проверять ДО стандартных) ----
    # SortedSet → отсортированный list (детерминированное сравнение).
    if isinstance(value, SortedSet):
        try:
            return sorted(_normalize(v) for v in value)
        except TypeError:
            return [_normalize(v) for v in value]
    # OrderedMap → dict (порядок ключей сохраняем как есть).
    if isinstance(value, (OrderedMap, OrderedMapSerializedKey)):
        return {str(_normalize(k)): _normalize(v) for k, v in value.items()}
    # ---- Стандартные Python-типы ----
    # Множества → отсортированные списки (детерминированное сравнение).
    if isinstance(value, (set, frozenset)):
        try:
            return sorted(_normalize(v) for v in value)
        except TypeError:
            return [_normalize(v) for v in value]
    if isinstance(value, list):
        return [_normalize(v) for v in value]
    if isinstance(value, tuple):
        return [_normalize(v) for v in value]
    if isinstance(value, dict):
        return {str(_normalize(k)): _normalize(v) for k, v in value.items()}
    if isinstance(value, uuid.UUID):
        return str(value)
    if isinstance(value, (datetime, date, dtime)):
        return value.isoformat()
    if isinstance(value, Decimal):
        # Decimal как строка — точность сохраняется.
        return str(value)
    if isinstance(value, bytes):
        try:
            return value.decode("utf-8")
        except UnicodeDecodeError:
            return value.hex()
    return value


def _row_to_dict(row: Any) -> dict[str, Any]:
    """Преобразует cassandra-driver Row (named-tuple-like) в обычный dict."""
    if hasattr(row, "_asdict"):
        return {k: _normalize(v) for k, v in row._asdict().items()}
    if hasattr(row, "_fields"):
        return {k: _normalize(getattr(row, k)) for k in row._fields}
    # Fallback — пробуем как dict.
    if isinstance(row, dict):
        return {k: _normalize(v) for k, v in row.items()}
    return {"value": _normalize(row)}


# ---------- Выполнение скрипта ----------

def _execute_sync(
    cluster_hosts: list[str],
    cluster_port:  int,
    keyspace:      str,
    preload:       list[str],
    statements:    list[ParsedStatement],
) -> Any:
    """Синхронное выполнение в отдельном потоке.

    cassandra-driver не имеет async API, поэтому делаем blocking-вызовы и
    оборачиваем функцию в asyncio.to_thread. Все операции с keyspace (создание,
    USE, DROP) происходят здесь же, чтобы был один цикл подключения.

    Возвращает результат последней команды студента, либо бросает исключение.
    """
    cluster = Cluster(cluster_hosts, port=cluster_port, connect_timeout=5)
    session = cluster.connect()
    try:
        # 1. Создаём keyspace песочницы.
        session.execute(
            f"CREATE KEYSPACE {keyspace} "
            f"WITH REPLICATION = {{'class': 'SimpleStrategy', 'replication_factor': 1}}"
        )
        session.set_keyspace(keyspace)

        # 2. Preload.
        for raw in preload:
            stmt = raw.strip().rstrip(";").strip()
            if not stmt:
                continue
            session.execute(SimpleStatement(stmt, fetch_size=None))

        # 3. Скрипт студента — последовательно.
        last_result: Any = None
        for st in statements:
            try:
                result_set = session.execute(SimpleStatement(st.text, fetch_size=None))
            except InvalidRequest as err:
                # Включаем номер строки в ошибку — студенту так понятнее.
                raise InvalidRequest(f"Строка {st.line}: {err}") from err
            # Если это SELECT (или вообще запрос с результатом) — собираем строки.
            if result_set is not None:
                rows = list(result_set)
                if rows:
                    last_result = [_row_to_dict(r) for r in rows]
                else:
                    # SELECT который ничего не вернул → пустой список.
                    # Команды без результата (INSERT/UPDATE/DELETE/...) тоже
                    # дают пустой ResultSet — приходится различать по verb.
                    if st.verb == "SELECT":
                        last_result = []
                    else:
                        last_result = None
            else:
                last_result = None
        return last_result
    finally:
        # 4. Чистим за собой.
        try:
            session.execute(f"DROP KEYSPACE IF EXISTS {keyspace}")
        except Exception as exc:
            logger.warning("Failed to drop sandbox keyspace %s: %s", keyspace, exc)
        try:
            cluster.shutdown()
        except Exception:
            pass


async def execute_cql_script(
    cluster_hosts: list[str],
    cluster_port:  int,
    fixture:       dict,
    query_text:    str,
) -> ExecutionResult:
    """Выполняет CQL-скрипт студента в свежем keyspace.

    Совместим по контракту с mongo_runner.execute_mql и
    redis_runner.execute_redis_script.
    """
    start = time.perf_counter()

    # 1. Парсим.
    try:
        statements = parse_cql_script(query_text)
    except CQLParseError as err:
        return ExecutionResult(
            ok=False,
            duration_ms=int((time.perf_counter() - start) * 1000),
            error=str(err),
        )

    # 2. Уникальный keyspace.
    # Cassandra требует, чтобы имя keyspace начиналось с буквы и состояло из
    # alphanumeric+underscore. uuid.hex даёт alphanumeric, добавляем префикс.
    ks_name = f"sandbox_{uuid.uuid4().hex[:24]}"

    preload: list[str] = list(fixture.get("preload", []))

    try:
        result = await asyncio.wait_for(
            asyncio.to_thread(
                _execute_sync,
                cluster_hosts, cluster_port, ks_name, preload, statements,
            ),
            timeout=QUERY_TIMEOUT_SEC + PRELOAD_TIMEOUT,
        )
    except asyncio.TimeoutError:
        return ExecutionResult(
            ok=False,
            duration_ms=int((QUERY_TIMEOUT_SEC + PRELOAD_TIMEOUT) * 1000),
            error=f"Превышено время ожидания (~{int(QUERY_TIMEOUT_SEC + PRELOAD_TIMEOUT)} сек)",
        )
    except InvalidRequest as err:
        return ExecutionResult(
            ok=False,
            duration_ms=int((time.perf_counter() - start) * 1000),
            error=f"Ошибка Cassandra: {err}",
        )
    except OperationTimedOut as err:
        return ExecutionResult(
            ok=False,
            duration_ms=int((time.perf_counter() - start) * 1000),
            error=f"Cassandra timeout: {err}",
        )
    except Exception as err:
        # Любая другая cassandra-driver ошибка — отдаём студенту как есть.
        logger.exception("CQL execution error")
        return ExecutionResult(
            ok=False,
            duration_ms=int((time.perf_counter() - start) * 1000),
            error=f"{type(err).__name__}: {err}",
        )

    return ExecutionResult(
        ok=True,
        duration_ms=int((time.perf_counter() - start) * 1000),
        result=_normalize(result),
    )
