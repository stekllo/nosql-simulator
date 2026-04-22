"""FastAPI-зависимости для работы с текущим пользователем и ролями."""
from typing import Annotated

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import decode_access_token
from app.db import get_db
from app.models import User, UserRole


# tokenUrl указывает, где в Swagger UI найти форму получения токена.
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login")


async def get_current_user(
    token:   Annotated[str, Depends(oauth2_scheme)],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> User:
    """Достаёт пользователя по access-токену из заголовка Authorization."""
    credentials_exc = HTTPException(
        status_code = status.HTTP_401_UNAUTHORIZED,
        detail      = "Не удалось проверить токен",
        headers     = {"WWW-Authenticate": "Bearer"},
    )

    try:
        payload = decode_access_token(token)
        user_id = payload.get("sub")
        if user_id is None:
            raise credentials_exc
    except JWTError:
        raise credentials_exc

    result = await session.execute(select(User).where(User.user_id == int(user_id)))
    user   = result.scalar_one_or_none()
    if user is None:
        raise credentials_exc
    return user


def require_role(*allowed: UserRole):
    """Фабрика зависимостей: пускать только пользователей с указанными ролями."""

    async def _check(
        user: Annotated[User, Depends(get_current_user)],
    ) -> User:
        if user.role not in allowed:
            raise HTTPException(
                status_code = status.HTTP_403_FORBIDDEN,
                detail      = "Недостаточно прав",
            )
        return user

    return _check


CurrentUser = Annotated[User, Depends(get_current_user)]
