"""Эндпоинты авторизации: регистрация, вход, профиль."""
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import CurrentUser
from app.core.security import create_access_token, hash_password, verify_password
from app.db import get_db
from app.models import User, UserRole
from app.schemas.auth import LoginResponse, RegisterRequest, UserOut

router = APIRouter()


@router.post("/register", response_model=LoginResponse, status_code=status.HTTP_201_CREATED)
async def register(
    data:    RegisterRequest,
    session: Annotated[AsyncSession, Depends(get_db)],
) -> LoginResponse:
    """Регистрирует нового пользователя с ролью student и сразу выдаёт токен."""
    # Проверяем, что логин/email не заняты.
    existing = await session.execute(
        select(User).where((User.login == data.login) | (User.email == data.email))
    )
    if existing.scalar_one_or_none() is not None:
        raise HTTPException(
            status_code = status.HTTP_409_CONFLICT,
            detail      = "Пользователь с таким логином или email уже существует",
        )

    user = User(
        login         = data.login,
        email         = data.email,
        password_hash = hash_password(data.password),
        display_name  = data.display_name or data.login,
        role          = UserRole.STUDENT,
    )
    session.add(user)
    await session.commit()
    await session.refresh(user)

    token = create_access_token(
        subject = user.user_id,
        extra   = {"role": user.role.value, "login": user.login},
    )
    return LoginResponse(access_token=token)


@router.post("/login", response_model=LoginResponse)
async def login(
    form_data: Annotated[OAuth2PasswordRequestForm, Depends()],
    session:   Annotated[AsyncSession, Depends(get_db)],
) -> LoginResponse:
    """Принимает login + password (form-data), возвращает access_token.

    Поле username в форме трактуется как наш login.
    """
    result = await session.execute(
        select(User).where(User.login == form_data.username)
    )
    user = result.scalar_one_or_none()

    if user is None or not verify_password(form_data.password, user.password_hash):
        raise HTTPException(
            status_code = status.HTTP_401_UNAUTHORIZED,
            detail      = "Неверный логин или пароль",
            headers     = {"WWW-Authenticate": "Bearer"},
        )

    # Обновляем время последнего входа.
    user.last_login_at = func.now()
    await session.commit()

    token = create_access_token(
        subject = user.user_id,
        extra   = {"role": user.role.value, "login": user.login},
    )
    return LoginResponse(access_token=token)


@router.get("/me", response_model=UserOut)
async def me(user: CurrentUser) -> User:
    """Возвращает профиль авторизованного пользователя."""
    return user
