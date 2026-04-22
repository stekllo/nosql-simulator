"""Модель пользователя и вспомогательные перечисления."""
from __future__ import annotations

from datetime import datetime
from enum import Enum as PyEnum
from typing import TYPE_CHECKING, Optional

from sqlalchemy import BigInteger, String, func
from sqlalchemy.dialects.postgresql import ENUM as PgEnum
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base

if TYPE_CHECKING:
    from app.models.course import Course, Progress
    from app.models.submission import Submission


class UserRole(str, PyEnum):
    STUDENT = "student"
    TEACHER = "teacher"
    ADMIN   = "admin"


# Явно создаём ENUM, чтобы Alembic не плодил его при каждой миграции.
user_role_enum = PgEnum(
    UserRole,
    name         = "user_role",
    create_type  = False,         # тип создаётся в миграции вручную
    values_callable = lambda e: [m.value for m in e],
)


class User(Base):
    __tablename__ = "users"

    user_id:       Mapped[int]                   = mapped_column(BigInteger, primary_key=True)
    login:         Mapped[str]                   = mapped_column(String(64),  unique=True, nullable=False, index=True)
    email:         Mapped[str]                   = mapped_column(String(128), unique=True, nullable=False, index=True)
    password_hash: Mapped[str]                   = mapped_column(String(255), nullable=False)
    display_name:  Mapped[Optional[str]]         = mapped_column(String(128))
    role:          Mapped[UserRole]              = mapped_column(user_role_enum, default=UserRole.STUDENT, nullable=False)
    created_at:    Mapped[datetime]              = mapped_column(server_default=func.now(), nullable=False)
    last_login_at: Mapped[Optional[datetime]]

    authored_courses: Mapped[list["Course"]]     = relationship(back_populates="author", cascade="all")
    submissions:      Mapped[list["Submission"]] = relationship(back_populates="user",   cascade="all")
    progresses:       Mapped[list["Progress"]]   = relationship(back_populates="user",   cascade="all")

    def __repr__(self) -> str:
        return f"<User {self.login} ({self.role.value})>"
