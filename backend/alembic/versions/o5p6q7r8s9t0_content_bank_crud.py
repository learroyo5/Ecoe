"""Content bank CRUD (station_templates + simulated_patients): ownership + soft-delete + FK ondelete.

OPT-7b (follow-up de OPT-7). Replica el patrón de ``n4o5p6q7r8s9`` para
``assessment_tools`` sobre los otros dos bancos institucionales que eran de
solo-creación:

- agrega ``created_by`` / ``origin_event_id`` / ``archived`` a ambas tablas;
- da un ``ondelete`` explícito a las cuatro FK que las referencian, para que el
  soft-delete no sea la única opción segura y un hard-delete falle limpio:

  - ``stations.template_id``               -> SET NULL
  - ``stations.simulated_patient_id``      -> SET NULL
  - ``station_bank.template_id``           -> SET NULL
  - ``station_bank.simulated_patient_id``  -> SET NULL

A diferencia de OPT-7 no hay gate de editabilidad: el contenido de estos dos
bancos no se lee en runtime (verificado en el hallazgo §6).

Revision ID: o5p6q7r8s9t0
Revises: n4o5p6q7r8s9
Create Date: 2026-08-29
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "o5p6q7r8s9t0"
down_revision: Union[str, Sequence[str], None] = "n4o5p6q7r8s9"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


_TABLES = ("station_templates", "simulated_patients")

# Nombres reales de las FK autogeneradas por PostgreSQL en el baseline
# (verificados contra information_schema; en SQLite las FK del baseline son
# anónimas y no se recrean por nombre). Formato: (tabla, constraint, columna,
# tabla_referida).
_PG_REF_FKS = (
    ("stations", "stations_template_id_fkey", "template_id", "station_templates"),
    ("stations", "stations_simulated_patient_id_fkey", "simulated_patient_id", "simulated_patients"),
    ("station_bank", "station_bank_template_id_fkey", "template_id", "station_templates"),
    ("station_bank", "station_bank_simulated_patient_id_fkey", "simulated_patient_id", "simulated_patients"),
)

# FK nueva de origin_event_id -> ecoe_events (una por tabla del banco).
_ORIGIN_FKS = tuple(
    (table, f"fk_{table}_origin_event_id_ecoe_events") for table in _TABLES
)


def upgrade() -> None:
    dialect = op.get_bind().dialect.name

    # 1. Columnas nuevas en ambas tablas. `server_default` se conserva (mismo
    #    patrón que k1f2a3b4c5d6 / n4o5p6q7r8s9): las filas existentes quedan en
    #    NULL / false y SQLite no soporta DROP DEFAULT.
    for table in _TABLES:
        op.add_column(table, sa.Column("created_by", sa.String(length=255), nullable=True))
        op.add_column(table, sa.Column("origin_event_id", sa.Integer(), nullable=True))
        op.add_column(
            table,
            sa.Column("archived", sa.Boolean(), nullable=False, server_default=sa.false()),
        )
        op.create_index(f"ix_{table}_archived", table, ["archived"])

    if dialect == "sqlite":
        # En SQLite el ALTER de FK exige recrear la tabla por copia. Esta app no
        # valida FKs en SQLite (los tests recrean el schema con create_all desde
        # los modelos, que ya llevan el ondelete). Solo se agregan, vía
        # batch_alter_table, las dos FK nuevas de `origin_event_id`.
        for table, name in _ORIGIN_FKS:
            with op.batch_alter_table(table, schema=None) as batch_op:
                batch_op.create_foreign_key(
                    name, "ecoe_events", ["origin_event_id"], ["id"], ondelete="SET NULL"
                )
        return

    # 2. PostgreSQL (CI/prod): FK nuevas + recrear las cuatro FK de referencia
    #    con ondelete SET NULL.
    for table, name in _ORIGIN_FKS:
        op.create_foreign_key(
            name, table, "ecoe_events", ["origin_event_id"], ["id"], ondelete="SET NULL"
        )
    for table, name, column, referred in _PG_REF_FKS:
        op.drop_constraint(name, table, type_="foreignkey")
        op.create_foreign_key(
            name, table, referred, [column], ["id"], ondelete="SET NULL"
        )


def downgrade() -> None:
    dialect = op.get_bind().dialect.name

    if dialect != "sqlite":
        # Revertir las cuatro FK a su forma sin ondelete y quitar las FK nuevas.
        for table, name, column, referred in _PG_REF_FKS:
            op.drop_constraint(name, table, type_="foreignkey")
            op.create_foreign_key(name, table, referred, [column], ["id"])
        for table, name in _ORIGIN_FKS:
            op.drop_constraint(name, table, type_="foreignkey")

    for table in _TABLES:
        op.drop_index(f"ix_{table}_archived", table_name=table)
        # batch_alter_table: en SQLite reconstruye la tabla sin las columnas (y
        # sin la FK de origin_event_id); en PostgreSQL emite ALTER TABLE DROP.
        with op.batch_alter_table(table, schema=None) as batch_op:
            batch_op.drop_column("archived")
            batch_op.drop_column("origin_event_id")
            batch_op.drop_column("created_by")
