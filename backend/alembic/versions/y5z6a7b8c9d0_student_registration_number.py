"""Matrícula del estudiante.

``students.registration_number`` guarda el número de registro/matrícula que
trae el listado oficial de curso de la universidad. Nullable: los estudiantes
existentes y los cargados con la plantilla propia quedan sin él.

Revision ID: y5z6a7b8c9d0
Revises: x4y5z6a7b8c9
Create Date: 2026-10-12
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "y5z6a7b8c9d0"
down_revision: Union[str, Sequence[str], None] = "x4y5z6a7b8c9"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("students", sa.Column("registration_number", sa.String(length=32), nullable=True))


def downgrade() -> None:
    op.drop_column("students", "registration_number")
