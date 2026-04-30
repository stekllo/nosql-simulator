"""Общие pytest-фикстуры для интеграционных тестов.

Архитектура:

  - Каждый тест работает с **реальной** Postgres БД, той же схемой,
    что и production (через Base.metadata.create_all). SQLite-альтернатива
    не используется — asyncpg в неё не умеет, и поведение PostgreSQL-
    специфики (JSONB, ENUM) не воспроизвести.

  - Изоляция между тестами — через **savepoint-pattern**: внешняя
    транзакция, внутри session.commit() работает как nested savepoint.
    После теста внешняя транзакция откатывается, все изменения исчезают.

  - Сессия теста подменяет dependency `get_db` в FastAPI, так что
    эндпоинты внутри теста видят ту же транзакцию, что и сам тест.

  - sandbox-runner (Mongo/Redis/Cassandra/Neo4j) **замокан** через
    monkeypatch. Это значит тесты не требуют живых NoSQL-сервисов.

Запуск:

    docker compose exec backend pytest -v

или локально:

    cd backend
    TEST_DATABASE_URL="postgresql+asyncpg://sim:sim@localhost:5432/sim_test" \
        poetry run pytest -v
"""
from __future__ import annotations

import os
from collections.abc import AsyncGenerator
from typing import Any

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker, create_async_engine

from app.core.config import settings
from app.core.security import hash_password
from app.db import Base, get_db
from app.main import app
from app.models import User, UserRole


# ---------- Конфигурация тестовой БД ----------

# Берём тот же сервер Postgres, что dev, но другая БД (sim_test).
# Если TEST_DATABASE_URL задан явно — используем его (для локального запуска
# без docker-compose).
def _build_test_database_url() -> str:
    explicit = os.environ.get("TEST_DATABASE_URL")
    if explicit:
        return explicit
    # Берём dev-DSN и подменяем имя БД на _test.
    dev_url = settings.DATABASE_URL
    # postgresql+asyncpg://sim:sim@postgres:5432/sim → ...:5432/sim_test
    if dev_url.endswith("/sim"):
        return dev_url.rsplit("/", 1)[0] + "/sim_test"
    raise RuntimeError(
        "Не удалось определить TEST_DATABASE_URL. Укажите его в env."
    )


TEST_DATABASE_URL = _build_test_database_url()


# ---------- Создание/удаление тестовой БД ----------

async def _ensure_test_database() -> None:
    """Создаёт `sim_test`, если её ещё нет.

    Подключаемся к системной БД `postgres` (не `sim`), чтобы выполнить
    `CREATE DATABASE`.
    """
    # Извлекаем имя тестовой БД из URL.
    test_db_name = TEST_DATABASE_URL.rsplit("/", 1)[1]
    admin_url = TEST_DATABASE_URL.rsplit("/", 1)[0] + "/postgres"

    admin_engine = create_async_engine(admin_url, isolation_level="AUTOCOMMIT")
    try:
        async with admin_engine.connect() as conn:
            exists = await conn.execute(
                text("SELECT 1 FROM pg_database WHERE datname = :n"),
                {"n": test_db_name},
            )
            if exists.scalar() is None:
                # Имя БД нельзя параметризовать — но мы валидируем что
                # это литерал из конфига, не пользовательский ввод.
                await conn.execute(text(f'CREATE DATABASE "{test_db_name}"'))
    finally:
        await admin_engine.dispose()


@pytest_asyncio.fixture
async def test_engine() -> AsyncGenerator[AsyncEngine, None]:
    """Engine для тестовой БД, создаётся для каждого теста.

    Function-scope (вместо session-scope) — это нужно из-за pytest-asyncio
    в режиме auto, который создаёт новый event loop на каждый тест. Если
    engine из session-scope, его соединения привязаны к старому loop'у —
    получаем "Task got Future attached to a different loop".

    Function-scope даёт ~3-5 секунд оверхеда на 23 теста — приемлемо.
    """
    await _ensure_test_database()

    engine = create_async_engine(TEST_DATABASE_URL, echo=False)

    # В моделях ENUM-типы (UserRole, NoSQLType, ProgressStatus, SubmissionStatus)
    # объявлены с create_type=False — их создаёт миграция Alembic вручную.
    # В тестах мы не запускаем Alembic, поэтому эти типы нужно создать
    # руками перед metadata.create_all (иначе CREATE TABLE упадёт с
    # 'type "user_role" does not exist').
    enum_create_sql = [
        "DROP TYPE IF EXISTS user_role         CASCADE",
        "DROP TYPE IF EXISTS nosql_type        CASCADE",
        "DROP TYPE IF EXISTS progress_status   CASCADE",
        "DROP TYPE IF EXISTS submission_status CASCADE",
        "CREATE TYPE user_role         AS ENUM ('student', 'teacher', 'admin')",
        "CREATE TYPE nosql_type        AS ENUM ('document', 'key_value', 'column', 'graph', 'mixed')",
        "CREATE TYPE progress_status   AS ENUM ('started', 'in_progress', 'completed')",
        "CREATE TYPE submission_status AS ENUM ('pending', 'correct', 'wrong', 'timeout')",
    ]

    async with engine.begin() as conn:
        # 1. Сносим прошлую схему (от прошлого теста или прошлого прогона).
        await conn.run_sync(Base.metadata.drop_all)
        # 2. Создаём ENUM-типы вручную.
        for sql in enum_create_sql:
            await conn.execute(text(sql))
        # 3. Создаём таблицы.
        await conn.run_sync(Base.metadata.create_all)

    yield engine

    await engine.dispose()


@pytest_asyncio.fixture
async def db_session(test_engine: AsyncEngine) -> AsyncGenerator[AsyncSession, None]:
    """Свежая сессия в транзакции для каждого теста.

    Используется savepoint-pattern: внешняя транзакция, внутри — nested
    savepoint. Если эндпоинт делает session.commit() — это коммитит
    savepoint, но внешняя транзакция всё равно откатывается в finally,
    унося все изменения.

    Это стандартный SQLAlchemy-pattern для тестирования с реальной БД,
    официально документированный.
    """
    from sqlalchemy import event

    async with test_engine.connect() as connection:
        outer_transaction = await connection.begin()

        sessionmaker = async_sessionmaker(
            bind=connection,
            class_=AsyncSession,
            expire_on_commit=False,
            join_transaction_mode="create_savepoint",
        )

        async with sessionmaker() as session:
            try:
                yield session
            finally:
                await session.close()
                # Внешняя транзакция: всё что было — отменяется.
                if outer_transaction.is_active:
                    await outer_transaction.rollback()


# ---------- Подмена FastAPI-dependency ----------

@pytest_asyncio.fixture
async def client(db_session: AsyncSession) -> AsyncGenerator[AsyncClient, None]:
    """HTTP-клиент к FastAPI с подменённым get_db.

    Эндпоинты внутри теста используют ту же сессию-в-транзакции, что и
    сам тест — поэтому изменения, сделанные в тесте через ORM, сразу
    видны в API.
    """
    async def _get_db_override() -> AsyncGenerator[AsyncSession, None]:
        # ВАЖНО: yield той же сессии, что у теста. Не создавать новую.
        yield db_session

    app.dependency_overrides[get_db] = _get_db_override
    try:
        async with AsyncClient(
            transport = ASGITransport(app=app),
            base_url  = "http://test",
        ) as c:
            yield c
    finally:
        app.dependency_overrides.pop(get_db, None)


# ---------- Мок sandbox-runner'а ----------

class MockSandbox:
    """Хелпер для мокинга execute_for_task в тестах.

    По умолчанию все запросы возвращают одинаковый успешный результат —
    тогда submit студента совпадает с эталоном и засчитывается.

    Можно через set_outcome(query_text → outcome) задать разные ответы
    для разных текстов запросов, чтобы протестировать wrong-кейсы.
    """
    def __init__(self):
        from app.sandbox.dispatch import SandboxResult
        # Тип результата (через duck-typing — просто dataclass-like с .ok, .result, .error, .duration_ms)
        self._default_result = self._make_outcome(ok=True, result=[{"x": 1}])
        self._by_query: dict[str, Any] = {}

    @staticmethod
    def _make_outcome(*, ok: bool, result: Any = None, error: str | None = None, duration_ms: int = 5):
        # Используем простую namespace-структуру, совместимую с ExecutionResult
        # из mongo_runner / redis_runner / cassandra_runner / neo4j_runner.
        from types import SimpleNamespace
        return SimpleNamespace(
            ok          = ok,
            result      = result,
            error       = error,
            duration_ms = duration_ms,
        )

    def set_outcome(self, query_text: str, *, ok: bool, result: Any = None, error: str | None = None):
        """Зарегистрировать конкретный outcome для конкретного текста запроса."""
        self._by_query[query_text] = self._make_outcome(ok=ok, result=result, error=error)

    def set_default(self, *, ok: bool, result: Any = None, error: str | None = None):
        self._default_result = self._make_outcome(ok=ok, result=result, error=error)

    async def execute(self, db_type, fixture, query_text):
        return self._by_query.get(query_text, self._default_result)


@pytest.fixture
def mock_sandbox(monkeypatch) -> MockSandbox:
    """Подменяет execute_for_task на mock.

    Используется в тестах submit/run, где не нужно реально запускать
    Mongo/Redis/Cassandra/Neo4j.
    """
    sandbox = MockSandbox()
    # Патчим в обоих местах — где импортирован и где определён.
    monkeypatch.setattr("app.api.tasks.execute_for_task", sandbox.execute)
    monkeypatch.setattr("app.api.builder.execute_for_task", sandbox.execute, raising=False)
    return sandbox


# ---------- Хелперы создания пользователей ----------

@pytest_asyncio.fixture
async def student_user(db_session: AsyncSession) -> User:
    """Создаёт студента с фиксированным паролем 'test_student_pass'."""
    user = User(
        login         = "test_student",
        email         = "student@example.com",
        password_hash = hash_password("test_student_pass"),
        display_name  = "Тестовый студент",
        role          = UserRole.STUDENT,
    )
    db_session.add(user)
    await db_session.flush()  # получаем user_id, но без commit
    return user


@pytest_asyncio.fixture
async def teacher_user(db_session: AsyncSession) -> User:
    user = User(
        login         = "test_teacher",
        email         = "teacher@example.com",
        password_hash = hash_password("test_teacher_pass"),
        display_name  = "Тестовый преподаватель",
        role          = UserRole.TEACHER,
    )
    db_session.add(user)
    await db_session.flush()
    return user


@pytest_asyncio.fixture
async def admin_user(db_session: AsyncSession) -> User:
    user = User(
        login         = "test_admin",
        email         = "admin@example.com",
        password_hash = hash_password("test_admin_pass"),
        display_name  = "Тестовый админ",
        role          = UserRole.ADMIN,
    )
    db_session.add(user)
    await db_session.flush()
    return user


# ---------- Хелперы получения токена ----------

async def _login_and_get_token(client: AsyncClient, login: str, password: str) -> str:
    """Логинится и возвращает Bearer-токен."""
    response = await client.post(
        "/auth/login",
        data={"username": login, "password": password},
    )
    assert response.status_code == 200, f"Login failed: {response.text}"
    return response.json()["access_token"]


@pytest_asyncio.fixture
async def student_token(client: AsyncClient, student_user: User) -> str:
    return await _login_and_get_token(client, "test_student", "test_student_pass")


@pytest_asyncio.fixture
async def teacher_token(client: AsyncClient, teacher_user: User) -> str:
    return await _login_and_get_token(client, "test_teacher", "test_teacher_pass")


@pytest_asyncio.fixture
async def admin_token(client: AsyncClient, admin_user: User) -> str:
    return await _login_and_get_token(client, "test_admin", "test_admin_pass")


def auth_headers(token: str) -> dict[str, str]:
    """Хедер Authorization для запросов от имени пользователя."""
    return {"Authorization": f"Bearer {token}"}


# Экспортируем как фикстуру, чтобы тесты могли импортировать через conftest.
@pytest.fixture
def make_auth_headers():
    """Помощник: make_auth_headers(token) → {'Authorization': '...'}."""
    return auth_headers


# ---------- Фикстуры тестового контента (курс/модуль/урок/задание) ----------

@pytest_asyncio.fixture
async def teacher_with_course(db_session: AsyncSession, teacher_user: User):
    """Создаёт курс, принадлежащий teacher_user, с одним модулем,
    одним уроком и одним заданием.

    Возвращает кортеж (teacher, course, module, lesson, task).
    """
    from app.models import Course, Module, Lesson
    from app.models.submission import Task
    from app.models.course import NoSQLType

    course = Course(
        title       = "Test Course",
        description = "Тестовый курс",
        nosql_type  = NoSQLType.DOCUMENT,
        author_id   = teacher_user.user_id,
        difficulty  = 1,
    )
    db_session.add(course)
    await db_session.flush()

    module = Module(
        title       = "Тестовый модуль",
        description = "Описание модуля",
        course_id   = course.course_id,
        order_num   = 1,
    )
    db_session.add(module)
    await db_session.flush()

    lesson = Lesson(
        title        = "Тестовый урок",
        content_md   = "# Тестовый урок\n\nКонтент урока.",
        module_id    = module.module_id,
        order_num    = 1,
        duration_min = 10,
    )
    db_session.add(lesson)
    await db_session.flush()

    task = Task(
        statement           = "Тестовое условие задания",
        db_type             = NoSQLType.DOCUMENT,
        fixture             = {"collection": "test", "documents": []},
        reference_solution  = "db.test.find({})",
        reference_solutions = [],
        compare_ordered     = False,
        max_score           = 10,
        attempts_limit      = 0,
        lesson_id           = lesson.lesson_id,
    )
    db_session.add(task)
    await db_session.flush()

    return teacher_user, course, module, lesson, task


@pytest_asyncio.fixture
async def teacher_lesson_no_tasks(db_session: AsyncSession, teacher_user: User):
    """Курс с уроком БЕЗ заданий (для тестов теории/lesson-completion).

    Возвращает (teacher, course, module, lesson).
    """
    from app.models import Course, Module, Lesson
    from app.models.course import NoSQLType

    course = Course(
        title       = "Theory Course",
        description = "Теоретический курс",
        nosql_type  = NoSQLType.DOCUMENT,
        author_id   = teacher_user.user_id,
    )
    db_session.add(course)
    await db_session.flush()

    module = Module(
        title     = "Теоретический модуль",
        course_id = course.course_id,
        order_num = 1,
    )
    db_session.add(module)
    await db_session.flush()

    lesson = Lesson(
        title       = "Теория без задания",
        content_md  = "# Теория\n\nТолько текст.",
        module_id   = module.module_id,
        order_num   = 1,
    )
    db_session.add(lesson)
    await db_session.flush()

    return teacher_user, course, module, lesson
