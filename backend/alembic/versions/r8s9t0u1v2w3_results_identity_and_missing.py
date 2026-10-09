"""PROC-6 / PROC-8: el acta congela identidad, cobertura y estaciones faltantes.

- ``ecoe_results.student_name`` / ``student_rut`` / ``ecoe_number``: identidad
  del estudiante tal como estaba al consolidar (antes sólo ``student_id``, así
  que renumerar o renombrar tras el cierre cambiaba lo que mostraba el acta).
- ``ecoe_results.stations_counted`` / ``stations_expected``: cobertura.
- ``station_results.is_missing``: estación esperada sin registro que entró con
  0 por cierre forzado.

Todo nullable o con ``server_default`` — sin backfill. Los snapshots previos
quedan con identidad nula y se siguen leyendo desde ``students``.

Revision ID: r8s9t0u1v2w3
Revises: q7r8s9t0u1v2
Create Date: 2026-10-09
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "r8s9t0u1v2w3"
down_revision: Union[str, Sequence[str], None] = "q7r8s9t0u1v2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("ecoe_results", sa.Column("student_name", sa.String(length=255), nullable=True))
    op.add_column("ecoe_results", sa.Column("student_rut", sa.String(length=32), nullable=True))
    op.add_column("ecoe_results", sa.Column("ecoe_number", sa.String(length=32), nullable=True))
    op.add_column("ecoe_results", sa.Column("stations_counted", sa.Integer(), nullable=True))
    op.add_column("ecoe_results", sa.Column("stations_expected", sa.Integer(), nullable=True))
    op.add_column(
        "station_results",
        sa.Column("is_missing", sa.Boolean(), nullable=False, server_default=sa.false()),
    )


def downgrade() -> None:
    op.drop_column("station_results", "is_missing")
    op.drop_column("ecoe_results", "stations_expected")
    op.drop_column("ecoe_results", "stations_counted")
    op.drop_column("ecoe_results", "ecoe_number")
    op.drop_column("ecoe_results", "student_rut")
    op.drop_column("ecoe_results", "student_name")
