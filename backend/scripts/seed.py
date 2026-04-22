"""Заполнение БД демо-данными для ручного тестирования.

Запуск:
    docker compose exec backend python -m scripts.seed

Идемпотентность: скрипт безопасно запускать несколько раз — существующие
записи не дублируются.
"""
import asyncio
import logging

from sqlalchemy import select

from app.core.security import hash_password
from app.db import AsyncSessionLocal
from app.models import (
    Achievement, Course, Lesson, Module, NoSQLType, Task, User, UserRole,
)

logging.basicConfig(level=logging.INFO, format="%(levelname)s  %(message)s")
log = logging.getLogger("seed")


async def ensure_user(session, *, login: str, email: str, password: str,
                      display_name: str, role: UserRole) -> User:
    result = await session.execute(select(User).where(User.login == login))
    user   = result.scalar_one_or_none()
    if user:
        log.info("user %s already exists (id=%s)", login, user.user_id)
        return user

    user = User(
        login         = login,
        email         = email,
        password_hash = hash_password(password),
        display_name  = display_name,
        role          = role,
    )
    session.add(user)
    await session.flush()
    log.info("created user %s (id=%s, role=%s)", login, user.user_id, role.value)
    return user


async def ensure_demo_course(session, author: User) -> Course:
    result = await session.execute(
        select(Course).where(Course.title == "MongoDB для начинающих")
    )
    course = result.scalar_one_or_none()
    if course:
        log.info("demo course already exists (id=%s)", course.course_id)
        return course

    course = Course(
        title       = "MongoDB для начинающих",
        description = (
            "Базовый курс по документной СУБД MongoDB. "
            "Охватывает создание коллекций, вставку, выборку, агрегацию и индексы."
        ),
        nosql_type = NoSQLType.DOCUMENT,
        author_id  = author.user_id,
        difficulty = 2,
    )
    session.add(course)
    await session.flush()

    # Модуль 1 — введение.
    m1 = Module(
        course_id   = course.course_id,
        title       = "Модуль 1. Основы MongoDB",
        order_num   = 1,
        description = "Знакомство с документной моделью данных.",
    )
    session.add(m1)
    await session.flush()

    session.add(
        Lesson(
            module_id    = m1.module_id,
            title        = "Что такое MongoDB",
            order_num    = 1,
            duration_min = 8,
            content_md   = (
                "# Что такое MongoDB\n\n"
                "MongoDB — популярная документная NoSQL-база данных. "
                "Данные хранятся в формате BSON (двоичный JSON), что делает "
                "схему гибкой и удобной для работы с разнородной информацией.\n\n"
                "## Ключевые понятия\n\n"
                "- **Документ** — запись в формате JSON.\n"
                "- **Коллекция** — аналог таблицы в SQL.\n"
                "- **База данных** — набор коллекций.\n"
            ),
        )
    )

    # Модуль 2 — выборка.
    m2 = Module(
        course_id   = course.course_id,
        title       = "Модуль 2. Чтение и выборка",
        order_num   = 2,
        description = "Базовые запросы find() и операторы сравнения.",
    )
    session.add(m2)
    await session.flush()

    lesson2 = Lesson(
        module_id    = m2.module_id,
        title        = "Агрегация данных",
        order_num    = 1,
        duration_min = 10,
        content_md   = (
            "# Агрегация в MongoDB\n\n"
            "Конвейер `aggregate()` — ключевой инструмент аналитических "
            "запросов. Каждая стадия принимает документы от предыдущей и "
            "возвращает документы следующей.\n\n"
            "Основные стадии: `$match`, `$group`, `$sort`, `$limit`, `$project`, `$lookup`."
        ),
    )
    session.add(lesson2)
    await session.flush()

    session.add(
        Task(
            lesson_id          = lesson2.lesson_id,
            statement          = (
                "Для каждого пользователя из коллекции `orders` посчитайте "
                "суммарную стоимость **оплаченных** заказов (status = \"paid\") "
                "и верните ТОП-5 покупателей в порядке убывания суммы. "
                "Результат должен содержать поля `_id` (user_id) и `total`."
            ),
            db_type            = NoSQLType.DOCUMENT,
            fixture            = {
                "collection": "orders",
                "documents": [
                    {"_id": 1,  "user_id": "u_0481", "status": "paid",      "amount": 3200},
                    {"_id": 2,  "user_id": "u_0257", "status": "paid",      "amount": 4500},
                    {"_id": 3,  "user_id": "u_0481", "status": "paid",      "amount": 9140},
                    {"_id": 4,  "user_id": "u_0893", "status": "paid",      "amount": 7715},
                    {"_id": 5,  "user_id": "u_0112", "status": "paid",      "amount": 6420},
                    {"_id": 6,  "user_id": "u_0257", "status": "paid",      "amount": 5360},
                    {"_id": 7,  "user_id": "u_0556", "status": "paid",      "amount": 5180},
                    {"_id": 8,  "user_id": "u_0481", "status": "cancelled", "amount": 1200},
                    {"_id": 9,  "user_id": "u_0893", "status": "paid",      "amount": 3300},
                    {"_id": 10, "user_id": "u_0112", "status": "paid",      "amount": 2900},
                ],
            },
            reference_solution = (
                "db.orders.aggregate([\n"
                "  { $match: { status: 'paid' } },\n"
                "  { $group: { _id: '$user_id', total: { $sum: '$amount' } } },\n"
                "  { $sort:  { total: -1 } },\n"
                "  { $limit: 5 }\n"
                "])"
            ),
            max_score      = 10,
            attempts_limit = 5,
        )
    )

    log.info("created demo course (id=%s) with 2 modules, 2 lessons, 1 task",
             course.course_id)
    return course


async def ensure_achievements(session) -> None:
    for name, desc, icon, cond, pts in [
        ("Первые шаги",    "Решить 1 задание",            "🏅", "submissions >= 1",  5),
        ("Книжный червь",  "Пройти 10 уроков",            "📚", "lessons >= 10",    10),
        ("В огне",         "7 дней подряд",               "🔥", "streak >= 7",      15),
        ("Снайпер",        "5 заданий с первой попытки",  "🎯", "first_try >= 5",   20),
        ("Знаток",         "Пройти весь курс",            "🏆", "course_completed", 50),
    ]:
        result = await session.execute(
            select(Achievement).where(Achievement.name == name)
        )
        if result.scalar_one_or_none() is None:
            session.add(Achievement(
                name=name, description=desc, icon=icon, condition=cond, points=pts,
            ))
    log.info("ensured achievement set")


async def main() -> None:
    async with AsyncSessionLocal() as session:
        teacher = await ensure_user(
            session,
            login        = "yuri",
            email        = "yuri@example.com",
            password     = "teacher123",
            display_name = "Юрий Аджем",
            role         = UserRole.TEACHER,
        )
        await ensure_user(
            session,
            login        = "student",
            email        = "student@example.com",
            password     = "student123",
            display_name = "Фёдор Данилов",
            role         = UserRole.STUDENT,
        )
        await ensure_user(
            session,
            login        = "admin",
            email        = "admin@example.com",
            password     = "admin123",
            display_name = "Администратор",
            role         = UserRole.ADMIN,
        )

        await ensure_demo_course(session, teacher)
        await ensure_achievements(session)

        await session.commit()
        log.info("seed completed successfully")


if __name__ == "__main__":
    asyncio.run(main())
