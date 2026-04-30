"""Программный запуск миграций Alembic при старте приложения.

Вместо запуска `alembic upgrade head` руками после `docker compose up`,
эта функция вызывается из FastAPI lifespan на старте, и БД всегда
актуальна без забот.

Реализация делает два важных дела:
  1. **Retry с backoff** — если Postgres ещё не готов принимать DDL
     (контейнер проходит healthcheck чуть раньше, чем реально готов),
     мы ждём и пробуем ещё раз. Максимум 5 попыток за ~30 секунд.
  2. **Использует Alembic как библиотеку**, а не subprocess. Так что
     мы не зависим от наличия alembic в PATH контейнера и не платим
     за лишний процесс.
"""
from __future__ import annotations

import asyncio
import logging
from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy.exc import OperationalError

from app.core.config import settings

logger = logging.getLogger(__name__)

# Путь к alembic.ini относительно корня backend-приложения.
# В контейнере backend смонтирован в /app, alembic.ini лежит в /app/alembic.ini.
_ALEMBIC_INI_PATH = Path(__file__).resolve().parent.parent.parent / "alembic.ini"

# Параметры retry: первая попытка через 1 секунду, потом 2, 4, 8, 16 — максимум.
_MAX_ATTEMPTS = 5
_INITIAL_BACKOFF_SEC = 1.0


def _run_upgrade_sync() -> None:
    """Синхронный запуск `alembic upgrade head`.

    Alembic-команды все синхронные, поэтому из async-кода вызываем
    через asyncio.to_thread.
    """
    if not _ALEMBIC_INI_PATH.exists():
        raise FileNotFoundError(
            f"Не найден alembic.ini по пути {_ALEMBIC_INI_PATH}. "
            "Проверьте структуру backend-контейнера."
        )

    cfg = Config(str(_ALEMBIC_INI_PATH))
    # На всякий случай пробрасываем DATABASE_URL — env.py его всё равно
    # подставит из settings, но дублирование не вредит и делает поведение
    # более явным.
    cfg.set_main_option("sqlalchemy.url", settings.DATABASE_URL)
    command.upgrade(cfg, "head")


async def run_migrations_on_startup() -> None:
    """Применяет все непримененные миграции с retry-логикой.

    Бросает RuntimeError, если все попытки не удались — чтобы FastAPI
    не запустился на сломанной/неполной БД.
    """
    backoff = _INITIAL_BACKOFF_SEC
    last_error: Exception | None = None

    for attempt in range(1, _MAX_ATTEMPTS + 1):
        try:
            logger.info(
                "Running database migrations (attempt %d/%d)...",
                attempt, _MAX_ATTEMPTS,
            )
            await asyncio.to_thread(_run_upgrade_sync)
            logger.info("Database migrations applied successfully.")
            return
        except OperationalError as exc:
            # Postgres ещё не готов — типичная ошибка "connection refused"
            # или "database is starting up".
            last_error = exc
            logger.warning(
                "Database not ready yet (attempt %d/%d): %s. Retrying in %.1f s...",
                attempt, _MAX_ATTEMPTS, exc.orig if exc.orig else exc, backoff,
            )
        except Exception as exc:
            # Любая другая ошибка миграции — не ретраим, это баг в коде или
            # SQL-конфликт, который ретраи не решат.
            logger.error("Migration failed with non-retryable error: %s", exc)
            raise RuntimeError(f"Migration error: {exc}") from exc

        if attempt < _MAX_ATTEMPTS:
            await asyncio.sleep(backoff)
            backoff = min(backoff * 2, 16.0)

    # Все попытки исчерпаны.
    raise RuntimeError(
        f"Could not apply migrations after {_MAX_ATTEMPTS} attempts. "
        f"Last error: {last_error}"
    )
