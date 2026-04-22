"""Эндпоинты /courses: каталог, детали курса, навигация по урокам."""
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.deps import CurrentUser
from app.db import get_db
from app.models import Course, Lesson, Module, NoSQLType, Task
from app.schemas.course import (
    AuthorBrief, CourseBrief, CourseDetail, LessonBrief,
    LessonDetail, ModuleWithLessons, TaskBrief,
)

router = APIRouter()


# ---------- Каталог ----------

@router.get("", response_model=list[CourseBrief])
async def list_courses(
    _user:      CurrentUser,
    session:    Annotated[AsyncSession, Depends(get_db)],
    nosql_type: Annotated[NoSQLType | None, Query()] = None,
    author_id:  Annotated[int        | None, Query()] = None,
) -> list[CourseBrief]:
    """Список курсов. Фильтры: тип СУБД, автор."""
    stmt = (
        select(Course)
        .options(selectinload(Course.author))
        .order_by(Course.created_at.desc())
    )
    if nosql_type:
        stmt = stmt.where(Course.nosql_type == nosql_type)
    if author_id:
        stmt = stmt.where(Course.author_id == author_id)

    result = await session.execute(stmt)
    return [CourseBrief.model_validate(c) for c in result.scalars().all()]


# ---------- Детали курса ----------

@router.get("/{course_id}", response_model=CourseDetail)
async def get_course(
    course_id: int,
    _user:     CurrentUser,
    session:   Annotated[AsyncSession, Depends(get_db)],
) -> CourseDetail:
    """Полная карточка курса: автор, модули, уроки, счётчики заданий."""
    # Подтягиваем курс с автором.
    course_q = await session.execute(
        select(Course)
        .options(selectinload(Course.author))
        .where(Course.course_id == course_id)
    )
    course = course_q.scalar_one_or_none()
    if course is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Курс не найден")

    # Модули с уроками (упорядочены).
    modules_q = await session.execute(
        select(Module)
        .options(selectinload(Module.lessons))
        .where(Module.course_id == course_id)
        .order_by(Module.order_num)
    )
    modules = modules_q.scalars().all()

    # Счётчики заданий по урокам — одним запросом.
    lesson_ids = [l.lesson_id for m in modules for l in m.lessons]
    task_counts: dict[int, int] = {}
    if lesson_ids:
        counts_q = await session.execute(
            select(Task.lesson_id, func.count(Task.task_id))
            .where(Task.lesson_id.in_(lesson_ids))
            .group_by(Task.lesson_id)
        )
        task_counts = dict(counts_q.all())

    modules_out = [
        ModuleWithLessons(
            module_id   = m.module_id,
            title       = m.title,
            description = m.description,
            order_num   = m.order_num,
            lessons     = [
                LessonBrief(
                    lesson_id    = l.lesson_id,
                    title        = l.title,
                    order_num    = l.order_num,
                    duration_min = l.duration_min,
                    task_count   = task_counts.get(l.lesson_id, 0),
                )
                for l in sorted(m.lessons, key=lambda x: x.order_num)
            ],
        )
        for m in modules
    ]

    return CourseDetail(
        course_id   = course.course_id,
        title       = course.title,
        description = course.description,
        nosql_type  = course.nosql_type,
        difficulty  = course.difficulty,
        created_at  = course.created_at,
        author      = AuthorBrief.model_validate(course.author),
        modules     = modules_out,
    )


# ---------- Урок ----------

@router.get("/lessons/{lesson_id}", response_model=LessonDetail)
async def get_lesson(
    lesson_id: int,
    _user:     CurrentUser,
    session:   Annotated[AsyncSession, Depends(get_db)],
) -> LessonDetail:
    """Содержимое урока + список заданий (без эталонного решения)."""
    result = await session.execute(
        select(Lesson)
        .options(selectinload(Lesson.tasks))
        .where(Lesson.lesson_id == lesson_id)
    )
    lesson = result.scalar_one_or_none()
    if lesson is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Урок не найден")

    return LessonDetail(
        lesson_id    = lesson.lesson_id,
        module_id    = lesson.module_id,
        title        = lesson.title,
        content_md   = lesson.content_md,
        order_num    = lesson.order_num,
        duration_min = lesson.duration_min,
        tasks        = [
            TaskBrief(
                task_id   = t.task_id,
                statement = t.statement,
                db_type   = t.db_type,
                max_score = t.max_score,
            )
            for t in sorted(lesson.tasks, key=lambda x: x.task_id)
        ],
    )
