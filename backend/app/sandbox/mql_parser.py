"""Парсер MongoDB Query Language (MQL).

Разбирает строку вида `db.orders.aggregate([...])` на структуру,
которую можно выполнить через Motor.

Поддерживаемые методы: find, findOne, aggregate, count, countDocuments,
distinct, insertOne, insertMany, updateOne, updateMany, deleteOne,
deleteMany.

JSON-like синтаксис MongoDB отличается от строгого JSON: ключи могут
быть без кавычек, строки в одинарных кавычках, присутствуют комментарии.
Перед парсингом нормализуем синтаксис.
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Any


class MQLParseError(ValueError):
    """Не удалось разобрать запрос студента."""


# ---------- Список разрешённых методов ----------

READ_ONLY_METHODS = frozenset({
    "find", "findOne", "aggregate", "count", "countDocuments",
    "estimatedDocumentCount", "distinct",
})

WRITE_METHODS = frozenset({
    "insertOne", "insertMany",
    "updateOne", "updateMany", "replaceOne",
    "deleteOne", "deleteMany",
})

ALLOWED_METHODS = READ_ONLY_METHODS | WRITE_METHODS

# Потенциально опасные токены, которые мы никогда не пропустим.
FORBIDDEN_TOKENS = (
    "dropDatabase", "dropIndex", "drop(",
    "$where", "$function", "$accumulator",
    "mapReduce", "eval(", "shutdown",
    "createUser", "createRole", "grantPrivilege",
)


# ---------- Результат парсинга ----------

@dataclass
class ParsedQuery:
    collection: str
    method:     str
    args:       list[Any]


# ---------- Нормализация MQL → валидный JSON ----------

def _strip_comments(text: str) -> str:
    """Удаляет комментарии // и /* */ из запроса."""
    # Многострочные /* ... */
    text = re.sub(r"/\*.*?\*/", " ", text, flags=re.DOTALL)
    # Однострочные // до конца строки
    text = re.sub(r"//[^\n]*", " ", text)
    return text


def _normalize_to_json(mql: str) -> str:
    """Превращает JS-подобный MQL-литерал в валидный JSON.

    Шаги:
    1. Одинарные кавычки → двойные.
    2. Неэкранированные ключи `{foo: ...}` → `{"foo": ...}`.
    3. `ObjectId("...")` и `ISODate("...")` → строки-placeholders
       (для диплома достаточно; продвинутая семантика не требуется).
    """
    s = mql

    # Заменяем ObjectId("...") на строки.
    s = re.sub(r"ObjectId\(\s*(['\"])(.*?)\1\s*\)",  r'"\2"', s)
    s = re.sub(r"ISODate\(\s*(['\"])(.*?)\1\s*\)",   r'"\2"', s)
    s = re.sub(r"NumberLong\(\s*(\d+)\s*\)",         r"\1",   s)
    s = re.sub(r"NumberInt\(\s*(-?\d+)\s*\)",        r"\1",   s)

    # Одинарные кавычки → двойные (осторожно со строками).
    # Простой замены достаточно для диплома, edge cases с ' внутри строк
    # встречаются крайне редко в учебных задачах.
    s = re.sub(r"'([^'\\]*(?:\\.[^'\\]*)*)'", r'"\1"', s)

    # Ключи без кавычек: { foo: 1 } → { "foo": 1 }
    # Работает для буквенно-цифровых ключей + $-операторов.
    s = re.sub(
        r"([\{,]\s*)([A-Za-z_$][A-Za-z_0-9$]*)\s*:",
        r'\1"\2":',
        s,
    )

    # Удаляем trailing commas, которые JavaScript допускает, а JSON нет.
    s = re.sub(r",(\s*[\]\}])", r"\1", s)

    return s


def _parse_args(args_src: str) -> list[Any]:
    """Парсит содержимое скобок вызова метода.

    Принимает строку `{...}, {...}, {...}` и возвращает список
    распарсенных python-объектов.
    """
    args_src = args_src.strip()
    if not args_src:
        return []

    # Оборачиваем в массив, чтобы JSON-парсер съел весь список целиком.
    wrapped = "[" + args_src + "]"
    try:
        return json.loads(wrapped)
    except json.JSONDecodeError as err:
        raise MQLParseError(f"Не удалось разобрать аргументы: {err.msg}") from err


# ---------- Главная функция ----------

# Регексп верхнего уровня: db.<collection>.<method>(<args>)
_CALL_RE = re.compile(
    r"""
    ^\s*
    db\.
    ([A-Za-z_][A-Za-z_0-9]*)   # имя коллекции
    \.
    ([A-Za-z][A-Za-z0-9]*)     # имя метода
    \s*\(                      # открывающая скобка
    (?P<args>.*)               # всё, что внутри (балансировку скобок делаем вручную)
    \)                         # закрывающая скобка
    \s*;?\s*$
    """,
    re.VERBOSE | re.DOTALL,
)


def parse_mql(query: str) -> ParsedQuery:
    """Преобразует строку MQL в структурированный вызов.

    Бросает MQLParseError, если запрос:
    - синтаксически некорректен,
    - использует неподдерживаемый метод,
    - содержит запрещённые токены.
    """
    if not query or not query.strip():
        raise MQLParseError("Пустой запрос")

    # Проверка на опасные токены.
    for token in FORBIDDEN_TOKENS:
        if token in query:
            raise MQLParseError(f"Запрещённая операция: {token!r}")

    cleaned = _strip_comments(query)
    match   = _CALL_RE.match(cleaned)
    if not match:
        raise MQLParseError(
            "Ожидается вызов вида db.<коллекция>.<метод>(...). "
            "Проверьте синтаксис."
        )

    collection = match.group(1)
    method     = match.group(2)
    args_src   = match.group("args")

    if method not in ALLOWED_METHODS:
        raise MQLParseError(
            f"Метод {method!r} не поддерживается. "
            f"Доступны: {', '.join(sorted(ALLOWED_METHODS))}"
        )

    normalized = _normalize_to_json(args_src)
    args       = _parse_args(normalized)

    return ParsedQuery(collection=collection, method=method, args=args)
