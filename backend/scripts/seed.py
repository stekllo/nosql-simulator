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
    "description": "Хранилище ключ-значение Redis. Работа со строками, списками, множествами, хэшами.",
    "nosql_type":  NoSQLType.KEY_VALUE,
    "difficulty":  2,
    "modules": [
        {
            "title":       "Модуль 1. Введение в Redis",
            "description": "Что такое Redis и базовые команды для работы со строками.",
            "lessons": [
                {
                    "title":        "Зачем нужен Redis",
                    "duration_min": 6,
                    "content_md": """# Redis — in-memory key-value хранилище

Redis хранит данные в оперативной памяти, что обеспечивает очень высокую скорость доступа — миллионы операций в секунду.

## Типичные применения

- Кэширование результатов запросов
- Хранение пользовательских сессий
- Очереди сообщений
- Счётчики и метрики реального времени
- Распределённые блокировки

## Структуры данных

Redis поддерживает не только строки: списки (`LIST`), множества (`SET`), хэши (`HASH`), упорядоченные множества (`ZSET`).

## Примеры команд

```
SET user:1001:name "Alice"
GET user:1001:name
INCR counter

LPUSH queue:tasks "task_1"
RPOP queue:tasks

SADD online:users "alice" "bob"
SISMEMBER online:users "alice"
```

> Этот курс находится в разработке. Полное наполнение появится позже.
""",
                },
                # ---- Урок 1.2: первое практическое задание ----
                {
                    "title":        "Счётчики: INCR и DECR",
                    "duration_min": 8,
                    "content_md": """# Счётчики в Redis

Одно из самых частых применений Redis — атомарные счётчики. Команды `INCR` и `DECR` увеличивают и уменьшают значение ключа на 1, а `INCRBY` / `DECRBY` — на любое число.

## Базовые команды

| Команда           | Что делает                                |
|-------------------|-------------------------------------------|
| `SET key value`   | Установить значение                        |
| `GET key`         | Получить значение                          |
| `INCR key`        | Увеличить на 1 (создаёт ключ, если нет)    |
| `DECR key`        | Уменьшить на 1                             |
| `INCRBY key N`    | Увеличить на N                             |
| `DECRBY key N`    | Уменьшить на N                             |

## Атомарность

Главное преимущество — `INCR` атомарен: даже если 1000 клиентов одновременно увеличат счётчик, гонок не будет. Это **не то же самое**, что `GET` + прибавить + `SET`!

## Пример

```
SET pageviews 0
INCR pageviews
INCR pageviews
INCRBY pageviews 5
GET pageviews
```

Результат последней команды: `"7"`.
""",
                    "tasks": [
                        {
                            "statement": (
                                "В песочнице уже есть счётчик `views` со значением 10. "
                                "Увеличьте его на 5, затем ещё раз на 1, и верните итоговое значение командой GET."
                            ),
                            "fixture": {
                                "preload": [
                                    "SET views 10",
                                ],
                            },
                            # Эталон: студент должен прийти к 16
                            "reference_solution": "INCRBY views 5\nINCR views\nGET views",
                            "reference_solutions": [
                                # Альтернативный путь — INCRBY 6
                                "INCRBY views 6\nGET views",
                                # Или просто SET 16, тоже даёт правильный финальный результат
                                "SET views 16\nGET views",
                            ],
                            "compare_ordered": True,
                            "max_score":      10,
                            "attempts_limit":  0,
                        },
                    ],
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
            "title":       "Модуль 1. Архитектура Cassandra",
            "description": "Шардирование, репликация, кворумы.",
            "lessons": [
                {
                    "title":        "Кольцевая архитектура",
                    "duration_min": 12,
                    "content_md": """# Архитектура Cassandra

Cassandra использует **peer-to-peer** архитектуру: все узлы равноправны, нет ведущего и ведомого. Данные распределяются по узлам с помощью консистентного хэширования.

## Ключевые свойства

- Линейное горизонтальное масштабирование
- Tunable consistency (настраиваемая согласованность)
- Без единой точки отказа
- Оптимизирована для больших объёмов записи

> **Скоро:** интерактивная Cassandra-песочница с CQL-запросами. Пока курс находится в разработке.
""",
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
            "title":       "Модуль 1. Графовая модель",
            "description": "Узлы, отношения, свойства.",
            "lessons": [
                {
                    "title":        "Что такое граф свойств",
                    "duration_min": 10,
                    "content_md": """# Графовая модель данных

В Neo4j данные представлены как **граф свойств** (labeled property graph): узлы (вершины) с метками и рёбра (отношения) между ними. И узлы, и рёбра могут иметь произвольный набор свойств.

## Пример

```cypher
CREATE (alice:Person {name: 'Alice', age: 30})
CREATE (bob:Person {name: 'Bob',   age: 25})
CREATE (alice)-[:KNOWS {since: 2020}]->(bob)
```

## Когда использовать

- Социальные сети
- Рекомендательные системы
- Анализ зависимостей и мошенничества
- Графы знаний

> **Скоро:** интерактивная Neo4j-песочница с Cypher-запросами. Пока курс находится в разработке.
""",
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

    tasks_q = await session.execute(select(Task).where(Task.db_type == NoSQLType.DOCUMENT))
    tasks = list(tasks_q.scalars().all())
    if not tasks:
        log.warning("no tasks found, cannot seed activity")
        return 0

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
                query_text = "db.users.find({})",  # неправильное решение
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
