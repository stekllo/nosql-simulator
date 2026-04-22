"""Заполнение БД демо-данными для ручного тестирования."""
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


async def ensure_user(session, *, login, email, password, display_name, role):
    result = await session.execute(select(User).where(User.login == login))
    user   = result.scalar_one_or_none()
    if user:
        log.info("user %s already exists (id=%s)", login, user.user_id)
        return user
    user = User(
        login=login, email=email,
        password_hash=hash_password(password),
        display_name=display_name, role=role,
    )
    session.add(user)
    await session.flush()
    log.info("created user %s (id=%s, role=%s)", login, user.user_id, role.value)
    return user


async def ensure_course(
    session, author, *,
    title:       str,
    description: str,
    nosql_type:  NoSQLType,
    difficulty:  int,
    modules:     list[dict],
) -> Course:
    """Создаёт курс с модулями, уроками и заданиями (если не существует)."""
    result = await session.execute(select(Course).where(Course.title == title))
    course = result.scalar_one_or_none()
    if course:
        log.info("course %r already exists (id=%s)", title, course.course_id)
        return course

    course = Course(
        title       = title,
        description = description,
        nosql_type  = nosql_type,
        author_id   = author.user_id,
        difficulty  = difficulty,
    )
    session.add(course)
    await session.flush()

    for m_idx, m_data in enumerate(modules, start=1):
        module = Module(
            course_id   = course.course_id,
            title       = m_data["title"],
            description = m_data.get("description"),
            order_num   = m_idx,
        )
        session.add(module)
        await session.flush()

        for l_idx, l_data in enumerate(m_data["lessons"], start=1):
            lesson = Lesson(
                module_id    = module.module_id,
                title        = l_data["title"],
                content_md   = l_data["content_md"],
                order_num    = l_idx,
                duration_min = l_data.get("duration_min", 8),
            )
            session.add(lesson)
            await session.flush()

            for t_data in l_data.get("tasks", []):
                session.add(Task(
                    lesson_id          = lesson.lesson_id,
                    statement          = t_data["statement"],
                    db_type            = nosql_type,
                    fixture            = t_data["fixture"],
                    reference_solution = t_data["reference_solution"],
                    max_score          = t_data.get("max_score", 10),
                    attempts_limit     = t_data.get("attempts_limit", 5),
                ))

    log.info("created course %r (id=%s)", title, course.course_id)
    return course


# ============ Контент курсов ============

MONGO_COURSE = {
    "title":       "MongoDB для начинающих",
    "description": "Базовый курс по документной СУБД MongoDB. Создание коллекций, выборка, агрегация, индексы.",
    "nosql_type":  NoSQLType.DOCUMENT,
    "difficulty":  2,
    "modules": [
        {
            "title":       "Модуль 1. Основы MongoDB",
            "description": "Знакомство с документной моделью данных.",
            "lessons": [
                {
                    "title":        "Что такое MongoDB",
                    "duration_min": 8,
                    "content_md":   (
                        "# Что такое MongoDB\n\n"
                        "MongoDB — популярная документная NoSQL-база данных. "
                        "Данные хранятся в формате BSON (двоичный JSON), что делает "
                        "схему гибкой и удобной для работы с разнородной информацией.\n\n"
                        "## Ключевые понятия\n\n"
                        "- **Документ** — запись в формате JSON.\n"
                        "- **Коллекция** — аналог таблицы в SQL.\n"
                        "- **База данных** — набор коллекций.\n\n"
                        "## Чем отличается от SQL\n\n"
                        "В отличие от реляционных СУБД, в MongoDB:\n\n"
                        "- Нет жёсткой схемы — документы в одной коллекции могут отличаться по составу полей.\n"
                        "- Нет JOIN — связанные данные обычно хранятся вложенно.\n"
                        "- Шардирование встроено в систему."
                    ),
                },
                {
                    "title":        "Базовые команды find()",
                    "duration_min": 10,
                    "content_md":   (
                        "# Выборка документов\n\n"
                        "Метод `db.collection.find(filter)` возвращает документы, "
                        "соответствующие фильтру.\n\n"
                        "Пример: `db.users.find({ age: { $gt: 18 } })` — все пользователи "
                        "старше 18.\n\n"
                        "Операторы сравнения: `$gt`, `$gte`, `$lt`, `$lte`, `$eq`, `$ne`, `$in`, `$nin`."
                    ),
                },
            ],
        },
        {
            "title":       "Модуль 2. Чтение и выборка",
            "description": "Базовые запросы find() и операторы сравнения.",
            "lessons": [
                {
                    "title":        "Агрегация данных",
                    "duration_min": 12,
                    "content_md":   (
                        "# Агрегация в MongoDB\n\n"
                        "Конвейер `aggregate()` — ключевой инструмент аналитических "
                        "запросов. Каждая стадия принимает документы от предыдущей и "
                        "возвращает документы следующей.\n\n"
                        "## Основные стадии\n\n"
                        "- `$match` — фильтрация (синтаксис как у `find`).\n"
                        "- `$group` — группировка с агрегатами `$sum`, `$avg`, `$min`, `$max`.\n"
                        "- `$project` — выбор/переименование полей.\n"
                        "- `$sort`, `$limit`, `$skip` — упорядочивание и страничная выборка.\n"
                        "- `$lookup` — соединение с другой коллекцией.\n\n"
                        "## Пример\n\n"
                        "```javascript\n"
                        "db.orders.aggregate([\n"
                        "  { $match: { status: 'paid' } },\n"
                        "  { $group: { _id: '$user_id', total: { $sum: '$amount' } } },\n"
                        "  { $sort:  { total: -1 } },\n"
                        "  { $limit: 5 }\n"
                        "])\n"
                        "```"
                    ),
                    "tasks": [
                        {
                            "statement": (
                                "Для каждого пользователя из коллекции `orders` посчитайте "
                                "суммарную стоимость **оплаченных** заказов "
                                "(status = \"paid\") и верните ТОП-5 покупателей в порядке "
                                "убывания суммы. Результат должен содержать поля `_id` и `total`."
                            ),
                            "fixture": {
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
                            "reference_solution": (
                                "db.orders.aggregate([\n"
                                "  { $match: { status: 'paid' } },\n"
                                "  { $group: { _id: '$user_id', total: { $sum: '$amount' } } },\n"
                                "  { $sort:  { total: -1 } },\n"
                                "  { $limit: 5 }\n"
                                "])"
                            ),
                        },
                    ],
                },
            ],
        },
    ],
}

REDIS_COURSE = {
    "title":       "Redis: кэш и структуры",
    "description": "Хранилище ключ-значение Redis. Работа со строками, списками, множествами, хэшами.",
    "nosql_type":  NoSQLType.KEY_VALUE,
    "difficulty":  2,
    "modules": [
        {
            "title": "Модуль 1. Введение в Redis",
            "description": "Что такое Redis и где он применяется.",
            "lessons": [
                {
                    "title":        "Зачем нужен Redis",
                    "duration_min": 6,
                    "content_md":   (
                        "# Redis — in-memory key-value хранилище\n\n"
                        "Redis хранит данные в оперативной памяти, что обеспечивает "
                        "очень высокую скорость доступа (миллионы операций в секунду).\n\n"
                        "## Типичные применения\n\n"
                        "- Кэширование результатов запросов\n"
                        "- Хранение пользовательских сессий\n"
                        "- Очереди сообщений\n"
                        "- Счётчики и метрики реального времени\n"
                        "- Распределённые блокировки\n\n"
                        "## Структуры данных\n\n"
                        "Redis поддерживает не только строки: списки (`LIST`), "
                        "множества (`SET`), хэши (`HASH`), упорядоченные множества (`ZSET`)."
                    ),
                },
            ],
        },
    ],
}

CASSANDRA_COURSE = {
    "title":       "Cassandra: большие данные",
    "description": "Распределённая колоночная СУБД для масштабируемых нагрузок. Язык CQL.",
    "nosql_type":  NoSQLType.COLUMN,
    "difficulty":  4,
    "modules": [
        {
            "title": "Модуль 1. Архитектура Cassandra",
            "description": "Шардирование, репликация, кворумы.",
            "lessons": [
                {
                    "title":        "Кольцевая архитектура",
                    "duration_min": 12,
                    "content_md":   (
                        "# Архитектура Cassandra\n\n"
                        "Cassandra использует **peer-to-peer** архитектуру: все узлы "
                        "равноправны, нет ведущего и ведомого. Данные распределяются "
                        "по узлам с помощью консистентного хэширования.\n\n"
                        "## Ключевые свойства\n\n"
                        "- Линейное горизонтальное масштабирование\n"
                        "- Tunable consistency (настраиваемая согласованность)\n"
                        "- Без единой точки отказа\n"
                        "- Оптимизирована для больших объёмов записи"
                    ),
                },
            ],
        },
    ],
}

NEO4J_COURSE = {
    "title":       "Neo4j и язык Cypher",
    "description": "Графовая СУБД Neo4j. Узлы, рёбра, обход графа на языке Cypher.",
    "nosql_type":  NoSQLType.GRAPH,
    "difficulty":  3,
    "modules": [
        {
            "title": "Модуль 1. Графовая модель",
            "description": "Узлы, отношения, свойства.",
            "lessons": [
                {
                    "title":        "Что такое граф свойств",
                    "duration_min": 10,
                    "content_md":   (
                        "# Графовая модель данных\n\n"
                        "В Neo4j данные представлены как **граф свойств** "
                        "(labeled property graph): узлы (вершины) с метками "
                        "и рёбра (отношения) между ними. И узлы, и рёбра могут "
                        "иметь произвольный набор свойств.\n\n"
                        "## Пример\n\n"
                        "```cypher\n"
                        "CREATE (alice:Person {name: 'Alice', age: 30})\n"
                        "CREATE (bob:Person {name: 'Bob',   age: 25})\n"
                        "CREATE (alice)-[:KNOWS {since: 2020}]->(bob)\n"
                        "```\n\n"
                        "## Когда использовать\n\n"
                        "- Социальные сети\n"
                        "- Рекомендательные системы\n"
                        "- Анализ зависимостей и мошенничества\n"
                        "- Графы знаний"
                    ),
                },
            ],
        },
    ],
}

ALL_COURSES = [MONGO_COURSE, REDIS_COURSE, CASSANDRA_COURSE, NEO4J_COURSE]


async def ensure_achievements(session):
    for name, desc, icon, cond, pts in [
        ("Первые шаги",   "Решить 1 задание",            "🏅", "submissions >= 1",  5),
        ("Книжный червь", "Пройти 10 уроков",            "📚", "lessons >= 10",    10),
        ("В огне",        "7 дней подряд",               "🔥", "streak >= 7",      15),
        ("Снайпер",       "5 заданий с первой попытки",  "🎯", "first_try >= 5",   20),
        ("Знаток",        "Пройти весь курс",            "🏆", "course_completed", 50),
    ]:
        result = await session.execute(select(Achievement).where(Achievement.name == name))
        if result.scalar_one_or_none() is None:
            session.add(Achievement(
                name=name, description=desc, icon=icon, condition=cond, points=pts,
            ))
    log.info("ensured achievement set")


async def main():
    async with AsyncSessionLocal() as session:
        teacher = await ensure_user(
            session,
            login="yuri", email="yuri@example.com",
            password="teacher123", display_name="Юрий Аджем",
            role=UserRole.TEACHER,
        )
        await ensure_user(
            session,
            login="student", email="student@example.com",
            password="student123", display_name="Фёдор Данилов",
            role=UserRole.STUDENT,
        )
        await ensure_user(
            session,
            login="admin", email="admin@example.com",
            password="admin123", display_name="Администратор",
            role=UserRole.ADMIN,
        )

        for course_data in ALL_COURSES:
            await ensure_course(session, teacher, **course_data)

        await ensure_achievements(session)
        await session.commit()
        log.info("seed completed successfully")


if __name__ == "__main__":
    asyncio.run(main())
