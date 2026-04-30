"""Глобальные настройки приложения (переменные окружения)."""
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Все настройки берутся из ENV (см. docker-compose.yml)."""

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    APP_NAME: str = "NoSQL Simulator"
    LOG_LEVEL: str = "INFO"

    # Метаданные
    DATABASE_URL: str = "postgresql+asyncpg://sim:sim@postgres:5432/sim"

    # Автоматические миграции при старте FastAPI.
    # На прод можно выставить false и запускать `alembic upgrade head` вручную
    # через CI/CD-пайплайн или предзапусковой скрипт. По дефолту — true,
    # потому что так удобнее и локально, и на VPS-деплое: backend сам
    # подтягивает миграции после `docker compose up`.
    RUN_MIGRATIONS_ON_STARTUP: bool = True

    # NoSQL песочница
    MONGO_URL:         str = "mongodb://mongo:27017"
    REDIS_SANDBOX_URL: str = "redis://redis-sandbox:6379"
    CASSANDRA_HOST:    str = "cassandra"
    NEO4J_URL:         str = "bolt://neo4j:7687"
    NEO4J_AUTH:        str = "neo4j:changeme123"

    # Брокер
    REDIS_BROKER_URL: str = "redis://redis-broker:6379/0"

    # Auth
    JWT_SECRET:                  str = "dev-only-change-me"
    JWT_ALGORITHM:               str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 15


settings = Settings()
