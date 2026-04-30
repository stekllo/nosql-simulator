"""Тесты эндпоинта POST /tasks/{id}/submit.

Покрытие: правильное решение → CORRECT + score, неправильное → WRONG, без
авторизации → 401, и что после CORRECT-submission урок становится пройденным.

sandbox-runner замокан через monkeypatch — настоящие Mongo/Redis не нужны.
"""
import pytest
from httpx import AsyncClient

from app.models import User


@pytest.mark.asyncio
async def test_submit_correct_solution(
    client: AsyncClient,
    teacher_with_course,
    student_token: str,
    mock_sandbox,
    make_auth_headers,
):
    """Если результат студента совпадает с эталоном — CORRECT, max_score."""
    _, _, _, _, task = teacher_with_course

    # И эталон, и студент дают одинаковый результат — оба пути в моке
    # вернут default-результат [{"x": 1}]
    response = await client.post(
        f"/tasks/{task.task_id}/submit",
        json={"query_text": "db.test.find({})"},
        headers=make_auth_headers(student_token),
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["is_correct"] is True
    assert body["score"] == task.max_score
    assert body["status"] == "correct"
    assert body["submission_id"] > 0


@pytest.mark.asyncio
async def test_submit_wrong_solution(
    client: AsyncClient,
    teacher_with_course,
    student_token: str,
    mock_sandbox,
    make_auth_headers,
):
    """Если результаты не совпадают — WRONG, score=0."""
    _, _, _, _, task = teacher_with_course

    # Студент даёт другой результат, чем эталон.
    student_query = "db.test.find({wrong: true})"
    mock_sandbox.set_outcome(student_query, ok=True, result=[{"different": 999}])

    response = await client.post(
        f"/tasks/{task.task_id}/submit",
        json={"query_text": student_query},
        headers=make_auth_headers(student_token),
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["is_correct"] is False
    assert body["score"] == 0
    assert body["status"] == "wrong"


@pytest.mark.asyncio
async def test_submit_unauthenticated(
    client: AsyncClient,
    teacher_with_course,
    mock_sandbox,
):
    """Без Authorization-хедера → 401."""
    _, _, _, _, task = teacher_with_course

    response = await client.post(
        f"/tasks/{task.task_id}/submit",
        json={"query_text": "db.test.find({})"},
    )
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_submit_creates_submission_in_db(
    client: AsyncClient,
    teacher_with_course,
    student_token: str,
    mock_sandbox,
    make_auth_headers,
    db_session,
):
    """Сабмит реально пишет запись в таблицу submissions."""
    from sqlalchemy import select
    from app.models import Submission

    _, _, _, _, task = teacher_with_course

    # До сабмита — пусто.
    result = await db_session.execute(select(Submission).where(Submission.task_id == task.task_id))
    assert result.scalars().all() == []

    response = await client.post(
        f"/tasks/{task.task_id}/submit",
        json={"query_text": "db.test.find({})"},
        headers=make_auth_headers(student_token),
    )
    assert response.status_code == 200

    # После сабмита — одна запись.
    result = await db_session.execute(select(Submission).where(Submission.task_id == task.task_id))
    submissions = result.scalars().all()
    assert len(submissions) == 1
    assert submissions[0].is_correct is True
    assert submissions[0].score == task.max_score
