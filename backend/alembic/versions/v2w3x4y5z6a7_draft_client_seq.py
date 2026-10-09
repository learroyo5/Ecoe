"""F0.2 (H05): orden de los borradores del estudiante.

``station_response_drafts.client_seq``: número creciente que envía el
dispositivo con cada autoguardado; el servidor descarta los que llegan con un
número menor o igual al ya guardado. Nullable: clientes antiguos sin el campo
siguen funcionando como antes (último en llegar gana).

Revision ID: v2w3x4y5z6a7
Revises: u1v2w3x4y5z6
Create Date: 2026-10-09
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "v2w3x4y5z6a7"
down_revision: Union[str, Sequence[str], None] = "u1v2w3x4y5z6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "station_response_drafts", sa.Column("client_seq", sa.BigInteger(), nullable=True)
    )


def downgrade() -> None:
    op.drop_column("station_response_drafts", "client_seq")
