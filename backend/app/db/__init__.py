"""Подключение к базе данных и базовый ORM-класс."""
from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

from app.core.config import settings


class Base(DeclarativeBase):
    """Базовый класс для всех SQLAlchemy-моделей."""


# Глобальный engine для приложения.
engine = create_async_engine(
    settings.DATABASE_URL,
    echo         = False,         # True для отладки SQL в логах
    pool_pre_ping = True,          # Проверять соединение перед использованием
    pool_size     = 5,
    max_overflow  = 10,
)

AsyncSessionLocal = async_sessionmaker(
    bind            = engine,
    class_          = AsyncSession,
    expire_on_commit = False,
    autoflush        = False,
)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """FastAPI-зависимость: даёт свежую сессию на каждый запрос."""
    async with AsyncSessionLocal() as session:
        try:
            yield session
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()
