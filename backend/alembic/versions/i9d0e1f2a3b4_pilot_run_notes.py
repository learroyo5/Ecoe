"""Add findings notes to pilot runs.

Revision ID: i9d0e1f2a3b4
Revises: h8c9d0e1f2a3
Create Date: 2026-07-15
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "i9d0e1f2a3b4"
down_revision: Union[str, Sequence[str], None] = "h8c9d0e1f2a3"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "pilot_runs",
        sa.Column("notes", sa.Text(), nullable=False, server_default=""),
    )


def downgrade() -> None:
    op.drop_column("pilot_runs", "notes")
