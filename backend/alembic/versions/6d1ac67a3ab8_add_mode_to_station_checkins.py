"""add mode to station_checkins

Revision ID: 6d1ac67a3ab8
Revises: k1f2a3b4c5d6
Create Date: 2026-08-28

OPT-2 Parte 2: `station_checkins` no distinguía un check-in de pilotaje de
uno de ejecución real salvo por la fecha. La columna `mode` la estampa
`confirm_station_checkin` con el modo resuelto del evento, y alimenta
`activity_log` y los conteos de la trazabilidad de cierre.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "6d1ac67a3ab8"
down_revision: Union[str, Sequence[str], None] = "k1f2a3b4c5d6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # server_default="ejecucion": las filas existentes quedan como ejecución
    # (no hay datos de producción con pilotaje relevante). Se mantiene el
    # server_default tras el backfill — mismo patrón que la migración de
    # `requires_deferred_grading`; SQLite no soporta DROP DEFAULT.
    op.add_column(
        "station_checkins",
        sa.Column(
            "mode",
            sa.String(length=32),
            nullable=False,
            server_default="ejecucion",
        ),
    )


def downgrade() -> None:
    op.drop_column("station_checkins", "mode")
