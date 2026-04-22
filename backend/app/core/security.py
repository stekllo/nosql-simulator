"""Криптография и утилиты авторизации.

- Хэширование паролей через чистый bcrypt (без passlib-прослойки).
- Генерация и проверка JWT access-токенов.
"""
from datetime import datetime, timedelta, timezone
from typing import Any

import bcrypt
from jose import JWTError, jwt

from app.core.config import settings


# ============ Пароли ============

# bcrypt принимает не более 72 байт — урезаем длинные пароли.
_BCRYPT_MAX_BYTES = 72


def _truncate(password: str) -> bytes:
    return password.encode("utf-8")[:_BCRYPT_MAX_BYTES]


def hash_password(password: str) -> str:
    """Хэширует пароль в строку вида '$2b$...'."""
    return bcrypt.hashpw(_truncate(password), bcrypt.gensalt()).decode("utf-8")


def verify_password(password: str, hashed: str) -> bool:
    """Проверяет plaintext-пароль против сохранённого хэша."""
    try:
        return bcrypt.checkpw(_truncate(password), hashed.encode("utf-8"))
    except (ValueError, TypeError):
        return False


# ============ JWT-токены ============

def create_access_token(
    subject: str | int,
    extra: dict[str, Any] | None = None,
    expires_in: timedelta | None = None,
) -> str:
    """Создаёт подписанный JWT access-токен.

    subject  — user_id пользователя (sub claim).
    extra    — дополнительные поля (роль, login и т. п.).
    """
    to_encode: dict[str, Any] = {"sub": str(subject)}
    if extra:
        to_encode.update(extra)

    expire = datetime.now(timezone.utc) + (
        expires_in or timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    )
    to_encode["exp"] = expire

    return jwt.encode(to_encode, settings.JWT_SECRET, algorithm=settings.JWT_ALGORITHM)


def decode_access_token(token: str) -> dict[str, Any]:
    """Декодирует JWT и возвращает payload. Бросает JWTError при ошибке."""
    return jwt.decode(token, settings.JWT_SECRET, algorithms=[settings.JWT_ALGORITHM])


__all__ = [
    "create_access_token",
    "decode_access_token",
    "hash_password",
    "verify_password",
    "JWTError",
]
