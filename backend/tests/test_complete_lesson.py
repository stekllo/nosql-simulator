"""Тесты эндпоинта POST /courses/lessons/{id}/complete.

Покрытие: первый POST создаёт LessonCompletion и возвращает
already_completed=False; повторный POST идемпотентен (already_completed=True);
несуществующий lesson_id → 404.
"""
import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_complete_lesson_first_time(
    client: AsyncClient,
    teacher_lesson_no_tasks,
    student_token: str,
    make_auth_headers,
):
    """Первый POST на /complete: 200, already_completed=False."""
    _, _, _, lesson = teacher_lesson_no_tasks

    response = await client.post(
        f"/courses/lessons/{lesson.lesson_id}/complete",
        headers=make_auth_headers(student_token),
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["lesson_id"] == lesson.lesson_id
    assert body["already_completed"] is False


@pytest.mark.asyncio
async def test_complete_lesson_idempotent(
    client: AsyncClient,
    teacher_lesson_no_tasks,
    student_token: str,
    make_auth_headers,
):
    """Повторный POST на тот же урок: 200, already_completed=True."""
    _, _, _, lesson = teacher_lesson_no_tasks

    first = await client.post(
        f"/courses/lessons/{lesson.lesson_id}/complete",
        headers=make_auth_headers(student_token),
    )
    assert first.status_code == 200
    assert first.json()["already_completed"] is False

    second = await client.post(
        f"/courses/lessons/{lesson.lesson_id}/complete",
        headers=make_auth_headers(student_token),
    )
    assert second.status_code == 200
    assert second.json()["already_completed"] is True
    assert second.json()["lesson_id"] == lesson.lesson_id


@pytest.mark.asyncio
async def test_complete_lesson_marks_as_completed_in_get(
    client: AsyncClient,
    teacher_lesson_no_tasks,
    student_token: str,
    make_auth_headers,
):
    """После /complete в GET /lessons/{id} должно быть is_completed=true."""
    _, _, _, lesson = teacher_lesson_no_tasks

    # Сначала проверяем что не пройден.
    before = await client.get(
        f"/courses/lessons/{lesson.lesson_id}",
        headers=make_auth_headers(student_token),
    )
    assert before.json()["is_completed"] is False

    # Помечаем.
    await client.post(
        f"/courses/lessons/{lesson.lesson_id}/complete",
        headers=make_auth_headers(student_token),
    )

    # Теперь должен быть пройден.
    after = await client.get(
        f"/courses/lessons/{lesson.lesson_id}",
        headers=make_auth_headers(student_token),
    )
    assert after.json()["is_completed"] is True


@pytest.mark.asyncio
async def test_complete_lesson_404(
    client: AsyncClient,
    student_token: str,
    make_auth_headers,
):
    """Несуществующий lesson_id → 404."""
    response = await client.post(
        "/courses/lessons/999999/complete",
        headers=make_auth_headers(student_token),
    )
    assert response.status_code == 404
