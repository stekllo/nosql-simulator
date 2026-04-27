"""Схемы для конструктора заданий (роль teacher/admin)."""
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from app.models import NoSQLType


# ---------- Создание курса/модуля/урока ----------

class CourseCreate(BaseModel):
    title:       str = Field(min_length=3, max_length=255)
    description: str | None = Field(default=None, max_length=4000)
    nosql_type:  NoSQLType
    difficulty:  int = Field(ge=1, le=5, default=2)


class ModuleCreate(BaseModel):
    title:       str = Field(min_length=3, max_length=255)
    description: str | None = Field(default=None, max_length=2000)
    order_num:   int = Field(ge=1)


class LessonCreate(BaseModel):
    title:        str = Field(min_length=3, max_length=255)
    content_md:   str = Field(min_length=1, max_length=20000)
    order_num:    int = Field(ge=1)
    duration_min: int | None = Field(default=None, ge=1, le=300)


class LessonUpdate(BaseModel):
    """Обновление урока (PATCH-семантика — все поля опциональны)."""
    title:        str | None = Field(default=None, min_length=3, max_length=255)
    content_md:   str | None = Field(default=None, min_length=1, max_length=20000)
    order_num:    int | None = Field(default=None, ge=1)
    duration_min: int | None = Field(default=None, ge=1, le=300)


# ---------- Создание задания ----------

class TaskCreate(BaseModel):
    statement:           str = Field(min_length=10, max_length=4000)
    db_type:             NoSQLType
    fixture:             dict[str, Any]            # JSON (collection + documents)
    reference_solution:  str = Field(min_length=1, max_length=8000)
    # Дополнительные эталоны (альтернативные правильные решения).
    # Если массив пуст — используется только reference_solution.
    reference_solutions: list[str] = Field(default_factory=list, max_length=10)
    # True — порядок элементов в результате важен (для $sort, $limit).
    # False — сравнение как multiset.
    compare_ordered:     bool = Field(default=True)
    max_score:           int = Field(ge=1, le=100, default=10)
    attempts_limit:      int = Field(ge=0, le=100, default=0)


class TaskOut(BaseModel):
    """Полный вид задания (с эталоном) — только для автора/админа."""
    model_config = ConfigDict(from_attributes=True)

    task_id:             int
    lesson_id:           int
    statement:           str
    db_type:             NoSQLType
    fixture:             dict[str, Any]
    reference_solution:  str
    reference_solutions: list[str] = Field(default_factory=list)
    compare_ordered:     bool = True
    max_score:           int
    attempts_limit:      int


# ---------- Проверка эталона (dry-run для препода) ----------

class ReferenceDryRun(BaseModel):
    """Результат тестового прогона эталонного решения."""
    ok:          bool
    duration_ms: int
    result:      Any | None = None
    error:       str | None = None
