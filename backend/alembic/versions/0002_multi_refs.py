"""Multiple references and compare_ordered flag for tasks.

Revision ID: 0002_multi_refs
Revises: 0001_initial
Create Date: 2026-04-27 12:00:00
"""

from typing import Sequence, Union

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "0002_multi_refs"
down_revision: Union[str, None] = "0001_initial"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Добавляем массив альтернативных эталонных решений.
    op.add_column(
        "tasks",
        sa.Column(
            "reference_solutions",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
        ),
    )
    # Флаг: учитывать ли порядок при сравнении результатов.
    op.add_column(
        "tasks",
        sa.Column(
            "compare_ordered",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("true"),
        ),
    )


def downgrade() -> None:
    op.drop_column("tasks", "compare_ordered")
    op.drop_column("tasks", "reference_solutions")
