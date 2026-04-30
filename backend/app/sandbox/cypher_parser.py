"""Парсер скрипта Cypher-команд для Neo4j-песочницы.

Cypher похож на SQL: команды разделяются `;`, поддерживают комментарии `//`
и `/* */`. Этот парсер:

  1. Разбивает скрипт на отдельные команды по `;`, уважая строки в кавычках.
  2. Удаляет комментарии (`//` до конца строки и `/* ... */`).
  3. Проверяет, что каждая команда начинается с разрешённого глагола
     (whitelist), и блокирует опасные команды.

Сложный синтаксис Cypher (паттерны узлов/связей, выражения и т.п.) парсит сам
драйвер Neo4j — его сообщения об ошибках обычно достаточно понятны студенту.
"""
from __future__ import annotations

import re
from dataclasses import dataclass


class CypherParseError(ValueError):
    """Не удалось разобрать Cypher-скрипт студента."""


@dataclass
class ParsedCypherStatement:
    """Одно разобранное Cypher-выражение."""
    text: str   # полный текст (без trailing `;`)
    verb: str   # первое слово (всегда верхний регистр): MATCH, CREATE и т.п.
    line: int   # номер строки в исходнике (для сообщений об ошибках)


# ---------- Whitelist разрешённых стартовых слов ----------
#
# Принцип: разрешено только то, что нужно для уроков курса.
# CRUD над узлами/связями, чтение, агрегации.
# Запрещено: всё, что меняет схему БД, плагины, файловые операции.

ALLOWED_VERBS: frozenset[str] = frozenset({
    # CRUD
    "CREATE", "MATCH", "MERGE", "SET", "DELETE", "REMOVE",
    # Чтение и агрегация
    "RETURN", "WITH", "UNWIND", "OPTIONAL",
    # USE — выбор БД (на Community нет multi-db, но синтаксически безвреден)
    "USE",
    # Параметры запроса (для будущих расширений)
    "PROFILE", "EXPLAIN",
})


# Паттерны опасных команд — ловим даже если глагол сам по себе разрешён.
DANGEROUS_PATTERNS: list[tuple[re.Pattern[str], str]] = [
    # Изменение схемы БД
    (re.compile(r"\bCREATE\s+(DATABASE|USER|ROLE|INDEX|CONSTRAINT|FULLTEXT|LOOKUP|POINT|RANGE)\b", re.IGNORECASE),
     "Команды управления базами/пользователями/индексами недоступны в песочнице"),
    (re.compile(r"\bDROP\s+(DATABASE|USER|ROLE|INDEX|CONSTRAINT)\b", re.IGNORECASE),
     "Команды DROP DATABASE/USER/ROLE/INDEX/CONSTRAINT недоступны"),
    (re.compile(r"\bALTER\s+(DATABASE|USER|ROLE)\b", re.IGNORECASE),
     "Команды ALTER DATABASE/USER/ROLE недоступны"),
    (re.compile(r"\bSHOW\s+(USERS|ROLES|DATABASES|PRIVILEGES)\b", re.IGNORECASE),
     "Команды SHOW USERS/ROLES/DATABASES недоступны"),
    (re.compile(r"\bGRANT\b|\bREVOKE\b|\bDENY\b", re.IGNORECASE),
     "GRANT/REVOKE/DENY недоступны в песочнице"),
    # Загрузка из файлов и плагинов
    (re.compile(r"\bLOAD\s+CSV\b", re.IGNORECASE),
     "LOAD CSV недоступен (загрузка файлов сервера)"),
    (re.compile(r"\bCALL\s+apoc\.", re.IGNORECASE),
     "Процедуры APOC недоступны в учебной песочнице"),
    (re.compile(r"\bCALL\s+db\.(create|drop|index|constraint)", re.IGNORECASE),
     "Изменение схемы через db.* недоступно"),
    (re.compile(r"\bCALL\s+dbms\.", re.IGNORECASE),
     "Управление сервером через dbms.* недоступно"),
    # Изменение настроек
    (re.compile(r"\bCALL\s+(.+?\.shutdown|.+?\.killTransaction)", re.IGNORECASE),
     "Управление транзакциями/процессом недоступно"),
]


def _strip_comments(text: str) -> str:
    """Удаляет комментарии Cypher: '// ...' до конца строки и '/* ... */'.

    Уважает кавычки — внутри них '//' не считается комментарием.
    Cypher поддерживает и одинарные, и двойные кавычки для строк.
    """
    result: list[str] = []
    i = 0
    n = len(text)
    in_str: str | None = None  # None или символ кавычки ('", '")

    while i < n:
        ch = text[i]
        if in_str:
            result.append(ch)
            # Экранирование внутри строки: \"  \'  \\
            if ch == "\\" and i + 1 < n:
                result.append(text[i + 1])
                i += 2
                continue
            if ch == in_str:
                in_str = None
            i += 1
            continue
        # Не в строке.
        if ch in ("'", '"'):
            in_str = ch
            result.append(ch)
            i += 1
            continue
        # Однострочный коммент //
        if ch == "/" and i + 1 < n and text[i + 1] == "/":
            j = text.find("\n", i)
            if j == -1:
                break
            i = j   # \n оставляем
            continue
        # Многострочный коммент /* ... */
        if ch == "/" and i + 1 < n and text[i + 1] == "*":
            j = text.find("*/", i + 2)
            if j == -1:
                break
            i = j + 2
            continue
        result.append(ch)
        i += 1
    return "".join(result)


def _split_statements(text: str) -> list[tuple[str, int]]:
    """Разбивает скрипт на отдельные statement'ы по `;` (вне кавычек).

    Возвращает (текст, номер_строки_начала).
    """
    statements: list[tuple[str, int]] = []
    buf: list[str] = []
    in_str: str | None = None
    line_no   = 1
    start_line = 1

    i = 0
    n = len(text)
    while i < n:
        ch = text[i]
        if ch == "\n":
            line_no += 1
        if in_str:
            buf.append(ch)
            if ch == "\\" and i + 1 < n:
                buf.append(text[i + 1])
                i += 2
                continue
            if ch == in_str:
                in_str = None
            i += 1
            continue
        if ch in ("'", '"'):
            in_str = ch
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

    tail = "".join(buf).strip()
    if tail:
        statements.append((tail, start_line))

    return statements


def parse_cypher_script(text: str) -> list[ParsedCypherStatement]:
    """Разбирает многострочный Cypher-скрипт студента.

    Возвращает список ParsedCypherStatement. Бросает CypherParseError при первой
    проблеме (опасная команда, неразрешённый глагол).
    """
    if not text or not text.strip():
        raise CypherParseError("Скрипт пуст — введите хотя бы одну команду")

    cleaned = _strip_comments(text)

    # Опасные паттерны — на сыром тексте, до разбиения по `;`.
    for pat, message in DANGEROUS_PATTERNS:
        if pat.search(cleaned):
            raise CypherParseError(f"Запрещённая команда: {message}")

    statements = _split_statements(cleaned)
    if not statements:
        raise CypherParseError("В скрипте нет ни одной команды")

    parsed: list[ParsedCypherStatement] = []
    for stmt_text, line in statements:
        # Первое слово (нечувствительно к регистру).
        m = re.match(r"^\s*([A-Za-z_]+)", stmt_text)
        if not m:
            raise CypherParseError(
                f"Строка {line}: не удалось распознать команду — "
                "текст начинается не с ключевого слова"
            )
        verb = m.group(1).upper()

        if verb not in ALLOWED_VERBS:
            raise CypherParseError(
                f"Строка {line}: команда {verb!r} не поддерживается в песочнице. "
                "Список разрешённых команд — в шпаргалке к курсу."
            )

        parsed.append(ParsedCypherStatement(text=stmt_text, verb=verb, line=line))

    return parsed
