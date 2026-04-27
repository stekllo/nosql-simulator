"""Схемы данных для эндпоинтов /courses, /modules, /lessons."""
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.models import NoSQLType


# ---------- Autor (мини-блок) ----------

class AuthorBrief(BaseModel):
    """Сокращённое представление автора курса (без пароля и пр.)."""
    model_config = ConfigDict(from_attributes=True)

    user_id:      int
    login:        str
    display_name: str | None


# ---------- Прогресс по курсу ----------

class CourseProgress(BaseModel):
    """Прогресс конкретного студента по конкретному курсу.

    Логика:
    - Урок считается пройденным, если решены ВСЕ его задания.
    - Урок без заданий (чистая теория) считается пройденным автоматически.
    - Прогресс курса = lessons_completed / lessons_total в процентах.
    """
    lessons_completed: int = Field(ge=0)
    lessons_total:     int = Field(ge=0)
    tasks_solved:      int = Field(ge=0)
    tasks_total:       int = Field(ge=0)
    percent:           int = Field(ge=0, le=100)


# ---------- Course ----------

class CourseBrief(BaseModel):
    """Курс в каталоге (без модулей)."""
    model_config = ConfigDict(from_attributes=True)

    course_id:   int
    title:       str
    description: str | None
    nosql_type:  NoSQLType
    difficulty:  int | None
    created_at:  datetime
    author:      AuthorBrief
    # Прогресс текущего пользователя — None если в курсе нет ни одного урока,
    # или если у пользователя нет ни одного решения (тогда прогресс = 0/N
    # и мы его всё равно показываем).
    progress:    CourseProgress | None = None


class LessonBrief(BaseModel):
    """Урок в списке модуля."""
    model_config = ConfigDict(from_attributes=True)

    lesson_id:    int
    title:        str
    order_num:    int
    duration_min: int | None
    task_count:   int = 0
    # Урок пройден: все задания решены текущим пользователем,
    # либо у урока нет заданий вообще (теоретический урок).
    is_completed: bool = False


class ModuleWithLessons(BaseModel):
    """Модуль с уроками (для страницы курса)."""
    model_config = ConfigDict(from_attributes=True)

    module_id:   int
    title:       str
    description: str | None
    order_num:   int
    lessons:     list[LessonBrief]


class CourseDetail(CourseBrief):
    """Полная карточка курса — с модулями."""
    modules: list[ModuleWithLessons]


# ---------- Lesson ----------

class TaskBrief(BaseModel):
    """Короткая карточка задания, лежащего в уроке."""
    model_config = ConfigDict(from_attributes=True)

    task_id:    int
    statement:  str
    db_type:    NoSQLType
    max_score:  int
    # Решено ли это задание текущим пользователем (есть ли CORRECT submission).
    is_solved:  bool = False


class LessonDetail(BaseModel):
    """Урок с контентом и заданиями."""
    model_config = ConfigDict(from_attributes=True)

    lesson_id:    int
    module_id:    int
    title:        str
    content_md:   str
    order_num:    int
    duration_min: int | None
    tasks:        list[TaskBrief]
