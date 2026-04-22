# syntax=docker/dockerfile:1.7
FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

# Системные зависимости (для asyncpg и сборки колёс)
RUN apt-get update \
 && apt-get install -y --no-install-recommends gcc libpq-dev curl \
 && rm -rf /var/lib/apt/lists/*

# Установка Poetry
RUN pip install poetry==2.0.1 \
 && poetry config virtualenvs.create false

# Кэш слоя зависимостей (меняется редко)
COPY pyproject.toml ./
RUN poetry install --no-root --no-interaction

# Исходники монтируются как volume в docker-compose,
# но копию закладываем для prod-образа
COPY . .

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
