"""Заполнение БД демо-данными для ручного тестирования."""
import asyncio
import logging
from datetime import datetime, timedelta

from sqlalchemy import select

from app.core.security import hash_password
from app.db import AsyncSessionLocal
from app.models import (
    Achievement, Course, Lesson, Module, NoSQLType, Submission, SubmissionStatus,
    Task, User, UserRole,
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
                    lesson_id           = lesson.lesson_id,
                    statement           = t_data["statement"],
                    db_type             = nosql_type,
                    fixture             = t_data["fixture"],
                    reference_solution  = t_data["reference_solution"],
                    reference_solutions = t_data.get("reference_solutions", []),
                    compare_ordered     = t_data.get("compare_ordered", True),
                    max_score           = t_data.get("max_score", 10),
                    attempts_limit      = t_data.get("attempts_limit", 5),
                ))

    log.info("created course %r (id=%s)", title, course.course_id)
    return course


# ============================================================================
# КОНТЕНТ MONGODB-КУРСА (полный, 3 модуля × 3 урока, с заданиями)
# ============================================================================

MONGO_COURSE = {
    "title":       "MongoDB для начинающих",
    "description": "Базовый курс по документной СУБД MongoDB. Создание коллекций, выборка, агрегация, индексы.",
    "nosql_type":  NoSQLType.DOCUMENT,
    "difficulty":  2,
    "modules": [

        # ------------------------------------------------------------
        # МОДУЛЬ 1. Основы MongoDB
        # ------------------------------------------------------------
        {
            "title":       "Модуль 1. Основы MongoDB",
            "description": "Знакомство с документной моделью данных, базовые команды find().",
            "lessons": [
                # ---- Урок 1.1 ----
                {
                    "title":        "Что такое MongoDB",
                    "duration_min": 8,
                    "content_md": """# Что такое MongoDB

MongoDB — самая популярная документная NoSQL-база данных. Данные хранятся в формате BSON (двоичный JSON), что делает схему гибкой и удобной для работы с разнородной информацией.

## Ключевые понятия

- **Документ** — запись в формате JSON с произвольной структурой.
- **Коллекция** — аналог таблицы в SQL, набор документов.
- **База данных** — набор коллекций, связанных по смыслу.

## Чем отличается от SQL

В отличие от реляционных СУБД, в MongoDB:

- **Нет жёсткой схемы** — документы в одной коллекции могут отличаться по составу полей.
- **Нет JOIN** — связанные данные обычно хранятся вложенно прямо в документе.
- **Шардирование встроено** в систему, горизонтальное масштабирование работает «из коробки».

## Пример документа

```json
{
  "_id": 1,
  "name": "Alice",
  "age": 30,
  "orders": [
    { "product": "Laptop", "amount": 1200 },
    { "product": "Mouse",  "amount": 25 }
  ]
}
```

Обрати внимание — массив заказов хранится прямо внутри документа пользователя. В реляционной БД пришлось бы создавать отдельную таблицу и делать JOIN.

## Области применения

MongoDB хорошо подходит для:

- каталогов товаров в электронной коммерции,
- систем управления контентом (CMS),
- хранения пользовательских профилей и сессий,
- логов событий и метрик,
- прототипов и MVP, где схема данных ещё не устоялась.
""",
                },

                # ---- Урок 1.2 ----
                {
                    "title":        "Базовые команды find()",
                    "duration_min": 12,
                    "content_md": """# Выборка документов: find()

Метод `db.collection.find(filter)` — основной инструмент чтения данных из MongoDB. Он возвращает все документы, соответствующие фильтру.

## Базовый синтаксис

```javascript
db.users.find({ age: 25 })
```

Этот запрос вернёт всех пользователей, у которых поле `age` равно 25. Если вызвать `find()` без аргументов или с пустым объектом `{}`, вернутся все документы коллекции.

## Операторы сравнения

Для более сложных условий используются операторы, начинающиеся с `$`:

- `$eq` — равно (используется неявно)
- `$ne` — не равно
- `$gt`, `$gte` — больше, больше или равно
- `$lt`, `$lte` — меньше, меньше или равно
- `$in` — значение входит в массив
- `$nin` — значение не входит в массив

Пример:

```javascript
db.users.find({ age: { $gte: 18, $lt: 65 } })
```

Найдёт всех совершеннолетних, которые ещё не на пенсии.

## Логические операторы

- `$and` — все условия выполняются (обычно достаточно перечислить поля через запятую)
- `$or` — хотя бы одно из условий
- `$not` — отрицание

```javascript
db.users.find({
  $or: [
    { country: "Russia" },
    { country: "Belarus" }
  ]
})
```

## Модификаторы курсора

После `find()` можно уточнить результат:

- `.sort({ field: 1 })` — сортировка по возрастанию, `-1` — по убыванию
- `.limit(n)` — ограничить количество результатов
- `.skip(n)` — пропустить первые n документов

```javascript
db.products.find({ category: "electronics" })
  .sort({ price: -1 })
  .limit(10)
```

Найдёт 10 самых дорогих товаров из категории «электроника».
""",
                    "tasks": [
                        {
                            "statement": (
                                "В коллекции `users` хранятся пользователи системы. "
                                "Найдите всех пользователей старше 30 лет. "
                                "Результат отсортируйте по возрасту в **порядке убывания**."
                            ),
                            "fixture": {
                                "collection": "users",
                                "documents": [
                                    {"_id": 1, "name": "Alice",   "age": 25},
                                    {"_id": 2, "name": "Bob",     "age": 35},
                                    {"_id": 3, "name": "Charlie", "age": 42},
                                    {"_id": 4, "name": "Diana",   "age": 28},
                                    {"_id": 5, "name": "Eve",     "age": 31},
                                    {"_id": 6, "name": "Frank",   "age": 19},
                                ],
                            },
                            "reference_solution":
                                "db.users.find({ age: { $gt: 30 } }).sort({ age: -1 })",
                            "max_score": 10,
                        },
                        {
                            "statement": (
                                "В коллекции `products` хранятся товары интернет-магазина. "
                                "Найдите **первые 3** товара из категории `electronics`, "
                                "отсортированных по цене в **порядке возрастания**."
                            ),
                            "fixture": {
                                "collection": "products",
                                "documents": [
                                    {"_id": 1, "name": "Phone",     "category": "electronics", "price": 800},
                                    {"_id": 2, "name": "Laptop",    "category": "electronics", "price": 1500},
                                    {"_id": 3, "name": "Book",      "category": "books",       "price": 25},
                                    {"_id": 4, "name": "Tablet",    "category": "electronics", "price": 600},
                                    {"_id": 5, "name": "Headphones","category": "electronics", "price": 200},
                                    {"_id": 6, "name": "Mouse",     "category": "electronics", "price": 45},
                                    {"_id": 7, "name": "Notebook",  "category": "stationery",  "price": 10},
                                ],
                            },
                            "reference_solution":
                                "db.products.find({ category: 'electronics' }).sort({ price: 1 }).limit(3)",
                            "max_score": 10,
                        },
                    ],
                },

                # ---- Урок 1.3 ----
                {
                    "title":        "Работа с вложенными документами",
                    "duration_min": 10,
                    "content_md": """# Работа с вложенными документами

В MongoDB документы могут иметь сложную вложенную структуру — это одно из главных отличий от реляционных СУБД. Внутри документа могут лежать другие документы или массивы.

## Доступ к вложенным полям

Для обращения к полям внутри вложенного документа используется **точечная нотация**:

```javascript
db.users.find({ "address.city": "Москва" })
```

Этот запрос найдёт пользователей, у которых внутри `address` поле `city` равно "Москва".

## Запросы по элементам массива

Если поле — массив, можно искать по любому его элементу:

```javascript
db.products.find({ tags: "новинка" })
```

Найдёт товары, у которых в массиве `tags` есть значение "новинка".

Для более сложных условий используется `$elemMatch`:

```javascript
db.users.find({
  orders: { $elemMatch: { status: "paid", amount: { $gt: 1000 } } }
})
```

Найдёт пользователей, у которых **есть хотя бы один** заказ со статусом "paid" и суммой больше 1000.

## Оператор $exists

Проверяет наличие поля:

```javascript
db.users.find({ phone: { $exists: true } })
```

Найдёт всех, у кого вообще задан номер телефона.

## Размер массива

Оператор `$size` фильтрует по точному размеру массива:

```javascript
db.users.find({ orders: { $size: 0 } })
```

Найдёт пользователей без заказов.
""",
                    "tasks": [
                        {
                            "statement": (
                                "В коллекции `users` каждый документ содержит вложенный объект `address` "
                                "с полем `city`. Найдите всех пользователей, проживающих в Москве. "
                                "Отсортируйте по `_id` по возрастанию."
                            ),
                            "fixture": {
                                "collection": "users",
                                "documents": [
                                    {"_id": 1, "name": "Alice",   "address": {"city": "Москва",  "street": "Тверская"}},
                                    {"_id": 2, "name": "Bob",     "address": {"city": "СПб",     "street": "Невский"}},
                                    {"_id": 3, "name": "Charlie", "address": {"city": "Москва",  "street": "Арбат"}},
                                    {"_id": 4, "name": "Diana",   "address": {"city": "Казань",  "street": "Баумана"}},
                                    {"_id": 5, "name": "Eve",     "address": {"city": "Москва",  "street": "Пушкина"}},
                                ],
                            },
                            "reference_solution":
                                "db.users.find({ 'address.city': 'Москва' }).sort({ _id: 1 })",
                            "max_score": 10,
                        },
                    ],
                },
            ],
        },

        # ------------------------------------------------------------
        # МОДУЛЬ 2. Агрегация
        # ------------------------------------------------------------
        {
            "title":       "Модуль 2. Агрегация и аналитика",
            "description": "Конвейер aggregate(), группировка, сортировка, статистические операторы.",
            "lessons": [
                # ---- Урок 2.1 ----
                {
                    "title":        "Агрегация данных",
                    "duration_min": 15,
                    "content_md": """# Агрегация в MongoDB

Конвейер `aggregate()` — ключевой инструмент аналитических запросов к коллекциям.

Агрегация в MongoDB — это механизм, позволяющий преобразовывать документы коллекции через последовательность стадий. В отличие от метода `find()`, агрегационный конвейер способен группировать записи, считать статистики, объединять коллекции и реструктурировать данные в произвольную форму.

## Базовый синтаксис

Метод `db.collection.aggregate()` принимает массив стадий. Каждая стадия — это документ с одним оператором, начинающимся со знака `$`:

```javascript
// Пример простого конвейера
db.orders.aggregate([
  { $match: { status: "paid" } },
  { $group: { _id: "$user_id", total: { $sum: "$amount" } } },
  { $sort:  { total: -1 } },
  { $limit: 10 }
])
```

Каждая стадия принимает документы от предыдущей и возвращает документы для следующей, поэтому **порядок стадий важен**.

## Основные стадии

- `$match` — фильтрация документов, синтаксис совпадает с обычным запросом `find()`.
- `$group` — группировка по одному или нескольким полям с агрегирующими функциями (`$sum`, `$avg`, `$min`, `$max`, `$count`).
- `$project` — выбор, переименование полей, вычисление новых.
- `$sort`, `$limit`, `$skip` — упорядочивание и страничная выборка.
- `$lookup` — «левое» соединение с другой коллекцией (аналог JOIN в SQL).
- `$unwind` — «разворачивание» массива: одна запись с массивом из N элементов превращается в N записей.

## Агрегирующие операторы

Внутри `$group` используются специальные операторы:

- `$sum: "$field"` — сумма значений поля
- `$sum: 1` — просто подсчёт количества
- `$avg: "$field"` — среднее значение
- `$min`, `$max` — минимум и максимум
- `$first`, `$last` — первое/последнее значение в группе
- `$push: "$field"` — собрать значения в массив

## Производительность

Порядок стадий напрямую влияет на скорость запроса. Стадия `$match` должна располагаться как можно ближе к началу конвейера, чтобы как можно раньше отсечь ненужные документы и не тащить их через все последующие стадии. По той же причине `$project` с сокращением состава полей полезен перед дорогими операциями (`$group`, `$lookup`).
""",
                    "tasks": [
                        {
                            "statement": (
                                "Для каждого пользователя из коллекции `orders` посчитайте "
                                "суммарную стоимость **оплаченных** заказов "
                                "(status = \"paid\") и верните **ТОП-5** покупателей в порядке "
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
                            "max_score": 10,
                        },
                    ],
                },

                # ---- Урок 2.2 ----
                {
                    "title":        "Подсчёт количества и группировка",
                    "duration_min": 10,
                    "content_md": """# Подсчёт количества и группировка

Помимо ТОП-выборок, агрегация полезна для построения сводок и отчётов: «сколько заказов в каждой категории», «средний чек по городам», «количество активных пользователей за период».

## Подсчёт количества элементов

Самый простой случай — просто посчитать сколько документов попадает под условие. Используется `$sum: 1`:

```javascript
db.orders.aggregate([
  { $match: { status: "paid" } },
  { $group: { _id: null, count: { $sum: 1 } } }
])
```

Здесь `_id: null` означает «всё в одну группу», и в `count` мы получим общее количество оплаченных заказов.

## Группировка по полю

Чтобы посчитать количество в разрезе категорий, в `_id` указываем имя поля:

```javascript
db.orders.aggregate([
  { $group: { _id: "$status", count: { $sum: 1 } } }
])
```

Получим документы вида `{ _id: "paid", count: 47 }`, `{ _id: "cancelled", count: 12 }` и т.д.

## Среднее значение

Для расчёта среднего используется `$avg`:

```javascript
db.orders.aggregate([
  { $match:  { status: "paid" } },
  { $group: { _id: "$category", avg_amount: { $avg: "$amount" } } }
])
```

## Несколько метрик одновременно

В одной стадии `$group` можно посчитать сразу несколько метрик:

```javascript
db.orders.aggregate([
  {
    $group: {
      _id:        "$user_id",
      total:      { $sum: "$amount" },
      count:      { $sum: 1 },
      max_order:  { $max: "$amount" }
    }
  }
])
```

Так вы получите для каждого пользователя сумму заказов, их количество и максимальный чек одним запросом.
""",
                    "tasks": [
                        {
                            "statement": (
                                "В коллекции `orders` подсчитайте **количество заказов** для каждого статуса. "
                                "Результат должен содержать поля `_id` (статус) и `count` (количество). "
                                "Отсортируйте результат по количеству заказов в **порядке убывания**."
                            ),
                            "fixture": {
                                "collection": "orders",
                                "documents": [
                                    {"_id": 1, "status": "paid"},
                                    {"_id": 2, "status": "paid"},
                                    {"_id": 3, "status": "cancelled"},
                                    {"_id": 4, "status": "paid"},
                                    {"_id": 5, "status": "pending"},
                                    {"_id": 6, "status": "paid"},
                                    {"_id": 7, "status": "cancelled"},
                                    {"_id": 8, "status": "paid"},
                                    {"_id": 9, "status": "pending"},
                                ],
                            },
                            "reference_solution": (
                                "db.orders.aggregate([\n"
                                "  { $group: { _id: '$status', count: { $sum: 1 } } },\n"
                                "  { $sort: { count: -1 } }\n"
                                "])"
                            ),
                            "max_score": 10,
                        },
                    ],
                },

                # ---- Урок 2.3 ----
                {
                    "title":        "Средние значения и статистика",
                    "duration_min": 10,
                    "content_md": """# Средние значения и статистика

Когда вы строите аналитический отчёт, простого подсчёта количества часто недостаточно — нужно понимать **среднее**, **минимум**, **максимум**, **разброс** значений. MongoDB поддерживает все эти операторы прямо в стадии `$group`.

## Основные статистические операторы

- `$avg: "$field"` — среднее арифметическое значение
- `$min: "$field"` — минимальное значение в группе
- `$max: "$field"` — максимальное значение в группе
- `$sum: "$field"` — сумма (мы уже видели её)
- `$stdDevPop: "$field"` — стандартное отклонение (по всей популяции)
- `$stdDevSamp: "$field"` — стандартное отклонение (по выборке)

## Пример: средний чек по категориям

```javascript
db.orders.aggregate([
  { $match: { status: "paid" } },
  {
    $group: {
      _id:         "$category",
      avg_amount:  { $avg: "$amount" },
      min_amount:  { $min: "$amount" },
      max_amount:  { $max: "$amount" }
    }
  }
])
```

В одном запросе получаем для каждой категории три статистики: среднее, минимум, максимум.

## Пример: глобальные статистики

Если нужно посчитать общую статистику без группировки, используется `_id: null`:

```javascript
db.orders.aggregate([
  { $match: { status: "paid" } },
  {
    $group: {
      _id:        null,
      total_count: { $sum: 1 },
      avg_amount:  { $avg: "$amount" },
      total_amount: { $sum: "$amount" }
    }
  }
])
```

Результат — один документ с глобальными метриками по всем оплаченным заказам.
""",
                    "tasks": [
                        {
                            "statement": (
                                "В коллекции `orders` для каждой `category` посчитайте **средний чек** "
                                "(`avg_amount`) только среди **оплаченных** заказов (status = \"paid\"). "
                                "Результат отсортируйте по среднему чеку в **порядке убывания**. "
                                "Каждый документ должен содержать поля `_id` и `avg_amount`."
                            ),
                            "fixture": {
                                "collection": "orders",
                                "documents": [
                                    {"_id": 1, "category": "electronics", "status": "paid",      "amount": 1500},
                                    {"_id": 2, "category": "electronics", "status": "paid",      "amount": 2500},
                                    {"_id": 3, "category": "books",       "status": "paid",      "amount": 30},
                                    {"_id": 4, "category": "books",       "status": "paid",      "amount": 50},
                                    {"_id": 5, "category": "clothing",    "status": "paid",      "amount": 800},
                                    {"_id": 6, "category": "clothing",    "status": "paid",      "amount": 1200},
                                    {"_id": 7, "category": "electronics", "status": "cancelled", "amount": 9999},
                                    {"_id": 8, "category": "books",       "status": "paid",      "amount": 70},
                                ],
                            },
                            "reference_solution": (
                                "db.orders.aggregate([\n"
                                "  { $match: { status: 'paid' } },\n"
                                "  { $group: { _id: '$category', avg_amount: { $avg: '$amount' } } },\n"
                                "  { $sort: { avg_amount: -1 } }\n"
                                "])"
                            ),
                            "max_score": 10,
                        },
                    ],
                },
            ],
        },

        # ------------------------------------------------------------
        # МОДУЛЬ 3. Продвинутые техники
        # ------------------------------------------------------------
        {
            "title":       "Модуль 3. Продвинутые техники",
            "description": "Соединения коллекций ($lookup), работа с массивами ($unwind), проекции.",
            "lessons": [
                # ---- Урок 3.1 ----
                {
                    "title":        "Проекции и $project",
                    "duration_min": 10,
                    "content_md": """# Проекции: выбор и преобразование полей

Часто из документа нужны не все поля, а только некоторые — или нужно вычислить новое поле на основе существующих. Для этого используется **проекция** — второй аргумент `find()` или стадия `$project` в агрегации.

## Проекция в find()

Второй аргумент `find()` — это объект, где поля помечаются `1` (включить) или `0` (исключить):

```javascript
db.users.find(
  { age: { $gte: 18 } },
  { name: 1, email: 1, _id: 0 }
)
```

Этот запрос вернёт только поля `name` и `email` (без `_id`).

**Правило**: в одной проекции нельзя смешивать включения и исключения, кроме `_id`. Поле `_id` включается по умолчанию — если оно не нужно, явно укажите `_id: 0`.

## Стадия $project в агрегации

В агрегации `$project` мощнее: можно не только выбирать поля, но и **переименовывать**, **вычислять новые**, использовать выражения:

```javascript
db.users.aggregate([
  {
    $project: {
      _id: 0,
      full_name: "$name",
      age_group: {
        $cond: { if: { $gte: ["$age", 18] }, then: "adult", else: "minor" }
      },
      email_domain: { $arrayElemAt: [{ $split: ["$email", "@"] }, 1] }
    }
  }
])
```

Этот запрос для каждого пользователя возвращает три поля: переименованное имя, вычисленную возрастную группу и домен из email.

## Часто используемые операторы внутри $project

- `$cond` — условный оператор (if/then/else)
- `$concat`, `$split`, `$substr` — строковые операции
- `$add`, `$subtract`, `$multiply`, `$divide` — арифметика
- `$year`, `$month`, `$dayOfWeek` — операции с датами
- `$arrayElemAt` — взять элемент массива по индексу
""",
                    "tasks": [
                        {
                            "statement": (
                                "В коллекции `users` верните для всех пользователей только поля "
                                "`name` и `email` (без `_id`). Отсортируйте результат по `name` "
                                "в **порядке возрастания**."
                            ),
                            "fixture": {
                                "collection": "users",
                                "documents": [
                                    {"_id": 1, "name": "Charlie", "email": "c@x.com", "age": 30},
                                    {"_id": 2, "name": "Alice",   "email": "a@x.com", "age": 25},
                                    {"_id": 3, "name": "Bob",     "email": "b@x.com", "age": 28},
                                    {"_id": 4, "name": "Diana",   "email": "d@x.com", "age": 22},
                                ],
                            },
                            "reference_solution":
                                "db.users.find({}, { name: 1, email: 1, _id: 0 }).sort({ name: 1 })",
                            "max_score": 10,
                        },
                    ],
                },

                # ---- Урок 3.2 ----
                {
                    "title":        "Работа с массивами: $unwind",
                    "duration_min": 12,
                    "content_md": """# Работа с массивами: $unwind

В документной модели часто массив хранится прямо внутри документа — например, список тегов, заказов, комментариев. Чтобы агрегировать такие данные (посчитать самый популярный тег, например), нужно «развернуть» массив с помощью `$unwind`.

## Как работает $unwind

Стадия `$unwind` берёт документ с массивом и превращает его в **N документов** — по одному на каждый элемент массива. Все остальные поля копируются.

**Было** (1 документ):
```json
{ "_id": 1, "name": "Phone", "tags": ["electronics", "новинка", "хит"] }
```

**Стало после $unwind: "$tags"** (3 документа):
```json
{ "_id": 1, "name": "Phone", "tags": "electronics" }
{ "_id": 1, "name": "Phone", "tags": "новинка" }
{ "_id": 1, "name": "Phone", "tags": "хит" }
```

## Типичный сценарий: топ-теги

Допустим, у нас есть товары с массивом тегов, и мы хотим узнать, какие теги самые популярные:

```javascript
db.products.aggregate([
  { $unwind: "$tags" },
  { $group: { _id: "$tags", count: { $sum: 1 } } },
  { $sort:  { count: -1 } },
  { $limit: 5 }
])
```

После `$unwind` каждый тег становится отдельным «документом», который мы можем сгруппировать и посчитать.

## Сценарий: средняя цена товара по тегам

```javascript
db.products.aggregate([
  { $unwind: "$tags" },
  {
    $group: {
      _id: "$tags",
      avg_price: { $avg: "$price" },
      count:     { $sum: 1 }
    }
  },
  { $sort: { avg_price: -1 } }
])
```

Получим: для каждого тега — среднюю цену товаров, в которых он используется.

## Подводные камни

Если массив пустой (`[]`), документ после `$unwind` **исчезнет**. Если поле отсутствует — то же самое. Чтобы сохранять такие документы, используйте опцию `preserveNullAndEmptyArrays`:

```javascript
{ $unwind: { path: "$tags", preserveNullAndEmptyArrays: true } }
```
""",
                    "tasks": [
                        {
                            "statement": (
                                "В коллекции `products` каждый товар имеет массив `tags`. "
                                "Найдите **топ-3** самых популярных тегов: для каждого тега "
                                "выведите его и количество товаров с этим тегом. "
                                "Результат отсортируйте по количеству в **порядке убывания**. "
                                "Поля результата: `_id` (тег) и `count`."
                            ),
                            "fixture": {
                                "collection": "products",
                                "documents": [
                                    {"_id": 1, "name": "Phone",   "tags": ["electronics", "новинка", "хит"]},
                                    {"_id": 2, "name": "Laptop",  "tags": ["electronics", "хит"]},
                                    {"_id": 3, "name": "Book",    "tags": ["новинка"]},
                                    {"_id": 4, "name": "Tablet",  "tags": ["electronics", "хит", "распродажа"]},
                                    {"_id": 5, "name": "Mouse",   "tags": ["electronics", "распродажа"]},
                                    {"_id": 6, "name": "Pen",     "tags": ["распродажа"]},
                                ],
                            },
                            "reference_solution": (
                                "db.products.aggregate([\n"
                                "  { $unwind: '$tags' },\n"
                                "  { $group: { _id: '$tags', count: { $sum: 1 } } },\n"
                                "  { $sort: { count: -1 } },\n"
                                "  { $limit: 3 }\n"
                                "])"
                            ),
                            "max_score": 10,
                        },
                    ],
                },

                # ---- Урок 3.3 ----
                {
                    "title":        "Соединение коллекций: $lookup",
                    "duration_min": 12,
                    "content_md": """# Соединение коллекций: $lookup

В реляционных СУБД для соединения таблиц используется JOIN. В MongoDB исторически предполагалось, что связанные данные будут храниться внутри документа, но в реальности часто нужно объединить две коллекции — для этого есть стадия **$lookup** (аналог LEFT JOIN из SQL).

## Базовый синтаксис

```javascript
db.orders.aggregate([
  {
    $lookup: {
      from:         "users",
      localField:   "user_id",
      foreignField: "_id",
      as:           "user_info"
    }
  }
])
```

Что это делает:
1. Берём каждый документ из `orders`.
2. Ищем в коллекции `users` все документы, где `_id` равен `user_id` из текущего заказа.
3. Найденные документы складываем в **массив** `user_info` внутри документа заказа.

## Особенности результата

После `$lookup` поле `user_info` — это **всегда массив**, даже если найден ровно один пользователь. Чтобы превратить его в обычный объект, обычно делают `$unwind`:

```javascript
db.orders.aggregate([
  { $lookup: { from: "users", localField: "user_id", foreignField: "_id", as: "user" } },
  { $unwind: "$user" }
])
```

## Типичный сценарий: имена в результатах

Предположим, в коллекции `orders` хранится только `user_id`, а имя пользователя — в `users`. Чтобы отобразить отчёт «какой пользователь сделал какой заказ», нужно объединить:

```javascript
db.orders.aggregate([
  { $match: { status: "paid" } },
  { $lookup: { from: "users", localField: "user_id", foreignField: "_id", as: "user" } },
  { $unwind: "$user" },
  {
    $project: {
      _id:        0,
      order_id:   "$_id",
      user_name:  "$user.name",
      amount:     1
    }
  }
])
```

Результат: документы вида `{ order_id: 5, user_name: "Alice", amount: 1500 }`.

## Производительность

`$lookup` — дорогая операция. Старайтесь применять `$match` **до** `$lookup`, чтобы соединять как можно меньше документов. Также следите за тем, чтобы поле `foreignField` было проиндексировано.
""",
                    "tasks": [
                        {
                            "statement": (
                                "В коллекции `orders` хранятся заказы (поля: `_id`, `user_id`, `amount`), "
                                "а в `users` — пользователи (`_id`, `name`). Постройте список "
                                "**оплаченных** заказов с подставленным именем покупателя. "
                                "Результат должен содержать поля `_id` (id заказа), `user_name` и `amount`. "
                                "Отсортируйте по `_id` заказа по возрастанию."
                            ),
                            "fixture": {
                                "collection": "orders",
                                "documents": [
                                    {"_id": 101, "user_id": 1, "amount": 500,  "status": "paid"},
                                    {"_id": 102, "user_id": 2, "amount": 1200, "status": "paid"},
                                    {"_id": 103, "user_id": 1, "amount": 300,  "status": "cancelled"},
                                    {"_id": 104, "user_id": 3, "amount": 800,  "status": "paid"},
                                    {"_id": 105, "user_id": 2, "amount": 1500, "status": "paid"},
                                ],
                            },
                            "reference_solution": (
                                "db.orders.aggregate([\n"
                                "  { $match: { status: 'paid' } },\n"
                                "  { $lookup: { from: 'users', localField: 'user_id', foreignField: '_id', as: 'user' } },\n"
                                "  { $unwind: '$user' },\n"
                                "  { $project: { _id: 1, user_name: '$user.name', amount: 1 } },\n"
                                "  { $sort: { _id: 1 } }\n"
                                "])"
                            ),
                            # Тут к fixture нужны и orders, и users — но текущая модель fixture
                            # хранит только одну коллекцию. Чтобы добавить вторую, нужно расширение.
                            # Поэтому пока для этого задания используем старый подход —
                            # данные подмешиваем через documents с двумя коллекциями.
                            "max_score": 15,
                        },
                    ],
                },
            ],
        },
    ],
}


# ============================================================================
# КОНТЕНТ ОСТАЛЬНЫХ КУРСОВ — пока минимальный (заполним в следующих патчах)
# ============================================================================

REDIS_COURSE = {
    "title":       "Redis: кэш и структуры",
    "description": "Хранилище ключ-значение Redis. Работа со строками, хешами, списками, множествами, sorted sets и TTL.",
    "nosql_type":  NoSQLType.KEY_VALUE,
    "difficulty":  2,
    "modules": [

        # ============================================================
        # МОДУЛЬ 1. Строки и базовые операции
        # ============================================================
        {
            "title":       "Модуль 1. Строки и хеши",
            "description": "Базовые типы данных Redis: строки и хеши. Команды чтения, записи, инкремента.",
            "lessons": [

                # ---- Урок 1.1 ----
                {
                    "title":        "Что такое Redis",
                    "duration_min": 8,
                    "content_md": """# Что такое Redis

**Redis** (**RE**mote **DI**ctionary **S**erver) — это NoSQL-хранилище типа «ключ-значение», работающее в оперативной памяти. Главные особенности — высокая скорость (миллионы операций в секунду) и поддержка нескольких типов данных, не только строк.

## Чем Redis отличается от обычной БД

В отличие от реляционных СУБД, Redis:

- **Хранит данные в RAM** — отсюда скорость, но и ограничение по объёму.
- **Не имеет схемы** — каждый ключ независим, типы данных смешиваются свободно.
- **Не использует SQL** — вместо запросов есть набор простых команд (`SET`, `GET`, `INCR`, ...).
- **Однопоточный** для операций с данными, но это не проблема благодаря скорости памяти.

## Типичные сценарии

- **Кэширование** — самое частое применение. Перед обращением к медленной БД проверяем кэш.
- **Сессии пользователей** — токены, корзины, временные данные.
- **Счётчики и метрики** — просмотры страниц, лимиты запросов (rate limiting).
- **Очереди задач** — простые FIFO/LIFO структуры на списках.
- **Лидерборды и рейтинги** — sorted sets для упорядоченных данных по очкам.
- **Pub/Sub** и потоки сообщений (в этот курс не входят).

## Типы данных

Redis — не «просто словарь строк». Поддерживаемые типы:

| Тип             | Команды-префиксы | Применение                                |
|-----------------|------------------|-------------------------------------------|
| **String**      | `SET`, `GET`     | значения, JSON, счётчики                  |
| **Hash**        | `HSET`, `HGET`   | объекты с полями (профиль пользователя)    |
| **List**        | `LPUSH`, `RPOP`  | очереди, стеки                            |
| **Set**         | `SADD`, `SINTER` | множества, теги, уникальные посетители    |
| **Sorted Set**  | `ZADD`, `ZRANGE` | лидерборды, сортировка по очкам           |
| **Stream**      | `XADD`, `XREAD`  | потоки событий (вне этого курса)          |

## Команды и интерактивная песочница

В этом курсе ты будешь писать команды Redis в специальном редакторе. Каждая строка — отдельная команда. Возвращается результат **последней** команды. Например:

```
SET counter 10
INCR counter
GET counter
```

Здесь итоговый результат — `"11"`.

## Что дальше

В следующих уроках начнём с самого простого типа — строк, потом перейдём к хешам, спискам, множествам и в финале разберём TTL и атомарные операции.
""",
                },

                # ---- Урок 1.2: Счётчики INCR/DECR (с заданием — было в Step 1) ----
                {
                    "title":        "Счётчики: INCR и DECR",
                    "duration_min": 10,
                    "content_md": """# Счётчики в Redis

Одно из самых частых применений Redis — атомарные счётчики. Команды `INCR` и `DECR` увеличивают и уменьшают значение ключа на 1, а `INCRBY` / `DECRBY` — на произвольное число.

## Базовые команды для строк

| Команда                | Что делает                                       |
|------------------------|--------------------------------------------------|
| `SET key value`        | Установить значение                              |
| `GET key`              | Получить значение                                |
| `DEL key`              | Удалить ключ                                     |
| `EXISTS key`           | Проверить, существует ли ключ (`0` или `1`)      |
| `INCR key`             | Увеличить на 1 (создаёт ключ со значением 0, если нет) |
| `DECR key`             | Уменьшить на 1                                   |
| `INCRBY key N`         | Увеличить на N                                   |
| `DECRBY key N`         | Уменьшить на N                                   |
| `STRLEN key`           | Длина строки                                     |
| `APPEND key value`     | Дописать в конец строки                          |

## Атомарность — главное преимущество

Главное преимущество `INCR` — он **атомарен**. Это значит: даже если 1000 клиентов одновременно пошлют `INCR pageviews`, никаких гонок не будет. Каждый клиент получит уникальное увеличенное значение.

Это **не то же самое**, что последовательность `GET` + прибавить + `SET`! Между этими тремя операциями значение мог изменить кто-то другой, и инкремент потеряется.

## Пример

```
SET pageviews 0
INCR pageviews
INCR pageviews
INCRBY pageviews 5
GET pageviews
```

Результат последней команды: `"7"`.

## Подвох: значение всегда строка

Хотя `INCR` работает с числами, при `GET` Redis возвращает строку — `"7"`, а не `7`. Если значение нечисловое, `INCR` упадёт с ошибкой:

```
SET name Anna
INCR name        # ❌ ERR value is not an integer or out of range
```

## Практическое задание

Ниже под этим уроком — практическое задание на работу со счётчиком. Открой его, попробуй решить разными способами и нажми «Отправить» для проверки.
""",
                    "tasks": [
                        {
                            "statement": (
                                "В песочнице уже есть счётчик `views` со значением 10. "
                                "Увеличьте его на 5, затем ещё раз на 1, и верните итоговое "
                                "значение командой GET."
                            ),
                            "fixture": {
                                "preload": [
                                    "SET views 10",
                                ],
                            },
                            "reference_solution": "INCRBY views 5\nINCR views\nGET views",
                            "reference_solutions": [
                                "INCRBY views 6\nGET views",
                                "SET views 16\nGET views",
                            ],
                            "compare_ordered": True,
                            "max_score":      10,
                            "attempts_limit":  0,
                        },
                    ],
                },

                # ---- Урок 1.3: Хеши ----
                {
                    "title":        "Хеши: HSET и HGETALL",
                    "duration_min": 12,
                    "content_md": """# Хеши в Redis

**Хеш** в Redis — это структура «поле → значение» внутри одного ключа. Это аналог объекта или словаря: вместо того чтобы хранить пользователя как пять отдельных ключей `user:1:name`, `user:1:age`, ..., можно сложить всё в один хеш `user:1` с полями `name`, `age` и т.д.

## Основные команды

| Команда                          | Что делает                                |
|----------------------------------|-------------------------------------------|
| `HSET key field value [...]`     | Установить одно или несколько полей       |
| `HGET key field`                 | Получить значение поля                    |
| `HGETALL key`                    | Получить весь хеш как пары поле-значение  |
| `HDEL key field [field ...]`     | Удалить поле(я)                           |
| `HEXISTS key field`              | Проверить, есть ли поле (`0` или `1`)     |
| `HKEYS key`                      | Список всех полей                         |
| `HVALS key`                      | Список всех значений                      |
| `HLEN key`                       | Количество полей                          |
| `HINCRBY key field N`            | Увеличить числовое поле на N              |
| `HMGET key field1 field2 ...`    | Получить несколько полей за один запрос   |

## Пример: профиль пользователя

```
HSET user:1 name Anna age 25 city Moscow
HGET user:1 name           # "Anna"
HGETALL user:1             # все поля
HINCRBY user:1 age 1       # день рождения
HEXISTS user:1 email       # 0 — поля email нет
HSET user:1 email anna@example.com
```

## Когда хеш лучше JSON-строки

Можно было бы хранить профиль как JSON-строку: `SET user:1 '{"name":"Anna","age":25}'`. Но у хеша есть три преимущества:

- **Частичное чтение/запись** — можно достать или поменять одно поле, не трогая остальные. С JSON-строкой пришлось бы каждый раз парсить и пересобирать.
- **Атомарный инкремент поля** — `HINCRBY` для счётчиков внутри объекта.
- **Экономия памяти** — Redis оптимизирует маленькие хеши специальной упакованной формой (`ziplist`).

## Когда лучше JSON

Если структура сложная, со вложенными объектами и массивами — хеш не подходит (он плоский). В таких случаях либо разбивают на несколько ключей, либо хранят как JSON-строку.

## Практическое задание

Ниже под этим уроком — задание на работу с хешем. Нужно добавить поле, увеличить числовое поле и получить весь хеш.
""",
                    "tasks": [
                        {
                            "statement": (
                                "В песочнице уже есть хеш `user:42` с полями `name`, `age`, `city`. "
                                "Добавьте к нему поле `email` со значением `anna@example.com`, "
                                "увеличьте поле `age` на 1, и верните весь хеш командой HGETALL."
                            ),
                            "fixture": {
                                "preload": [
                                    "HSET user:42 name Anna age 25 city Moscow",
                                ],
                            },
                            "reference_solution": (
                                "HSET user:42 email anna@example.com\n"
                                "HINCRBY user:42 age 1\n"
                                "HGETALL user:42"
                            ),
                            "reference_solutions": [
                                "HSET user:42 email anna@example.com age 26\nHGETALL user:42",
                            ],
                            "compare_ordered": False,   # HGETALL — порядок полей не важен
                            "max_score":      10,
                            "attempts_limit":  0,
                        },
                    ],
                },
            ],
        },

        # ============================================================
        # МОДУЛЬ 2. Коллекции
        # ============================================================
        {
            "title":       "Модуль 2. Коллекции: списки, множества, sorted sets",
            "description": "Структуры данных Redis для работы с упорядоченными и неупорядоченными коллекциями.",
            "lessons": [

                # ---- Урок 2.1: Списки ----
                {
                    "title":        "Списки: очереди и стеки",
                    "duration_min": 12,
                    "content_md": """# Списки в Redis

**Список** в Redis — это упорядоченная коллекция строк, в которую можно добавлять элементы с обоих концов. Это базовая структура для очередей задач, стеков, последних N сообщений и т.п.

## Основные команды

| Команда                   | Что делает                                          |
|---------------------------|-----------------------------------------------------|
| `LPUSH key v1 [v2 ...]`   | Добавить элементы в начало (слева)                  |
| `RPUSH key v1 [v2 ...]`   | Добавить элементы в конец (справа)                  |
| `LPOP key`                | Извлечь и вернуть элемент слева                     |
| `RPOP key`                | Извлечь и вернуть элемент справа                    |
| `LRANGE key start stop`   | Получить срез по индексам (включительно)            |
| `LLEN key`                | Длина списка                                        |
| `LINDEX key i`            | Элемент по индексу                                  |
| `LREM key count value`    | Удалить элементы со значением `value`               |

Индексы — с нуля. `-1` означает последний, `-2` — предпоследний и т.д. `LRANGE key 0 -1` — весь список целиком.

## Пример: очередь задач

```
RPUSH queue "task1" "task2" "task3"
LPOP queue                 # "task1" — первая задача (FIFO)
LRANGE queue 0 -1          # ["task2", "task3"] — что осталось
LLEN queue                 # 2
```

`RPUSH` + `LPOP` = классическая очередь FIFO (first in, first out).
`LPUSH` + `LPOP` = стек LIFO (last in, first out).

## Пример: последние N логов

Часто нужно хранить только N последних событий. Сочетание `LPUSH` + `LTRIM` решает задачу:

```
LPUSH logs "event-1"
LPUSH logs "event-2"
LPUSH logs "event-3"
LTRIM logs 0 99            # оставить только 100 последних
```

## Подсказка по индексам

В `LRANGE`:

- `LRANGE key 0 0` — только первый элемент
- `LRANGE key -1 -1` — только последний
- `LRANGE key 0 -1` — все
- `LRANGE key 0 9` — первые 10

## Практическое задание

Ниже — задание на работу с очередью: извлечь элемент, добавить новый, проверить итоговое состояние.
""",
                    "tasks": [
                        {
                            "statement": (
                                "В песочнице уже есть очередь `queue` с 4 задачами: "
                                "`task1`, `task2`, `task3`, `task4`. "
                                "Извлеките первую задачу (FIFO — слева), добавьте новую задачу "
                                "`task5` в конец, и верните все элементы очереди в их текущем порядке."
                            ),
                            "fixture": {
                                "preload": [
                                    "RPUSH queue task1 task2 task3 task4",
                                ],
                            },
                            "reference_solution": (
                                "LPOP queue\n"
                                "RPUSH queue task5\n"
                                "LRANGE queue 0 -1"
                            ),
                            "reference_solutions": [
                                "RPUSH queue task5\nLPOP queue\nLRANGE queue 0 -1",
                            ],
                            "compare_ordered": True,  # LRANGE — порядок важен
                            "max_score":      10,
                            "attempts_limit":  0,
                        },
                    ],
                },

                # ---- Урок 2.2: Множества ----
                {
                    "title":        "Множества: SADD и операции над ними",
                    "duration_min": 10,
                    "content_md": """# Множества в Redis

**Множество** (set) — это неупорядоченная коллекция уникальных строк. Если попытаться добавить элемент, который уже есть, ничего не произойдёт (без ошибки, просто `0` в ответе вместо `1`).

## Основные команды

| Команда                            | Что делает                              |
|------------------------------------|-----------------------------------------|
| `SADD key v1 [v2 ...]`             | Добавить элементы                       |
| `SREM key v1 [v2 ...]`             | Удалить элементы                        |
| `SMEMBERS key`                     | Все элементы (без определённого порядка)|
| `SISMEMBER key v`                  | Есть ли элемент (`0` или `1`)           |
| `SCARD key`                        | Количество элементов                    |
| `SINTER key1 key2 [...]`           | Пересечение нескольких множеств         |
| `SUNION key1 key2 [...]`           | Объединение                             |
| `SDIFF  key1 key2 [...]`           | Разность (что есть в первом, но нет в остальных) |
| `SRANDMEMBER key [count]`          | Случайный элемент                       |
| `SPOP key [count]`                 | Случайный элемент с удалением           |

## Где применяются множества

- **Теги** — `SADD post:1:tags "python" "redis" "tutorial"`.
- **Уникальные посетители за день** — `SADD visitors:2024-04-27 user_id`. В конце дня `SCARD` даст количество.
- **Социальные графы** — `SADD followers:alice "bob" "carol"`, потом `SINTER` для общих друзей.
- **Anti-spam / blacklist** — быстрая проверка `SISMEMBER blocked_ips $ip`.

## Пример: общие интересы

```
SADD tags:python "lang" "web" "async"
SADD tags:rust   "lang" "web" "async" "low-level"
SINTER tags:python tags:rust          # ["lang", "web", "async"]
SDIFF  tags:rust  tags:python         # ["low-level"]
```

## Особенность сравнения в этом курсе

В Redis множества неупорядочены, но при сравнении с эталонным решением мы автоматически сортируем результат `SMEMBERS`/`SINTER`/`SUNION`/`SDIFF` — иначе сравнение было бы недетерминированным. Просто помни: **порядок в выводе множеств не предсказуем**, и не пытайся написать решение, которое от него зависит.
""",
                    "tasks": [],
                },

                # ---- Урок 2.3: Sorted sets ----
                {
                    "title":        "Sorted sets: лидерборды и ранжирование",
                    "duration_min": 14,
                    "content_md": """# Sorted Sets (ZSET) — упорядоченные множества

**Sorted set** — это множество, в котором каждому элементу прикреплено числовое **очко** (score), и элементы автоматически держатся в отсортированном по очкам порядке. Это самая мощная структура Redis — на ней строят лидерборды, очереди приоритетов, рейтинги.

## Основные команды

| Команда                                       | Что делает                                     |
|-----------------------------------------------|------------------------------------------------|
| `ZADD key score1 member1 [score2 member2]`    | Добавить элемент(ы) с очками                   |
| `ZREM key m1 [m2 ...]`                        | Удалить элементы                               |
| `ZRANGE key start stop [REV] [WITHSCORES]`    | Срез по позициям; `REV` — в обратном порядке   |
| `ZRANGEBYSCORE key min max`                   | Элементы с очками в диапазоне                  |
| `ZSCORE key member`                           | Очки конкретного элемента                      |
| `ZRANK key member`                            | Позиция (с нуля, по возрастанию)               |
| `ZREVRANK key member`                         | Позиция по убыванию                            |
| `ZINCRBY key delta member`                    | Увеличить очки                                 |
| `ZCARD key`                                   | Размер множества                               |
| `ZCOUNT key min max`                          | Сколько элементов в диапазоне очков            |

## Пример: лидерборд

```
ZADD scores 100 alice 250 bob 175 carol
ZRANGE scores 0 -1 REV WITHSCORES
# ["bob", "250", "carol", "175", "alice", "100"]

ZINCRBY scores 50 alice              # 150 — игрок набрал ещё 50
ZRANK   scores carol                 # 1 (с нуля, по возрастанию: alice=150, carol=175, bob=250)
ZREVRANK scores bob                  # 0 (по убыванию)
```

Обрати внимание на формат вывода `ZRANGE WITHSCORES`: это **плоский** список вида `[member, score, member, score, ...]`, а не список пар. В нашей песочнице очки приходят как строки (`"250"`, не `250`) — это особенность Redis-протокола.

## Топ-N

```
ZRANGE scores 0 9 REV WITHSCORES     # топ-10 лучших
```

## Диапазон очков

```
ZRANGEBYSCORE scores 100 200         # все игроки с 100..200 очками
```

## Практическое задание

Ниже — задание на лидерборд: нужно увеличить очки игрока и вернуть топ-3.
""",
                    "tasks": [
                        {
                            "statement": (
                                "В песочнице есть лидерборд `leaderboard` с 4 игроками: "
                                "alice (100), bob (250), carol (175), dave (90). "
                                "Игрок `alice` набрал ещё 200 очков — увеличьте её счёт. "
                                "Затем верните топ-3 игроков по убыванию очков, вместе с их очками."
                            ),
                            "fixture": {
                                "preload": [
                                    "ZADD leaderboard 100 alice 250 bob 175 carol 90 dave",
                                ],
                            },
                            "reference_solution": (
                                "ZINCRBY leaderboard 200 alice\n"
                                "ZRANGE leaderboard 0 2 REV WITHSCORES"
                            ),
                            "reference_solutions": [
                                "ZADD leaderboard 300 alice\nZRANGE leaderboard 0 2 REV WITHSCORES",
                                "ZINCRBY leaderboard 200 alice\nZREVRANGE leaderboard 0 2 WITHSCORES",
                            ],
                            "compare_ordered": True,  # топ-N — порядок критичен
                            "max_score":      15,
                            "attempts_limit":  0,
                        },
                    ],
                },
            ],
        },

        # ============================================================
        # МОДУЛЬ 3. Паттерны применения
        # ============================================================
        {
            "title":       "Модуль 3. TTL, кэширование и атомарность",
            "description": "Время жизни ключей, стратегии кэширования, атомарные операции.",
            "lessons": [

                # ---- Урок 3.1: TTL и кэширование ----
                {
                    "title":        "TTL: время жизни ключей и кэширование",
                    "duration_min": 12,
                    "content_md": """# Время жизни ключей (TTL)

Любому ключу в Redis можно назначить **время жизни** — через сколько секунд (или миллисекунд) ключ автоматически удалится. Это основа кэширования: данные «живут» в Redis ровно столько, сколько мы готовы получать устаревшую информацию.

## Команды для TTL

| Команда                     | Что делает                                            |
|-----------------------------|-------------------------------------------------------|
| `EXPIRE key seconds`        | Установить TTL в секундах                             |
| `PEXPIRE key milliseconds`  | TTL в миллисекундах                                   |
| `TTL key`                   | Сколько секунд осталось (`-1` если нет TTL, `-2` если ключа нет) |
| `PTTL key`                  | Остаток в миллисекундах                               |
| `PERSIST key`               | Снять TTL — ключ станет жить вечно                    |
| `SETEX key seconds value`   | Атомарно: SET + EXPIRE                                |
| `PSETEX key ms value`       | То же в миллисекундах                                 |

## Пример: кэш с TTL

```
SETEX cache:user:42 60 '{"name":"Anna"}'    # живёт 60 секунд
TTL cache:user:42                            # 60 (или 59)
GET cache:user:42                            # пока живо
# через минуту:
GET cache:user:42                            # (nil) — удалилось автоматически
```

`SETEX` атомарен — это SET и EXPIRE одной командой. Без него пришлось бы делать две команды:

```
SET cache:user:42 '{"name":"Anna"}'
EXPIRE cache:user:42 60
```

И между ними теоретически могла бы случиться авария — ключ остался бы без TTL.

## Стратегии кэширования

### Cache-Aside (Lazy Loading)

Самая распространённая. Приложение само управляет кэшем:

1. Запрос данных — сначала смотрим в Redis.
2. Если есть — возвращаем (cache hit).
3. Если нет — идём в основную БД, возвращаем результат, **и кладём в Redis** с TTL.

```python
def get_user(user_id):
    cached = redis.get(f"user:{user_id}")
    if cached:
        return json.loads(cached)
    user = db.query(...)
    redis.setex(f"user:{user_id}", 300, json.dumps(user))
    return user
```

### Write-Through

Любая запись идёт сразу и в БД, и в кэш. Дороже, но кэш всегда актуален.

### Write-Behind

Записи буферизуются в Redis, в БД сбрасываются периодически. Очень быстро, но риск потерять данные при сбое.

## Подвох: TTL не наследуется

Когда ты делаешь `INCR` или `HSET` на существующий ключ — TTL **не сбрасывается**. Но когда делаешь полный `SET` — старый TTL **слетает** (если не использовать `KEEPTTL`).

```
SETEX counter 60 0
INCR counter        # TTL остаётся
SET counter 0       # ❌ TTL слетел, ключ стал бессрочным
SET counter 0 KEEPTTL  # ✓ TTL сохраняется (Redis 6+)
```

## Практическое задание

Ниже — задание на создание кэш-записи с TTL.
""",
                    "tasks": [
                        {
                            "statement": (
                                "Создайте в песочнице кэш-запись для сессии пользователя: "
                                "ключ `session:user2` со значением `xyz789` и временем жизни 300 секунд. "
                                "Затем верните оставшееся время жизни этого ключа командой TTL."
                            ),
                            "fixture": {
                                "preload": [
                                    # Просто чтобы показать, что в кэше уже что-то есть
                                    "SET session:user1 abc123",
                                ],
                            },
                            "reference_solution": (
                                "SETEX session:user2 300 xyz789\n"
                                "TTL session:user2"
                            ),
                            "reference_solutions": [
                                "SET session:user2 xyz789\n"
                                "EXPIRE session:user2 300\n"
                                "TTL session:user2",
                            ],
                            "compare_ordered": True,
                            "max_score":      10,
                            "attempts_limit":  0,
                        },
                    ],
                },

                # ---- Урок 3.2: Атомарность ----
                {
                    "title":        "Атомарность: INCR vs GET+SET",
                    "duration_min": 10,
                    "content_md": """# Атомарные операции — почему это важно

Redis выполняет команды **по одной за раз**, в строгом порядке. Это означает, что внутри одной команды никаких гонок нет: `INCR`, `SADD`, `HSET` всегда атомарны.

Но если ты разбиваешь логику на несколько команд — между ними другой клиент может вклиниться.

## Классическая ошибка: счётчик через GET+SET

Допустим, мы хотим увеличить счётчик. **Неправильный** способ:

```
GET counter        # вернуло "5"
# (приложение прибавляет 1)
SET counter 6
```

Если 100 клиентов делают это одновременно, **счётчик потеряет инкременты**: они все прочитают `5`, все запишут `6`, а должно было получиться `105`.

## Правильно: INCR

```
INCR counter
```

Эта одна команда атомарна. 100 клиентов одновременно вызывают `INCR` — счётчик честно станет `105`.

## Что атомарно «из коробки»

- Любая **одна** команда Redis. Полностью.
- `INCR`, `INCRBY`, `DECR`, `DECRBY`, `INCRBYFLOAT`
- `HINCRBY`, `HINCRBYFLOAT`
- `ZINCRBY`
- `LPUSH`, `RPUSH`, `LPOP`, `RPOP`
- `SETEX` (вместо двух команд `SET` + `EXPIRE`)
- `SETNX` («set if not exists» — основа для распределённых блокировок)
- `GETSET` (получить старое и установить новое)

## Когда нужно несколько команд атомарно

Если логика требует нескольких команд (например, переложить элемент из одного списка в другой), есть несколько подходов:

### MULTI / EXEC (транзакции)

Команды между `MULTI` и `EXEC` выполняются как одна последовательность:

```
MULTI
LPOP queue:in
RPUSH queue:out "moved"
EXEC
```

Между ними другие клиенты не вклинятся. *Эта тема в задания этого курса не входит.*

### Lua-скрипты

Сложную логику можно завернуть в скрипт `EVAL` — он выполнится атомарно на сервере. *Тоже вне курса.*

## Связка с предыдущим уроком: счётчик с TTL

Часто нужен счётчик, который сам сбрасывается через сутки (для rate limiting, например):

```
INCR rate:user:42
EXPIRE rate:user:42 86400   # установить TTL только при создании
```

Здесь есть тонкость: после первого `INCR` ключ существует, и `EXPIRE` каждый раз обновлял бы TTL. Чтобы установить TTL только однажды, проверяют:

```
INCR rate:user:42
TTL  rate:user:42          # если -1 (нет TTL), значит ключ только что создан
```

Или используют Lua-скрипт.

## Резюме

- Одиночные команды Redis — атомарны.
- Связки `GET` + ... + `SET` — НЕ атомарны.
- Для счётчиков всегда используй `INCR`, никогда `GET`+`SET`.
- Для условного «set if not exists» — `SETNX`, не `EXISTS`+`SET`.
- Для атомарной установки с TTL — `SETEX`, не `SET`+`EXPIRE`.

В этом уроке заданий нет — это теоретический материал. На защите ВКР этот урок поможет ответить на возможные вопросы про concurrency и race conditions.
""",
                    "tasks": [],
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

        # ============================================================
        # МОДУЛЬ 1. Введение в Cassandra и CQL
        # ============================================================
        {
            "title":       "Модуль 1. Введение в Cassandra и CQL",
            "description": "Колоночная модель данных, базовые команды CQL.",
            "lessons": [

                # ---- Урок 1.1 ----
                {
                    "title":        "Что такое Cassandra",
                    "duration_min": 10,
                    "content_md": """# Что такое Apache Cassandra

**Apache Cassandra** — распределённая NoSQL-база данных, спроектированная для линейного горизонтального масштабирования и высокой доступности. Изначально создавалась в Facebook для системы поиска по сообщениям, позже стала open-source проектом Apache.

## Ключевые свойства

- **Peer-to-peer архитектура** — все узлы равноправны, нет ведущего/ведомого. Любой узел может принять запрос.
- **Линейное масштабирование** — добавление узлов увеличивает пропускную способность пропорционально, без перекройки данных.
- **Tunable consistency** — для каждого запроса можно выбрать уровень согласованности: от ONE (быстро, но возможна устаревшая запись) до ALL (медленно, но гарантия).
- **Оптимизирована под запись** — структура SSTable + memtable делает запись очень быстрой.
- **Без единой точки отказа** — выход одного узла не останавливает кластер.

## Когда использовать

Cassandra хороша для нагрузок, где:

- Объём данных огромен (террабайты-петабайты)
- Запись преобладает над чтением, либо чтение идёт по простым ключам
- Нужна высокая доступность (ритейл, IoT, мониторинг, временные ряды, метрики)
- Можно простить eventual consistency

Плохо подходит для сложных аналитических запросов с JOIN'ами, агрегациями по произвольным полям, транзакций. Эту нишу занимают реляционные БД и ClickHouse.

## CQL — язык запросов

Cassandra Query Language (CQL) синтаксически похож на SQL: те же `SELECT`, `INSERT`, `UPDATE`, `DELETE`, `CREATE TABLE`. Но **семантика принципиально другая**: нет JOIN'ов, нет группировки по произвольным полям, фильтр должен использовать ключи таблицы.

### Пример

```cql
-- Создаём таблицу
CREATE TABLE users (
    user_id int PRIMARY KEY,
    name text,
    email text
);

-- Вставляем данные
INSERT INTO users (user_id, name, email) VALUES (1, 'Anna', 'anna@example.com');

-- Читаем
SELECT * FROM users WHERE user_id = 1;
```

> Cassandra проектировалась с принципом **«запрос определяет схему»**: сначала ты понимаешь, какие запросы тебе нужны, и под них строишь таблицы. В реляционных БД наоборот — схема первична, запросы пишутся как угодно.

В следующем уроке создадим первую таблицу и сделаем простые SELECT/INSERT.
""",
                },

                # ---- Урок 1.2 (с заданием) ----
                {
                    "title":        "Первая таблица: CREATE, INSERT, SELECT",
                    "duration_min": 12,
                    "content_md": """# Создание таблицы и работа с данными

В этом уроке создадим простую таблицу и научимся вставлять и читать данные.

## CREATE TABLE — синтаксис

```cql
CREATE TABLE table_name (
    column1 type1,
    column2 type2,
    ...
    PRIMARY KEY (column1)
);
```

Можно объявить первичный ключ inline: `column1 type1 PRIMARY KEY`.

## Базовые типы CQL

| Тип       | Что хранит                     |
|-----------|--------------------------------|
| `int`     | 32-битное целое                |
| `bigint`  | 64-битное целое                |
| `text`    | Строка UTF-8                   |
| `boolean` | true/false                     |
| `uuid`    | UUID                           |
| `timestamp` | Дата+время                   |
| `decimal` | Точное десятичное число        |
| `float`, `double` | Числа с плавающей точкой |

Также есть коллекции — `set<T>`, `list<T>`, `map<K, V>`. Их разберём в одном из следующих уроков.

## INSERT

```cql
INSERT INTO users (user_id, name, email) VALUES (1, 'Anna', 'anna@example.com');
```

Если ключ совпадает с уже существующим — данные **перезаписываются** (upsert). В Cassandra нет такого понятия, как «нарушение уникального ключа».

## SELECT

```cql
SELECT * FROM users;                    -- все строки, все колонки
SELECT name, email FROM users;          -- только указанные колонки
SELECT * FROM users WHERE user_id = 1;  -- по партиционному ключу
```

Важная особенность Cassandra: фильтр в `WHERE` обычно должен использовать партиционный ключ. Иначе нужно `ALLOW FILTERING`, что Cassandra делать не любит и ругается.

## Песочница в этом курсе

В песочнице автоматически создаётся свежий keyspace перед каждой проверкой и удаляется после. Это значит:

- **Не нужно** писать `CREATE KEYSPACE` или `USE` — keyspace уже выбран.
- **Каждый запуск изолирован** — данные одной проверки не попадут в другую.
- Можешь спокойно писать `CREATE TABLE`, `INSERT`, `SELECT` — всё в свежем окружении.

## Практическое задание

Под этим уроком — задание: создать таблицу, вставить три строки, прочитать одну по ключу.
""",
                    "tasks": [
                        {
                            "statement": (
                                "Создайте таблицу `users` с колонками `user_id` (int, "
                                "первичный ключ), `name` (text), `email` (text). "
                                "Вставьте трёх пользователей: (1, Anna, anna@example.com), "
                                "(2, Bob, bob@example.com), (3, Carol, carol@example.com). "
                                "Затем вернитe пользователя с user_id = 2 командой SELECT."
                            ),
                            "fixture": {"preload": []},
                            "reference_solution": (
                                "CREATE TABLE users (user_id int PRIMARY KEY, name text, email text);\n"
                                "INSERT INTO users (user_id, name, email) VALUES (1, 'Anna', 'anna@example.com');\n"
                                "INSERT INTO users (user_id, name, email) VALUES (2, 'Bob', 'bob@example.com');\n"
                                "INSERT INTO users (user_id, name, email) VALUES (3, 'Carol', 'carol@example.com');\n"
                                "SELECT * FROM users WHERE user_id = 2;"
                            ),
                            "reference_solutions": [
                                "CREATE TABLE users (user_id int, name text, email text, PRIMARY KEY (user_id));\n"
                                "INSERT INTO users (user_id, name, email) VALUES (1, 'Anna', 'anna@example.com');\n"
                                "INSERT INTO users (user_id, name, email) VALUES (2, 'Bob', 'bob@example.com');\n"
                                "INSERT INTO users (user_id, name, email) VALUES (3, 'Carol', 'carol@example.com');\n"
                                "SELECT * FROM users WHERE user_id = 2;",
                            ],
                            "compare_ordered": False,
                            "max_score":      10,
                            "attempts_limit":  0,
                        },
                    ],
                },

                # ---- Урок 1.3 (теория) ----
                {
                    "title":        "Keyspace и базовые типы CQL",
                    "duration_min": 10,
                    "content_md": """# Keyspace — пространство имён для таблиц

В Cassandra **keyspace** — это аналог «базы данных» в реляционных СУБД. Это контейнер для таблиц, в котором задаются параметры репликации.

## Создание keyspace

```cql
CREATE KEYSPACE my_app
WITH REPLICATION = {
    'class': 'SimpleStrategy',
    'replication_factor': 3
};
```

- `SimpleStrategy` — для одного дата-центра. В продакшене обычно используют `NetworkTopologyStrategy`, где можно задать число реплик в каждом дата-центре отдельно.
- `replication_factor: 3` — данные хранятся в трёх копиях на разных узлах.

После создания нужно «переключиться» на keyspace:

```cql
USE my_app;
```

После этого все CREATE TABLE, INSERT, SELECT будут работать в этом keyspace.

> В нашей песочнице `CREATE KEYSPACE` и `USE` запрещены — keyspace создаётся автоматически перед каждой проверкой и удаляется после. Студент работает только с таблицами.

## Типы CQL подробнее

В прошлом уроке мы упомянули базовые типы. Теперь — несколько практических подсказок.

### Числовые

| Тип        | Размер           | Когда использовать                       |
|------------|------------------|------------------------------------------|
| `tinyint`  | 1 байт (-128..127) | флаги, маленькие счётчики              |
| `smallint` | 2 байта           | возраст, год, маленькие ID              |
| `int`      | 4 байта           | стандартный целочисленный тип           |
| `bigint`   | 8 байт            | большие счётчики, timestamps в мс       |
| `varint`   | произвольный      | редко — точные большие числа            |
| `float`    | 4 байта           | приближённые дробные числа              |
| `double`   | 8 байт            | приближённые дробные числа высокой точности |
| `decimal`  | произвольный      | деньги, точные дробные числа            |

### Строковые

- `text` (он же `varchar`) — UTF-8 строка любой длины. Используется в 99% случаев.
- `ascii` — только ASCII-символы. Чуть быстрее, но почти никогда не нужен.

### Время и UUID

- `timestamp` — дата + время с миллисекундами. Записывается как `'2024-01-15 14:30:00'` или ISO-строкой.
- `date` — только дата, без времени.
- `time` — только время, без даты.
- `uuid` — UUID v4 (случайный).
- `timeuuid` — UUID v1 (содержит timestamp). Удобен как кластерный ключ — упорядочен по времени.

### Бинарные

- `blob` — массив байт. Подходит для маленьких файлов или сериализованных структур. Но обычно файлы хранят отдельно (S3, диск), а в Cassandra — только ссылки.

### Коллекции

- `set<T>` — множество уникальных элементов.
- `list<T>` — упорядоченный список с дубликатами.
- `map<K, V>` — ассоциативный массив.

Эти типы хороши для маленьких коллекций (до ~100 элементов). Для больших — лучше моделировать через отдельную таблицу с кластерным ключом.

В одном из следующих уроков мы будем использовать `set<text>` для тегов статьи.

## Что дальше

В следующем модуле научимся фильтровать данные по партиционному ключу и работать с кластерными ключами для упорядочивания.
""",
                },
            ],
        },

        # ============================================================
        # МОДУЛЬ 2. Запросы и проекции
        # ============================================================
        {
            "title":       "Модуль 2. Запросы и проекции",
            "description": "Фильтрация по партиционному ключу, кластерные ключи, обновление и удаление данных.",
            "lessons": [

                # ---- Урок 2.1 ----
                {
                    "title":        "Фильтрация по партиционному ключу",
                    "duration_min": 14,
                    "content_md": """# Фильтрация по партиционному ключу

Главное отличие Cassandra от SQL — **запросы должны идти по ключу таблицы**. Это не каприз, а следствие архитектуры: данные распределены по узлам именно по партиционному ключу, и без него Cassandra не может эффективно их найти.

## Что такое партиционный ключ

Когда мы пишем `PRIMARY KEY (author_id)`, поле `author_id` становится **партиционным ключом**. Cassandra хеширует его и по хешу определяет, на каком узле лежит строка.

Партиционный ключ может быть составным:

```cql
CREATE TABLE messages (
    chat_id int,
    msg_id int,
    text text,
    PRIMARY KEY (chat_id, msg_id)
);
```

Здесь `chat_id` — партиционный ключ (по нему распределение), `msg_id` — кластерный (упорядочивание внутри партиции).

Чтобы партиционный ключ был **составным** (несколько полей), его берут в скобки:

```cql
PRIMARY KEY ((chat_id, date), msg_id)
```

Тут партиция — это пара `(chat_id, date)`, а кластер — `msg_id`.

## SELECT с фильтром

```cql
-- ВАЛИДНО: фильтр по партиционному ключу
SELECT * FROM messages WHERE chat_id = 42;

-- ВАЛИДНО: партиционный ключ + кластерный
SELECT * FROM messages WHERE chat_id = 42 AND msg_id = 100;

-- НЕ РАБОТАЕТ: фильтр без партиционного ключа
SELECT * FROM messages WHERE msg_id = 100;
-- ❌ InvalidRequest: PRIMARY KEY column "msg_id" cannot be restricted...
```

## ALLOW FILTERING — мина замедленного действия

Cassandra может позволить фильтрацию по неключевым полям, если добавить `ALLOW FILTERING`:

```cql
SELECT * FROM users WHERE name = 'Anna' ALLOW FILTERING;
```

Но это означает, что Cassandra **просканирует все узлы**, прочитает каждую строку и отфильтрует в памяти. На таблице с миллиардами строк это ляжет за секунды и заблокирует кластер. **Никогда не используй `ALLOW FILTERING` в продакшене** — это либо признак неправильной модели данных, либо одноразовый аналитический запрос.

Правильное решение — создать **отдельную таблицу** с нужным партиционным ключом. Например, `users_by_name`, где партиционный ключ — `name`. Это и называется query-driven design (про него — в Модуле 3).

## Операторы в WHERE

Для партиционного ключа доступны:

- `=` — точное совпадение (основной случай)
- `IN (a, b, c)` — несколько значений (Cassandra сделает несколько запросов)

Сравнения `<`, `>`, `<=`, `>=` для партиционного ключа **не работают** — потому что хеш не упорядочен по значению. Эти операторы доступны только для кластерных ключей.

## Практическое задание

Ниже — задание: в таблице `posts` найти все посты конкретного автора.
""",
                    "tasks": [
                        {
                            "statement": (
                                "В песочнице уже есть таблица `posts` с постами разных "
                                "авторов: 3 поста автора 1 (post_id 101, 102, 103), "
                                "1 пост автора 2 и 1 пост автора 3. Верните все посты автора "
                                "с `author_id = 1` — поля `post_id` и `title`."
                            ),
                            "fixture": {
                                "preload": [
                                    "CREATE TABLE posts (author_id int, post_id int, title text, PRIMARY KEY (author_id, post_id));",
                                    "INSERT INTO posts (author_id, post_id, title) VALUES (1, 101, 'Привет всем');",
                                    "INSERT INTO posts (author_id, post_id, title) VALUES (1, 102, 'Второй пост');",
                                    "INSERT INTO posts (author_id, post_id, title) VALUES (1, 103, 'Третий пост');",
                                    "INSERT INTO posts (author_id, post_id, title) VALUES (2, 201, 'Чужой пост');",
                                    "INSERT INTO posts (author_id, post_id, title) VALUES (3, 301, 'Ещё чужой пост');",
                                ],
                            },
                            "reference_solution": (
                                "SELECT post_id, title FROM posts WHERE author_id = 1;"
                            ),
                            "reference_solutions": [],
                            "compare_ordered": True,  # порядок по кластерному ключу определён
                            "max_score":      10,
                            "attempts_limit":  0,
                        },
                    ],
                },

                # ---- Урок 2.2 ----
                {
                    "title":        "Кластерные ключи и порядок сортировки",
                    "duration_min": 14,
                    "content_md": """# Кластерные ключи: упорядочивание внутри партиции

Партиционный ключ определяет, **на каком узле** лежат данные. Кластерный ключ определяет, **в каком порядке** строки лежат внутри одной партиции на этом узле.

## Простой пример

```cql
CREATE TABLE messages (
    chat_id int,
    msg_id int,
    text text,
    PRIMARY KEY (chat_id, msg_id)
);
```

- `chat_id` — партиционный ключ (по нему распределение).
- `msg_id` — кластерный ключ. Внутри одного `chat_id` строки физически хранятся в порядке возрастания `msg_id`.

Это значит:

```cql
SELECT * FROM messages WHERE chat_id = 42;
-- Вернёт сообщения в порядке возрастания msg_id (самые старые первыми)

SELECT * FROM messages WHERE chat_id = 42 LIMIT 10;
-- Самые ранние 10 сообщений

SELECT * FROM messages WHERE chat_id = 42 ORDER BY msg_id DESC LIMIT 10;
-- Последние 10 сообщений
```

## CLUSTERING ORDER BY — изменение порядка по умолчанию

Часто нужно «по умолчанию хранить от новых к старым» — для лент, событий, чатов. Это делается так:

```cql
CREATE TABLE events (
    user_id int,
    event_time timestamp,
    event_type text,
    PRIMARY KEY (user_id, event_time)
) WITH CLUSTERING ORDER BY (event_time DESC);
```

Теперь `SELECT ... LIMIT 3` сразу даст три самых свежих события, без `ORDER BY`. Это эффективно — Cassandra просто берёт первые строки в физическом порядке.

```cql
SELECT event_time, event_type FROM events WHERE user_id = 5 LIMIT 3;
-- Три последних события user_id = 5
```

## Несколько кластерных ключей

```cql
CREATE TABLE forum (
    forum_id int,
    thread_id int,
    msg_id int,
    body text,
    PRIMARY KEY (forum_id, thread_id, msg_id)
);
```

Тут партиция — `forum_id`. Внутри партиции строки сначала упорядочены по `thread_id`, потом по `msg_id`. Это иерархическое упорядочивание.

## Диапазон по кластерному ключу

В отличие от партиционного, по кластерному ключу можно делать диапазонные запросы:

```cql
SELECT * FROM messages
WHERE chat_id = 42
  AND msg_id >= 100
  AND msg_id < 200;
```

Это эффективно — Cassandra просто читает кусок партиции.

## Подвох: ORDER BY и составной ключ

Если у тебя несколько кластерных ключей, `ORDER BY` должен либо повторять направление по умолчанию, либо инвертировать **все** кластерные ключи. Нельзя отсортировать по второму, не отсортировав по первому.

## Практическое задание

Ниже — задание про события пользователя. Таблица создана с `CLUSTERING ORDER BY (event_time DESC)` — то есть события уже физически хранятся от новых к старым.
""",
                    "tasks": [
                        {
                            "statement": (
                                "В таблице `events` хранятся события пользователей. Таблица "
                                "создана с `CLUSTERING ORDER BY (event_time DESC)`, то есть "
                                "события уже хранятся от новых к старым. Верните последние 3 "
                                "события пользователя с `user_id = 5` — поля `event_time` и "
                                "`event_type`."
                            ),
                            "fixture": {
                                "preload": [
                                    "CREATE TABLE events (user_id int, event_time timestamp, event_type text, PRIMARY KEY (user_id, event_time)) WITH CLUSTERING ORDER BY (event_time DESC);",
                                    "INSERT INTO events (user_id, event_time, event_type) VALUES (5, '2024-01-01 10:00:00', 'login');",
                                    "INSERT INTO events (user_id, event_time, event_type) VALUES (5, '2024-01-02 11:00:00', 'click');",
                                    "INSERT INTO events (user_id, event_time, event_type) VALUES (5, '2024-01-03 12:00:00', 'purchase');",
                                    "INSERT INTO events (user_id, event_time, event_type) VALUES (5, '2024-01-04 13:00:00', 'logout');",
                                    "INSERT INTO events (user_id, event_time, event_type) VALUES (5, '2024-01-05 14:00:00', 'login');",
                                    "INSERT INTO events (user_id, event_time, event_type) VALUES (7, '2024-01-01 10:00:00', 'login');",
                                ],
                            },
                            "reference_solution": (
                                "SELECT event_time, event_type FROM events WHERE user_id = 5 LIMIT 3;"
                            ),
                            "reference_solutions": [],
                            "compare_ordered": True,
                            "max_score":      15,
                            "attempts_limit":  0,
                        },
                    ],
                },

                # ---- Урок 2.3 ----
                {
                    "title":        "UPDATE и DELETE",
                    "duration_min": 12,
                    "content_md": """# Изменение и удаление данных

В Cassandra UPDATE и DELETE работают почти как в SQL, но с нюансами.

## UPDATE

```cql
UPDATE inventory SET stock = 45 WHERE product_id = 10;
```

Важно: `WHERE` обязательно должен указать **полный** первичный ключ. Нельзя обновить «всю партицию» одной командой — только конкретную строку.

Можно обновить несколько колонок сразу:

```cql
UPDATE users SET name = 'Anna', email = 'anna@new.com' WHERE user_id = 1;
```

### UPSERT — UPDATE равно INSERT

Если строки с таким ключом ещё нет — `UPDATE` создаст её. В Cassandra нет разницы между INSERT и UPDATE: оба работают как upsert. Это удобно, но иногда сюрприз: если ты опечатался в ключе, ты не получишь ошибку «строки не существует» — просто создастся новая.

### Условный UPDATE (LWT)

Если нужно «обновить, только если значение было таким-то», есть `IF`:

```cql
UPDATE accounts SET balance = 100 WHERE id = 1 IF balance = 90;
```

Это **lightweight transaction (LWT)** — она использует Paxos и сильно медленнее обычного UPDATE. Использовать только когда действительно нужна гонка-безопасная проверка.

## DELETE

```cql
DELETE FROM inventory WHERE product_id = 10;
```

Можно удалить только конкретные колонки:

```cql
DELETE email FROM users WHERE user_id = 1;
```

Это пометит колонку `email` как удалённую (значение станет NULL), но саму строку сохранит.

## Подвох: DELETE и tombstone

Когда ты удаляешь строку, Cassandra **не стирает её сразу**. Вместо этого она пишет специальную метку — **tombstone** (надгробие). Tombstone живёт `gc_grace_seconds` (по умолчанию 10 дней), потом удаляется при compaction.

Это означает:
- Удалённые строки могут «оживать», если узел был офлайн дольше gc_grace_seconds, а потом вернулся (поэтому ремонт `nodetool repair` критичен).
- Большое количество tombstones замедляет SELECT — Cassandra их пропускает, но всё равно читает.

Простой совет: не удаляй много строк подряд в одной партиции. Если нужна «временная» таблица — используй TTL (про него в следующем уроке).

## TRUNCATE

```cql
TRUNCATE inventory;
```

Это полная очистка таблицы. Быстрее, чем `DELETE FROM inventory` (для каждой строки), но **необратимо** и пишет в commit-log.

## Практическое задание

Под этим уроком — задание: обновить остаток одного товара, удалить другой, вернуть итоговое содержимое таблицы.
""",
                    "tasks": [
                        {
                            "statement": (
                                "В таблице `inventory` есть три товара: Laptop (id=10, stock=50), "
                                "Mouse (id=20, stock=200), Keyboard (id=30, stock=100). "
                                "Уменьшите остаток Laptop'а на 5 единиц (новое значение — 45). "
                                "Удалите Mouse целиком. Затем верните весь оставшийся inventory."
                            ),
                            "fixture": {
                                "preload": [
                                    "CREATE TABLE inventory (product_id int PRIMARY KEY, name text, stock int);",
                                    "INSERT INTO inventory (product_id, name, stock) VALUES (10, 'Laptop', 50);",
                                    "INSERT INTO inventory (product_id, name, stock) VALUES (20, 'Mouse', 200);",
                                    "INSERT INTO inventory (product_id, name, stock) VALUES (30, 'Keyboard', 100);",
                                ],
                            },
                            "reference_solution": (
                                "UPDATE inventory SET stock = 45 WHERE product_id = 10;\n"
                                "DELETE FROM inventory WHERE product_id = 20;\n"
                                "SELECT * FROM inventory;"
                            ),
                            "reference_solutions": [],
                            "compare_ordered": False,  # партиционный ключ — порядок не гарантирован
                            "max_score":      10,
                            "attempts_limit":  0,
                        },
                    ],
                },
            ],
        },

        # ============================================================
        # МОДУЛЬ 3. Моделирование
        # ============================================================
        {
            "title":       "Модуль 3. Моделирование данных",
            "description": "Query-driven design, денормализация, коллекции и TTL.",
            "lessons": [

                # ---- Урок 3.1 (теория) ----
                {
                    "title":        "Query-driven design и денормализация",
                    "duration_min": 12,
                    "content_md": """# Моделирование данных в Cassandra

Это, пожалуй, самая важная тема всего курса. Cassandra — это не «SQL без JOIN'ов». Это другой подход к проектированию данных.

## Принцип «запрос определяет схему»

В реляционных БД сначала проектируется **нормализованная схема** (третья нормальная форма, без дублирования), а потом под неё пишутся любые запросы — оптимизатор сам разберётся, какие JOIN'ы делать.

В Cassandra — **наоборот**:

1. Сначала пиши список запросов, которые тебе нужны.
2. Под каждый запрос — спроектируй таблицу, в которой партиционный ключ совпадает с фильтром этого запроса.
3. Не бойся **дублировать данные** между таблицами — диск дешёвый, скорость важнее.

## Пример: соцсеть

Допустим, нужно три запроса:

- (A) Получить все посты пользователя по `user_id`.
- (B) Получить пост по его `post_id`.
- (C) Получить ленту друзей пользователя — последние посты от тех, на кого он подписан.

**Реляционно** мы бы сделали одну таблицу `posts(post_id, user_id, text, created_at)` и три разных запроса с JOIN'ами или индексами.

**В Cassandra** — три таблицы:

```cql
-- (A) Посты конкретного пользователя
CREATE TABLE posts_by_user (
    user_id int,
    post_id timeuuid,
    text text,
    PRIMARY KEY (user_id, post_id)
) WITH CLUSTERING ORDER BY (post_id DESC);

-- (B) Пост по id
CREATE TABLE posts_by_id (
    post_id timeuuid PRIMARY KEY,
    user_id int,
    text text
);

-- (C) Лента подписчиков (push-модель: при публикации копируем во все ленты)
CREATE TABLE feed (
    follower_id int,
    post_id timeuuid,
    author_id int,
    text text,
    PRIMARY KEY (follower_id, post_id)
) WITH CLUSTERING ORDER BY (post_id DESC);
```

Когда пользователь публикует пост, мы пишем его **одновременно** в все три таблицы (а в `feed` — для каждого подписчика). Запись стала дороже, зато чтение каждого из трёх запросов — тривиальное и быстрое.

## Денормализация — это нормально

В реляционной БД дублирование считается ошибкой. В Cassandra — это **необходимость**. Главный риск — рассинхронизация: если автор поста сменил имя, а во всех `feed`-записях оно уже скопировано — нужно либо обновлять везде, либо хранить только `author_id` и подгружать имя отдельно.

В реальных проектах обычно компромисс: **редко меняющиеся** данные (имя пользователя) копируют, **часто меняющиеся** (количество лайков) — хранят отдельно или вычисляют на лету.

## Антипаттерны

### 1. Огромные партиции

Если партиционный ключ слишком общий (`country` вместо `user_id`), внутри партиции окажутся миллионы строк. Cassandra такого не любит — рекомендация: **не больше ~100 МБ** на партицию.

Решение: добавить в партиционный ключ что-то ограничивающее размер — например, `(country, year_month)`.

### 2. ALLOW FILTERING

Уже обсуждали в Модуле 2. Если приходится использовать — это значит, что нужна ещё одна таблица под этот запрос.

### 3. Использование Cassandra как реляционной БД

Если в твоей логике много JOIN'ов, транзакций между сущностями, сложных аналитических запросов — Cassandra не лучший выбор. Возможно, тебе нужен PostgreSQL или, для аналитики, ClickHouse.

## Резюме

- Сначала пиши запросы, потом таблицы.
- Одна таблица под один запрос (примерно).
- Дублируй данные между таблицами без стеснения.
- Маленькие партиции лучше больших.
- Не используй ALLOW FILTERING.

В следующем уроке — практика работы с коллекциями и TTL.
""",
                },

                # ---- Урок 3.2 (с заданием) ----
                {
                    "title":        "Коллекции и TTL",
                    "duration_min": 14,
                    "content_md": """# Коллекции и время жизни данных

В этом уроке — два мощных инструмента Cassandra, которые часто используются вместе.

## Коллекции

Cassandra поддерживает три типа коллекций прямо в ячейке таблицы:

- `set<T>` — множество уникальных элементов.
- `list<T>` — упорядоченный список (с дубликатами).
- `map<K, V>` — ассоциативный массив.

### Использование

```cql
CREATE TABLE articles (
    article_id int PRIMARY KEY,
    title text,
    tags set<text>,
    revisions list<text>,
    metadata map<text, text>
);

INSERT INTO articles (article_id, title, tags) VALUES (
    1, 'Cassandra Tutorial', {'nosql', 'database', 'tutorial'}
);
```

Обрати внимание на синтаксис литералов:

- Set: `{'a', 'b', 'c'}` — фигурные скобки.
- List: `['a', 'b', 'c']` — квадратные скобки.
- Map: `{'key1': 'val1', 'key2': 'val2'}` — фигурные с двоеточиями.

### Когда использовать коллекции

Коллекции хороши для **маленьких** наборов: теги статьи, права пользователя, настройки. Cassandra хранит коллекцию как одну ячейку, и с ростом количества элементов производительность падает. Рекомендация: **до ~100 элементов** в коллекции.

Если коллекция большая — моделируй через отдельную таблицу с кластерным ключом (как в примере про посты в прошлом уроке).

### Подвох: чтение коллекции

Cassandra читает коллекцию **целиком**. Если в `tags` 500 элементов, а нужен один — всё равно прочитаются все. Это ещё одна причина не делать коллекции большими.

## TTL — Time To Live

Любой записи в Cassandra можно назначить **время жизни**. Через указанное число секунд запись автоматически удаляется (точнее, помечается tombstone'ом, но снаружи это выглядит как удаление).

### Синтаксис

```cql
INSERT INTO sessions (session_id, user_id, data) VALUES (
    'sess123', 1, 'some data'
) USING TTL 3600;   -- живёт 1 час

UPDATE sessions USING TTL 1800 SET data = 'new data' WHERE session_id = 'sess123';
```

`USING TTL <секунды>` — записать с временем жизни.

После истечения TTL запись становится недоступной для SELECT, потом физически удаляется при compaction.

### Особенности

- `TTL 0` — запись без TTL (живёт вечно).
- `WRITETIME(col)` и `TTL(col)` — функции, чтобы посмотреть, когда колонка была записана и сколько ей жить:

```cql
SELECT WRITETIME(data), TTL(data) FROM sessions WHERE session_id = 'sess123';
```

- TTL применяется **на колонку**, не на строку. У разных колонок одной строки могут быть разные TTL. Когда все колонки истекут — строка считается удалённой.
- TTL выживает при `UPDATE` без `USING TTL` — если хочешь продлить, надо явно указать новое TTL.

### Применения

- **Сессии** — токен авторизации живёт 1 час.
- **Кэш** — данные актуальны N минут, потом перечитываются из основного источника.
- **Лимиты** — счётчик попыток входа автоматически сбрасывается через сутки.
- **Временные данные** — данные эксперимента, которые не нужны после завершения.

> Одно из частых применений — Cassandra как replacement для Redis в задачах с большими объёмами кэша. Скорость записи в Cassandra сравнима с Redis, а данные не теряются при перезагрузке.

## Практическое задание

Финальное задание курса: создать запись с тегами (`set<text>`) и TTL.
""",
                    "tasks": [
                        {
                            "statement": (
                                "В песочнице есть таблица `articles` с колонками `article_id` "
                                "(int, первичный ключ), `title` (text), `tags` (set<text>). "
                                "Создайте новую статью с `article_id = 99`, заголовком "
                                "'Cassandra Tutorial' и тегами `{'nosql', 'database', 'tutorial'}`. "
                                "Время жизни записи — 3600 секунд. Затем верните эту статью."
                            ),
                            "fixture": {
                                "preload": [
                                    "CREATE TABLE articles (article_id int PRIMARY KEY, title text, tags set<text>);",
                                ],
                            },
                            "reference_solution": (
                                "INSERT INTO articles (article_id, title, tags) VALUES (99, 'Cassandra Tutorial', {'nosql', 'database', 'tutorial'}) USING TTL 3600;\n"
                                "SELECT * FROM articles WHERE article_id = 99;"
                            ),
                            "reference_solutions": [],
                            "compare_ordered": False,
                            "max_score":      15,
                            "attempts_limit":  0,
                        },
                    ],
                },
            ],
        },
    ],
}


NEO4J_COURSE = {
    "title":       "Neo4j: графовая модель",
    "description": "Графовая СУБД Neo4j. Узлы, рёбра, свойства, обход графа на языке Cypher.",
    "nosql_type":  NoSQLType.GRAPH,
    "difficulty":  3,
    "modules": [

        # ============================================================
        # МОДУЛЬ 1. Введение в Neo4j и Cypher
        # ============================================================
        {
            "title":       "Модуль 1. Введение в Neo4j и Cypher",
            "description": "Узлы, отношения, свойства. Базовые команды Cypher.",
            "lessons": [

                # ---- Урок 1.1: теория ----
                {
                    "title":        "Что такое граф свойств",
                    "duration_min": 10,
                    "content_md": """# Графовая модель данных

**Neo4j** — это нативно графовая СУБД. В отличие от реляционных, документных или колоночных баз, данные в Neo4j представлены как **граф свойств** (labeled property graph).

## Основные понятия

- **Узел (node)** — сущность с одной или несколькими метками. Метки группируют узлы по типам: `:Person`, `:Movie`, `:City`.
- **Отношение (relationship)** — связь между двумя узлами с обязательным типом: `KNOWS`, `ACTED_IN`, `LIVES_IN`. Отношения всегда направленные.
- **Свойства (properties)** — пары ключ-значение, могут быть и у узлов, и у отношений: `{name: 'Anna', age: 30}`.

## Когда использовать графы

Графовая модель идеально подходит, когда **связи между сущностями важнее самих сущностей**:

- **Социальные сети** — друзья друзей, группы, рекомендации.
- **Рекомендательные системы** — «посмотревшие X также смотрели Y».
- **Анализ мошенничества** — поиск подозрительных цепочек транзакций.
- **Графы знаний** — Wikipedia, Google Knowledge Graph.
- **Анализ зависимостей** — пакеты, импорты, права доступа.

В реляционной модели «найти всех друзей друзей» требует JOIN'а таблицы `friendship` саму с собой. На графе это естественный обход — за один запрос.

## Cypher — язык запросов

Запросы пишутся в виде **визуальных паттернов** — на ASCII «рисуется» то что мы ищем:

```cypher
// Узел Person с именем Alice
(alice:Person {name: 'Alice'})

// Отношение KNOWS от Alice к кому-то
(alice)-[:KNOWS]->(other)

// Полный паттерн: Alice знает кого-то
MATCH (alice:Person {name: 'Alice'})-[:KNOWS]->(friend)
RETURN friend.name
```

Этот запрос читается как: «найди узел Person с name='Alice', найди от него отношение KNOWS, верни имя того, к кому это отношение ведёт».

В следующем уроке создадим первые узлы и связи.
""",
                },

                # ---- Урок 1.2: с заданием ----
                {
                    "title":        "Создание узлов и связей",
                    "duration_min": 12,
                    "content_md": """# Создание узлов и связей

В этом уроке научимся создавать узлы, связи и читать их обратно.

## CREATE — создание узлов

```cypher
CREATE (n:Person {name: 'Anna', age: 28})
```

Слева от двоеточия — переменная `n` (имя в рамках запроса), справа — метка `Person`. В фигурных скобках — свойства.

Можно создать несколько узлов в одном CREATE:

```cypher
CREATE (a:Person {name: 'Anna'}), (b:Person {name: 'Bob'})
```

Можно создать узел сразу со связью:

```cypher
CREATE (a:Person {name: 'Anna'})-[:KNOWS]->(b:Person {name: 'Bob'})
```

Это создаст: узел Anna, узел Bob, и связь KNOWS от Anna к Bob.

## MATCH — поиск узлов

```cypher
MATCH (n:Person) RETURN n
```

Найдёт все узлы с меткой `:Person`.

С фильтрацией по свойству:

```cypher
MATCH (n:Person {name: 'Anna'}) RETURN n
MATCH (n:Person) WHERE n.age > 25 RETURN n.name
```

## Поиск через связи

Это сильнейшая сторона графов. Найти всех, с кем знакома Anna:

```cypher
MATCH (anna:Person {name: 'Anna'})-[:KNOWS]->(friend)
RETURN friend.name
```

Этот паттерн читается слева направо как стрелка: «от Anna через KNOWS к friend».

Связь без указания направления:

```cypher
MATCH (a:Person {name: 'Anna'})-[:KNOWS]-(b:Person)
RETURN b.name
```

Используется `--` или `<--` для обратного направления.

## Песочница в этом курсе

Каждая проверка работает в **изолированной транзакции**, которая откатывается после выполнения. Это значит:

- Любые узлы и связи, которые ты создашь, **не сохраняются** между запусками.
- Не нужно очищать данные перед следующей проверкой.
- Можешь свободно экспериментировать с CREATE/DELETE/MERGE — это безопасно.

## Практическое задание

Под этим уроком — задание: создать трёх людей со связью «знаком», прочитать одну связь.
""",
                    "tasks": [
                        {
                            "statement": (
                                "Создайте трёх пользователей с меткой `Person`: "
                                "Anna (age=28), Bob (age=30), Carol (age=25). "
                                "Затем создайте связь `KNOWS` от Anna к Bob. "
                                "В конце верните имя того, с кем знакома Anna, "
                                "и его возраст. Поля результата — `name` и `age`."
                            ),
                            "fixture": {"preload": []},
                            "reference_solution": (
                                "CREATE (anna:Person {name: 'Anna', age: 28});\n"
                                "CREATE (bob:Person {name: 'Bob', age: 30});\n"
                                "CREATE (carol:Person {name: 'Carol', age: 25});\n"
                                "MATCH (a:Person {name: 'Anna'}), (b:Person {name: 'Bob'}) CREATE (a)-[:KNOWS]->(b);\n"
                                "MATCH (a:Person {name: 'Anna'})-[:KNOWS]->(friend) RETURN friend.name AS name, friend.age AS age;"
                            ),
                            "reference_solutions": [
                                "CREATE (a:Person {name: 'Anna', age: 28})-[:KNOWS]->(b:Person {name: 'Bob', age: 30});\n"
                                "CREATE (c:Person {name: 'Carol', age: 25});\n"
                                "MATCH (a:Person {name: 'Anna'})-[:KNOWS]->(friend) RETURN friend.name AS name, friend.age AS age;",
                            ],
                            "compare_ordered": False,
                            "max_score":      10,
                            "attempts_limit":  0,
                        },
                    ],
                },

                # ---- Урок 1.3: теория ----
                {
                    "title":        "Метки, типы связей и свойства",
                    "duration_min": 10,
                    "content_md": """# Метки, типы связей и свойства

В прошлом уроке мы видели простой граф из узлов `Person` и связей `KNOWS`. Теперь разберём подробнее, что можно делать с метками, типами связей и свойствами.

## Метки узлов

Узел может иметь **несколько меток** одновременно:

```cypher
CREATE (n:Person:Employee:Manager {name: 'Anna'})
```

Эта Anna — одновременно `Person`, `Employee` и `Manager`. Поиск работает так:

```cypher
// Все Person
MATCH (n:Person) RETURN n

// Все Manager (среди Person)
MATCH (n:Manager) RETURN n

// Только те, кто И Person, И Manager
MATCH (n:Person:Manager) RETURN n
```

Метки удобны для иерархий и категорий, потому что узел можно отнести сразу к нескольким группам.

## Добавление и удаление меток

```cypher
// Добавить метку существующему узлу
MATCH (n:Person {name: 'Anna'}) SET n:Manager

// Удалить метку
MATCH (n:Person {name: 'Anna'}) REMOVE n:Manager
```

## Типы связей

Каждая связь имеет ровно **один тип**, и он обязателен (в отличие от меток узлов, которых может быть много или ноль).

```cypher
CREATE (a:Person)-[:KNOWS]->(b:Person)
CREATE (a:Person)-[:WORKS_WITH {since: 2020}]->(b:Person)
```

В Cypher принято писать типы связей **CAPS_WITH_UNDERSCORES** — это конвенция, как `UPPER_CASE` для констант в Python.

## Свойства — что можно хранить

Поддерживаемые типы:
- **Числа**: `int`, `float` — `42`, `3.14`
- **Строки**: `'text'` или `"text"`
- **Булевы**: `true`, `false`
- **Списки одного типа**: `[1, 2, 3]`, `['a', 'b']`
- **Дата/время**: `date('2024-01-15')`, `datetime('2024-01-15T10:00:00')`
- `null`

Чего **нельзя** хранить:
- Вложенные объекты — `{address: {city: 'X'}}` (используй отдельные узлы)
- Списки разных типов — `[1, 'two']`

## Доступ к свойствам

```cypher
MATCH (n:Person)
WHERE n.age > 25 AND n.name STARTS WITH 'A'
RETURN n.name, n.age, n.email
```

Точечная нотация — `n.property`. Если свойства нет, возвращается `NULL`.

## SET — изменение свойств

```cypher
// Установить одно свойство
MATCH (n:Person {name: 'Anna'}) SET n.age = 29

// Установить несколько свойств за раз
MATCH (n:Person {name: 'Anna'}) SET n.age = 29, n.email = 'anna@example.com'

// Удалить свойство
MATCH (n:Person {name: 'Anna'}) REMOVE n.age
```

## Что дальше

В следующем модуле научимся искать данные сложнее: фильтровать через `WHERE`, обходить граф через несколько связей, считать агрегации.
""",
                },
            ],
        },

        # ============================================================
        # МОДУЛЬ 2. Поиск и обход графа
        # ============================================================
        {
            "title":       "Модуль 2. Поиск и обход графа",
            "description": "Фильтрация, обход графа на несколько уровней, агрегации.",
            "lessons": [

                # ---- Урок 2.1: с заданием ----
                {
                    "title":        "Фильтрация и WHERE",
                    "duration_min": 12,
                    "content_md": """# Фильтрация результатов

В простом случае фильтр пишется прямо в паттерне:

```cypher
MATCH (p:Person {name: 'Anna'}) RETURN p
```

Но это только для точного равенства. Для всего остального — `WHERE`.

## WHERE — условия после паттерна

```cypher
MATCH (p:Person)
WHERE p.age > 25
RETURN p.name, p.age
```

Можно комбинировать через `AND`, `OR`, `NOT`:

```cypher
MATCH (p:Person)
WHERE p.age > 25 AND p.age < 40
RETURN p
```

## Операторы сравнения

| Оператор | Значение |
|----------|----------|
| `=` | Равно |
| `<>` | Не равно |
| `<`, `>`, `<=`, `>=` | Сравнение чисел и дат |
| `IS NULL` / `IS NOT NULL` | Проверка отсутствия |
| `IN [...]` | Принадлежность списку |
| `STARTS WITH` / `ENDS WITH` / `CONTAINS` | Поиск по подстроке |
| `=~ '...'` | Регулярное выражение |

Примеры:

```cypher
// Имена начинающиеся на 'A'
MATCH (p:Person) WHERE p.name STARTS WITH 'A' RETURN p.name

// Возраст в списке
MATCH (p:Person) WHERE p.age IN [25, 30, 35] RETURN p

// У кого есть email
MATCH (p:Person) WHERE p.email IS NOT NULL RETURN p
```

## ORDER BY и LIMIT

```cypher
MATCH (p:Person)
WHERE p.age > 18
RETURN p.name, p.age
ORDER BY p.age DESC
LIMIT 5
```

`ORDER BY` сортирует, `LIMIT` ограничивает. По возрастанию по умолчанию (`ASC`), для убывания — `DESC`. Можно сортировать по нескольким полям.

## DISTINCT — уникальные значения

Если запрос может вернуть дубликаты, `DISTINCT` их убирает:

```cypher
MATCH (p:Person)-[:KNOWS]->(friend)
RETURN DISTINCT friend.name
```

Полезно когда один и тот же узел можно получить разными путями.

## Практическое задание

Под этим уроком — задание: отфильтровать `Person` по возрасту и отсортировать.
""",
                    "tasks": [
                        {
                            "statement": (
                                "В песочнице уже есть пять пользователей разных возрастов. "
                                "Найдите всех `Person`, чей возраст больше 25, и верните "
                                "поля `name` и `age`. Отсортируйте результат по возрасту "
                                "по возрастанию."
                            ),
                            "fixture": {
                                "preload": [
                                    "CREATE (:Person {name: 'Anna', age: 28})",
                                    "CREATE (:Person {name: 'Bob', age: 30})",
                                    "CREATE (:Person {name: 'Carol', age: 22})",
                                    "CREATE (:Person {name: 'Dave', age: 26})",
                                    "CREATE (:Person {name: 'Eve', age: 19})",
                                ],
                            },
                            "reference_solution": (
                                "MATCH (p:Person) WHERE p.age > 25 "
                                "RETURN p.name AS name, p.age AS age "
                                "ORDER BY p.age ASC;"
                            ),
                            "reference_solutions": [],
                            "compare_ordered": True,  # ORDER BY → порядок важен
                            "max_score":      10,
                            "attempts_limit":  0,
                        },
                    ],
                },

                # ---- Урок 2.2: с заданием ----
                {
                    "title":        "Обход графа: друзья друзей",
                    "duration_min": 14,
                    "content_md": """# Обход графа на несколько уровней

Главная сила графовых СУБД — **обход графа** через несколько связей за один запрос. То, что в SQL потребовало бы цепочки JOIN'ов, в Cypher пишется как естественная стрелка.

## Несколько связей в паттерне

```cypher
MATCH (a:Person)-[:KNOWS]->(b:Person)-[:KNOWS]->(c:Person)
RETURN a.name, b.name, c.name
```

Этот запрос находит **тройки** людей, где a знает b, и b знает c. Хороший способ найти «друзей друзей».

## Поиск с переменной длиной пути

```cypher
// От 1 до 3 шагов по KNOWS
MATCH (a:Person {name: 'Anna'})-[:KNOWS*1..3]->(other)
RETURN DISTINCT other.name

// Точно 2 шага
MATCH (a:Person {name: 'Anna'})-[:KNOWS*2]->(other)
RETURN DISTINCT other.name
```

Синтаксис `*N..M` — длина пути от N до M шагов.

⚠️ Будь осторожен с очень длинными путями — на больших графах запросы вида `*1..10` могут «взорваться» по числу комбинаций.

## Исключение через NOT

«Друзья друзей, но не сами уже друзья» — типичная задача рекомендательной системы. В Cypher это пишется так:

```cypher
MATCH (anna:Person {name: 'Anna'})-[:KNOWS]->(friend)-[:KNOWS]->(fof)
WHERE fof <> anna AND NOT (anna)-[:KNOWS]->(fof)
RETURN DISTINCT fof.name
```

Разбор:
- Находим путь длиной 2: `anna → friend → fof`.
- `fof <> anna` — исключаем саму Anna (если граф циклический).
- `NOT (anna)-[:KNOWS]->(fof)` — проверяем, что между anna и fof **нет** прямой связи. Это «инлайн»-проверка существования паттерна.
- `DISTINCT` — убираем дубликаты (один человек может быть «другом друга» через разных друзей).

## Ненаправленные связи

Если направление не важно, используй `-[:KNOWS]-` вместо `-[:KNOWS]->`:

```cypher
MATCH (a:Person {name: 'Anna'})-[:KNOWS]-(other)
RETURN other.name
```

Это вернёт всех, кого знает Anna **или** кто знает её.

## Любой тип связи

Если хочешь обойти любые связи, без указания типа:

```cypher
MATCH (a:Person {name: 'Anna'})-[r]-(other)
RETURN type(r), other.name
```

Функция `type(r)` возвращает имя типа связи.

## Практическое задание

Найди «друзей друзей» в небольшом графе.
""",
                    "tasks": [
                        {
                            "statement": (
                                "В песочнице есть граф знакомств. Найдите всех "
                                "«друзей друзей» Anna — то есть людей, до которых "
                                "от Anna два шага по `KNOWS`, исключая саму Anna и "
                                "её прямых друзей. Верните только их `name`."
                            ),
                            "fixture": {
                                "preload": [
                                    "CREATE (a:Person {name: 'Anna'})",
                                    "CREATE (b:Person {name: 'Bob'})",
                                    "CREATE (c:Person {name: 'Carol'})",
                                    "CREATE (d:Person {name: 'Dave'})",
                                    "CREATE (e:Person {name: 'Eve'})",
                                    "MATCH (a:Person {name: 'Anna'}), (b:Person {name: 'Bob'}) CREATE (a)-[:KNOWS]->(b)",
                                    "MATCH (b:Person {name: 'Bob'}), (c:Person {name: 'Carol'}) CREATE (b)-[:KNOWS]->(c)",
                                    "MATCH (b:Person {name: 'Bob'}), (d:Person {name: 'Dave'}) CREATE (b)-[:KNOWS]->(d)",
                                    "MATCH (a:Person {name: 'Anna'}), (e:Person {name: 'Eve'}) CREATE (a)-[:KNOWS]->(e)",
                                ],
                            },
                            "reference_solution": (
                                "MATCH (anna:Person {name: 'Anna'})-[:KNOWS]->(friend)-[:KNOWS]->(fof) "
                                "WHERE fof <> anna AND NOT (anna)-[:KNOWS]->(fof) "
                                "RETURN DISTINCT fof.name AS name;"
                            ),
                            "reference_solutions": [],
                            "compare_ordered": False,  # DISTINCT — порядок не гарантирован
                            "max_score":      15,
                            "attempts_limit":  0,
                        },
                    ],
                },

                # ---- Урок 2.3: с заданием ----
                {
                    "title":        "Агрегации и подсчёт",
                    "duration_min": 12,
                    "content_md": """# Агрегации в Cypher

Cypher умеет почти все агрегации, что и SQL: `count`, `sum`, `avg`, `min`, `max`, `collect`. Группировка делается **неявно** — по тем полям, что в `RETURN` не агрегатные.

## count() — подсчёт

```cypher
// Сколько всего Person
MATCH (p:Person) RETURN count(p)

// Сколько у каждого друзей (KNOWS-связей)
MATCH (p:Person)-[:KNOWS]->(friend)
RETURN p.name, count(friend) AS friends_count
```

Во втором запросе группировка идёт по `p.name`. Cypher сам понимает: всё, что не `count(...)`, — поле группировки.

## Разница count(x) и count(*)

- `count(x)` — считает только не-NULL значения.
- `count(*)` — считает строки, включая те где `x` IS NULL.

Это важно при `OPTIONAL MATCH` (увидим в Модуле 3).

## sum, avg, min, max

```cypher
MATCH (p:Person)
RETURN
  count(p) AS total,
  avg(p.age) AS avg_age,
  min(p.age) AS youngest,
  max(p.age) AS oldest,
  sum(p.age) AS total_age
```

Все эти функции работают только с числовыми полями.

## collect() — сбор в список

Часто нужно «получить для каждого узла список связанных»:

```cypher
MATCH (p:Person)-[:KNOWS]->(friend)
RETURN p.name, collect(friend.name) AS friends
```

Результат — для каждого Person один объект с полем `friends`, в котором массив имён друзей.

## ORDER BY с агрегатами

После агрегации сортируем по результату:

```cypher
MATCH (p:Person)-[:KNOWS]->(friend)
RETURN p.name, count(friend) AS friends_count
ORDER BY friends_count DESC, p.name ASC
```

Сначала по убыванию количества друзей, потом по имени (для ровного количества).

## Практическое задание

Подсчитать для каждого `Person` количество посещённых городов.
""",
                    "tasks": [
                        {
                            "statement": (
                                "В песочнице есть граф посещений: связь `VISITED` от "
                                "`Person` к `City`. Найдите для каждого человека "
                                "количество посещённых им городов. Верните `name` и "
                                "`cities_count`. Отсортируйте по убыванию количества "
                                "городов, при равенстве — по имени по возрастанию."
                            ),
                            "fixture": {
                                "preload": [
                                    "CREATE (a:Person {name: 'Anna'})",
                                    "CREATE (b:Person {name: 'Bob'})",
                                    "CREATE (c:Person {name: 'Carol'})",
                                    "CREATE (paris:City {name: 'Paris'})",
                                    "CREATE (london:City {name: 'London'})",
                                    "CREATE (rome:City {name: 'Rome'})",
                                    "CREATE (berlin:City {name: 'Berlin'})",
                                    "MATCH (a:Person {name: 'Anna'}), (p:City {name: 'Paris'}) CREATE (a)-[:VISITED]->(p)",
                                    "MATCH (a:Person {name: 'Anna'}), (l:City {name: 'London'}) CREATE (a)-[:VISITED]->(l)",
                                    "MATCH (a:Person {name: 'Anna'}), (r:City {name: 'Rome'}) CREATE (a)-[:VISITED]->(r)",
                                    "MATCH (b:Person {name: 'Bob'}), (l:City {name: 'London'}) CREATE (b)-[:VISITED]->(l)",
                                    "MATCH (b:Person {name: 'Bob'}), (be:City {name: 'Berlin'}) CREATE (b)-[:VISITED]->(be)",
                                    "MATCH (c:Person {name: 'Carol'}), (p:City {name: 'Paris'}) CREATE (c)-[:VISITED]->(p)",
                                ],
                            },
                            "reference_solution": (
                                "MATCH (p:Person)-[:VISITED]->(c:City) "
                                "RETURN p.name AS name, count(c) AS cities_count "
                                "ORDER BY cities_count DESC, name ASC;"
                            ),
                            "reference_solutions": [],
                            "compare_ordered": True,  # ORDER BY → порядок важен
                            "max_score":      10,
                            "attempts_limit":  0,
                        },
                    ],
                },
            ],
        },

        # ============================================================
        # МОДУЛЬ 3. Моделирование графов
        # ============================================================
        {
            "title":       "Модуль 3. Моделирование графов",
            "description": "MERGE и идемпотентность, OPTIONAL MATCH, паттерны проектирования.",
            "lessons": [

                # ---- Урок 3.1: теория ----
                {
                    "title":        "MERGE и идемпотентность",
                    "duration_min": 10,
                    "content_md": """# MERGE — создать или найти

Команда `CREATE` всегда создаёт новый узел/связь. Если ты её запустишь дважды, в БД будет **две копии** одного и того же. Часто это не то, что нужно.

`MERGE` решает эту проблему: «найди если есть, иначе создай».

## Простой MERGE

```cypher
MERGE (n:Person {name: 'Anna'})
```

- Если узел `Person {name: 'Anna'}` уже есть — `n` будет ссылаться на него.
- Если нет — создастся новый.

Этот запрос **идемпотентен** — можно запускать сколько угодно раз, результат одинаковый.

## MERGE связи

```cypher
MATCH (a:Person {name: 'Anna'}), (b:Person {name: 'Bob'})
MERGE (a)-[:KNOWS]->(b)
```

Если связь KNOWS между Anna и Bob уже существует — ничего не создаётся. Если нет — создастся.

## ON CREATE и ON MATCH

Часто нужна разная логика в зависимости от того, узел существовал или нет:

```cypher
MERGE (n:Person {name: 'Anna'})
ON CREATE SET n.created_at = datetime(), n.visits = 1
ON MATCH SET n.visits = n.visits + 1, n.last_seen = datetime()
```

- При создании — записываем дату создания и счётчик `visits = 1`.
- При попадании на существующий — увеличиваем `visits` и обновляем `last_seen`.

Это типичный паттерн для аналитики посещений.

## MERGE vs CREATE — когда что

| Сценарий | Команда |
|----------|---------|
| Заведомо новые данные (сидинг) | `CREATE` (быстрее) |
| Загрузка из внешнего источника, может повториться | `MERGE` |
| Регистрация пользователя | `CREATE` (с `UNIQUE`-констрейнтом) |
| Идемпотентные импорты | `MERGE` |
| Лог событий (записать факт) | `CREATE` (каждое событие уникально) |

## Подвох: MERGE по нескольким свойствам

```cypher
MERGE (n:Person {name: 'Anna', age: 28})
```

Это **не** «найди по имени, остальное обнови», а «найди узел, где **И** name='Anna', **И** age=28». Если в БД есть Anna с age=29 — будет создан новый узел.

Для «найди по ключу, обнови остальное» правильно так:

```cypher
MERGE (n:Person {name: 'Anna'})
ON MATCH SET n.age = 28
ON CREATE SET n.age = 28
```

## Практическое значение

`MERGE` — основа надёжного импорта данных в Neo4j. Все ETL-процессы работают через `MERGE`, чтобы можно было перезапускать пайплайны без дубликатов.

## Что дальше

В следующем уроке — `OPTIONAL MATCH` для работы с «опциональными» связями, и финальное задание курса.
""",
                },

                # ---- Урок 3.2: с заданием ----
                {
                    "title":        "OPTIONAL MATCH и сложные паттерны",
                    "duration_min": 14,
                    "content_md": """# OPTIONAL MATCH — связи которые могут отсутствовать

Обычный `MATCH` возвращает строку **только если паттерн найден целиком**. Если в графе есть `Person` без друзей, такой `MATCH` его пропустит:

```cypher
MATCH (p:Person)-[:KNOWS]->(friend)
RETURN p.name, friend.name
```

Этот запрос вернёт только тех `Person`, у кого **есть** хотя бы один друг. Одиноких `Person` мы потеряем.

## Решение — OPTIONAL MATCH

```cypher
MATCH (p:Person)
OPTIONAL MATCH (p)-[:KNOWS]->(friend)
RETURN p.name, friend.name
```

Теперь:
- Сначала находим всех `Person` (это обязательно — `MATCH`).
- Потом пытаемся найти друзей (это опционально — `OPTIONAL MATCH`).
- Если друзей нет, в `friend.name` будет `NULL`, но `Person` всё равно попадёт в результат.

Это аналог `LEFT JOIN` в SQL.

## OPTIONAL MATCH с агрегацией

Здесь нужно быть аккуратным с `count()`:

```cypher
MATCH (p:Person)
OPTIONAL MATCH (p)-[:KNOWS]->(friend)
RETURN p.name, count(friend) AS friends_count
```

- `count(friend)` считает только **не-NULL** значения. У Person без друзей `friend = NULL`, и `count = 0` — то что нужно.
- А `count(*)` посчитал бы строки, включая те где friend NULL — у одинокого получилось бы **1**, что неправильно.

**Правило**: после `OPTIONAL MATCH` всегда используй `count(переменная)`, а не `count(*)`.

## OPTIONAL MATCH с несколькими связями

```cypher
MATCH (p:Person)
OPTIONAL MATCH (p)-[:KNOWS]->(friend)
OPTIONAL MATCH (p)-[:VISITED]->(city)
RETURN p.name,
       count(DISTINCT friend) AS friends,
       count(DISTINCT city)   AS cities
```

Каждый `OPTIONAL MATCH` независим. `DISTINCT` нужен потому что иначе при наличии нескольких друзей и нескольких городов, мы получим декартово произведение строк.

## Сложные паттерны

Можно комбинировать обязательные и опциональные части:

```cypher
MATCH (p:Person)-[:WORKS_AT]->(company:Company)
OPTIONAL MATCH (p)-[:MANAGES]->(report:Person)
RETURN p.name, company.name, collect(report.name) AS reports
```

«Все работающие сотрудники, со списком их подчинённых (если есть)».

`collect()` тоже игнорирует NULL — у сотрудника без подчинённых будет пустой список `[]`.

## Финальное задание

Подсчитай количество друзей у каждого `Person` — даже у тех, у кого друзей нет.
""",
                    "tasks": [
                        {
                            "statement": (
                                "В графе есть `Person` с разным количеством друзей — у "
                                "некоторых нет друзей вообще. Верните **всех** "
                                "`Person` с количеством их друзей (`KNOWS`-связь от "
                                "них к другим). У человека без друзей `friends_count` "
                                "должен быть **0**, а не отсутствовать. Сортировка — "
                                "по убыванию количества друзей, при равенстве — по "
                                "имени по возрастанию."
                            ),
                            "fixture": {
                                "preload": [
                                    "CREATE (:Person {name: 'Anna'})",
                                    "CREATE (:Person {name: 'Bob'})",
                                    "CREATE (:Person {name: 'Carol'})",
                                    "CREATE (:Person {name: 'Dave'})",
                                    "MATCH (a:Person {name: 'Anna'}), (b:Person {name: 'Bob'}) CREATE (a)-[:KNOWS]->(b)",
                                    "MATCH (a:Person {name: 'Anna'}), (c:Person {name: 'Carol'}) CREATE (a)-[:KNOWS]->(c)",
                                    "MATCH (b:Person {name: 'Bob'}), (c:Person {name: 'Carol'}) CREATE (b)-[:KNOWS]->(c)",
                                ],
                            },
                            "reference_solution": (
                                "MATCH (p:Person) "
                                "OPTIONAL MATCH (p)-[:KNOWS]->(friend) "
                                "RETURN p.name AS name, count(friend) AS friends_count "
                                "ORDER BY friends_count DESC, name ASC;"
                            ),
                            "reference_solutions": [],
                            "compare_ordered": True,  # ORDER BY → порядок важен
                            "max_score":      15,
                            "attempts_limit":  0,
                        },
                    ],
                },
            ],
        },
    ],
}


ALL_COURSES = [MONGO_COURSE, REDIS_COURSE, CASSANDRA_COURSE, NEO4J_COURSE]


# ============================================================================
# ДОСТИЖЕНИЯ
# ============================================================================

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


# ============================================================================
# ДЕМО-АКТИВНОСТЬ СТУДЕНТА (для красивого дашборда на защите)
# ============================================================================

async def seed_student_activity(
    session,
    student: User,
    *,
    days_back:        int   = 28,
    daily_correct:    tuple[int, int] = (1, 3),  # min, max правильных в день
    skip_day_chance:  float = 0.15,
    wrong_chance:     float = 0.30,
    seed_value:       int   = 42,
) -> int:
    """Создаёт демо-сабмишены для студента.

    Возвращает количество созданных сабмишенов.
    Если у студента уже есть сабмишены — пропускает (идемпотентно).
    """
    existing = await session.execute(
        select(Submission).where(Submission.user_id == student.user_id).limit(1)
    )
    if existing.scalar_one_or_none() is not None:
        log.info("activity for user %s already exists, skipping", student.login)
        return 0

    tasks_q = await session.execute(
        select(Task).where(Task.db_type.in_([
            NoSQLType.DOCUMENT, NoSQLType.KEY_VALUE,
            NoSQLType.COLUMN,   NoSQLType.GRAPH,
        ]))
    )
    tasks = list(tasks_q.scalars().all())
    if not tasks:
        log.warning("no tasks found, cannot seed activity")
        return 0

    # Фейковые «неправильные» ответы по типу СУБД — чтобы query_text
    # выглядел правдоподобно, как реальное ошибочное решение студента.
    WRONG_QUERY_BY_TYPE = {
        NoSQLType.DOCUMENT:  "db.users.find({})",
        NoSQLType.KEY_VALUE: "GET nonexistent_key",
        NoSQLType.COLUMN:    "SELECT * FROM nonexistent_table;",
        NoSQLType.GRAPH:     "MATCH (n:NonexistentLabel) RETURN n;",
    }

    now = datetime.now()  # naive — БД хранит timestamp WITHOUT TIME ZONE
    submissions = []

    import random
    rng = random.Random(seed_value)

    for day_offset in range(days_back, 0, -1):
        day = now - timedelta(days=day_offset)
        if rng.random() < skip_day_chance:
            continue

        for _ in range(rng.randint(*daily_correct)):
            task = rng.choice(tasks)
            ts = day.replace(
                hour=rng.randint(9, 22),
                minute=rng.randint(0, 59),
                second=rng.randint(0, 59),
            )
            submissions.append(Submission(
                user_id    = student.user_id,
                task_id    = task.task_id,
                query_text = task.reference_solution,
                result     = {"items": [{"_id": 1, "demo": True}], "value": None},
                is_correct = True,
                score      = task.max_score,
                status     = SubmissionStatus.CORRECT,
                submitted_at = ts,
            ))

        if rng.random() < wrong_chance:
            task = rng.choice(tasks)
            ts = day.replace(
                hour=rng.randint(9, 22),
                minute=rng.randint(0, 59),
                second=rng.randint(0, 59),
            )
            submissions.append(Submission(
                user_id    = student.user_id,
                task_id    = task.task_id,
                query_text = WRONG_QUERY_BY_TYPE.get(task.db_type, ""),
                result     = {"items": [], "value": None},
                is_correct = False,
                score      = 0,
                status     = SubmissionStatus.WRONG,
                submitted_at = ts,
            ))

    session.add_all(submissions)
    log.info("seeded %d demo submissions for %s", len(submissions), student.login)
    return len(submissions)


# ============================================================================
# MAIN
# ============================================================================

async def main():
    async with AsyncSessionLocal() as session:
        teacher = await ensure_user(
            session,
            login="yuri", email="yuri@example.com",
            password="teacher123", display_name="Юрий Аджем",
            role=UserRole.TEACHER,
        )
        student = await ensure_user(
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

        # ---------- Дополнительные демо-студенты с разной активностью ----------
        demo_students_specs = [
            ("anna",    "anna@example.com",    "Анна Петрова",    "demo123",
             {"days_back": 28, "daily_correct": (2, 4), "skip_day_chance": 0.10, "wrong_chance": 0.20, "seed_value": 101}),
            ("dmitry",  "dmitry@example.com",  "Дмитрий Соколов", "demo123",
             {"days_back": 21, "daily_correct": (1, 2), "skip_day_chance": 0.30, "wrong_chance": 0.40, "seed_value": 202}),
            ("maria",   "maria@example.com",   "Мария Иванова",   "demo123",
             {"days_back": 14, "daily_correct": (1, 3), "skip_day_chance": 0.20, "wrong_chance": 0.25, "seed_value": 303}),
            ("alex",    "alex@example.com",    "Александр Лебедев","demo123",
             {"days_back": 7,  "daily_correct": (3, 5), "skip_day_chance": 0.05, "wrong_chance": 0.15, "seed_value": 404}),
            ("ekaterina","ekaterina@example.com","Екатерина Васильева","demo123",
             {"days_back": 28, "daily_correct": (1, 1), "skip_day_chance": 0.50, "wrong_chance": 0.50, "seed_value": 505}),
        ]
        demo_students = []
        for login, email, name, password, _ in demo_students_specs:
            u = await ensure_user(
                session,
                login=login, email=email,
                password=password, display_name=name,
                role=UserRole.STUDENT,
            )
            demo_students.append(u)

        for course_data in ALL_COURSES:
            await ensure_course(session, teacher, **course_data)

        await ensure_achievements(session)
        await session.flush()

        # ---------- Активность ----------
        # Главный демо-студент (`student`).
        await seed_student_activity(session, student)

        # Дополнительные демо-студенты с разной интенсивностью.
        for (_, _, _, _, params), s_user in zip(demo_students_specs, demo_students):
            await seed_student_activity(session, s_user, **params)

        await session.commit()
        log.info("seed completed successfully")


if __name__ == "__main__":
    asyncio.run(main())
