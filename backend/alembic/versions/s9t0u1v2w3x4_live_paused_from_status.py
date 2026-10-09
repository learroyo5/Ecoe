"""PROC-24: la pausa recuerda qué fase interrumpió.

``live_sessions.paused_from_status`` guarda la fase (``running`` /
``transition`` / ``round_pause``) que corría al pausar. Sin ella, reanudar
tras pausar en una transición la convertía en fase de estación: el circuito
automático daba por rendida una estación que no había empezado.

Nullable, sin backfill: una sesión pausada antes de esta migración reanuda a
``running`` como hasta ahora.

Revision ID: s9t0u1v2w3x4
Revises: r8s9t0u1v2w3
Create Date: 2026-10-09
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "s9t0u1v2w3x4"
down_revision: Union[str, Sequence[str], None] = "r8s9t0u1v2w3"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "live_sessions", sa.Column("paused_from_status", sa.String(length=32), nullable=True)
    )


def downgrade() -> None:
    op.drop_column("live_sessions", "paused_from_status")
