"""Circuitos espejo: una estación puede ser espejo de otra.

``stations.mirror_of_id`` apunta a la estación original (mismo evento, otro
circuito). Nullable: las estaciones existentes quedan como originales.

Revision ID: x4y5z6a7b8c9
Revises: w3x4y5z6a7b8
Create Date: 2026-10-09
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "x4y5z6a7b8c9"
down_revision: Union[str, Sequence[str], None] = "w3x4y5z6a7b8"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("stations", sa.Column("mirror_of_id", sa.Integer(), nullable=True))
    op.create_foreign_key(
        "fk_stations_mirror_of", "stations", "stations", ["mirror_of_id"], ["id"],
        ondelete="CASCADE",
    )
    op.create_index("ix_stations_mirror_of_id", "stations", ["mirror_of_id"])


def downgrade() -> None:
    op.drop_index("ix_stations_mirror_of_id", table_name="stations")
    op.drop_constraint("fk_stations_mirror_of", "stations", type_="foreignkey")
    op.drop_column("stations", "mirror_of_id")
