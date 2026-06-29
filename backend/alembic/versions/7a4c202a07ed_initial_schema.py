"""initial_schema

Revision ID: 7a4c202a07ed
Revises: 
Create Date: 2026-06-02 16:48:56.756167

"""
from typing import Sequence, Union

from alembic import op

from app.db.session import Base
from app.models import entities  # noqa: F401


# revision identifiers, used by Alembic.
revision: str = '7a4c202a07ed'
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create the complete application schema from a clean database."""
    Base.metadata.create_all(bind=op.get_bind())


def downgrade() -> None:
    """Drop the complete application schema."""
    bind = op.get_bind()
    for table in reversed(Base.metadata.sorted_tables):
        table.drop(bind=bind, checkfirst=True)
