"""Тесты эндпоинтов /admin/users.

Покрытие: список доступен админу, недоступен студенту, фильтр по роли,
смена роли работает, нельзя сменить собственную роль, 404 на
несуществующего пользователя.
"""
import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_list_users_as_admin(
    client: AsyncClient,
    admin_token: str,
    student_user,
    teacher_user,
    make_auth_headers,
):
    """Админ видит всех пользователей (admin + student + teacher)."""
    response = await client.get(
        "/admin/users",
        headers=make_auth_headers(admin_token),
    )
    assert response.status_code == 200, response.text
    body = response.json()

    # У нас как минимум 3 пользователя: admin, student, teacher.
    assert body["total"] >= 3
    logins = {u["login"] for u in body["users"]}
    assert "test_admin"   in logins
    assert "test_student" in logins
    assert "test_teacher" in logins

    # by_role: счётчики
    assert body["by_role"]["admin"]   >= 1
    assert body["by_role"]["student"] >= 1
    assert body["by_role"]["teacher"] >= 1


@pytest.mark.asyncio
async def test_list_users_filter_by_role(
    client: AsyncClient,
    admin_token: str,
    student_user,
    teacher_user,
    make_auth_headers,
):
    """Фильтр ?role=student возвращает только студентов."""
    response = await client.get(
        "/admin/users?role=student",
        headers=make_auth_headers(admin_token),
    )
    assert response.status_code == 200
    body = response.json()
    for u in body["users"]:
        assert u["role"] == "student"


@pytest.mark.asyncio
async def test_list_users_forbidden_for_student(
    client: AsyncClient,
    student_token: str,
    make_auth_headers,
):
    """Студент → 403, не имеет доступа к /admin/users."""
    response = await client.get(
        "/admin/users",
        headers=make_auth_headers(student_token),
    )
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_list_users_forbidden_for_teacher(
    client: AsyncClient,
    teacher_token: str,
    make_auth_headers,
):
    """Препод → 403."""
    response = await client.get(
        "/admin/users",
        headers=make_auth_headers(teacher_token),
    )
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_change_role_student_to_teacher(
    client: AsyncClient,
    admin_token: str,
    student_user,
    make_auth_headers,
):
    """Админ меняет student → teacher → ok, новая роль в ответе."""
    response = await client.patch(
        f"/admin/users/{student_user.user_id}/role",
        json={"role": "teacher"},
        headers=make_auth_headers(admin_token),
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["user_id"]  == student_user.user_id
    assert body["old_role"] == "student"
    assert body["new_role"] == "teacher"


@pytest.mark.asyncio
async def test_change_own_role_forbidden(
    client: AsyncClient,
    admin_token: str,
    admin_user,
    make_auth_headers,
):
    """Админ не может сменить собственную роль (защита от самоблокировки)."""
    response = await client.patch(
        f"/admin/users/{admin_user.user_id}/role",
        json={"role": "student"},
        headers=make_auth_headers(admin_token),
    )
    assert response.status_code == 400


@pytest.mark.asyncio
async def test_change_role_404(
    client: AsyncClient,
    admin_token: str,
    make_auth_headers,
):
    """Несуществующий user_id → 404."""
    response = await client.patch(
        "/admin/users/999999/role",
        json={"role": "teacher"},
        headers=make_auth_headers(admin_token),
    )
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_change_role_idempotent(
    client: AsyncClient,
    admin_token: str,
    student_user,
    make_auth_headers,
):
    """Назначение той же роли (student → student) не падает, возвращает ту же роль."""
    response = await client.patch(
        f"/admin/users/{student_user.user_id}/role",
        json={"role": "student"},
        headers=make_auth_headers(admin_token),
    )
    assert response.status_code == 200
    body = response.json()
    assert body["old_role"] == body["new_role"] == "student"
