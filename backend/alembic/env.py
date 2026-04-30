"""Alembic runtime — умеет работать с async SQLAlchemy-engine."""
import asyncio
from logging.config import fileConfig

from alembic import context
from sqlalchemy import pool
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import async_engine_from_config

from app.core.config import settings
from app.db import Base
# Импорт моделей нужен, чтобы metadata узнала про все таблицы.
from app.models import (  # noqa: F401
    Achievement, Course, Lesson, LessonCompletion, Module, Progress,
    Submission, Task, User, UserAchievement,
)

config = context.config

# Подставляем URL из настроек (чтобы не дублировать в alembic.ini).
config.set_main_option("sqlalchemy.url", settings.DATABASE_URL)

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    """Запуск миграций без подключения к БД (генерация SQL)."""
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url              = url,
        target_metadata  = target_metadata,
        literal_binds    = True,
        dialect_opts     = {"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection: Connection) -> None:
    context.configure(connection=connection, target_metadata=target_metadata)
    with context.begin_transaction():
        context.run_migrations()


async def run_migrations_online() -> None:
    """Обычный запуск — с подключением к БД."""
    connectable = async_engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix  = "sqlalchemy.",
        poolclass = pool.NullPool,
    )
    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)
    await connectable.dispose()


if context.is_offline_mode():
    run_migrations_offline()
else:
    asyncio.run(run_migrations_online())
