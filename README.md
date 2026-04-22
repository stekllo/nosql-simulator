# NoSQL Simulator

Обучающий симулятор для изучения NoSQL баз данных.
Дипломный проект, ВКР Аджема Юрия.

## Стек

- **Backend**: Python 3.12 + FastAPI + SQLAlchemy 2 + Alembic
- **Frontend**: React 18 + TypeScript + Vite + Tailwind CSS + Monaco Editor
- **Хранилище метаданных**: PostgreSQL 15
- **NoSQL-песочница**: MongoDB 7, Redis 7, Cassandra 4, Neo4j 5
- **Брокер задач**: Redis 7 (отдельный инстанс)
- **Оркестрация**: Docker Compose

## Структура репозитория

```
nosql-sim/
├── backend/          # FastAPI приложение
│   ├── app/
│   │   ├── api/      # REST-эндпоинты
│   │   ├── core/     # Конфиг, security, deps
│   │   ├── models/   # SQLAlchemy модели
│   │   └── main.py   # Точка входа
│   ├── tests/
│   └── pyproject.toml
├── frontend/         # React + Vite приложение
│   ├── src/
│   ├── package.json
│   └── vite.config.ts
├── infra/            # Скрипты инициализации СУБД
├── docs/             # Документация и заметки
├── scripts/          # Утилиты (seed, бэкап и т.п.)
├── docker-compose.yml
└── Makefile
```

## Первый запуск

Открой PowerShell или cmd в корне репозитория и выполни:

```cmd
docker compose up
```

Первый запуск долгий (5–10 минут): Docker качает образы (~3 ГБ).
Когда увидишь в логах строку `Uvicorn running on http://0.0.0.0:8000`,
открой в браузере:

- **Frontend**: http://localhost:3000
- **Backend API**: http://localhost:8000/docs (Swagger UI)
- **Health check**: http://localhost:8000/health

Чтобы остановить: `Ctrl+C` в окне с docker compose, потом `docker compose down`.

## Что уже работает

- ✅ FastAPI поднимается, отдаёт `/health` со статусом всех СУБД
- ✅ React-фронтенд собирается через Vite, отображает заглушку
- ✅ Все 5 контейнеров СУБД запускаются и проходят healthcheck
- ✅ Hot reload и для бэкенда, и для фронтенда

## Что предстоит сделать

Поэтапный план реализации:

1. Авторизация (регистрация, вход, JWT)
2. Модели курсов / модулей / уроков / заданий + миграции Alembic
3. Каталог курсов (страница + API)
4. Просмотр урока (Markdown-рендерер)
5. Query Runner для MongoDB (выполнение запроса в эфемерной БД)
6. Submission Evaluator (сравнение с эталоном)
7. Личный кабинет студента (статистика, прогресс)
8. Конструктор заданий (для роли teacher)
9. Query Runner для Redis / Cassandra / Neo4j
10. Полировка, тесты, документация

## Полезные команды

| Команда | Что делает |
|---|---|
| `docker compose up` | Поднять всё |
| `docker compose up -d` | Поднять в фоне |
| `docker compose down` | Остановить и удалить контейнеры |
| `docker compose down -v` | То же + удалить volumes (сбросить БД) |
| `docker compose logs -f backend` | Смотреть логи бэкенда |
| `docker compose exec backend bash` | Зайти внутрь контейнера бэкенда |
| `docker compose exec postgres psql -U sim -d sim` | Открыть psql |
