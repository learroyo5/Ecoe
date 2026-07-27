"""Add grading fields to student responses.

Revision ID: j0e1f2a3b4c5
Revises: i9d0e1f2a3b4
Create Date: 2026-07-15
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "j0e1f2a3b4c5"
down_revision: Union[str, Sequence[str], None] = "i9d0e1f2a3b4"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("student_responses", sa.Column("score_obtained", sa.Float(), nullable=True))
    op.add_column("student_responses", sa.Column("max_score", sa.Float(), nullable=True))
    op.add_column("student_responses", sa.Column("grading", sa.JSON(), nullable=True))
    op.add_column("student_responses", sa.Column("graded_by_email", sa.String(length=255), nullable=True))
    op.add_column("student_responses", sa.Column("graded_at", sa.DateTime(), nullable=True))


def downgrade() -> None:
    op.drop_column("student_responses", "graded_at")
    op.drop_column("student_responses", "graded_by_email")
    op.drop_column("student_responses", "grading")
    op.drop_column("student_responses", "max_score")
    op.drop_column("student_responses", "score_obtained")
