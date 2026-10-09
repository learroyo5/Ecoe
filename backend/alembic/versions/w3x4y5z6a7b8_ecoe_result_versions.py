"""F0.3: las actas reemplazadas se archivan en vez de borrarse.

Tabla ``ecoe_result_versions``: una fila por acta que dejó de estar vigente al
reabrir un ECOE cerrado, con el snapshot completo en JSON.

Revision ID: w3x4y5z6a7b8
Revises: v2w3x4y5z6a7
Create Date: 2026-10-09
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "w3x4y5z6a7b8"
down_revision: Union[str, Sequence[str], None] = "v2w3x4y5z6a7"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "ecoe_result_versions",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("ecoe_event_id", sa.Integer(), sa.ForeignKey("ecoe_events.id"), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("consolidated_at", sa.DateTime(), nullable=True),
        sa.Column("superseded_by_email", sa.String(length=255), nullable=False, server_default=""),
        sa.Column("reason", sa.Text(), nullable=False, server_default=""),
        sa.Column("payload", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        sa.UniqueConstraint("ecoe_event_id", "version", name="uq_ecoe_result_version_event_version"),
    )


def downgrade() -> None:
    op.drop_table("ecoe_result_versions")
