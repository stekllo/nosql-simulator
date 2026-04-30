"""Тесты эндпоинтов /courses, /courses/{id}, /courses/lessons/{id}.

Покрытие: каталог возвращает прогресс, страница курса показывает
is_completed для уроков, страница урока — is_solved для заданий, 404 для
несуществующих, прогресс=0 у нового студента.
"""
import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_list_courses_with_progress_zero(
    client: AsyncClient,
    teacher_with_course,
    student_token: str,
    make_auth_headers,
):
    """Каталог: студент без сабмишенов — прогресс 0%, lessons_completed=0."""
    _, course, _, _, _ = teacher_with_course

    response = await client.get("/courses", headers=make_auth_headers(student_token))
    assert response.status_code == 200, response.text
    courses = response.json()

    target = next((c for c in courses if c["course_id"] == course.course_id), None)
    assert target is not None, f"Курс {course.course_id} должен быть в каталоге"

    assert target["progress"] is not None
    assert target["progress"]["lessons_total"] == 1
    assert target["progress"]["lessons_completed"] == 0
    assert target["progress"]["percent"] == 0
    assert target["progress"]["tasks_total"] == 1
    assert target["progress"]["tasks_solved"] == 0


@pytest.mark.asyncio
async def test_get_course_returns_modules_and_lessons(
    client: AsyncClient,
    teacher_with_course,
    student_token: str,
    make_auth_headers,
):
    """Страница курса возвращает все модули с уроками."""
    _, course, module, lesson, _ = teacher_with_course

    response = await client.get(
        f"/courses/{course.course_id}",
        headers=make_auth_headers(student_token),
    )
    assert response.status_code == 200, response.text
    body = response.json()

    assert body["course_id"] == course.course_id
    assert len(body["modules"]) == 1
    m = body["modules"][0]
    assert m["module_id"] == module.module_id
    assert len(m["lessons"]) == 1
    l = m["lessons"][0]
    assert l["lesson_id"] == lesson.lesson_id
    assert l["task_count"] == 1
    assert l["is_completed"] is False  # ещё не решено


@pytest.mark.asyncio
async def test_get_course_404(
    client: AsyncClient,
    student_token: str,
    make_auth_headers,
):
    """Несуществующий course_id → 404."""
    response = await client.get(
        "/courses/999999",
        headers=make_auth_headers(student_token),
    )
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_get_lesson_returns_tasks(
    client: AsyncClient,
    teacher_with_course,
    student_token: str,
    make_auth_headers,
):
    """Страница урока возвращает контент и задания с is_solved=False."""
    _, _, _, lesson, task = teacher_with_course

    response = await client.get(
        f"/courses/lessons/{lesson.lesson_id}",
        headers=make_auth_headers(student_token),
    )
    assert response.status_code == 200, response.text
    body = response.json()

    assert body["lesson_id"] == lesson.lesson_id
    assert body["title"] == lesson.title
    assert "Тестовый урок" in body["content_md"]
    assert len(body["tasks"]) == 1
    assert body["tasks"][0]["task_id"] == task.task_id
    assert body["tasks"][0]["is_solved"] is False
    # Поле is_completed (от Patch-Progress2) должно присутствовать.
    assert body["is_completed"] is False


@pytest.mark.asyncio
async def test_get_lesson_404(client: AsyncClient, student_token: str, make_auth_headers):
    """Несуществующий lesson_id → 404."""
    response = await client.get(
        "/courses/lessons/999999",
        headers=make_auth_headers(student_token),
    )
    assert response.status_code == 404
