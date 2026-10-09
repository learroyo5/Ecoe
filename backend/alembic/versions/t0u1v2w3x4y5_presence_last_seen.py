"""Señal de vida de kioscos y evaluadores para el tablero de estaciones.

- ``station_kiosk_sessions.last_seen_at``: última consulta de contexto de la tablet.
- ``staff_assignments.last_seen_at``: última vez que la persona abrió su
  pantalla operativa en el evento.

Nullable, sin backfill.

Revision ID: t0u1v2w3x4y5
Revises: s9t0u1v2w3x4
Create Date: 2026-10-09
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "t0u1v2w3x4y5"
down_revision: Union[str, Sequence[str], None] = "s9t0u1v2w3x4"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("station_kiosk_sessions", sa.Column("last_seen_at", sa.DateTime(), nullable=True))
    op.add_column("staff_assignments", sa.Column("last_seen_at", sa.DateTime(), nullable=True))


def downgrade() -> None:
    op.drop_column("staff_assignments", "last_seen_at")
    op.drop_column("station_kiosk_sessions", "last_seen_at")
