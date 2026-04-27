"""Эндпоинты /tasks — получение задания и запуск запросов.

После Patch-12 диспатчинг по типу СУБД делается через app.sandbox.dispatch:
api-слой не знает деталей конкретных runner'ов и одинаково работает с
MongoDB (document) и Redis (key_value).
"""
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.deps import CurrentUser
from app.db import get_db
from app.models import Lesson, NoSQLType, Submission, SubmissionStatus, Task
from app.sandbox.dispatch import execute_for_task, is_supported
from app.sandbox.mongo_runner import compare_to_any_reference
from app.schemas.course import LessonDetail, TaskBrief
from app.schemas.submission import RunRequest, RunResponse, SubmitResponse

router = APIRouter()


async def _get_task_or_404(session: AsyncSession, task_id: int) -> Task:
    result = await session.execute(select(Task).where(Task.task_id == task_id))
    task   = result.scalar_one_or_none()
    if task is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Задание не найдено")
    return task


def _assert_supported(task: Task) -> None:
    if not is_supported(task.db_type):
        raise HTTPException(
            status.HTTP_501_NOT_IMPLEMENTED,
            f"Проверка для {task.db_type.value} будет добавлена позже. "
            f"Пока поддерживаются: MongoDB (document), Redis (key_value).",
        )


@router.get("/{task_id}/lesson", response_model=LessonDetail)
async def get_lesson_for_task(
    task_id: int,
    _user:   CurrentUser,
    session: Annotated[AsyncSession, Depends(get_db)],
) -> LessonDetail:
    """Возвращает урок, в котором лежит это задание (теория + список заданий)."""
    result = await session.execute(
        select(Lesson)
        .options(selectinload(Lesson.tasks))
        .join(Task, Task.lesson_id == Lesson.lesson_id)
        .where(Task.task_id == task_id)
    )
    lesson = result.scalar_one_or_none()
    if lesson is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Задание не найдено")

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


@router.post("/{task_id}/run", response_model=RunResponse)
async def run_query(
    task_id: int,
    body:    RunRequest,
    _user:   CurrentUser,
    session: Annotated[AsyncSession, Depends(get_db)],
) -> RunResponse:
    task = await _get_task_or_404(session, task_id)
    _assert_supported(task)

    outcome = await execute_for_task(task.db_type, task.fixture, body.query_text)

    return RunResponse(
        ok          = outcome.ok,
        duration_ms = outcome.duration_ms,
        result      = outcome.result,
        error       = outcome.error,
    )


@router.post("/{task_id}/submit", response_model=SubmitResponse)
async def submit_solution(
    task_id: int,
    body:    RunRequest,
    user:    CurrentUser,
    session: Annotated[AsyncSession, Depends(get_db)],
) -> SubmitResponse:
    task = await _get_task_or_404(session, task_id)
    _assert_supported(task)

    # Запускаем запрос студента.
    student_outcome = await execute_for_task(task.db_type, task.fixture, body.query_text)

    # Запускаем все эталонные решения (последовательно — не страшно,
    # их обычно 1-3 штуки).
    reference_outcomes = []
    for ref_query in task.all_reference_solutions:
        ref_outcome = await execute_for_task(task.db_type, task.fixture, ref_query)
        reference_outcomes.append(ref_outcome)

    if not student_outcome.ok:
        status_enum = (
            SubmissionStatus.TIMEOUT
            if (student_outcome.error or "").startswith("Превышено")
            else SubmissionStatus.WRONG
        )
        is_correct = False
        score      = 0
    else:
        # Все эталоны должны успешно отработать (хотя бы один).
        valid_references = [r.result for r in reference_outcomes if r.ok]
        if not valid_references:
            raise HTTPException(
                status.HTTP_500_INTERNAL_SERVER_ERROR,
                "Эталонные решения упали — свяжитесь с преподавателем",
            )

        # Сравниваем результат студента со всеми эталонами.
        # Если совпал хотя бы с одним — задание решено.
        is_correct = compare_to_any_reference(
            student_outcome.result,
            valid_references,
            ordered=task.compare_ordered,
        )
        status_enum = SubmissionStatus.CORRECT if is_correct else SubmissionStatus.WRONG
        score       = task.max_score if is_correct else 0

    submission = Submission(
        user_id    = user.user_id,
        task_id    = task.task_id,
        query_text = body.query_text,
        result     = {
            "items": student_outcome.result if isinstance(student_outcome.result, list) else None,
            "value": student_outcome.result if not isinstance(student_outcome.result, list) else None,
        },
        is_correct = is_correct,
        score      = score,
        status     = status_enum,
    )
    session.add(submission)
    await session.commit()
    await session.refresh(submission)

    return SubmitResponse(
        submission_id = submission.submission_id,
        is_correct    = is_correct,
        score         = score,
        status        = status_enum,
        duration_ms   = student_outcome.duration_ms,
        result        = student_outcome.result,
        error         = student_outcome.error,
        submitted_at  = submission.submitted_at,
    )
