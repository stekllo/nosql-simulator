"""Изолированная MongoDB-sandbox и выполнение пользовательских запросов.

Каждый запуск использует эфемерную БД с уникальным именем
(UUID), в которой воспроизводится исходное состояние из fixture.
После выполнения БД удаляется — защита от утечки данных между
попытками разных пользователей.
"""
from __future__ import annotations

import asyncio
import logging
import time
import uuid
from dataclasses import dataclass
from typing import Any

from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase
from pymongo.errors import OperationFailure, PyMongoError

from app.sandbox.mql_parser import (
    MQLParseError, ParsedQuery, WRITE_METHODS, parse_mql,
)

logger = logging.getLogger(__name__)

QUERY_TIMEOUT_SEC = 5.0
MAX_RESULT_ITEMS  = 1000


# ---------- DTO результата ----------

@dataclass
class ExecutionResult:
    """Итог выполнения одного запроса."""
    ok:          bool
    duration_ms: int
    result:      Any | None = None
    error:       str | None = None


# ---------- Выполнение парсенного запроса ----------

async def _run_on_db(db: AsyncIOMotorDatabase, parsed: ParsedQuery) -> Any:
    """Выполняет метод на коллекции и возвращает Python-объект.

    Результаты курсоров приводятся к list, чтобы было, что сравнивать.
    """
    coll   = db[parsed.collection]
    method = parsed.method
    args   = parsed.args

    # ---------- Чтение ----------
    if method == "find":
        cursor = coll.find(*args) if args else coll.find()
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
        res = await coll.update_one(args[0], args[1],
                                     upsert=bool(args[2].get("upsert")) if len(args) > 2 else False)
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

    # ---------- Неподдерживаемые (страховка) ----------
    raise MQLParseError(f"Метод {method!r} не реализован в раннере")


# ---------- Public API ----------

async def execute_mql(
    client:     AsyncIOMotorClient,
    fixture:    dict,
    query_text: str,
) -> ExecutionResult:
    """Выполняет MQL-запрос в эфемерной БД.

    Шаги:
    1. Парсинг запроса.
    2. Создание эфемерной БД с уникальным именем.
    3. Вставка документов из fixture в коллекцию.
    4. Выполнение запроса с тайм-аутом.
    5. Удаление эфемерной БД.
    """
    start = time.perf_counter()

    # 1. Парсинг.
    try:
        parsed = parse_mql(query_text)
    except MQLParseError as err:
        return ExecutionResult(
            ok=False,
            duration_ms=int((time.perf_counter() - start) * 1000),
            error=str(err),
        )

    # 2. Эфемерная БД.
    db_name = f"sandbox_{uuid.uuid4().hex[:16]}"
    db      = client[db_name]

    try:
        # 3. Fixture.
        coll_name = fixture.get("collection")
        documents = fixture.get("documents", [])
        if coll_name and documents:
            await db[coll_name].insert_many(documents)

        # 4. Выполнение с тайм-аутом.
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

        # Нормализация ObjectId в строки для JSON-сериализации.
        result = _normalize(result)

        return ExecutionResult(
            ok=True,
            duration_ms=int((time.perf_counter() - start) * 1000),
            result=result,
        )

    finally:
        # 5. Всегда чистим за собой.
        try:
            await client.drop_database(db_name)
        except Exception as exc:
            logger.warning("Failed to drop sandbox db %s: %s", db_name, exc)


# ---------- Сравнение результатов ----------

def _normalize(value: Any) -> Any:
    """Делает результат JSON-сериализуемым: ObjectId → str, datetime → iso."""
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
    """Сравнивает результат студента с эталонным.

    - Словари сравниваются поэлементно.
    - Списки: если ordered=True, порядок важен; иначе проверяется,
      что списки — мультимножественно равны (одинаковые элементы).
    """
    if isinstance(student, list) and isinstance(reference, list):
        if len(student) != len(reference):
            return False
        if ordered:
            return all(compare_results(a, b, ordered=ordered) for a, b in zip(student, reference))
        # Нестрогий порядок: сортируем через repr.
        return sorted(map(repr, student)) == sorted(map(repr, reference))

    if isinstance(student, dict) and isinstance(reference, dict):
        if set(student.keys()) != set(reference.keys()):
            return False
        return all(compare_results(student[k], reference[k], ordered=ordered) for k in student)

    # Числа разных типов с одинаковым значением считаем равными (1 == 1.0).
    return student == reference
