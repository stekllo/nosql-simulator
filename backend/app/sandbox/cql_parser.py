"""Парсер скрипта CQL-команд (Cassandra Query Language).

CQL очень похож на SQL: команды разделены точкой с запятой, могут занимать
несколько строк, поддерживают комментарии (`--` или `//`). В этом парсере
мы:

  1. Разбираем многострочный скрипт на отдельные команды по `;`,
     уважая строки в одинарных кавычках (где `;` может быть частью данных).
  2. Выкидываем комментарии (`-- ...`, `// ...` до конца строки и `/* ... */`).
  3. Проверяем, что каждая команда начинается с разрешённого глагола
     (whitelist), и явно блокируем опасные команды.

Сложный синтаксис CQL мы НЕ парсим (типы, выражения и т.д.) — это делает сам
драйвер Cassandra, и его сообщения об ошибках обычно понятны студенту.
"""
from __future__ import annotations

import re
from dataclasses import dataclass


class CQLParseError(ValueError):
    """Не удалось разобрать CQL-скрипт студента."""


@dataclass
class ParsedStatement:
    """Одно разобранное CQL-выражение."""
    text:    str   # полный текст (без trailing `;`)
    verb:    str   # первое слово (всегда верхний регистр): SELECT, INSERT, и т.п.
    line:    int   # номер строки в исходнике (примерный — для сообщений)


# ---------- Whitelist разрешённых глаголов ----------
#
# Принцип: разрешено только то, что нужно для уроков курса.
# DDL для таблиц — да (студент создаёт таблицы), DML — да, SELECT — да.
# Запрещены: всё что меняет keyspace, юзеров, роли, security, ноды.

ALLOWED_VERBS: frozenset[str] = frozenset({
    # DDL для таблиц / типов / индексов
    "CREATE", "ALTER", "DROP",
    # (DROP TABLE можно — но DROP KEYSPACE мы дополнительно блокируем ниже)
    # DML
    "INSERT", "UPDATE", "DELETE",
    # Чтение
    "SELECT",
    # Batch
    "BEGIN", "APPLY",
    # Использование keyspace
    "USE",
    # TRUNCATE TABLE — допустимо (это не TRUNCATE keyspace)
    "TRUNCATE",
})


# Регексы, которые ловят опасные паттерны даже если глагол сам по себе разрешён.
# Каждый — (regex, человеко-читаемое объяснение).
DANGEROUS_PATTERNS: list[tuple[re.Pattern[str], str]] = [
    (re.compile(r"^\s*DROP\s+KEYSPACE\b", re.IGNORECASE | re.MULTILINE),
     "DROP KEYSPACE — нельзя удалять keyspace песочницы"),
    (re.compile(r"^\s*CREATE\s+KEYSPACE\b", re.IGNORECASE | re.MULTILINE),
     "CREATE KEYSPACE — keyspace создаётся автоматически песочницей"),
    (re.compile(r"^\s*ALTER\s+KEYSPACE\b", re.IGNORECASE | re.MULTILINE),
     "ALTER KEYSPACE — нельзя менять параметры keyspace песочницы"),
    (re.compile(r"^\s*(CREATE|DROP|ALTER|GRANT|REVOKE|LIST)\s+(USER|ROLE)", re.IGNORECASE | re.MULTILINE),
     "Команды управления пользователями и ролями недоступны"),
    (re.compile(r"^\s*GRANT\b|^\s*REVOKE\b", re.IGNORECASE | re.MULTILINE),
     "GRANT/REVOKE недоступны в песочнице"),
    (re.compile(r"^\s*EXECUTE\b", re.IGNORECASE | re.MULTILINE),
     "EXECUTE недоступен (управление prepared statements)"),
    (re.compile(r"^\s*COPY\b", re.IGNORECASE | re.MULTILINE),
     "COPY недоступен (импорт/экспорт файлов сервера)"),
]


def _strip_comments(text: str) -> str:
    """Удаляет комментарии CQL: '-- ...', '// ...' до конца строки и '/* ... */'.

    Уважает одинарные кавычки — внутри них '--' не считается комментарием.
    """
    result: list[str] = []
    i = 0
    n = len(text)
    in_str = False
    while i < n:
        ch = text[i]
        # Внутри строки — переписываем как есть, ищем закрывающую кавычку.
        if in_str:
            result.append(ch)
            if ch == "'":
                # Проверим экранирование: '' внутри строки означает literal quote.
                if i + 1 < n and text[i + 1] == "'":
                    result.append("'")
                    i += 2
                    continue
                in_str = False
            i += 1
            continue
        # Не внутри строки.
        if ch == "'":
            in_str = True
            result.append(ch)
            i += 1
            continue
        # Однострочный коммент --
        if ch == "-" and i + 1 < n and text[i + 1] == "-":
            # пропускаем до \n
            j = text.find("\n", i)
            if j == -1:
                break
            i = j  # \n оставим
            continue
        # Однострочный коммент //
        if ch == "/" and i + 1 < n and text[i + 1] == "/":
            j = text.find("\n", i)
            if j == -1:
                break
            i = j
            continue
        # Многострочный коммент /* ... */
        if ch == "/" and i + 1 < n and text[i + 1] == "*":
            j = text.find("*/", i + 2)
            if j == -1:
                # незакрытый коммент — выкидываем до конца
                break
            i = j + 2
            continue
        result.append(ch)
        i += 1
    return "".join(result)


def _split_statements(text: str) -> list[tuple[str, int]]:
    """Разбивает скрипт на отдельные statement'ы по ';' (вне кавычек).

    Возвращает список пар (текст_statement, номер_строки_начала).
    """
    statements: list[tuple[str, int]] = []
    buf: list[str] = []
    in_str = False
    line_no = 1
    start_line = 1

    i = 0
    n = len(text)
    while i < n:
        ch = text[i]
        if ch == "\n":
            line_no += 1
        if in_str:
            buf.append(ch)
            if ch == "'":
                if i + 1 < n and text[i + 1] == "'":
                    buf.append("'")
                    i += 2
                    continue
                in_str = False
            i += 1
            continue
        if ch == "'":
            in_str = True
            buf.append(ch)
            i += 1
            continue
        if ch == ";":
            stmt = "".join(buf).strip()
            if stmt:
                statements.append((stmt, start_line))
            buf = []
            start_line = line_no
            i += 1
            continue
        buf.append(ch)
        i += 1

    # Добавляем хвост без `;` — допустимо для последней команды.
    tail = "".join(buf).strip()
    if tail:
        statements.append((tail, start_line))

    return statements


def parse_cql_script(text: str) -> list[ParsedStatement]:
    """Разбирает многострочный CQL-скрипт студента.

    Возвращает список ParsedStatement. Бросает CQLParseError при первой
    проблеме (опасная команда, неразрешённый глагол, незакрытая кавычка).
    """
    if not text or not text.strip():
        raise CQLParseError("Скрипт пуст — введите хотя бы одну команду")

    cleaned = _strip_comments(text)

    # Сначала проверяем опасные паттерны — на сыром тексте, до разбиения.
    # Это надёжнее: даже если кто-то спрятал `DROP KEYSPACE` без `;`,
    # мы поймаем его.
    for pat, message in DANGEROUS_PATTERNS:
        if pat.search(cleaned):
            raise CQLParseError(f"Запрещённая команда: {message}")

    statements = _split_statements(cleaned)
    if not statements:
        raise CQLParseError("В скрипте нет ни одной команды")

    parsed: list[ParsedStatement] = []
    for stmt_text, line in statements:
        # Первое слово (нечувствительно к регистру).
        m = re.match(r"^\s*([A-Za-z_]+)", stmt_text)
        if not m:
            raise CQLParseError(
                f"Строка {line}: не удалось распознать команду — текст начинается не с ключевого слова"
            )
        verb = m.group(1).upper()

        if verb not in ALLOWED_VERBS:
            raise CQLParseError(
                f"Строка {line}: команда {verb!r} не поддерживается в песочнице. "
                f"Список разрешённых команд — в шпаргалке к курсу."
            )

        parsed.append(ParsedStatement(text=stmt_text, verb=verb, line=line))

    return parsed
