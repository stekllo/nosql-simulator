"""Эндпоинты /courses: каталог, детали курса, навигация по урокам.

Все эндпоинты учитывают **прогресс текущего пользователя**:
- В каталоге у каждого курса возвращается CourseProgress (5/8 уроков пройдено).
- На странице курса у каждого урока — флаг is_completed.
- На странице урока у каждого задания — флаг is_solved.

Логика прогресса:
- Задание решено ⇔ есть Submission со status=CORRECT для (user_id, task_id).
- Урок пройден ⇔ все его задания решены ИЛИ у урока нет заданий (теоретический).
- Прогресс курса = lessons_completed / lessons_total в процентах.
"""
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.deps import CurrentUser
from app.db import get_db
from app.models import Course, Lesson, Module, NoSQLType, Submission, SubmissionStatus, Task
from app.schemas.course import (
    AuthorBrief, CourseBrief, CourseDetail, CourseProgress, LessonBrief,
    LessonDetail, ModuleWithLessons, TaskBrief,
)

router = APIRouter()


# ---------- Helpers ----------

async def _get_solved_task_ids(
    session:  AsyncSession,
    user_id:  int,
    task_ids: list[int],
) -> set[int]:
    """Возвращает подмножество task_ids, для которых у пользователя есть
    хотя бы один CORRECT-сабмишен.

    Один SQL-запрос. Если task_ids пуст — сразу возвращаем пустое множество.
    """
    if not task_ids:
        return set()
    result = await session.execute(
        select(Submission.task_id)
        .where(
            Submission.user_id == user_id,
            Submission.task_id.in_(task_ids),
            Submission.status == SubmissionStatus.CORRECT,
        )
        .distinct()
    )
    return {row[0] for row in result.all()}


def _compute_course_progress(
    *,
    lesson_to_tasks: dict[int, list[int]],
    solved_task_ids: set[int],
) -> CourseProgress:
    """Считает прогресс по курсу из мапы 'урок → его task_ids' и набора
    решённых заданий.

    Урок считается пройденным, если все его задания решены или у него нет
    заданий вообще (теория считается «пройденной» автоматически).
    """
    lessons_total     = len(lesson_to_tasks)
    lessons_completed = 0
    tasks_total       = 0
    tasks_solved      = 0

    for tasks in lesson_to_tasks.values():
        tasks_total += len(tasks)
        if not tasks:
            # Теоретический урок — считается пройденным.
            lessons_completed += 1
            continue
        solved_in_lesson = sum(1 for t in tasks if t in solved_task_ids)
        tasks_solved += solved_in_lesson
        if solved_in_lesson == len(tasks):
            lessons_completed += 1

    percent = int(round(100 * lessons_completed / lessons_total)) if lessons_total else 0

    return CourseProgress(
        lessons_completed = lessons_completed,
        lessons_total     = lessons_total,
        tasks_solved      = tasks_solved,
        tasks_total       = tasks_total,
        percent           = percent,
    )


# ---------- Каталог ----------

@router.get("", response_model=list[CourseBrief])
async def list_courses(
    user:       CurrentUser,
    session:    Annotated[AsyncSession, Depends(get_db)],
    nosql_type: Annotated[NoSQLType | None, Query()] = None,
    author_id:  Annotated[int        | None, Query()] = None,
) -> list[CourseBrief]:
    """Список курсов. Фильтры: тип СУБД, автор.

    Для каждого курса считается прогресс текущего пользователя.
    Дополнительно к прежним 1 запросу делается ещё 3:
    - все уроки этих курсов
    - все задания этих уроков
    - все CORRECT-сабмишены пользователя по этим заданиям
    """
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
    courses = list(result.scalars().all())
    if not courses:
        return []

    course_ids = [c.course_id for c in courses]

    # Все уроки этих курсов одним запросом (через JOIN на Module).
    lessons_q = await session.execute(
        select(Lesson.lesson_id, Module.course_id)
        .join(Module, Module.module_id == Lesson.module_id)
        .where(Module.course_id.in_(course_ids))
    )
    lessons_by_course: dict[int, list[int]] = {}
    all_lesson_ids: list[int] = []
    for lesson_id, c_id in lessons_q.all():
        lessons_by_course.setdefault(c_id, []).append(lesson_id)
        all_lesson_ids.append(lesson_id)

    # Все задания этих уроков.
    tasks_by_lesson: dict[int, list[int]] = {}
    all_task_ids: list[int] = []
    if all_lesson_ids:
        tasks_q = await session.execute(
            select(Task.task_id, Task.lesson_id)
            .where(Task.lesson_id.in_(all_lesson_ids))
        )
        for t_id, l_id in tasks_q.all():
            tasks_by_lesson.setdefault(l_id, []).append(t_id)
            all_task_ids.append(t_id)

    # Решённые задания студента.
    solved = await _get_solved_task_ids(session, user.user_id, all_task_ids)

    # Собираем CourseBrief с прогрессом.
    out: list[CourseBrief] = []
    for c in courses:
        lesson_ids = lessons_by_course.get(c.course_id, [])
        lesson_to_tasks = {
            lid: tasks_by_lesson.get(lid, []) for lid in lesson_ids
        }
        progress = (
            _compute_course_progress(
                lesson_to_tasks = lesson_to_tasks,
                solved_task_ids = solved,
            )
            if lesson_ids
            else None
        )
        brief = CourseBrief.model_validate(c)
        brief.progress = progress
        out.append(brief)

    return out


# ---------- Детали курса ----------

@router.get("/{course_id}", response_model=CourseDetail)
async def get_course(
    course_id: int,
    user:      CurrentUser,
    session:   Annotated[AsyncSession, Depends(get_db)],
) -> CourseDetail:
    """Полная карточка курса: автор, модули, уроки, прогресс пользователя."""
    course_q = await session.execute(
        select(Course)
        .options(selectinload(Course.author))
        .where(Course.course_id == course_id)
    )
    course = course_q.scalar_one_or_none()
    if course is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Курс не найден")

    modules_q = await session.execute(
        select(Module)
        .options(selectinload(Module.lessons))
        .where(Module.course_id == course_id)
        .order_by(Module.order_num)
    )
    modules = modules_q.scalars().all()

    # Все task_id курса с привязкой к урокам — одним запросом.
    lesson_ids = [l.lesson_id for m in modules for l in m.lessons]
    tasks_by_lesson: dict[int, list[int]] = {}
    task_counts:     dict[int, int]       = {}
    if lesson_ids:
        tasks_q = await session.execute(
            select(Task.task_id, Task.lesson_id)
            .where(Task.lesson_id.in_(lesson_ids))
        )
        for t_id, l_id in tasks_q.all():
            tasks_by_lesson.setdefault(l_id, []).append(t_id)
        task_counts = {l_id: len(ts) for l_id, ts in tasks_by_lesson.items()}

    all_task_ids = [t for ts in tasks_by_lesson.values() for t in ts]
    solved = await _get_solved_task_ids(session, user.user_id, all_task_ids)

    def lesson_completed(lesson_id: int) -> bool:
        tasks = tasks_by_lesson.get(lesson_id, [])
        if not tasks:
            return True   # теория считается пройденной
        return all(t in solved for t in tasks)

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
                    is_completed = lesson_completed(l.lesson_id),
                )
                for l in sorted(m.lessons, key=lambda x: x.order_num)
            ],
        )
        for m in modules
    ]

    lesson_to_tasks = {
        lid: tasks_by_lesson.get(lid, []) for lid in lesson_ids
    }
    progress = (
        _compute_course_progress(
            lesson_to_tasks = lesson_to_tasks,
            solved_task_ids = solved,
        )
        if lesson_ids
        else None
    )

    return CourseDetail(
        course_id   = course.course_id,
        title       = course.title,
        description = course.description,
        nosql_type  = course.nosql_type,
        difficulty  = course.difficulty,
        created_at  = course.created_at,
        author      = AuthorBrief.model_validate(course.author),
        progress    = progress,
        modules     = modules_out,
    )


# ---------- Урок ----------

@router.get("/lessons/{lesson_id}", response_model=LessonDetail)
async def get_lesson(
    lesson_id: int,
    user:      CurrentUser,
    session:   Annotated[AsyncSession, Depends(get_db)],
) -> LessonDetail:
    """Содержимое урока + список заданий (без эталонного решения).

    У каждого задания — флаг is_solved для текущего пользователя.
    """
    result = await session.execute(
        select(Lesson)
        .options(selectinload(Lesson.tasks))
        .where(Lesson.lesson_id == lesson_id)
    )
    lesson = result.scalar_one_or_none()
    if lesson is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Урок не найден")

    task_ids = [t.task_id for t in lesson.tasks]
    solved = await _get_solved_task_ids(session, user.user_id, task_ids)

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
                is_solved = t.task_id in solved,
            )
            for t in sorted(lesson.tasks, key=lambda x: x.task_id)
        ],
    )
