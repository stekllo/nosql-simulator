"""Pydantic-схемы для запросов и ответов в блоке /auth."""
from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field

from app.models import UserRole


class RegisterRequest(BaseModel):
    """Тело запроса на регистрацию."""

    login:        str = Field(min_length=3, max_length=64, pattern=r"^[a-zA-Z0-9_.-]+$")
    email:        EmailStr
    password:     str = Field(min_length=6, max_length=128)
    display_name: str | None = Field(default=None, max_length=128)


class LoginResponse(BaseModel):
    """Ответ эндпоинтов /auth/login и /auth/register."""

    access_token: str
    token_type:   str = "bearer"


class UserOut(BaseModel):
    """Публичные данные пользователя (без пароля)."""

    model_config = ConfigDict(from_attributes=True)

    user_id:      int
    login:        str
    email:        EmailStr
    display_name: str | None
    role:         UserRole
    created_at:   datetime
