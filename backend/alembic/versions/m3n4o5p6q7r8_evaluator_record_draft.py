"""Evaluator record draft flag + submission_kind (OPT-20 F3).

Revision ID: m3n4o5p6q7r8
Revises: l2m3n4o5p6q7
Create Date: 2026-08-29
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "m3n4o5p6q7r8"
down_revision: Union[str, Sequence[str], None] = "l2m3n4o5p6q7"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # `is_draft`: an EvaluatorRecord persisted while still half-filled (server
    # side, when the phase expires with no final submit — D3). The unique
    # constraint (event, station, student, mode) means the draft *is* the row;
    # it is promoted to `is_draft=False` on final submit or via contingency.
    # Existing rows are all final. server_default kept (SQLite has no DROP
    # DEFAULT), same pattern as `stations.requires_deferred_grading`.
    op.add_column(
        "evaluator_records",
        sa.Column(
            "is_draft",
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
        ),
    )
    # `submission_kind`: how the record entered — `manual` (evaluator submit),
    # `contingency` (finalized out-of-window by coordination). F4 will extend
    # the vocabulary; the sweep (F2/F3) and the contingency finalization of a
    # draft already need it, same criterion as `student_responses.submission_kind`.
    op.add_column(
        "evaluator_records",
        sa.Column(
            "submission_kind",
            sa.String(length=16),
            nullable=False,
            server_default="manual",
        ),
    )
    op.execute(
        "UPDATE evaluator_records SET submission_kind = 'contingency' "
        "WHERE by_contingency"
    )


def downgrade() -> None:
    op.drop_column("evaluator_records", "submission_kind")
    op.drop_column("evaluator_records", "is_draft")
