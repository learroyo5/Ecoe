"""M1 F1: ciclo automático del circuito.

Agrega el estado que necesita la máquina de fases explícita
(``services/live_cycle.py``):

- ``ecoe_events.inter_round_pause_minutes`` — pausa de cambio de estudiantes
  entre rondas del circuito. Única para todo el ciclo, se fija al crear el ECOE.
- ``live_sessions.auto_mode`` — el operador lo activa antes de arrancar.
- ``live_sessions.current_round`` / ``total_rounds`` — ronda en curso y total
  (⌈estudiantes_activos / nº estaciones⌉, congelado al arrancar).
- ``live_sessions.inter_round_pause_seconds`` — copiado de
  ``inter_round_pause_minutes`` al arrancar (mismo patrón que
  ``station_time_seconds`` / ``transition_time_seconds``).

Columnas con ``server_default`` — sin backfill manual.

Revision ID: q7r8s9t0u1v2
Revises: p6q7r8s9t0u1
Create Date: 2026-09-03
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "q7r8s9t0u1v2"
down_revision: Union[str, Sequence[str], None] = "p6q7r8s9t0u1"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "ecoe_events",
        sa.Column(
            "inter_round_pause_minutes",
            sa.Float(),
            nullable=False,
            server_default="5",
        ),
    )
    op.add_column(
        "live_sessions",
        sa.Column(
            "auto_mode",
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
        ),
    )
    op.add_column(
        "live_sessions",
        sa.Column(
            "current_round",
            sa.Integer(),
            nullable=False,
            server_default="1",
        ),
    )
    op.add_column(
        "live_sessions",
        sa.Column("total_rounds", sa.Integer(), nullable=True),
    )
    op.add_column(
        "live_sessions",
        sa.Column(
            "inter_round_pause_seconds",
            sa.Integer(),
            nullable=False,
            server_default="300",
        ),
    )


def downgrade() -> None:
    op.drop_column("live_sessions", "inter_round_pause_seconds")
    op.drop_column("live_sessions", "total_rounds")
    op.drop_column("live_sessions", "current_round")
    op.drop_column("live_sessions", "auto_mode")
    op.drop_column("ecoe_events", "inter_round_pause_minutes")
