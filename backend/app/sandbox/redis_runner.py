"""Изолированная Redis-sandbox и выполнение пользовательских скриптов.

Архитектура изоляции
--------------------

Redis не имеет аналога MongoDB-баз с независимыми namespace'ами в полной
мере (есть только 16 нумерованных DB). Чтобы две одновременные проверки
не наступали друг другу, мы:

  1. Защищаем выполнение глобальным asyncio-локом (одна проверка за раз).
     Для нагрузки учебного симулятора (<10 одновременных Submit) это
     приемлемо и существенно проще пула DB или префиксации ключей.
  2. Перед каждой проверкой делаем FLUSHDB на нашей выделенной DB,
     чтобы артефакты прошлой проверки не повлияли.
  3. После проверки тоже делаем FLUSHDB — освобождаем память.

Структура fixture
-----------------

Для Redis fixture — это объект вида:

    {
      "preload": [
        "SET counter 5",
        "RPUSH queue task1 task2 task3",
        "HSET user:1 name Anna age 25"
      ]
    }

Команды preload выполняются перед запросом студента (без проверки
whitelist'а — это код преподавателя). Если preload пуст или отсутствует —
студент работает с чистой DB.

Возврат результата
------------------

Скрипт студента — последовательность команд. Возвращаем результат
ПОСЛЕДНЕЙ команды (как в MongoDB-курсе). Это позволяет использовать
`compare_to_any_reference` без изменений: эталон и решение студента
сравниваются по последнему значению.
"""
from __future__ import annotations

import asyncio
import logging
import time
from dataclasses import dataclass
from typing import Any

import redis.asyncio as aioredis
from redis.exceptions import RedisError, ResponseError

from app.sandbox.redis_parser import (
    ParsedCommand, RedisParseError, parse_redis_script,
)

logger = logging.getLogger(__name__)

QUERY_TIMEOUT_SEC = 5.0
SANDBOX_DB        = 0     # выделенный номер DB для песочницы
PRELOAD_TIMEOUT   = 5.0


# Один глобальный лок на весь модуль: гарантирует, что в каждый
# момент времени только одна проверка работает с песочницей.
# В FastAPI uvloop это валидно (один event loop на процесс).
_sandbox_lock = asyncio.Lock()


@dataclass
class ExecutionResult:
    """Результат выполнения скрипта (тот же контракт, что у mongo_runner)."""
    ok:          bool
    duration_ms: int
    result:      Any | None = None
    error:       str | None = None


# ---------- Нормализация ответа Redis ----------

def _normalize(value: Any) -> Any:
    """Приводит ответ redis-py к JSON-совместимому виду.

    redis-py отдаёт:
      - bytes для строк (если decode_responses=False) — мы делаем decode_responses=True,
        так что обычно строки уже как str
      - int для счётчиков
      - list для ZRANGE/LRANGE/HKEYS и т.п.
      - dict для HGETALL
      - set для SMEMBERS, SINTER и т.п.
      - None для несуществующих ключей
      - bool для команд типа EXISTS/EXPIRE (часто на самом деле int 0/1)

    Множества переводим в отсортированные списки — иначе сравнение
    SMEMBERS с эталоном будет нестабильным (порядок не определён).
    """
    if isinstance(value, set):
        # Сортируем для детерминированного сравнения.
        # Если элементы не сравнимы (mixed types) — упадём, и это правильно:
        # значит fixture/эталон неправильно подобран.
        try:
            return sorted(_normalize(v) for v in value)
        except TypeError:
            return [_normalize(v) for v in value]
    if isinstance(value, list):
        return [_normalize(v) for v in value]
    if isinstance(value, tuple):
        return [_normalize(v) for v in value]
    if isinstance(value, dict):
        return {str(k): _normalize(v) for k, v in value.items()}
    if isinstance(value, bytes):
        try:
            return value.decode("utf-8")
        except UnicodeDecodeError:
            return value.hex()
    return value


# ---------- Выполнение списка команд ----------

async def _run_commands(
    client:   aioredis.Redis,
    commands: list[ParsedCommand],
) -> Any:
    """Выполняет команды по очереди, возвращает результат последней."""
    last_result: Any = None
    for cmd in commands:
        try:
            # Низкоуровневый execute_command принимает имя и args.
            last_result = await client.execute_command(cmd.name, *cmd.args)
        except ResponseError as err:
            # Redis вернул ошибку — например, неправильный тип данных,
            # неправильное число аргументов и т.п. Включаем номер строки
            # в сообщение, чтобы студент быстро нашёл проблему.
            raise RedisError(f"Строка {cmd.line}: {err}") from err
    return last_result


async def execute_redis_script(
    redis_url:  str,
    fixture:    dict,
    query_text: str,
) -> ExecutionResult:
    """Выполняет скрипт студента в эфемерной Redis-DB.

    Совместим по сигнатуре/возврату с mongo_runner.execute_mql, чтобы
    диспатчер мог вызывать оба единообразно.
    """
    start = time.perf_counter()

    # 1. Парсим скрипт студента.
    try:
        commands = parse_redis_script(query_text)
    except RedisParseError as err:
        return ExecutionResult(
            ok=False,
            duration_ms=int((time.perf_counter() - start) * 1000),
            error=str(err),
        )

    # 2. Под локом захватываем песочницу.
    async with _sandbox_lock:
        client = aioredis.from_url(
            redis_url,
            db=SANDBOX_DB,
            decode_responses=True,         # ответы в str, а не bytes
            socket_connect_timeout=3.0,
            socket_timeout=QUERY_TIMEOUT_SEC,
        )
        try:
            # 3. Чистим DB.
            await client.flushdb()

            # 4. Заливаем preload.
            preload: list[str] = list(fixture.get("preload", []))
            if preload:
                try:
                    await asyncio.wait_for(
                        _run_preload(client, preload),
                        timeout=PRELOAD_TIMEOUT,
                    )
                except asyncio.TimeoutError:
                    return ExecutionResult(
                        ok=False,
                        duration_ms=int((time.perf_counter() - start) * 1000),
                        error="Превышено время загрузки fixture (бага в задании)",
                    )
                except (ResponseError, RedisError) as err:
                    # Ошибка в preload — это проблема задания, а не студента.
                    # Логируем, чтобы препод увидел.
                    logger.error("Preload failed: %s", err)
                    return ExecutionResult(
                        ok=False,
                        duration_ms=int((time.perf_counter() - start) * 1000),
                        error=f"Ошибка загрузки исходных данных: {err}",
                    )

            # 5. Выполняем скрипт студента.
            try:
                result = await asyncio.wait_for(
                    _run_commands(client, commands),
                    timeout=QUERY_TIMEOUT_SEC,
                )
            except asyncio.TimeoutError:
                return ExecutionResult(
                    ok=False,
                    duration_ms=int(QUERY_TIMEOUT_SEC * 1000),
                    error=f"Превышено время ожидания ({QUERY_TIMEOUT_SEC:.0f} сек)",
                )
            except RedisError as err:
                return ExecutionResult(
                    ok=False,
                    duration_ms=int((time.perf_counter() - start) * 1000),
                    error=str(err),
                )

            return ExecutionResult(
                ok=True,
                duration_ms=int((time.perf_counter() - start) * 1000),
                result=_normalize(result),
            )

        finally:
            # 6. Чистим за собой и закрываем соединение.
            try:
                await client.flushdb()
            except Exception as exc:
                logger.warning("Failed to flush sandbox: %s", exc)
            await client.aclose()


async def _run_preload(client: aioredis.Redis, preload: list[str]) -> None:
    """Выполняет команды preload без whitelist'а (это код преподавателя)."""
    for raw in preload:
        # Используем тот же shlex-токенизатор, что и для скрипта студента.
        import shlex
        try:
            tokens = shlex.split(raw, comments=True, posix=True)
        except ValueError as err:
            raise RedisError(f"Некорректный preload {raw!r}: {err}") from err
        if not tokens:
            continue
        await client.execute_command(*tokens)
