"""Station response drafts + submission_kind on student responses (OPT-20 F2).

Revision ID: l2m3n4o5p6q7
Revises: 6d1ac67a3ab8
Create Date: 2026-08-29
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "l2m3n4o5p6q7"
down_revision: Union[str, Sequence[str], None] = "6d1ac67a3ab8"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "station_response_drafts",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "checkin_id",
            sa.Integer(),
            sa.ForeignKey("station_checkins.id"),
            nullable=False,
        ),
        sa.Column(
            "ecoe_event_id",
            sa.Integer(),
            sa.ForeignKey("ecoe_events.id"),
            nullable=False,
        ),
        sa.Column(
            "station_id", sa.Integer(), sa.ForeignKey("stations.id"), nullable=False
        ),
        sa.Column(
            "student_id", sa.Integer(), sa.ForeignKey("students.id"), nullable=False
        ),
        sa.Column("answers", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        sa.UniqueConstraint("checkin_id", name="uq_station_response_draft_checkin"),
    )
    op.create_index(
        "ix_station_response_drafts_event",
        "station_response_drafts",
        ["ecoe_event_id"],
    )

    # `submission_kind`: how the response entered — `manual` (student/kiosk
    # submit), `auto` (server-side sweep on phase expiry) or `contingency`
    # (out-of-window entry by coordination). server_default kept (SQLite has no
    # DROP DEFAULT). Existing contingency rows are backfilled to `contingency`.
    op.add_column(
        "student_responses",
        sa.Column(
            "submission_kind",
            sa.String(length=16),
            nullable=False,
            server_default="manual",
        ),
    )
    op.execute(
        "UPDATE student_responses SET submission_kind = 'contingency' "
        "WHERE by_contingency"
    )


def downgrade() -> None:
    op.drop_column("student_responses", "submission_kind")
    op.drop_index(
        "ix_station_response_drafts_event", table_name="station_response_drafts"
    )
    op.drop_table("station_response_drafts")
