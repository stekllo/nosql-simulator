"""Парсер скрипта Redis-команд.

В отличие от MongoDB, у Redis нет сложного синтаксиса запросов: каждая
команда — это просто слово команды и пробельно-разделённые аргументы.
Поэтому парсер сводится к токенизации (с учётом кавычек) и валидации
имени команды против whitelist'а — чтобы студент не мог запустить
`FLUSHALL`, `CONFIG SET`, `SHUTDOWN`, `DEBUG`, `EVAL` и прочие опасные
команды, которые либо ломают песочницу, либо дают arbitrary code execution.

Ввод студента — многострочный скрипт. Каждая непустая строка
(после удаления комментариев `#`) разбирается как одна команда.
Результат парсинга — список `ParsedCommand` для последующего выполнения.
"""
from __future__ import annotations

import shlex
from dataclasses import dataclass


class RedisParseError(ValueError):
    """Не удалось разобрать скрипт студента."""


@dataclass
class ParsedCommand:
    """Одна разобранная Redis-команда: имя + аргументы."""
    name: str         # например, "SET"  (всегда в верхнем регистре)
    args: list[str]   # все аргументы как строки
    line: int         # номер строки в исходнике (для сообщений об ошибках)

    @property
    def as_args(self) -> list[str]:
        """Полный список для redis-py: [name, *args]."""
        return [self.name, *self.args]


# ---------- Whitelist разрешённых команд ----------
#
# Принцип: разрешено только то, что нужно для уроков курса.
# Всё остальное (CONFIG, EVAL, SCRIPT, DEBUG, SHUTDOWN, FLUSHALL, MIGRATE,
# REPLICAOF, MONITOR, CLIENT, ACL, MODULE, OBJECT, MEMORY, LATENCY,
# subscribe-команды) — запрещено.

ALLOWED_COMMANDS: frozenset[str] = frozenset({
    # Generic / служебные
    "DEL", "EXISTS", "EXPIRE", "PEXPIRE", "PERSIST", "TTL", "PTTL",
    "TYPE", "KEYS", "RENAME", "RENAMENX",

    # Strings
    "SET", "GET", "GETSET", "SETEX", "PSETEX", "SETNX", "MSET", "MSETNX",
    "MGET", "INCR", "DECR", "INCRBY", "DECRBY", "INCRBYFLOAT",
    "APPEND", "STRLEN", "GETRANGE", "SETRANGE",

    # Hashes
    "HSET", "HGET", "HGETALL", "HDEL", "HEXISTS", "HKEYS", "HVALS",
    "HINCRBY", "HINCRBYFLOAT", "HLEN", "HMGET", "HMSET", "HSETNX",

    # Lists
    "LPUSH", "RPUSH", "LPOP", "RPOP", "LRANGE", "LLEN", "LINDEX",
    "LREM", "LSET", "LINSERT", "LPUSHX", "RPUSHX", "LTRIM",

    # Sets
    "SADD", "SREM", "SMEMBERS", "SCARD", "SISMEMBER", "SMISMEMBER",
    "SINTER", "SUNION", "SDIFF", "SINTERSTORE", "SUNIONSTORE", "SDIFFSTORE",
    "SRANDMEMBER", "SPOP",

    # Sorted sets
    "ZADD", "ZRANGE", "ZRANGEBYSCORE", "ZREVRANGE", "ZREVRANGEBYSCORE",
    "ZRANK", "ZREVRANK", "ZSCORE", "ZINCRBY", "ZCARD", "ZREM",
    "ZCOUNT", "ZPOPMIN", "ZPOPMAX",
})

# Эти команды запрещены, но если студент их использует — даём
# понятную ошибку с подсказкой, а не «команда не найдена».
EXPLICITLY_BLOCKED: frozenset[str] = frozenset({
    "FLUSHALL", "FLUSHDB", "CONFIG", "EVAL", "EVALSHA", "SCRIPT",
    "DEBUG", "SHUTDOWN", "SAVE", "BGSAVE", "BGREWRITEAOF", "MIGRATE",
    "REPLICAOF", "SLAVEOF", "MONITOR", "CLIENT", "ACL", "MODULE",
    "OBJECT", "MEMORY", "LATENCY", "WAIT", "FAILOVER",
    "SUBSCRIBE", "UNSUBSCRIBE", "PSUBSCRIBE", "PUNSUBSCRIBE", "PUBLISH",
    "MULTI", "EXEC", "DISCARD", "WATCH", "UNWATCH",  # транзакции — отдельная тема
    "XADD", "XREAD", "XRANGE",  # streams — не в курсе
})


def parse_redis_script(text: str) -> list[ParsedCommand]:
    """Разбирает многострочный скрипт студента в список команд.

    Правила:
      - Пустые строки и строки, начинающиеся с `#`, игнорируются.
      - В конце строки `# комментарий` отбрасывается (если # вне кавычек).
      - Аргументы разделяются пробелами; для строк с пробелами —
        двойные или одинарные кавычки.
      - Имя команды нечувствительно к регистру (нормализуется в UPPER).

    Бросает RedisParseError при первой синтаксической или логической
    ошибке (неизвестная команда, незакрытая кавычка и т.д.).
    """
    if not text or not text.strip():
        raise RedisParseError("Скрипт пуст — введите хотя бы одну команду")

    commands: list[ParsedCommand] = []

    for lineno, raw in enumerate(text.splitlines(), start=1):
        line = raw.strip()
        if not line or line.startswith("#"):
            continue

        # Используем shlex для разбиения с учётом кавычек.
        # posix=True — стандартное поведение шелла: кавычки убираются,
        # экранирование `\` работает.  comments=True — обрабатывать `#`
        # как начало комментария (если вне кавычек).
        try:
            tokens = shlex.split(line, comments=True, posix=True)
        except ValueError as err:
            # shlex кидает ValueError на незакрытых кавычках.
            raise RedisParseError(
                f"Строка {lineno}: ошибка разбора кавычек ({err})"
            ) from err

        if not tokens:
            # Строка состояла только из комментария.
            continue

        cmd_name = tokens[0].upper()
        cmd_args = tokens[1:]

        if cmd_name in EXPLICITLY_BLOCKED:
            raise RedisParseError(
                f"Строка {lineno}: команда {cmd_name!r} запрещена в песочнице. "
                f"Эта команда либо ломает изоляцию, либо относится к темам, "
                f"которые не входят в этот курс."
            )

        if cmd_name not in ALLOWED_COMMANDS:
            raise RedisParseError(
                f"Строка {lineno}: неизвестная команда {cmd_name!r}. "
                f"Список поддерживаемых команд — в шпаргалке к курсу."
            )

        commands.append(ParsedCommand(name=cmd_name, args=cmd_args, line=lineno))

    if not commands:
        raise RedisParseError(
            "В скрипте нет ни одной команды (только пустые строки или комментарии)"
        )

    return commands
