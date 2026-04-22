"""ORM-модели базы данных.

Импорт всех моделей в одном месте нужен Alembic'у, чтобы он увидел
их все при автогенерации миграций.
"""
from app.models.achievement import Achievement, UserAchievement
from app.models.course import Course, Lesson, Module, NoSQLType, Progress, ProgressStatus
from app.models.submission import Submission, SubmissionStatus, Task
from app.models.user import User, UserRole

__all__ = [
    "Achievement",
    "Course",
    "Lesson",
    "Module",
    "NoSQLType",
    "Progress",
    "ProgressStatus",
    "Submission",
    "SubmissionStatus",
    "Task",
    "User",
    "UserAchievement",
    "UserAchievement",
    "UserRole",
]
