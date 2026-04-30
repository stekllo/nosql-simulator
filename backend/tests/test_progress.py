"""Тесты прогресса студента: после CORRECT-сабмита урок становится
пройденным, прогресс курса растёт.

Это интеграционные тесты, которые проверяют связь между submit и
courses-эндпоинтами через реальную БД.
"""
import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_correct_submit_makes_lesson_completed(
    client: AsyncClient,
    teacher_with_course,
    student_token: str,
    mock_sandbox,
    make_auth_headers,
):
    """После CORRECT-сабмита урок (с одним заданием) становится пройденным."""
    _, _, _, lesson, task = teacher_with_course

    # До сабмита урок не пройден.
    before = await client.get(
        f"/courses/lessons/{lesson.lesson_id}",
        headers=make_auth_headers(student_token),
    )
    assert before.json()["is_completed"] is False

    # Решаем задание правильно.
    submit_response = await client.post(
        f"/tasks/{task.task_id}/submit",
        json={"query_text": "db.test.find({})"},
        headers=make_auth_headers(student_token),
    )
    assert submit_response.json()["is_correct"] is True

    # После — урок пройден (потому что все задания решены).
    after = await client.get(
        f"/courses/lessons/{lesson.lesson_id}",
        headers=make_auth_headers(student_token),
    )
    assert after.json()["is_completed"] is True


@pytest.mark.asyncio
async def test_correct_submit_grows_course_progress(
    client: AsyncClient,
    teacher_with_course,
    student_token: str,
    mock_sandbox,
    make_auth_headers,
):
    """После решения единственного задания прогресс курса = 100%."""
    _, course, _, _, task = teacher_with_course

    # До: 0%
    before = await client.get("/courses", headers=make_auth_headers(student_token))
    target_before = next(c for c in before.json() if c["course_id"] == course.course_id)
    assert target_before["progress"]["percent"] == 0

    # Решаем.
    await client.post(
        f"/tasks/{task.task_id}/submit",
        json={"query_text": "db.test.find({})"},
        headers=make_auth_headers(student_token),
    )

    # После: 100%
    after = await client.get("/courses", headers=make_auth_headers(student_token))
    target_after = next(c for c in after.json() if c["course_id"] == course.course_id)
    assert target_after["progress"]["percent"] == 100
    assert target_after["progress"]["lessons_completed"] == 1
    assert target_after["progress"]["tasks_solved"] == 1
