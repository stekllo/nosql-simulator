"""Схемы статистики пользователя."""
from datetime import date, datetime

from pydantic import BaseModel, ConfigDict

from app.models import NoSQLType


class DailyActivity(BaseModel):
    """Активность за один день — для гистограммы."""
    day:     date
    correct: int
    wrong:   int


class CourseProgress(BaseModel):
    """Прогресс по одному курсу."""
    model_config = ConfigDict(from_attributes=True)

    course_id:     int
    course_title:  str
    nosql_type:    NoSQLType
    percent:       float
    total_score:   int
    module_count:  int
    lesson_count:  int
    lessons_done:  int


class AchievementBrief(BaseModel):
    """Достижение пользователя (кратко)."""
    model_config = ConfigDict(from_attributes=True)

    achievement_id: int
    name:           str
    description:    str | None
    icon:           str | None
    points:         int
    granted:        bool
    granted_at:     datetime | None = None


class DashboardResponse(BaseModel):
    """Полный набор данных для личного кабинета."""

    # KPI-карточки
    active_courses:   int
    total_courses:    int
    solved_tasks:     int
    available_tasks:  int
    weekly_delta:     int              # решено за последнюю неделю
    total_score:      int
    recent_score:     int              # баллы за последнюю неделю
    streak_days:      int              # дней подряд с активностью
    best_streak:      int

    # Графики
    activity:         list[DailyActivity]   # 30 дней

    # Списки
    current_courses:  list[CourseProgress]
    achievements:     list[AchievementBrief]


class SubmissionBrief(BaseModel):
    """Элемент истории попыток."""
    model_config = ConfigDict(from_attributes=True)

    submission_id: int
    task_id:       int
    is_correct:    bool | None
    score:         int  | None
    status:        str
    submitted_at:  datetime
    lesson_title:  str
    course_title:  str
