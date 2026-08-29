"""Add deferred-grading capability to stations.

Revision ID: k1f2a3b4c5d6
Revises: j0e1f2a3b4c5
Create Date: 2026-08-28
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "k1f2a3b4c5d6"
down_revision: Union[str, Sequence[str], None] = "j0e1f2a3b4c5"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # server_default se mantiene (mismo patrón que pilot_runs.notes): las filas
    # existentes quedan en false y SQLite no soporta DROP DEFAULT.
    for table in ("stations", "station_bank"):
        op.add_column(
            table,
            sa.Column(
                "requires_deferred_grading",
                sa.Boolean(),
                nullable=False,
                server_default=sa.false(),
            ),
        )


def downgrade() -> None:
    op.drop_column("station_bank", "requires_deferred_grading")
    op.drop_column("stations", "requires_deferred_grading")
