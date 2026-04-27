"""Схемы для конструктора заданий (роль teacher/admin)."""
from datetime import datetime
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


class TaskUpdate(BaseModel):
    """Обновление задания (PATCH-семантика — все поля опциональны).

    `db_type` намеренно не входит — менять тип СУБД у существующего задания
    рискованно (ломает согласование с типом курса, эталон, fixture).
    Если нужен другой тип — задание следует удалить и создать заново.
    """
    statement:           str | None = Field(default=None, min_length=10, max_length=4000)
    fixture:             dict[str, Any] | None = None
    reference_solution:  str | None = Field(default=None, min_length=1, max_length=8000)
    reference_solutions: list[str] | None = Field(default=None, max_length=10)
    compare_ordered:     bool | None = None
    max_score:           int | None = Field(default=None, ge=1, le=100)
    attempts_limit:      int | None = Field(default=None, ge=0, le=100)


# ---------- Проверка эталона (dry-run для препода) ----------

class ReferenceDryRun(BaseModel):
    """Результат тестового прогона эталонного решения."""
    ok:          bool
    duration_ms: int
    result:      Any | None = None
    error:       str | None = None


# ---------- Дерево курса для билдера (с заданиями) ----------
#
# В отличие от студенческих схем (course.LessonBrief / ModuleWithLessons),
# здесь в каждом уроке приходит ещё и список заданий с id и формулировкой —
# чтобы препод мог открыть на редактирование любое задание прямо из дерева.

class BuilderTaskBrief(BaseModel):
    """Короткая карточка задания в дереве билдера."""
    model_config = ConfigDict(from_attributes=True)

    task_id:    int
    statement:  str
    db_type:    NoSQLType
    max_score:  int


class BuilderLessonBrief(BaseModel):
    """Урок в дереве билдера — с заданиями (а не просто счётчиком)."""
    model_config = ConfigDict(from_attributes=True)

    lesson_id:    int
    title:        str
    order_num:    int
    duration_min: int | None
    tasks:        list[BuilderTaskBrief]


class BuilderModuleBrief(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    module_id:   int
    title:       str
    description: str | None
    order_num:   int
    lessons:     list[BuilderLessonBrief]


class BuilderCourseDetail(BaseModel):
    """Полное дерево курса для редактирования: модули, уроки, задания."""
    model_config = ConfigDict(from_attributes=True)

    course_id:   int
    title:       str
    description: str | None
    nosql_type:  NoSQLType
    difficulty:  int | None
    created_at:  datetime
    modules:     list[BuilderModuleBrief]
