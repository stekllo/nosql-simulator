"""Lesson completions: явные пометки 'я прошёл этот урок'.

Создаёт таблицу `lesson_completions` для отметок студентом теоретических
уроков (через клик кнопки «Дальше →» внизу урока).

Бэкфил: для каждого студента, у которого уже есть хотя бы один CORRECT
сабмишен по курсу, сразу проставляются отметки на ВСЕ теоретические уроки
этого курса. Это нужно, чтобы существующая статистика прогресса не
«откатилась» после смены логики (раньше теория считалась пройденной
автоматически).

Revision ID: 0003_lesson_completions
Revises: 0002_multi_refs
Create Date: 2026-04-27 17:00:00
"""

from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

revision: str = "0003_lesson_completions"
down_revision: Union[str, None] = "0002_multi_refs"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ---- Таблица отметок ----
    op.create_table(
        "lesson_completions",
        sa.Column("completion_id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("user_id",       sa.BigInteger(), nullable=False),
        sa.Column("lesson_id",     sa.BigInteger(), nullable=False),
        sa.Column(
            "completed_at",
            sa.DateTime(timezone=False),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["user_id"], ["users.user_id"], ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["lesson_id"], ["lessons.lesson_id"], ondelete="CASCADE",
        ),
        sa.UniqueConstraint(
            "user_id", "lesson_id", name="uq_lesson_completions_user_lesson",
        ),
    )
    op.create_index(
        "ix_lesson_completions_user_id",
        "lesson_completions", ["user_id"],
    )
    op.create_index(
        "ix_lesson_completions_lesson_id",
        "lesson_completions", ["lesson_id"],
    )

    # ---- Бэкфил ----
    #
    # Для каждой пары (user_id, course_id) с хотя бы одним CORRECT-сабмишеном:
    # проставляем отметку на КАЖДЫЙ теоретический урок (где нет ни одного task).
    # Уроки с заданиями не трогаем — они и так считаются «пройденными»,
    # если все задания решены.
    #
    # SQL делает это одним INSERT'ом через WITH/JOIN — без Python-цикла.
    op.execute(
        """
        INSERT INTO lesson_completions (user_id, lesson_id, completed_at)
        SELECT DISTINCT
            s.user_id,
            l.lesson_id,
            NOW()
        FROM submissions s
        JOIN tasks   t  ON t.task_id   = s.task_id
        JOIN lessons l_solved ON l_solved.lesson_id = t.lesson_id
        JOIN modules m_solved ON m_solved.module_id = l_solved.module_id
        -- Все уроки этого же курса
        JOIN modules m  ON m.course_id = m_solved.course_id
        JOIN lessons l  ON l.module_id = m.module_id
        -- Только теоретические (без заданий)
        WHERE s.status = 'correct'
          AND NOT EXISTS (
              SELECT 1 FROM tasks t2 WHERE t2.lesson_id = l.lesson_id
          )
        ON CONFLICT (user_id, lesson_id) DO NOTHING
        """
    )


def downgrade() -> None:
    op.drop_index("ix_lesson_completions_lesson_id", table_name="lesson_completions")
    op.drop_index("ix_lesson_completions_user_id",   table_name="lesson_completions")
    op.drop_table("lesson_completions")
