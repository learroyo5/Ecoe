"""Add an institutional global administrator role.

Revision ID: f6a7b8c9d0e1
Revises: e5f6a7b8c9d0
Create Date: 2026-07-13
"""
from typing import Sequence, Union

from alembic import op


revision: str = "f6a7b8c9d0e1"
down_revision: Union[str, Sequence[str], None] = "e5f6a7b8c9d0"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Preserve the authority of accounts that were global administrators
    # before event-scoped and institutional administration were separated.
    op.execute(
        """
        INSERT INTO roles (code, name)
        SELECT 'admin_global', 'Administrador global'
        WHERE NOT EXISTS (SELECT 1 FROM roles WHERE code = 'admin_global')
        """
    )
    op.execute(
        """
        UPDATE users
        SET role_id = (SELECT id FROM roles WHERE code = 'admin_global')
        WHERE role_id = (SELECT id FROM roles WHERE code = 'admin_ecoe')
        """
    )


def downgrade() -> None:
    op.execute(
        """
        UPDATE users
        SET role_id = (SELECT id FROM roles WHERE code = 'admin_ecoe')
        WHERE role_id = (SELECT id FROM roles WHERE code = 'admin_global')
        """
    )
    op.execute("DELETE FROM roles WHERE code = 'admin_global'")
