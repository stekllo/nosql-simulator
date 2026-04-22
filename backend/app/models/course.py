"""Учебный контент: курсы, модули, уроки. Прогресс прохождения."""

from __future__ import annotations

from datetime import datetime
from enum import Enum as PyEnum
from typing import TYPE_CHECKING, Optional

from sqlalchemy import (
    REAL,
    BigInteger,
    CheckConstraint,
    ForeignKey,
    Integer,
    SmallInteger,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import ENUM as PgEnum
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base

if TYPE_CHECKING:
    from app.models.submission import Task
    from app.models.user import User


# ---------- ENUM типы ----------


class NoSQLType(str, PyEnum):
    DOCUMENT = "document"
    KEY_VALUE = "key_value"
    COLUMN = "column"
    GRAPH = "graph"
    MIXED = "mixed"


class ProgressStatus(str, PyEnum):
    STARTED = "started"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"


nosql_type_enum = PgEnum(
    NoSQLType,
    name="nosql_type",
    create_type=False,
    values_callable=lambda e: [m.value for m in e],
)

progress_status_enum = PgEnum(
    ProgressStatus,
    name="progress_status",
    create_type=False,
    values_callable=lambda e: [m.value for m in e],
)


# ---------- Модели ----------


class Course(Base):
    __tablename__ = "courses"

    course_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text)
    nosql_type: Mapped[NoSQLType] = mapped_column(nosql_type_enum, nullable=False)
    author_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("users.user_id", ondelete="RESTRICT"), nullable=False
    )
    difficulty: Mapped[Optional[int]] = mapped_column(SmallInteger)
    created_at: Mapped[datetime] = mapped_column(server_default=func.now(), nullable=False)

    author: Mapped["User"] = relationship(back_populates="authored_courses")
    modules: Mapped[list["Module"]] = relationship(
        back_populates="course",
        cascade="all, delete-orphan",
        order_by="Module.order_num",
    )
    progresses: Mapped[list["Progress"]] = relationship(back_populates="course", cascade="all")

    __table_args__ = (CheckConstraint("difficulty BETWEEN 1 AND 5", name="ck_courses_difficulty"),)


class Module(Base):
    __tablename__ = "modules"

    module_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    course_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("courses.course_id", ondelete="CASCADE"), nullable=False
    )
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text)
    order_num: Mapped[int] = mapped_column(Integer, nullable=False)

    course: Mapped["Course"] = relationship(back_populates="modules")
    lessons: Mapped[list["Lesson"]] = relationship(
        back_populates="module",
        cascade="all, delete-orphan",
        order_by="Lesson.order_num",
    )

    __table_args__ = (UniqueConstraint("course_id", "order_num", name="uq_modules_course_order"),)


class Lesson(Base):
    __tablename__ = "lessons"

    lesson_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    module_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("modules.module_id", ondelete="CASCADE"), nullable=False
    )
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    content_md: Mapped[str] = mapped_column(Text, nullable=False)
    order_num: Mapped[int] = mapped_column(Integer, nullable=False)
    duration_min: Mapped[Optional[int]] = mapped_column(SmallInteger)

    module: Mapped["Module"] = relationship(back_populates="lessons")
    tasks: Mapped[list["Task"]] = relationship(
        back_populates="lesson",
        cascade="all, delete-orphan",
        order_by="Task.task_id",
    )

    __table_args__ = (UniqueConstraint("module_id", "order_num", name="uq_lessons_module_order"),)


class Progress(Base):
    __tablename__ = "progress"

    progress_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    user_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("users.user_id", ondelete="CASCADE"), nullable=False
    )
    course_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("courses.course_id", ondelete="CASCADE"), nullable=False
    )
    percent: Mapped[float] = mapped_column(REAL, default=0.0, nullable=False)
    total_score: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    status: Mapped[ProgressStatus] = mapped_column(
        progress_status_enum, default=ProgressStatus.STARTED, nullable=False
    )
    started_at: Mapped[datetime] = mapped_column(server_default=func.now(), nullable=False)
    last_activity_at: Mapped[Optional[datetime]]

    user: Mapped["User"] = relationship(back_populates="progresses")
    course: Mapped["Course"] = relationship(back_populates="progresses")

    __table_args__ = (UniqueConstraint("user_id", "course_id", name="uq_progress_user_course"),)
