"""Эндпоинты /me — личный кабинет и история действий пользователя."""

from datetime import datetime, timedelta
from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy import case, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import CurrentUser
from app.db import get_db
from app.models import (
    Achievement,
    Course,
    Lesson,
    Module,
    Submission,
    SubmissionStatus,
    Task,
    UserAchievement,
)
from app.schemas.dashboard import (
    AchievementBrief,
    CourseProgress,
    DailyActivity,
    DashboardResponse,
    SubmissionBrief,
)

router = APIRouter()


# ---------- /me/dashboard ----------


@router.get("/dashboard", response_model=DashboardResponse)
async def dashboard(
    user: CurrentUser,
    session: Annotated[AsyncSession, Depends(get_db)],
) -> DashboardResponse:
    """Агрегированная статистика для личного кабинета."""
    now = datetime.utcnow()  # naive UTC, как хранит asyncpg
    month_ago = now - timedelta(days=30)
    week_ago = now - timedelta(days=7)

    # ---------- Решённые задания (уникальные task_id, где был correct) ----------
    solved_q = await session.execute(
        select(func.count(func.distinct(Submission.task_id)))
        .where(Submission.user_id == user.user_id)
        .where(Submission.is_correct.is_(True))
    )
    solved_tasks = solved_q.scalar_one() or 0

    # Всего заданий в каталоге.
    available_q = await session.execute(select(func.count(Task.task_id)))
    available_tasks = available_q.scalar_one() or 0

    # Решено за последнюю неделю.
    weekly_q = await session.execute(
        select(func.count(func.distinct(Submission.task_id)))
        .where(Submission.user_id == user.user_id)
        .where(Submission.is_correct.is_(True))
        .where(Submission.submitted_at >= week_ago)
    )
    weekly_delta = weekly_q.scalar_one() or 0

    # ---------- Баллы ----------
    total_score_q = await session.execute(
        select(func.coalesce(func.sum(Submission.score), 0))
        .where(Submission.user_id == user.user_id)
        .where(Submission.is_correct.is_(True))
    )
    total_score = int(total_score_q.scalar_one() or 0)

    recent_score_q = await session.execute(
        select(func.coalesce(func.sum(Submission.score), 0))
        .where(Submission.user_id == user.user_id)
        .where(Submission.is_correct.is_(True))
        .where(Submission.submitted_at >= week_ago)
    )
    recent_score = int(recent_score_q.scalar_one() or 0)

    # ---------- Активные / всего курсов ----------
    total_courses_q = await session.execute(select(func.count(Course.course_id)))
    total_courses = total_courses_q.scalar_one() or 0

    # Активный курс = курс, в котором есть хотя бы одна попытка студента.
    active_q = await session.execute(
        select(func.count(func.distinct(Course.course_id)))
        .select_from(Submission)
        .join(Task, Task.task_id == Submission.task_id)
        .join(Lesson, Lesson.lesson_id == Task.lesson_id)
        .join(Module, Module.module_id == Lesson.module_id)
        .join(Course, Course.course_id == Module.course_id)
        .where(Submission.user_id == user.user_id)
    )
    active_courses = active_q.scalar_one() or 0

    # ---------- Активность по дням (30 дней) ----------
    day_col = func.date_trunc("day", Submission.submitted_at).label("day")
    activity_q = await session.execute(
        select(
            day_col,
            func.sum(case((Submission.is_correct.is_(True), 1), else_=0)).label("correct"),
            func.sum(case((Submission.is_correct.is_(False), 1), else_=0)).label("wrong"),
        )
        .where(Submission.user_id == user.user_id)
        .where(Submission.submitted_at >= month_ago)
        .group_by(day_col)
        .order_by(day_col)
    )
    activity_by_day: dict[str, tuple[int, int]] = {
        row.day.date().isoformat(): (int(row.correct or 0), int(row.wrong or 0))
        for row in activity_q.all()
    }

    # Строим полный ряд из 30 дней (даже пустых).
    activity: list[DailyActivity] = []
    for i in range(29, -1, -1):
        d = (now - timedelta(days=i)).date()
        key = d.isoformat()
        corr, wr = activity_by_day.get(key, (0, 0))
        activity.append(DailyActivity(day=d, correct=corr, wrong=wr))

    # ---------- Серия дней подряд ----------
    dates_with_activity = {d.day for d in activity if d.correct + d.wrong > 0}
    streak_days = 0
    d = now.date()
    while d in dates_with_activity:
        streak_days += 1
        d -= timedelta(days=1)
    # Максимум серии за месяц (упрощённо).
    best_streak = streak_days
    run = 0
    for a in activity:
        if a.correct + a.wrong > 0:
            run += 1
            best_streak = max(best_streak, run)
        else:
            run = 0

    # ---------- Прогресс по курсам ----------
    # Берём курсы, где пользователь сделал хотя бы одну попытку.
    courses_stats_q = await session.execute(
        select(
            Course.course_id,
            Course.title,
            Course.nosql_type,
            func.count(func.distinct(Lesson.lesson_id)).label("lesson_count"),
            func.count(func.distinct(Module.module_id)).label("module_count"),
        )
        .select_from(Course)
        .join(Module, Module.course_id == Course.course_id, isouter=True)
        .join(Lesson, Lesson.module_id == Module.module_id, isouter=True)
        .group_by(Course.course_id, Course.title, Course.nosql_type)
        .order_by(Course.course_id)
    )

    current_courses: list[CourseProgress] = []
    for row in courses_stats_q.all():
        # Считаем, сколько уроков из этого курса уже пройдено (есть правильная попытка).
        lessons_done_q = await session.execute(
            select(func.count(func.distinct(Lesson.lesson_id)))
            .select_from(Submission)
            .join(Task, Task.task_id == Submission.task_id)
            .join(Lesson, Lesson.lesson_id == Task.lesson_id)
            .join(Module, Module.module_id == Lesson.module_id)
            .where(Module.course_id == row.course_id)
            .where(Submission.user_id == user.user_id)
            .where(Submission.is_correct.is_(True))
        )
        lessons_done = lessons_done_q.scalar_one() or 0

        course_score_q = await session.execute(
            select(func.coalesce(func.sum(Submission.score), 0))
            .select_from(Submission)
            .join(Task, Task.task_id == Submission.task_id)
            .join(Lesson, Lesson.lesson_id == Task.lesson_id)
            .join(Module, Module.module_id == Lesson.module_id)
            .where(Module.course_id == row.course_id)
            .where(Submission.user_id == user.user_id)
            .where(Submission.is_correct.is_(True))
        )
        course_score = int(course_score_q.scalar_one() or 0)

        percent = (lessons_done / row.lesson_count * 100) if row.lesson_count else 0.0

        # В dashboard показываем курсы где есть прогресс или который доступен.
        if lessons_done > 0 or row.lesson_count > 0:
            current_courses.append(
                CourseProgress(
                    course_id=row.course_id,
                    course_title=row.title,
                    nosql_type=row.nosql_type,
                    percent=round(percent, 1),
                    total_score=course_score,
                    module_count=row.module_count or 0,
                    lesson_count=row.lesson_count or 0,
                    lessons_done=lessons_done,
                )
            )

    # Сортируем: сначала с прогрессом, потом без.
    current_courses.sort(key=lambda c: (-c.percent, c.course_id))

    # ---------- Достижения ----------
    all_ach_q = await session.execute(select(Achievement).order_by(Achievement.achievement_id))
    all_ach = all_ach_q.scalars().all()

    granted_q = await session.execute(
        select(UserAchievement.achievement_id, UserAchievement.granted_at).where(
            UserAchievement.user_id == user.user_id
        )
    )
    granted_map = {row[0]: row[1] for row in granted_q.all()}

    achievements = [
        AchievementBrief(
            achievement_id=a.achievement_id,
            name=a.name,
            description=a.description,
            icon=a.icon,
            points=a.points,
            granted=a.achievement_id in granted_map,
            granted_at=granted_map.get(a.achievement_id),
        )
        for a in all_ach
    ]

    return DashboardResponse(
        active_courses=active_courses,
        total_courses=total_courses,
        solved_tasks=solved_tasks,
        available_tasks=available_tasks,
        weekly_delta=weekly_delta,
        total_score=total_score,
        recent_score=recent_score,
        streak_days=streak_days,
        best_streak=best_streak,
        activity=activity,
        current_courses=current_courses,
        achievements=achievements,
    )


# ---------- /me/submissions ----------


@router.get("/submissions", response_model=list[SubmissionBrief])
async def my_submissions(
    user: CurrentUser,
    session: Annotated[AsyncSession, Depends(get_db)],
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
) -> list[SubmissionBrief]:
    """Последние N попыток текущего пользователя с контекстом урока/курса."""
    stmt = (
        select(
            Submission.submission_id,
            Submission.task_id,
            Submission.is_correct,
            Submission.score,
            Submission.status,
            Submission.submitted_at,
            Lesson.title.label("lesson_title"),
            Course.title.label("course_title"),
        )
        .select_from(Submission)
        .join(Task, Task.task_id == Submission.task_id)
        .join(Lesson, Lesson.lesson_id == Task.lesson_id)
        .join(Module, Module.module_id == Lesson.module_id)
        .join(Course, Course.course_id == Module.course_id)
        .where(Submission.user_id == user.user_id)
        .order_by(Submission.submitted_at.desc())
        .limit(limit)
    )
    result = await session.execute(stmt)
    return [
        SubmissionBrief(
            submission_id=r.submission_id,
            task_id=r.task_id,
            is_correct=r.is_correct,
            score=r.score,
            status=r.status.value if hasattr(r.status, "value") else str(r.status),
            submitted_at=r.submitted_at,
            lesson_title=r.lesson_title,
            course_title=r.course_title,
        )
        for r in result.all()
    ]
