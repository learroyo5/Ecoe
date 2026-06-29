"""add_incident_resolved_fields

Revision ID: 95dccafb1304
Revises: 7a4c202a07ed
Create Date: 2026-06-03 16:02:02.959308

"""
from typing import Sequence, Union

# revision identifiers, used by Alembic.
revision: str = '95dccafb1304'
down_revision: Union[str, Sequence[str], None] = '7a4c202a07ed'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Columns are included in the corrected baseline migration."""
    pass


def downgrade() -> None:
    """No-op to preserve the historical revision chain."""
    pass
