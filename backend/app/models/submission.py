"""Задания и попытки решения."""
from __future__ import annotations

from datetime import datetime
from enum import Enum as PyEnum
from typing import TYPE_CHECKING, Any, Optional

from sqlalchemy import (
    BigInteger, Boolean, ForeignKey, SmallInteger, Text, func,
)
from sqlalchemy.dialects.postgresql import ENUM as PgEnum, JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base
from app.models.course import nosql_type_enum, NoSQLType

if TYPE_CHECKING:
    from app.models.course import Lesson
    from app.models.user import User


class SubmissionStatus(str, PyEnum):
    PENDING = "pending"
    CORRECT = "correct"
    WRONG   = "wrong"
    TIMEOUT = "timeout"


submission_status_enum = PgEnum(
    SubmissionStatus,
    name            = "submission_status",
    create_type     = False,
    values_callable = lambda e: [m.value for m in e],
)


class Task(Base):
    __tablename__ = "tasks"

    task_id:            Mapped[int]       = mapped_column(BigInteger, primary_key=True)
    lesson_id:          Mapped[int]       = mapped_column(
        BigInteger, ForeignKey("lessons.lesson_id", ondelete="CASCADE"), nullable=False
    )
    statement:          Mapped[str]       = mapped_column(Text, nullable=False)
    db_type:            Mapped[NoSQLType] = mapped_column(nosql_type_enum, nullable=False)
    fixture:            Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    reference_solution: Mapped[str]       = mapped_column(Text, nullable=False)
    max_score:          Mapped[int]       = mapped_column(SmallInteger, default=10, nullable=False)
    attempts_limit:     Mapped[int]       = mapped_column(SmallInteger, default=0,  nullable=False)

    lesson:      Mapped["Lesson"]           = relationship(back_populates="tasks")
    submissions: Mapped[list["Submission"]] = relationship(
        back_populates="task", cascade="all, delete-orphan",
    )


class Submission(Base):
    __tablename__ = "submissions"

    submission_id: Mapped[int]              = mapped_column(BigInteger, primary_key=True)
    user_id:       Mapped[int]              = mapped_column(
        BigInteger, ForeignKey("users.user_id", ondelete="CASCADE"), nullable=False, index=True
    )
    task_id:       Mapped[int]              = mapped_column(
        BigInteger, ForeignKey("tasks.task_id", ondelete="CASCADE"), nullable=False, index=True
    )
    query_text:    Mapped[str]              = mapped_column(Text, nullable=False)
    result:        Mapped[Optional[dict[str, Any]]] = mapped_column(JSONB)
    is_correct:    Mapped[Optional[bool]]   = mapped_column(Boolean)
    score:         Mapped[Optional[int]]    = mapped_column(SmallInteger)
    status:        Mapped[SubmissionStatus] = mapped_column(
        submission_status_enum, default=SubmissionStatus.PENDING, nullable=False
    )
    submitted_at:  Mapped[datetime]         = mapped_column(server_default=func.now(), nullable=False)

    user: Mapped["User"] = relationship(back_populates="submissions")
    task: Mapped["Task"] = relationship(back_populates="submissions")
