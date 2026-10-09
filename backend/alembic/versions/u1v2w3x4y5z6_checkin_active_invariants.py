"""F0.1 (H03): un ingreso activo por estación y por estudiante.

Índices únicos parciales sobre ``station_checkins`` para ``status =
'confirmado'``. Antes de crearlos se cierran los ingresos activos sobrantes
(se conserva el más reciente de cada estación y de cada estudiante): son
residuo de rotaciones anteriores que el código ya trataba como cerrados.

Revision ID: u1v2w3x4y5z6
Revises: t0u1v2w3x4y5
Create Date: 2026-10-09
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "u1v2w3x4y5z6"
down_revision: Union[str, Sequence[str], None] = "t0u1v2w3x4y5"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    for partition in ("station_id", "ecoe_event_id, student_id"):
        op.execute(
            f"""
            UPDATE station_checkins SET status = 'cerrado'
            WHERE id IN (
                SELECT id FROM (
                    SELECT id, ROW_NUMBER() OVER (
                        PARTITION BY {partition}
                        ORDER BY confirmed_at DESC, id DESC
                    ) AS position
                    FROM station_checkins
                    WHERE status = 'confirmado'
                ) ranked
                WHERE position > 1
            )
            """
        )
    op.create_index(
        "uq_station_checkins_active_station", "station_checkins", ["station_id"],
        unique=True, postgresql_where=sa.text("status = 'confirmado'"),
        sqlite_where=sa.text("status = 'confirmado'"),
    )
    op.create_index(
        "uq_station_checkins_active_student", "station_checkins", ["ecoe_event_id", "student_id"],
        unique=True, postgresql_where=sa.text("status = 'confirmado'"),
        sqlite_where=sa.text("status = 'confirmado'"),
    )


def downgrade() -> None:
    op.drop_index("uq_station_checkins_active_student", table_name="station_checkins")
    op.drop_index("uq_station_checkins_active_station", table_name="station_checkins")
