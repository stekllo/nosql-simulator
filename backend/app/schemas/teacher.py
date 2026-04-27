"""Схемы для кабинета преподавателя."""
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict


class StudentBrief(BaseModel):
    """Кратко о студенте: для таблицы списка."""
    model_config = ConfigDict(from_attributes=True)

    user_id:           int
    login:             str
    display_name:      str | None
    email:             str
    total_attempts:    int        # всего попыток отправлено
    correct_attempts:  int        # правильных
    total_score:       int        # общий счёт
    courses_started:   int        # сколько курсов начал
    last_activity_at:  datetime | None  # последняя попытка


class TeacherStudentsResponse(BaseModel):
    """Список студентов + сводка по курсам преподавателя."""
    students:           list[StudentBrief]
    total_students:     int
    active_this_week:   int        # были попытки за последние 7 дней
    teacher_courses:    int        # количество курсов, созданных этим препом
    average_score:      float      # средний счёт по студентам


class StudentCourseProgress(BaseModel):
    """Прогресс одного студента по одному курсу."""
    course_id:        int
    course_title:     str
    nosql_type:       str
    total_lessons:    int
    total_tasks:      int
    solved_tasks:     int
    percent:          float
    total_score:      int


class StudentSubmission(BaseModel):
    """Одна попытка студента (для подробной истории)."""
    submission_id:  int
    task_id:        int
    course_title:   str
    lesson_title:   str
    statement:      str
    is_correct:     bool | None
    score:          int  | None
    status:         str
    submitted_at:   datetime


class StudentDailyActivity(BaseModel):
    """Активность за один день — для гистограммы в карточке студента."""
    day:     str
    correct: int
    wrong:   int


class StudentDetailResponse(BaseModel):
    """Полный профиль студента: метрики + прогресс по курсам + последние попытки."""
    user_id:            int
    login:              str
    display_name:       str | None
    email:              str
    total_attempts:     int
    correct_attempts:   int
    total_score:        int
    courses_started:    int
    last_activity_at:   datetime | None
    course_progress:    list[StudentCourseProgress]
    recent_submissions: list[StudentSubmission]
    activity:           list[StudentDailyActivity]
