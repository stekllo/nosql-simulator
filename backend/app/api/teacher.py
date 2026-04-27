"""Эндпоинты /teacher — кабинет преподавателя.

Доступны только для пользователей с ролью `teacher` или `admin`.
Преподаватель видит студентов, которые отправляли решения по его курсам;
администратор видит вообще всех.
"""
from datetime import datetime, timedelta
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import case, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import require_role
from app.db import get_db
from app.models import (
    Course, Lesson, Module, Submission, SubmissionStatus,
    Task, User, UserRole,
)
from app.schemas.teacher import (
    StudentBrief, StudentCourseProgress, StudentDailyActivity,
    StudentDetailResponse, StudentSubmission, TeacherStudentsResponse,
)


router = APIRouter(dependencies=[Depends(require_role(UserRole.TEACHER, UserRole.ADMIN))])


# ============================================================================
# /teacher/students  — список студентов с прогрессом
# ============================================================================

@router.get("/students", response_model=TeacherStudentsResponse)
async def list_students(
    teacher: Annotated[User, Depends(require_role(UserRole.TEACHER, UserRole.ADMIN))],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> TeacherStudentsResponse:
    """Список всех студентов, которые занимались курсами этого преподавателя.

    Для админа — список вообще всех студентов в системе.
    """

    def _naive(dt: datetime | None) -> datetime | None:
        """БД хранит TIMESTAMP WITHOUT TIME ZONE. Нормализуем всё к naive."""
        if dt is None:
            return None
        return dt.replace(tzinfo=None) if dt.tzinfo is not None else dt
    # ---------- Список курсов преподавателя ----------
    if teacher.role == UserRole.ADMIN:
        teacher_course_ids: list[int] = []  # игнорируем фильтр
    else:
        c_q = await session.execute(
            select(Course.course_id).where(Course.author_id == teacher.user_id)
        )
        teacher_course_ids = [r[0] for r in c_q.all()]

    # ---------- Список студентов ----------
    # Берём всех студентов, которые делали попытки по заданиям из курсов этого препода.
    # Если препод курсов нет — список пустой (но всё равно покажем total).
    if teacher.role == UserRole.ADMIN:
        users_q = await session.execute(
            select(User).where(User.role == UserRole.STUDENT).order_by(User.user_id)
        )
        students = list(users_q.scalars().all())
    else:
        # Подзапрос: task_id заданий из курсов препода.
        task_ids_subq = (
            select(Task.task_id)
            .join(Lesson, Lesson.lesson_id == Task.lesson_id)
            .join(Module, Module.module_id == Lesson.module_id)
            .where(Module.course_id.in_(teacher_course_ids))
        ) if teacher_course_ids else None

        if task_ids_subq is not None:
            users_q = await session.execute(
                select(User)
                .where(User.role == UserRole.STUDENT)
                .where(
                    User.user_id.in_(
                        select(Submission.user_id)
                        .where(Submission.task_id.in_(task_ids_subq))
                        .distinct()
                    )
                )
                .order_by(User.user_id)
            )
            students = list(users_q.scalars().all())
        else:
            students = []

    # ---------- Метрики по каждому студенту ----------
    student_briefs: list[StudentBrief] = []
    for s in students:
        # Фильтр: учитываем только submissions по нашим курсам (если не админ).
        sub_filter = [Submission.user_id == s.user_id]
        if teacher.role != UserRole.ADMIN and teacher_course_ids:
            sub_filter.append(
                Submission.task_id.in_(
                    select(Task.task_id)
                    .join(Lesson, Lesson.lesson_id == Task.lesson_id)
                    .join(Module, Module.module_id == Lesson.module_id)
                    .where(Module.course_id.in_(teacher_course_ids))
                )
            )

        m_q = await session.execute(
            select(
                func.count(Submission.submission_id),
                func.count(case((Submission.is_correct.is_(True), 1))),
                func.coalesce(func.sum(Submission.score), 0),
                func.max(Submission.submitted_at),
            )
            .where(*sub_filter)
        )
        total, correct, score_sum, last_at = m_q.one()

        # Сколько курсов начато: сколько разных course_id среди заданий, к которым были попытки.
        courses_q = await session.execute(
            select(func.count(func.distinct(Module.course_id)))
            .select_from(Submission)
            .join(Task, Task.task_id == Submission.task_id)
            .join(Lesson, Lesson.lesson_id == Task.lesson_id)
            .join(Module, Module.module_id == Lesson.module_id)
            .where(*sub_filter)
        )
        courses_started = courses_q.scalar() or 0

        student_briefs.append(StudentBrief(
            user_id          = s.user_id,
            login            = s.login,
            display_name     = s.display_name,
            email            = s.email,
            total_attempts   = total or 0,
            correct_attempts = correct or 0,
            total_score      = int(score_sum or 0),
            courses_started  = int(courses_started),
            last_activity_at = _naive(last_at),
        ))

    # ---------- Сводка ----------
    week_ago = datetime.utcnow().replace(tzinfo=None) - timedelta(days=7)
    active_this_week = sum(
        1 for sb in student_briefs
        if sb.last_activity_at is not None
           and _naive(sb.last_activity_at) >= week_ago
    )

    if teacher.role == UserRole.ADMIN:
        tc_stmt = select(func.count(Course.course_id))
    else:
        tc_stmt = select(func.count(Course.course_id)).where(
            Course.author_id == teacher.user_id
        )
    teacher_courses_q = await session.execute(tc_stmt)
    teacher_courses_count = teacher_courses_q.scalar() or 0

    avg_score = (
        sum(sb.total_score for sb in student_briefs) / len(student_briefs)
        if student_briefs else 0.0
    )

    return TeacherStudentsResponse(
        students          = student_briefs,
        total_students    = len(student_briefs),
        active_this_week  = active_this_week,
        teacher_courses   = int(teacher_courses_count),
        average_score     = round(avg_score, 1),
    )


# ============================================================================
# /teacher/students/{user_id}  — детали одного студента
# ============================================================================

@router.get("/students/{user_id}", response_model=StudentDetailResponse)
async def student_detail(
    user_id: int,
    teacher: Annotated[User, Depends(require_role(UserRole.TEACHER, UserRole.ADMIN))],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> StudentDetailResponse:
    """Подробная информация о студенте: прогресс по курсам, попытки, активность."""
    s_q = await session.execute(
        select(User).where(User.user_id == user_id).where(User.role == UserRole.STUDENT)
    )
    student = s_q.scalar_one_or_none()
    if student is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Студент не найден")

    def _naive(dt: datetime | None) -> datetime | None:
        if dt is None:
            return None
        return dt.replace(tzinfo=None) if dt.tzinfo is not None else dt

    # Курсы преподавателя (если не админ).
    if teacher.role == UserRole.ADMIN:
        teacher_course_ids: list[int] = []
    else:
        c_q = await session.execute(
            select(Course.course_id).where(Course.author_id == teacher.user_id)
        )
        teacher_course_ids = [r[0] for r in c_q.all()]

    sub_filter = [Submission.user_id == student.user_id]
    if teacher.role != UserRole.ADMIN and teacher_course_ids:
        sub_filter.append(
            Submission.task_id.in_(
                select(Task.task_id)
                .join(Lesson, Lesson.lesson_id == Task.lesson_id)
                .join(Module, Module.module_id == Lesson.module_id)
                .where(Module.course_id.in_(teacher_course_ids))
            )
        )

    # ---------- Базовые метрики ----------
    m_q = await session.execute(
        select(
            func.count(Submission.submission_id),
            func.count(case((Submission.is_correct.is_(True), 1))),
            func.coalesce(func.sum(Submission.score), 0),
            func.max(Submission.submitted_at),
        )
        .where(*sub_filter)
    )
    total, correct, score_sum, last_at = m_q.one()

    courses_q = await session.execute(
        select(func.count(func.distinct(Module.course_id)))
        .select_from(Submission)
        .join(Task, Task.task_id == Submission.task_id)
        .join(Lesson, Lesson.lesson_id == Task.lesson_id)
        .join(Module, Module.module_id == Lesson.module_id)
        .where(*sub_filter)
    )
    courses_started = int(courses_q.scalar() or 0)

    # ---------- Прогресс по курсам ----------
    # Список курсов: все, в которых были попытки.
    courses_list_q = await session.execute(
        select(Course)
        .where(
            Course.course_id.in_(
                select(Module.course_id)
                .select_from(Submission)
                .join(Task, Task.task_id == Submission.task_id)
                .join(Lesson, Lesson.lesson_id == Task.lesson_id)
                .join(Module, Module.module_id == Lesson.module_id)
                .where(*sub_filter)
            )
        )
        .order_by(Course.course_id)
    )
    courses_with_activity = list(courses_list_q.scalars().all())

    course_progress: list[StudentCourseProgress] = []
    for course in courses_with_activity:
        # Всего уроков в курсе.
        lessons_count_q = await session.execute(
            select(func.count(Lesson.lesson_id))
            .join(Module, Module.module_id == Lesson.module_id)
            .where(Module.course_id == course.course_id)
        )
        total_lessons = int(lessons_count_q.scalar() or 0)

        # Всего заданий в курсе.
        tasks_count_q = await session.execute(
            select(func.count(Task.task_id))
            .join(Lesson, Lesson.lesson_id == Task.lesson_id)
            .join(Module, Module.module_id == Lesson.module_id)
            .where(Module.course_id == course.course_id)
        )
        total_tasks = int(tasks_count_q.scalar() or 0)

        # Решено заданий студентом (уникальные task_id с correct).
        solved_q = await session.execute(
            select(func.count(func.distinct(Submission.task_id)))
            .join(Task, Task.task_id == Submission.task_id)
            .join(Lesson, Lesson.lesson_id == Task.lesson_id)
            .join(Module, Module.module_id == Lesson.module_id)
            .where(Module.course_id == course.course_id)
            .where(Submission.user_id == student.user_id)
            .where(Submission.is_correct.is_(True))
        )
        solved = int(solved_q.scalar() or 0)

        # Очки по курсу.
        course_score_q = await session.execute(
            select(func.coalesce(func.sum(Submission.score), 0))
            .join(Task, Task.task_id == Submission.task_id)
            .join(Lesson, Lesson.lesson_id == Task.lesson_id)
            .join(Module, Module.module_id == Lesson.module_id)
            .where(Module.course_id == course.course_id)
            .where(Submission.user_id == student.user_id)
        )
        course_score = int(course_score_q.scalar() or 0)

        percent = (solved / total_tasks * 100.0) if total_tasks > 0 else 0.0

        course_progress.append(StudentCourseProgress(
            course_id      = course.course_id,
            course_title   = course.title,
            nosql_type     = course.nosql_type.value,
            total_lessons  = total_lessons,
            total_tasks    = total_tasks,
            solved_tasks   = solved,
            percent        = round(percent, 1),
            total_score    = course_score,
        ))

    # ---------- Последние попытки (топ-15) ----------
    recent_q = await session.execute(
        select(
            Submission.submission_id,
            Submission.task_id,
            Submission.is_correct,
            Submission.score,
            Submission.status,
            Submission.submitted_at,
            Task.statement,
            Lesson.title,
            Course.title,
        )
        .join(Task, Task.task_id == Submission.task_id)
        .join(Lesson, Lesson.lesson_id == Task.lesson_id)
        .join(Module, Module.module_id == Lesson.module_id)
        .join(Course, Course.course_id == Module.course_id)
        .where(*sub_filter)
        .order_by(Submission.submitted_at.desc())
        .limit(15)
    )
    recent_rows = recent_q.all()
    recent_submissions = [
        StudentSubmission(
            submission_id = sub_id,
            task_id       = task_id,
            course_title  = course_title,
            lesson_title  = lesson_title,
            statement     = statement[:200] + ("…" if len(statement) > 200 else ""),
            is_correct    = is_correct,
            score         = score,
            status        = sub_status.value if hasattr(sub_status, "value") else str(sub_status),
            submitted_at  = _naive(submitted_at),
        )
        for (sub_id, task_id, is_correct, score, sub_status,
             submitted_at, statement, lesson_title, course_title) in recent_rows
    ]

    # ---------- Активность за 30 дней (для гистограммы) ----------
    month_ago = datetime.utcnow().replace(tzinfo=None) - timedelta(days=30)
    activity_q = await session.execute(
        select(
            func.date(Submission.submitted_at).label("day"),
            func.count(case((Submission.is_correct.is_(True), 1))).label("correct"),
            func.count(case((Submission.is_correct.is_(False), 1))).label("wrong"),
        )
        .where(*sub_filter)
        .where(Submission.submitted_at >= month_ago)
        .group_by(func.date(Submission.submitted_at))
        .order_by(func.date(Submission.submitted_at))
    )
    activity = [
        StudentDailyActivity(
            day     = str(day),
            correct = int(correct),
            wrong   = int(wrong),
        )
        for day, correct, wrong in activity_q.all()
    ]

    return StudentDetailResponse(
        user_id            = student.user_id,
        login              = student.login,
        display_name       = student.display_name,
        email              = student.email,
        total_attempts     = int(total or 0),
        correct_attempts   = int(correct or 0),
        total_score        = int(score_sum or 0),
        courses_started    = courses_started,
        last_activity_at   = _naive(last_at),
        course_progress    = course_progress,
        recent_submissions = recent_submissions,
        activity           = activity,
    )
