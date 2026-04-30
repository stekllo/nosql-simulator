"""Тесты эндпоинтов /auth/login и /auth/register.

Покрытие: успешный логин, неправильный пароль, несуществующий пользователь,
успешная регистрация, дубликат логина/email.
"""
import pytest
from httpx import AsyncClient

from app.models import User


# ---------- Login ----------

@pytest.mark.asyncio
async def test_login_correct_password(client: AsyncClient, student_user: User):
    """Корректный логин/пароль → 200 + access_token."""
    response = await client.post(
        "/auth/login",
        data={"username": "test_student", "password": "test_student_pass"},
    )
    assert response.status_code == 200
    body = response.json()
    assert "access_token" in body
    assert body["token_type"].lower() == "bearer"
    # Токен — непустая строка JWT-подобной структуры (3 части через точки).
    assert body["access_token"].count(".") == 2


@pytest.mark.asyncio
async def test_login_wrong_password(client: AsyncClient, student_user: User):
    """Существующий логин, но неправильный пароль → 401."""
    response = await client.post(
        "/auth/login",
        data={"username": "test_student", "password": "wrong-password"},
    )
    assert response.status_code == 401
    assert "access_token" not in response.json()


@pytest.mark.asyncio
async def test_login_nonexistent_user(client: AsyncClient):
    """Несуществующий пользователь → 401 (не 404 — чтобы не палить
    какие логины существуют)."""
    response = await client.post(
        "/auth/login",
        data={"username": "ghost", "password": "anything"},
    )
    assert response.status_code == 401


# ---------- Register ----------

@pytest.mark.asyncio
async def test_register_new_user(client: AsyncClient):
    """Регистрация нового пользователя → 200/201 + token, роль = student."""
    response = await client.post(
        "/auth/register",
        json={
            "login":        "newuser",
            "email":        "newuser@example.com",
            "password":     "secret123",
            "display_name": "Новый пользователь",
        },
    )
    assert response.status_code in (200, 201), response.text
    body = response.json()
    assert "access_token" in body

    # Проверяем что токен работает — можно сразу запросить /auth/me.
    headers = {"Authorization": f"Bearer {body['access_token']}"}
    me_response = await client.get("/auth/me", headers=headers)
    assert me_response.status_code == 200
    me = me_response.json()
    assert me["login"] == "newuser"
    assert me["role"] == "student"  # хардкод в auth.py — все новые student


@pytest.mark.asyncio
async def test_register_duplicate_login(client: AsyncClient, student_user: User):
    """Регистрация с уже занятым логином → 409."""
    response = await client.post(
        "/auth/register",
        json={
            "login":    "test_student",  # уже занят фикстурой
            "email":    "different@example.com",
            "password": "secret123",
        },
    )
    assert response.status_code == 409


@pytest.mark.asyncio
async def test_register_duplicate_email(client: AsyncClient, student_user: User):
    """Регистрация с уже занятым email → 409."""
    response = await client.post(
        "/auth/register",
        json={
            "login":    "another_login",
            "email":    "student@example.com",   # уже занят фикстурой
            "password": "secret123",
        },
    )
    assert response.status_code == 409
