"""Эндпоинты /builder — создание и редактирование учебного контента.

Доступны только пользователям с ролью teacher или admin. Student получает 403.
"""
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.deps import require_role
from app.db import get_db
from app.models import (
    Course, Lesson, Module, NoSQLType, Task, User, UserRole,
)
from app.sandbox.dispatch import execute_for_task, is_supported
from app.schemas.builder import (
    CourseCreate, LessonCreate, LessonUpdate, ModuleCreate,
    ReferenceDryRun, TaskCreate, TaskOut,
)
from app.schemas.course import (
    AuthorBrief, CourseBrief, CourseDetail, LessonBrief, ModuleWithLessons,
)

router = APIRouter(dependencies=[Depends(require_role(UserRole.TEACHER, UserRole.ADMIN))])


# ---------- Мои курсы (только автора) ----------

@router.get("/courses", response_model=list[CourseBrief])
async def my_courses(
    user:    Annotated[User, Depends(require_role(UserRole.TEACHER, UserRole.ADMIN))],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> list[CourseBrief]:
    """Все курсы, созданные текущим преподавателем (admin видит все)."""
    stmt = (
        select(Course)
        .options(selectinload(Course.author))
        .order_by(Course.created_at.desc())
    )
    if user.role != UserRole.ADMIN:
        stmt = stmt.where(Course.author_id == user.user_id)

    result = await session.execute(stmt)
    return [CourseBrief.model_validate(c) for c in result.scalars().all()]


# ---------- Курс: создать ----------

@router.post("/courses", response_model=CourseBrief, status_code=status.HTTP_201_CREATED)
async def create_course(
    body:    CourseCreate,
    user:    Annotated[User, Depends(require_role(UserRole.TEACHER, UserRole.ADMIN))],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> CourseBrief:
    course = Course(
        title       = body.title,
        description = body.description,
        nosql_type  = body.nosql_type,
        author_id   = user.user_id,
        difficulty  = body.difficulty,
    )
    session.add(course)
    await session.commit()
    await session.refresh(course, ["author"])
    return CourseBrief.model_validate(course)


# ---------- Полный курс с модулями и уроками (для UI построения дерева) ----------

@router.get("/courses/{course_id}", response_model=CourseDetail)
async def get_course_for_builder(
    course_id: int,
    user:      Annotated[User, Depends(require_role(UserRole.TEACHER, UserRole.ADMIN))],
    session:   Annotated[AsyncSession, Depends(get_db)],
) -> CourseDetail:
    course_q = await session.execute(
        select(Course)
        .options(selectinload(Course.author))
        .where(Course.course_id == course_id)
    )
    course = course_q.scalar_one_or_none()
    if course is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Курс не найден")

    if user.role != UserRole.ADMIN and course.author_id != user.user_id:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Чужой курс нельзя редактировать")

    modules_q = await session.execute(
        select(Module)
        .options(selectinload(Module.lessons))
        .where(Module.course_id == course_id)
        .order_by(Module.order_num)
    )
    modules = modules_q.scalars().all()

    lesson_ids = [l.lesson_id for m in modules for l in m.lessons]
    task_counts: dict[int, int] = {}
    if lesson_ids:
        counts_q = await session.execute(
            select(Task.lesson_id, func.count(Task.task_id))
            .where(Task.lesson_id.in_(lesson_ids))
            .group_by(Task.lesson_id)
        )
        task_counts = dict(counts_q.all())

    return CourseDetail(
        course_id   = course.course_id,
        title       = course.title,
        description = course.description,
        nosql_type  = course.nosql_type,
        difficulty  = course.difficulty,
        created_at  = course.created_at,
        author      = AuthorBrief.model_validate(course.author),
        modules     = [
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
        ],
    )


# ---------- Модуль ----------

@router.post("/courses/{course_id}/modules", status_code=status.HTTP_201_CREATED)
async def create_module(
    course_id: int,
    body:      ModuleCreate,
    user:      Annotated[User, Depends(require_role(UserRole.TEACHER, UserRole.ADMIN))],
    session:   Annotated[AsyncSession, Depends(get_db)],
):
    course_q = await session.execute(select(Course).where(Course.course_id == course_id))
    course   = course_q.scalar_one_or_none()
    if course is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Курс не найден")
    if user.role != UserRole.ADMIN and course.author_id != user.user_id:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Чужой курс")

    exists_q = await session.execute(
        select(Module).where(Module.course_id == course_id)
        .where(Module.order_num == body.order_num)
    )
    if exists_q.scalar_one_or_none():
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            f"Модуль с порядком {body.order_num} уже существует",
        )

    module = Module(
        course_id   = course_id,
        title       = body.title,
        description = body.description,
        order_num   = body.order_num,
    )
    session.add(module)
    await session.commit()
    await session.refresh(module)
    return {"module_id": module.module_id, "title": module.title, "order_num": module.order_num}


# ---------- Урок: создание ----------

@router.post("/modules/{module_id}/lessons", status_code=status.HTTP_201_CREATED)
async def create_lesson(
    module_id: int,
    body:      LessonCreate,
    user:      Annotated[User, Depends(require_role(UserRole.TEACHER, UserRole.ADMIN))],
    session:   Annotated[AsyncSession, Depends(get_db)],
):
    module_q = await session.execute(
        select(Module)
        .options(selectinload(Module.course))
        .where(Module.module_id == module_id)
    )
    module = module_q.scalar_one_or_none()
    if module is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Модуль не найден")
    if user.role != UserRole.ADMIN and module.course.author_id != user.user_id:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Чужой курс")

    exists_q = await session.execute(
        select(Lesson).where(Lesson.module_id == module_id)
        .where(Lesson.order_num == body.order_num)
    )
    if exists_q.scalar_one_or_none():
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            f"Урок с порядком {body.order_num} уже существует в модуле",
        )

    lesson = Lesson(
        module_id    = module_id,
        title        = body.title,
        content_md   = body.content_md,
        order_num    = body.order_num,
        duration_min = body.duration_min,
    )
    session.add(lesson)
    await session.commit()
    await session.refresh(lesson)
    return {
        "lesson_id": lesson.lesson_id,
        "title":     lesson.title,
        "order_num": lesson.order_num,
    }


# ---------- Урок: получить полное содержимое для редактирования ----------

@router.get("/lessons/{lesson_id}")
async def get_lesson_for_edit(
    lesson_id: int,
    user:      Annotated[User, Depends(require_role(UserRole.TEACHER, UserRole.ADMIN))],
    session:   Annotated[AsyncSession, Depends(get_db)],
):
    """Полный текст урока (Markdown) для редактирования преподавателем."""
    q = await session.execute(
        select(Lesson)
        .options(selectinload(Lesson.module).selectinload(Module.course))
        .where(Lesson.lesson_id == lesson_id)
    )
    lesson = q.scalar_one_or_none()
    if lesson is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Урок не найден")

    course = lesson.module.course
    if user.role != UserRole.ADMIN and course.author_id != user.user_id:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Чужой урок")

    return {
        "lesson_id":    lesson.lesson_id,
        "module_id":    lesson.module_id,
        "course_id":    course.course_id,
        "title":        lesson.title,
        "content_md":   lesson.content_md,
        "order_num":    lesson.order_num,
        "duration_min": lesson.duration_min,
    }


# ---------- Урок: обновить (Markdown-редактор для преподавателя) ----------

@router.patch("/lessons/{lesson_id}")
async def update_lesson(
    lesson_id: int,
    body:      LessonUpdate,
    user:      Annotated[User, Depends(require_role(UserRole.TEACHER, UserRole.ADMIN))],
    session:   Annotated[AsyncSession, Depends(get_db)],
):
    q = await session.execute(
        select(Lesson)
        .options(selectinload(Lesson.module).selectinload(Module.course))
        .where(Lesson.lesson_id == lesson_id)
    )
    lesson = q.scalar_one_or_none()
    if lesson is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Урок не найден")

    course = lesson.module.course
    if user.role != UserRole.ADMIN and course.author_id != user.user_id:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Чужой урок")

    # Применяем только переданные поля.
    if body.title is not None:
        lesson.title = body.title
    if body.content_md is not None:
        lesson.content_md = body.content_md
    if body.duration_min is not None:
        lesson.duration_min = body.duration_min
    if body.order_num is not None and body.order_num != lesson.order_num:
        # Проверка уникальности нового order_num.
        conflict_q = await session.execute(
            select(Lesson)
            .where(Lesson.module_id == lesson.module_id)
            .where(Lesson.order_num == body.order_num)
            .where(Lesson.lesson_id != lesson_id)
        )
        if conflict_q.scalar_one_or_none():
            raise HTTPException(
                status.HTTP_409_CONFLICT,
                f"Урок с порядком {body.order_num} уже существует в модуле",
            )
        lesson.order_num = body.order_num

    await session.commit()
    await session.refresh(lesson)
    return {
        "lesson_id":    lesson.lesson_id,
        "title":        lesson.title,
        "content_md":   lesson.content_md,
        "order_num":    lesson.order_num,
        "duration_min": lesson.duration_min,
    }


# ---------- Урок: удалить ----------

@router.delete("/lessons/{lesson_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_lesson(
    lesson_id: int,
    user:      Annotated[User, Depends(require_role(UserRole.TEACHER, UserRole.ADMIN))],
    session:   Annotated[AsyncSession, Depends(get_db)],
):
    q = await session.execute(
        select(Lesson)
        .options(selectinload(Lesson.module).selectinload(Module.course))
        .where(Lesson.lesson_id == lesson_id)
    )
    lesson = q.scalar_one_or_none()
    if lesson is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Урок не найден")

    course = lesson.module.course
    if user.role != UserRole.ADMIN and course.author_id != user.user_id:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Чужой урок")

    await session.delete(lesson)
    await session.commit()


# ---------- Проверка эталонного решения ----------

@router.post("/reference-dry-run", response_model=ReferenceDryRun)
async def reference_dry_run(
    body:    TaskCreate,
    _user:   Annotated[User, Depends(require_role(UserRole.TEACHER, UserRole.ADMIN))],
) -> ReferenceDryRun:
    """Запускает эталонное решение на переданном fixture.

    Нужен для preview перед сохранением задания: препод видит,
    что его эталон действительно отрабатывает и возвращает ожидаемое.
    """
    if not is_supported(body.db_type):
        raise HTTPException(
            status.HTTP_501_NOT_IMPLEMENTED,
            f"Dry-run для {body.db_type.value} пока не реализован. "
            f"Поддерживаются: MongoDB (document), Redis (key_value).",
        )

    outcome = await execute_for_task(body.db_type, body.fixture, body.reference_solution)

    return ReferenceDryRun(
        ok          = outcome.ok,
        duration_ms = outcome.duration_ms,
        result      = outcome.result,
        error       = outcome.error,
    )


# ---------- Задание ----------

@router.post("/lessons/{lesson_id}/tasks", response_model=TaskOut, status_code=status.HTTP_201_CREATED)
async def create_task(
    lesson_id: int,
    body:      TaskCreate,
    user:      Annotated[User, Depends(require_role(UserRole.TEACHER, UserRole.ADMIN))],
    session:   Annotated[AsyncSession, Depends(get_db)],
) -> TaskOut:
    """Создаёт новое задание. Автор курса должен совпадать с текущим пользователем."""
    lesson_q = await session.execute(
        select(Lesson)
        .options(selectinload(Lesson.module).selectinload(Module.course))
        .where(Lesson.lesson_id == lesson_id)
    )
    lesson = lesson_q.scalar_one_or_none()
    if lesson is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Урок не найден")

    course = lesson.module.course
    if user.role != UserRole.ADMIN and course.author_id != user.user_id:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Можно добавлять задания только в свои курсы")

    if body.db_type != course.nosql_type:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            f"Тип СУБД задания ({body.db_type.value}) не совпадает с типом курса "
            f"({course.nosql_type.value})",
        )

    if body.db_type == NoSQLType.DOCUMENT:
        if "collection" not in body.fixture or "documents" not in body.fixture:
            raise HTTPException(
                status.HTTP_400_BAD_REQUEST,
                'Fixture для MongoDB должен содержать поля "collection" и "documents"',
            )
        if not isinstance(body.fixture["documents"], list):
            raise HTTPException(
                status.HTTP_400_BAD_REQUEST,
                '"documents" должен быть массивом',
            )

    if body.db_type == NoSQLType.KEY_VALUE:
        # Для Redis fixture — это {"preload": ["SET k v", ...]}.
        # Поле preload опционально (задание может работать с пустой DB).
        preload = body.fixture.get("preload", [])
        if not isinstance(preload, list):
            raise HTTPException(
                status.HTTP_400_BAD_REQUEST,
                'Fixture для Redis: поле "preload" должно быть массивом строк-команд',
            )
        for cmd in preload:
            if not isinstance(cmd, str):
                raise HTTPException(
                    status.HTTP_400_BAD_REQUEST,
                    'Fixture для Redis: каждая команда в "preload" должна быть строкой',
                )

    task = Task(
        lesson_id           = lesson_id,
        statement           = body.statement,
        db_type             = body.db_type,
        fixture             = body.fixture,
        reference_solution  = body.reference_solution,
        reference_solutions = body.reference_solutions,
        compare_ordered     = body.compare_ordered,
        max_score           = body.max_score,
        attempts_limit      = body.attempts_limit,
    )
    session.add(task)
    await session.commit()
    await session.refresh(task)
    return TaskOut.model_validate(task)


@router.delete("/tasks/{task_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_task(
    task_id: int,
    user:    Annotated[User, Depends(require_role(UserRole.TEACHER, UserRole.ADMIN))],
    session: Annotated[AsyncSession, Depends(get_db)],
):
    task_q = await session.execute(
        select(Task)
        .options(selectinload(Task.lesson).selectinload(Lesson.module).selectinload(Module.course))
        .where(Task.task_id == task_id)
    )
    task = task_q.scalar_one_or_none()
    if task is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Задание не найдено")

    course = task.lesson.module.course
    if user.role != UserRole.ADMIN and course.author_id != user.user_id:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Чужое задание")

    await session.delete(task)
    await session.commit()
