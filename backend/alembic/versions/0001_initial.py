"""Initial schema: users, courses, modules, lessons, tasks, submissions, progress, achievements.

Revision ID: 0001_initial
Revises:
Create Date: 2026-04-22 10:00:00
"""

from typing import Sequence, Union

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "0001_initial"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Создаём ENUM типы через прямой SQL, чтобы SQLAlchemy
    # не пытался создать их повторно при create_table.
    op.execute("CREATE TYPE user_role         AS ENUM ('student', 'teacher', 'admin')")
    op.execute(
        "CREATE TYPE nosql_type        AS ENUM ('document', 'key_value', 'column', 'graph', 'mixed')"
    )
    op.execute("CREATE TYPE submission_status AS ENUM ('pending', 'correct', 'wrong', 'timeout')")
    op.execute("CREATE TYPE progress_status   AS ENUM ('started', 'in_progress', 'completed')")

    # При использовании сырого SQL для создания типа в таблицах
    # передаём ENUM с create_type=False — тип уже есть.
    user_role = postgresql.ENUM(name="user_role", create_type=False)
    nosql_type = postgresql.ENUM(name="nosql_type", create_type=False)
    submission_status = postgresql.ENUM(name="submission_status", create_type=False)
    progress_status = postgresql.ENUM(name="progress_status", create_type=False)

    # ---------- users ----------
    op.create_table(
        "users",
        sa.Column("user_id", sa.BigInteger, primary_key=True),
        sa.Column("login", sa.String(64), nullable=False, unique=True),
        sa.Column("email", sa.String(128), nullable=False, unique=True),
        sa.Column("password_hash", sa.String(255), nullable=False),
        sa.Column("display_name", sa.String(128)),
        sa.Column("role", user_role, nullable=False, server_default="student"),
        sa.Column(
            "created_at", sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.Column("last_login_at", sa.TIMESTAMP(timezone=True)),
    )
    op.create_index("ix_users_login", "users", ["login"])
    op.create_index("ix_users_email", "users", ["email"])

    # ---------- courses ----------
    op.create_table(
        "courses",
        sa.Column("course_id", sa.BigInteger, primary_key=True),
        sa.Column("title", sa.String(255), nullable=False),
        sa.Column("description", sa.Text),
        sa.Column("nosql_type", nosql_type, nullable=False),
        sa.Column(
            "author_id",
            sa.BigInteger,
            sa.ForeignKey("users.user_id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("difficulty", sa.SmallInteger),
        sa.Column(
            "created_at", sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.CheckConstraint("difficulty BETWEEN 1 AND 5", name="ck_courses_difficulty"),
    )

    # ---------- modules ----------
    op.create_table(
        "modules",
        sa.Column("module_id", sa.BigInteger, primary_key=True),
        sa.Column(
            "course_id",
            sa.BigInteger,
            sa.ForeignKey("courses.course_id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("title", sa.String(255), nullable=False),
        sa.Column("description", sa.Text),
        sa.Column("order_num", sa.Integer, nullable=False),
        sa.UniqueConstraint("course_id", "order_num", name="uq_modules_course_order"),
    )

    # ---------- lessons ----------
    op.create_table(
        "lessons",
        sa.Column("lesson_id", sa.BigInteger, primary_key=True),
        sa.Column(
            "module_id",
            sa.BigInteger,
            sa.ForeignKey("modules.module_id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("title", sa.String(255), nullable=False),
        sa.Column("content_md", sa.Text, nullable=False),
        sa.Column("order_num", sa.Integer, nullable=False),
        sa.Column("duration_min", sa.SmallInteger),
        sa.UniqueConstraint("module_id", "order_num", name="uq_lessons_module_order"),
    )

    # ---------- tasks ----------
    op.create_table(
        "tasks",
        sa.Column("task_id", sa.BigInteger, primary_key=True),
        sa.Column(
            "lesson_id",
            sa.BigInteger,
            sa.ForeignKey("lessons.lesson_id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("statement", sa.Text, nullable=False),
        sa.Column("db_type", nosql_type, nullable=False),
        sa.Column("fixture", postgresql.JSONB, nullable=False),
        sa.Column("reference_solution", sa.Text, nullable=False),
        sa.Column("max_score", sa.SmallInteger, nullable=False, server_default="10"),
        sa.Column("attempts_limit", sa.SmallInteger, nullable=False, server_default="0"),
    )

    # ---------- submissions ----------
    op.create_table(
        "submissions",
        sa.Column("submission_id", sa.BigInteger, primary_key=True),
        sa.Column(
            "user_id",
            sa.BigInteger,
            sa.ForeignKey("users.user_id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "task_id",
            sa.BigInteger,
            sa.ForeignKey("tasks.task_id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("query_text", sa.Text, nullable=False),
        sa.Column("result", postgresql.JSONB),
        sa.Column("is_correct", sa.Boolean),
        sa.Column("score", sa.SmallInteger),
        sa.Column("status", submission_status, nullable=False, server_default="pending"),
        sa.Column(
            "submitted_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )
    op.create_index("ix_submissions_user_id", "submissions", ["user_id"])
    op.create_index("ix_submissions_task_id", "submissions", ["task_id"])

    # ---------- progress ----------
    op.create_table(
        "progress",
        sa.Column("progress_id", sa.BigInteger, primary_key=True),
        sa.Column(
            "user_id",
            sa.BigInteger,
            sa.ForeignKey("users.user_id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "course_id",
            sa.BigInteger,
            sa.ForeignKey("courses.course_id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("percent", sa.REAL, nullable=False, server_default="0"),
        sa.Column("total_score", sa.Integer, nullable=False, server_default="0"),
        sa.Column("status", progress_status, nullable=False, server_default="started"),
        sa.Column(
            "started_at", sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.Column("last_activity_at", sa.TIMESTAMP(timezone=True)),
        sa.UniqueConstraint("user_id", "course_id", name="uq_progress_user_course"),
    )

    # ---------- achievements ----------
    op.create_table(
        "achievements",
        sa.Column("achievement_id", sa.BigInteger, primary_key=True),
        sa.Column("name", sa.String(128), nullable=False),
        sa.Column("description", sa.Text),
        sa.Column("icon", sa.String(255)),
        sa.Column("condition", sa.String(255)),
        sa.Column("points", sa.SmallInteger, nullable=False, server_default="0"),
    )

    # ---------- user_achievements ----------
    op.create_table(
        "user_achievements",
        sa.Column("ua_id", sa.BigInteger, primary_key=True),
        sa.Column(
            "user_id",
            sa.BigInteger,
            sa.ForeignKey("users.user_id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "achievement_id",
            sa.BigInteger,
            sa.ForeignKey("achievements.achievement_id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "granted_at", sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.UniqueConstraint("user_id", "achievement_id", name="uq_user_achievements"),
    )


def downgrade() -> None:
    op.drop_table("user_achievements")
    op.drop_table("achievements")
    op.drop_table("progress")
    op.drop_index("ix_submissions_task_id", table_name="submissions")
    op.drop_index("ix_submissions_user_id", table_name="submissions")
    op.drop_table("submissions")
    op.drop_table("tasks")
    op.drop_table("lessons")
    op.drop_table("modules")
    op.drop_table("courses")
    op.drop_index("ix_users_email", table_name="users")
    op.drop_index("ix_users_login", table_name="users")
    op.drop_table("users")

    for enum_name in ("progress_status", "submission_status", "nosql_type", "user_role"):
        op.execute(f"DROP TYPE IF EXISTS {enum_name}")
