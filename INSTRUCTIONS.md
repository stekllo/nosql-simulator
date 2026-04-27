# Patch 10 — Quick Wins + полный MongoDB-курс

Этот патч закрывает несколько задач из списка комиссии:

1. ✅ **Сравнение результатов без учёта порядка** (флаг `compare_ordered` в задании)
2. ✅ **Несколько эталонных решений** (массив `reference_solutions` в задании)
3. ✅ **Полный MongoDB-курс**: 3 модуля × 3 урока, 7 практических заданий с готовыми эталонами
4. ✅ **Активность студента за 28 дней** для красивого дашборда
5. ✅ **API для конструктора лекций** (PATCH/DELETE /builder/lessons/{id}) — UI ещё не сделан, это в патче-11

## Что меняется

### Backend
- `backend/app/sandbox/mongo_runner.py` — улучшенный `compare_results` + новая `compare_to_any_reference`
- `backend/app/models/submission.py` — модель `Task` получает поля `reference_solutions: list[str]` и `compare_ordered: bool`
- `backend/app/api/tasks.py` — submit использует множественные эталоны и флаг сравнения
- `backend/app/schemas/builder.py` — `TaskCreate` принимает новые поля
- `backend/app/api/builder.py` — добавлены endpoints для редактирования урока (GET/PATCH/DELETE /lessons/{id})
- `backend/alembic/versions/0002_multi_refs.py` — миграция (добавляет 2 столбца в tasks)
- `backend/scripts/seed.py` — полный обогащённый seed с MongoDB-курсом и демо-активностью

### Frontend
- `frontend/src/lib/types.ts` — добавлены `reference_solutions` и `compare_ordered` в `TaskCreate` / `TaskOut`
- `frontend/src/pages/TaskBuilderPage.tsx` — UI для добавления нескольких эталонов и чекбокс «Учитывать порядок»

---

## Применение патча

### Шаг 1. Распакуй архив поверх проекта

Из корня проекта:

```powershell
cd C:\Dev\nosql-sim
# Распакуй архив с заменой существующих файлов
Expand-Archive -Path "путь\к\patch-10-quick-wins.zip" -DestinationPath . -Force
```

### Шаг 2. Полный сброс БД и пересев

Это перетрёт все данные и создаст заново — но в новом seed уже зашита нужная активность.

```powershell
docker compose down -v
docker compose up -d
# Ждём ~30 секунд пока контейнеры стартанут
Start-Sleep -Seconds 30
# Применяем миграции
docker compose exec backend alembic upgrade head
# Заполняем данными
docker compose exec backend python -m scripts.seed
```

### Шаг 3. Проверка

```powershell
# Должно показать что в MongoDB-курсе теперь 3 модуля, 9 уроков, 7 заданий
docker compose exec postgres psql -U sim -d sim -c "SELECT c.title, COUNT(DISTINCT m.module_id) AS modules, COUNT(DISTINCT l.lesson_id) AS lessons, COUNT(DISTINCT t.task_id) AS tasks FROM courses c LEFT JOIN modules m ON m.course_id = c.course_id LEFT JOIN lessons l ON l.module_id = m.module_id LEFT JOIN tasks t ON t.lesson_id = l.lesson_id GROUP BY c.course_id, c.title ORDER BY c.course_id;"
```

Ожидаемый результат:

```
            title             | modules | lessons | tasks
------------------------------+---------+---------+-------
 MongoDB для начинающих       |       3 |       9 |     7
 Redis: кэш и структуры       |       1 |       1 |     0
 Cassandra: большие данные    |       1 |       1 |     0
 Neo4j и язык Cypher          |       1 |       1 |     0
```

### Шаг 4. Проверка работы

1. Открой http://localhost:3000
2. Залогинься как `student / student123`
3. Зайди в дашборд — должна быть видна активность за последний месяц с гистограммой
4. Зайди в любой курс MongoDB → урок «Базовые команды find()» → попробуй решить задание

### Шаг 5. Зафиксировать в Git

```powershell
git add .
git commit -m "Patch 10: multi-references, unordered compare, full MongoDB course"
git push
```

---

## Что дальше

- **Патч-11** — Кабинет преподавателя (страница со списком студентов и их прогрессом) + UI конструктора лекций (Markdown-редактор)
- **Патч-12** — Песочница Redis + 3-4 урока с заданиями
- **Патч-13** — Песочница Cassandra (CQL)
- **Патч-14** — Песочница Neo4j (Cypher)
- **Патч-15** — Кабинет администратора + базовые автотесты pytest
- **День 12** — Деплой на VPS, домен, HTTPS
