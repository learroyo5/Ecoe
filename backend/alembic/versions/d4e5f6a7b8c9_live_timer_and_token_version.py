"""Live timer server authority + JWT revocation support

- live_sessions.phase_started_at: timestamp of the current running phase,
  so remaining time is computed server-side instead of trusted to clients.
- users.token_version: bumped on deactivation/password change to invalidate
  previously issued JWTs.

Revision ID: d4e5f6a7b8c9
Revises: c7d8e9f00123
Create Date: 2026-07-08
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'd4e5f6a7b8c9'
down_revision: Union[str, Sequence[str], None] = 'c7d8e9f00123'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('live_sessions', sa.Column('phase_started_at', sa.DateTime(), nullable=True))
    op.add_column(
        'users',
        sa.Column('token_version', sa.Integer(), nullable=False, server_default='0'),
    )


def downgrade() -> None:
    op.drop_column('users', 'token_version')
    op.drop_column('live_sessions', 'phase_started_at')
