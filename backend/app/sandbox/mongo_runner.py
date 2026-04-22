"""Изолированная MongoDB-sandbox и выполнение пользовательских запросов."""
from __future__ import annotations

import asyncio
import logging
import time
import uuid
from dataclasses import dataclass
from typing import Any

from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase
from pymongo.errors import OperationFailure, PyMongoError

from app.sandbox.mql_parser import MQLParseError, ParsedQuery, parse_mql

logger = logging.getLogger(__name__)

QUERY_TIMEOUT_SEC = 5.0
MAX_RESULT_ITEMS  = 1000


@dataclass
class ExecutionResult:
    ok:          bool
    duration_ms: int
    result:      Any | None = None
    error:       str | None = None


# ---------- Применение курсорных modifiers ----------

def _apply_modifiers(cursor, modifiers: list[tuple[str, list[Any]]]):
    """Накладывает .sort/.limit/.skip/.project на курсор Motor."""
    for name, args in modifiers:
        if name == "sort":
            spec = args[0] if args else {}
            if isinstance(spec, dict):
                cursor = cursor.sort(list(spec.items()))
            else:
                cursor = cursor.sort(spec)
        elif name == "limit":
            n = args[0] if args else 0
            cursor = cursor.limit(int(n))
        elif name == "skip":
            n = args[0] if args else 0
            cursor = cursor.skip(int(n))
        elif name == "project":
            projection = args[0] if args else {}
            # Motor у курсора есть только конструктор с projection; для совместимости
            # через find с тем же filter не получится здесь — пропускаем, чтобы не падать.
            # Практически .project(...) редко встречается как метод курсора в учебных
            # задачах; второй аргумент find покрывает 99% случаев.
            if hasattr(cursor, "project"):
                cursor = cursor.project(projection)
    return cursor


# ---------- Выполнение парсенного запроса ----------

async def _run_on_db(db: AsyncIOMotorDatabase, parsed: ParsedQuery) -> Any:
    """Выполняет метод на коллекции и возвращает Python-объект."""
    coll   = db[parsed.collection]
    method = parsed.method
    args   = parsed.args

    # ---------- Чтение ----------
    if method == "find":
        cursor = coll.find(*args) if args else coll.find()
        cursor = _apply_modifiers(cursor, parsed.modifiers)
        return await cursor.to_list(length=MAX_RESULT_ITEMS)

    if method == "findOne":
        return await coll.find_one(*args) if args else await coll.find_one()

    if method == "aggregate":
        pipeline = args[0] if args else []
        cursor   = coll.aggregate(pipeline)
        return await cursor.to_list(length=MAX_RESULT_ITEMS)

    if method in ("count", "countDocuments"):
        filt = args[0] if args else {}
        return await coll.count_documents(filt)

    if method == "estimatedDocumentCount":
        return await coll.estimated_document_count()

    if method == "distinct":
        key  = args[0]
        filt = args[1] if len(args) > 1 else {}
        return await coll.distinct(key, filt)

    # ---------- Запись ----------
    if method == "insertOne":
        res = await coll.insert_one(args[0])
        return {"insertedId": str(res.inserted_id)}

    if method == "insertMany":
        res = await coll.insert_many(args[0])
        return {"insertedIds": [str(x) for x in res.inserted_ids]}

    if method == "updateOne":
        res = await coll.update_one(
            args[0], args[1],
            upsert=bool(args[2].get("upsert")) if len(args) > 2 else False,
        )
        return {"matchedCount": res.matched_count, "modifiedCount": res.modified_count}

    if method == "updateMany":
        res = await coll.update_many(args[0], args[1])
        return {"matchedCount": res.matched_count, "modifiedCount": res.modified_count}

    if method == "deleteOne":
        res = await coll.delete_one(args[0])
        return {"deletedCount": res.deleted_count}

    if method == "deleteMany":
        res = await coll.delete_many(args[0])
        return {"deletedCount": res.deleted_count}

    raise MQLParseError(f"Метод {method!r} не реализован в раннере")


# ---------- Public API ----------

async def execute_mql(
    client:     AsyncIOMotorClient,
    fixture:    dict,
    query_text: str,
) -> ExecutionResult:
    """Выполняет MQL-запрос в эфемерной БД."""
    start = time.perf_counter()

    try:
        parsed = parse_mql(query_text)
    except MQLParseError as err:
        return ExecutionResult(
            ok=False,
            duration_ms=int((time.perf_counter() - start) * 1000),
            error=str(err),
        )

    db_name = f"sandbox_{uuid.uuid4().hex[:16]}"
    db      = client[db_name]

    try:
        coll_name = fixture.get("collection")
        documents = fixture.get("documents", [])
        if coll_name and documents:
            await db[coll_name].insert_many(documents)

        try:
            result = await asyncio.wait_for(
                _run_on_db(db, parsed),
                timeout=QUERY_TIMEOUT_SEC,
            )
        except asyncio.TimeoutError:
            return ExecutionResult(
                ok=False,
                duration_ms=int(QUERY_TIMEOUT_SEC * 1000),
                error=f"Превышено время ожидания ({QUERY_TIMEOUT_SEC:.0f} сек)",
            )
        except (OperationFailure, PyMongoError) as err:
            return ExecutionResult(
                ok=False,
                duration_ms=int((time.perf_counter() - start) * 1000),
                error=f"Ошибка MongoDB: {err}",
            )
        except MQLParseError as err:
            return ExecutionResult(
                ok=False,
                duration_ms=int((time.perf_counter() - start) * 1000),
                error=str(err),
            )

        result = _normalize(result)
        return ExecutionResult(
            ok=True,
            duration_ms=int((time.perf_counter() - start) * 1000),
            result=result,
        )

    finally:
        try:
            await client.drop_database(db_name)
        except Exception as exc:
            logger.warning("Failed to drop sandbox db %s: %s", db_name, exc)


# ---------- Сравнение результатов ----------

def _normalize(value: Any) -> Any:
    """ObjectId → str, datetime → iso."""
    from bson import ObjectId
    from datetime import datetime

    if isinstance(value, list):
        return [_normalize(v) for v in value]
    if isinstance(value, dict):
        return {str(k): _normalize(v) for k, v in value.items()}
    if isinstance(value, ObjectId):
        return str(value)
    if isinstance(value, datetime):
        return value.isoformat()
    return value


def compare_results(student: Any, reference: Any, *, ordered: bool = True) -> bool:
    """Сравнивает результат студента с эталонным."""
    if isinstance(student, list) and isinstance(reference, list):
        if len(student) != len(reference):
            return False
        if ordered:
            return all(compare_results(a, b, ordered=ordered) for a, b in zip(student, reference))
        return sorted(map(repr, student)) == sorted(map(repr, reference))

    if isinstance(student, dict) and isinstance(reference, dict):
        if set(student.keys()) != set(reference.keys()):
            return False
        return all(compare_results(student[k], reference[k], ordered=ordered) for k in student)

    return student == reference
