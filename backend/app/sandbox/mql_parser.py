"""Парсер MongoDB Query Language (MQL).

Разбирает строку вида `db.orders.aggregate([...])` на структуру,
которую можно выполнить через Motor. Также поддерживает chain:

    db.users.find({...}).sort({...}).limit(5)

Цепочечные `.sort(...)`, `.limit(...)`, `.skip(...)`, `.project(...)`
собираются как modifiers у главного вызова.

Поддерживаемые главные методы: find, findOne, aggregate, count,
countDocuments, distinct, insertOne, insertMany, updateOne,
updateMany, deleteOne, deleteMany.

JSON-like синтаксис MongoDB отличается от строгого JSON: ключи могут
быть без кавычек, строки в одинарных кавычках, присутствуют комментарии.
Перед парсингом нормализуем синтаксис.
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from typing import Any


class MQLParseError(ValueError):
    """Не удалось разобрать запрос студента."""


# ---------- Разрешённые методы ----------

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

# Cursor-модификаторы — разрешены ТОЛЬКО после find().
CURSOR_MODIFIERS = frozenset({"sort", "limit", "skip", "project"})

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
    modifiers:  list[tuple[str, list[Any]]] = field(default_factory=list)


# ---------- Чистка комментариев ----------

def _strip_comments(text: str) -> str:
    text = re.sub(r"/\*.*?\*/", " ", text, flags=re.DOTALL)
    text = re.sub(r"//[^\n]*",  " ", text)
    return text


# ---------- Нормализация JS-литерала → JSON ----------

def _normalize_to_json(mql: str) -> str:
    s = mql
    s = re.sub(r"ObjectId\(\s*(['\"])(.*?)\1\s*\)",  r'"\2"', s)
    s = re.sub(r"ISODate\(\s*(['\"])(.*?)\1\s*\)",   r'"\2"', s)
    s = re.sub(r"NumberLong\(\s*(\d+)\s*\)",         r"\1",   s)
    s = re.sub(r"NumberInt\(\s*(-?\d+)\s*\)",        r"\1",   s)

    # Одинарные кавычки → двойные.
    s = re.sub(r"'([^'\\]*(?:\\.[^'\\]*)*)'", r'"\1"', s)
    # Ключи без кавычек → в кавычки.
    s = re.sub(
        r"([\{,]\s*)([A-Za-z_$][A-Za-z_0-9$]*)\s*:",
        r'\1"\2":',
        s,
    )
    # Trailing commas.
    s = re.sub(r",(\s*[\]\}])", r"\1", s)
    return s


def _parse_args_block(args_src: str) -> list[Any]:
    """Парсит содержимое скобок вызова в список python-объектов."""
    args_src = args_src.strip()
    if not args_src:
        return []
    wrapped = "[" + _normalize_to_json(args_src) + "]"
    try:
        return json.loads(wrapped)
    except json.JSONDecodeError as err:
        raise MQLParseError(f"Не удалось разобрать аргументы: {err.msg}") from err


# ---------- Балансировка скобок ----------

def _find_matching_paren(text: str, open_pos: int) -> int:
    """Находит позицию закрывающей ')' для открывающей в open_pos.

    Учитывает вложенные скобки, строки в одинарных и двойных кавычках.
    Бросает MQLParseError при дисбалансе.
    """
    depth      = 0
    i          = open_pos
    in_string  = False
    quote_ch   = ""

    while i < len(text):
        ch = text[i]
        if in_string:
            if ch == "\\":            # экранирование — пропускаем следующий символ
                i += 2
                continue
            if ch == quote_ch:
                in_string = False
        else:
            if ch in ("'", '"'):
                in_string = True
                quote_ch  = ch
            elif ch == "(":
                depth += 1
            elif ch == ")":
                depth -= 1
                if depth == 0:
                    return i
        i += 1
    raise MQLParseError("Не сбалансированы скобки в запросе")


# ---------- Главная функция ----------

_HEAD_RE = re.compile(
    r"""
    ^\s*
    db\.
    ([A-Za-z_][A-Za-z_0-9]*)        # коллекция
    \.
    ([A-Za-z][A-Za-z0-9]*)          # первый метод
    \s*\(
    """,
    re.VERBOSE,
)

_CHAIN_RE = re.compile(
    r"""
    \s*\.
    ([A-Za-z][A-Za-z0-9]*)          # имя cursor-метода
    \s*\(
    """,
    re.VERBOSE,
)


def parse_mql(query: str) -> ParsedQuery:
    """Преобразует строку MQL в структурированный вызов с modifiers."""
    if not query or not query.strip():
        raise MQLParseError("Пустой запрос")

    for token in FORBIDDEN_TOKENS:
        if token in query:
            raise MQLParseError(f"Запрещённая операция: {token!r}")

    cleaned = _strip_comments(query).strip().rstrip(";").strip()

    # 1) Голова: db.<coll>.<method>(
    head = _HEAD_RE.match(cleaned)
    if not head:
        raise MQLParseError(
            "Ожидается вызов вида db.<коллекция>.<метод>(...). "
            "Проверьте синтаксис."
        )

    collection = head.group(1)
    method     = head.group(2)
    if method not in ALLOWED_METHODS:
        raise MQLParseError(
            f"Метод {method!r} не поддерживается. "
            f"Доступны: {', '.join(sorted(ALLOWED_METHODS))}"
        )

    open_paren  = head.end() - 1       # позиция '('
    close_paren = _find_matching_paren(cleaned, open_paren)
    args_src    = cleaned[open_paren + 1 : close_paren]
    args        = _parse_args_block(args_src)

    # 2) Chain: .method1(...).method2(...) ...
    modifiers: list[tuple[str, list[Any]]] = []
    i = close_paren + 1

    while i < len(cleaned):
        rest = cleaned[i:]
        if not rest.strip():
            break

        m = _CHAIN_RE.match(rest)
        if not m:
            # Осталось что-то лишнее вроде точки с запятой.
            if rest.strip() in (";", ""):
                break
            raise MQLParseError(f"Не понимаю хвост запроса: {rest[:40]!r}")

        mod_name = m.group(1)
        if mod_name not in CURSOR_MODIFIERS:
            raise MQLParseError(
                f"Метод {mod_name!r} нельзя вызвать в цепочке после {method}. "
                f"Разрешённые: {', '.join(sorted(CURSOR_MODIFIERS))}"
            )

        mod_open  = i + m.end() - 1
        mod_close = _find_matching_paren(cleaned, mod_open)
        mod_args  = _parse_args_block(cleaned[mod_open + 1 : mod_close])

        modifiers.append((mod_name, mod_args))
        i = mod_close + 1

    # Модификаторы допустимы только для find.
    if modifiers and method != "find":
        raise MQLParseError(
            f"Цепочка .sort/.limit/.skip применима только к find(), "
            f"но получено .{modifiers[0][0]} после {method}"
        )

    return ParsedQuery(
        collection = collection,
        method     = method,
        args       = args,
        modifiers  = modifiers,
    )
