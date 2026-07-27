"""Persistent auth rate limits

Revision ID: e5f6a7b8c9d0
Revises: d4e5f6a7b8c9
Create Date: 2026-07-08
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'e5f6a7b8c9d0'
down_revision: Union[str, Sequence[str], None] = 'd4e5f6a7b8c9'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'auth_rate_limits',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('bucket_key', sa.String(length=320), nullable=False),
        sa.Column('attempts', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('window_start', sa.DateTime(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('bucket_key'),
    )
    op.create_index(
        'ix_auth_rate_limits_window',
        'auth_rate_limits',
        ['window_start'],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index('ix_auth_rate_limits_window', table_name='auth_rate_limits')
    op.drop_table('auth_rate_limits')
