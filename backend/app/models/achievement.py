"""Достижения и привязка к пользователям."""
from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlalchemy import (
    BigInteger, ForeignKey, SmallInteger, String, Text, UniqueConstraint, func,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


class Achievement(Base):
    __tablename__ = "achievements"

    achievement_id: Mapped[int]           = mapped_column(BigInteger, primary_key=True)
    name:           Mapped[str]           = mapped_column(String(128), nullable=False)
    description:    Mapped[Optional[str]] = mapped_column(Text)
    icon:           Mapped[Optional[str]] = mapped_column(String(255))
    condition:      Mapped[Optional[str]] = mapped_column(String(255))
    points:         Mapped[int]           = mapped_column(SmallInteger, default=0, nullable=False)


class UserAchievement(Base):
    __tablename__ = "user_achievements"

    ua_id:          Mapped[int]       = mapped_column(BigInteger, primary_key=True)
    user_id:        Mapped[int]       = mapped_column(
        BigInteger, ForeignKey("users.user_id", ondelete="CASCADE"), nullable=False
    )
    achievement_id: Mapped[int]       = mapped_column(
        BigInteger, ForeignKey("achievements.achievement_id", ondelete="CASCADE"), nullable=False
    )
    granted_at:     Mapped[datetime]  = mapped_column(server_default=func.now(), nullable=False)

    __table_args__ = (
        UniqueConstraint("user_id", "achievement_id", name="uq_user_achievements"),
    )
