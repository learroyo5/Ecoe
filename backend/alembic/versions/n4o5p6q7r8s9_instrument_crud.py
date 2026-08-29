"""Instrument (AssessmentTool) CRUD: ownership + soft-delete + FK ondelete.

OPT-7. Adds `created_by`, `origin_event_id`, `archived` to `assessment_tools`
and gives the three assessment-tool foreign keys an explicit `ondelete` so the
soft-delete is not the only safe option and a hard-delete fails cleanly:

- ``stations.assessment_tool_id``       -> SET NULL
- ``station_bank.assessment_tool_id``   -> SET NULL
- ``assessment_items.tool_id``          -> CASCADE (the ORM already cascades;
                                           this aligns the database)

Revision ID: n4o5p6q7r8s9
Revises: m3n4o5p6q7r8
Create Date: 2026-08-29
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "n4o5p6q7r8s9"
down_revision: Union[str, Sequence[str], None] = "m3n4o5p6q7r8"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


# Nombres reales de las FK autogeneradas en el baseline sobre PostgreSQL
# (información obtenida de information_schema; en SQLite las FK del baseline son
# anónimas y no se pueden recrear por nombre).
_PG_FKS = (
    ("stations", "stations_assessment_tool_id_fkey", "assessment_tool_id", "SET NULL"),
    ("station_bank", "station_bank_assessment_tool_id_fkey", "assessment_tool_id", "SET NULL"),
    ("assessment_items", "assessment_items_tool_id_fkey", "tool_id", "CASCADE"),
)
_ORIGIN_FK = "fk_assessment_tools_origin_event_id_ecoe_events"


def upgrade() -> None:
    dialect = op.get_bind().dialect.name

    # 1. Columnas nuevas. `server_default` se conserva (mismo patrón que
    #    k1f2a3b4c5d6 / pilot_runs.archived): las filas existentes quedan en
    #    NULL / false y SQLite no soporta DROP DEFAULT.
    op.add_column(
        "assessment_tools",
        sa.Column("created_by", sa.String(length=255), nullable=True),
    )
    op.add_column(
        "assessment_tools",
        sa.Column("origin_event_id", sa.Integer(), nullable=True),
    )
    op.add_column(
        "assessment_tools",
        sa.Column(
            "archived", sa.Boolean(), nullable=False, server_default=sa.false()
        ),
    )
    op.create_index(
        "ix_assessment_tools_archived", "assessment_tools", ["archived"]
    )

    if dialect == "sqlite":
        # En SQLite el ALTER de FK exige recrear la tabla por copia. Esta app no
        # valida FKs en SQLite (los tests recrean el schema con create_all desde
        # los modelos, que ya llevan el ondelete). Solo se agrega, vía
        # batch_alter_table, la FK nueva de `origin_event_id`.
        with op.batch_alter_table("assessment_tools", schema=None) as batch_op:
            batch_op.create_foreign_key(
                _ORIGIN_FK, "ecoe_events", ["origin_event_id"], ["id"],
                ondelete="SET NULL",
            )
        return

    # 2. PostgreSQL (lo que corre CI y prod): FK nueva + recrear las tres FK de
    #    assessment_tool con ondelete.
    op.create_foreign_key(
        _ORIGIN_FK, "assessment_tools", "ecoe_events",
        ["origin_event_id"], ["id"], ondelete="SET NULL",
    )
    for table, name, column, ondelete in _PG_FKS:
        op.drop_constraint(name, table, type_="foreignkey")
        op.create_foreign_key(
            name, table, "assessment_tools", [column], ["id"], ondelete=ondelete
        )


def downgrade() -> None:
    dialect = op.get_bind().dialect.name

    if dialect != "sqlite":
        # Revertir las tres FK a su forma sin ondelete y quitar la FK nueva.
        for table, name, column, _ondelete in _PG_FKS:
            op.drop_constraint(name, table, type_="foreignkey")
            op.create_foreign_key(
                name, table, "assessment_tools", [column], ["id"]
            )
        op.drop_constraint(_ORIGIN_FK, "assessment_tools", type_="foreignkey")

    op.drop_index("ix_assessment_tools_archived", table_name="assessment_tools")
    # batch_alter_table: en SQLite reconstruye la tabla sin las columnas (y sin
    # la FK de origin_event_id); en PostgreSQL emite ALTER TABLE DROP COLUMN.
    with op.batch_alter_table("assessment_tools", schema=None) as batch_op:
        batch_op.drop_column("archived")
        batch_op.drop_column("origin_event_id")
        batch_op.drop_column("created_by")
