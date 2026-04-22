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


# ---------- Создание задания ----------

class TaskCreate(BaseModel):
    statement:          str = Field(min_length=10, max_length=4000)
    db_type:            NoSQLType
    fixture:            dict[str, Any]            # JSON (collection + documents)
    reference_solution: str = Field(min_length=1, max_length=8000)
    max_score:          int = Field(ge=1, le=100, default=10)
    attempts_limit:     int = Field(ge=0, le=100, default=0)


class TaskOut(BaseModel):
    """Полный вид задания (с эталоном) — только для автора/админа."""
    model_config = ConfigDict(from_attributes=True)

    task_id:            int
    lesson_id:          int
    statement:          str
    db_type:            NoSQLType
    fixture:            dict[str, Any]
    reference_solution: str
    max_score:          int
    attempts_limit:     int


# ---------- Проверка эталона (dry-run для препода) ----------

class ReferenceDryRun(BaseModel):
    """Результат тестового прогона эталонного решения."""
    ok:          bool
    duration_ms: int
    result:      Any | None = None
    error:       str | None = None
