# Patch-11A — Кабинет преподавателя

Этот патч закрывает один из ключевых пунктов комиссии:
**«Сделать личные кабинеты студентов и преподавателей разными — преподаватель должен видеть прогресс студентов»**.

## Что добавляется

### Backend
- `GET /teacher/students` — список студентов с прогрессом
- `GET /teacher/students/{user_id}` — детали одного студента (метрики, курсы, попытки, активность)
- В seed добавлено **5 демо-студентов** с разной активностью:
  - **Анна Петрова** — активный студент, 4 недели, мало ошибается
  - **Дмитрий Соколов** — средний, 3 недели, иногда ошибается
  - **Мария Иванова** — недавно начала (2 недели)
  - **Александр Лебедев** — очень активный за последнюю неделю
  - **Екатерина Васильева** — слабая активность, много пропусков
- Все демо-студенты — пароль `demo123`

### Frontend
- Новая страница **`/teacher/students`** — таблица всех студентов
- Новая страница **`/teacher/students/{id}`** — детали одного студента с гистограммой
- В шапке у preподавателя появляется вкладка **«Студенты»**

## Состав файлов

```
backend/app/api/teacher.py             — новый роутер
backend/app/main.py                    — обновлён (подключение teacher_router)
backend/app/schemas/teacher.py         — новые схемы
backend/scripts/seed.py                — обновлён (5 доп. студентов)

frontend/src/App.tsx                   — обновлён (новые маршруты)
frontend/src/components/AppLayout.tsx  — обновлён (вкладка «Студенты»)
frontend/src/hooks/useTeacher.ts       — новый
frontend/src/lib/types.ts              — обновлён (типы teacher)
frontend/src/pages/TeacherStudentsPage.tsx       — новый
frontend/src/pages/TeacherStudentDetailPage.tsx  — новый
```

## Применение патча

### Шаг 1. Распакуй архив поверх проекта

```powershell
cd C:\Dev\nosql-sim
Expand-Archive -Path "путь\к\patch-11a-teacher-cabinet.zip" -DestinationPath . -Force
```

### Шаг 2. Сбросить и пересеять БД

```powershell
docker compose down -v
docker compose up -d
Start-Sleep -Seconds 30
docker compose exec backend alembic upgrade head
docker compose exec backend python -m scripts.seed
```

В логах должно появиться:
```
INFO  created user yuri ...
INFO  created user student ...
INFO  created user admin ...
INFO  created user anna ...
INFO  created user dmitry ...
INFO  created user maria ...
INFO  created user alex ...
INFO  created user ekaterina ...
INFO  ...
INFO  seeded 57 demo submissions for student
INFO  seeded 70 demo submissions for anna
INFO  seeded 35 demo submissions for dmitry
...
INFO  seed completed successfully
```

### Шаг 3. Перезапусти frontend (если он запущен в режиме `npm run dev` — он сам подхватит)

Если frontend запущен через docker:
```powershell
docker compose restart frontend
```

### Шаг 4. Проверка

1. Открой http://localhost:3000
2. Залогинься как `yuri / teacher123` (преподаватель)
3. В шапке появится вкладка **«Студенты»** — клик
4. Должна показаться таблица из 6 студентов с метриками: попытки, точность, баллы, активность
5. Клик на любой строке — откроется страница деталей с гистограммой и попытками

### Шаг 5. Закоммить

```powershell
git add .
git commit -m "Patch 11A: teacher cabinet (students list + details)"
git push
```

## Что дальше — Patch-11B (конструктор лекций)

После этого делаем **конструктор лекций** — преподаватель сможет создавать и редактировать уроки (Markdown-редактор) прямо в UI.
