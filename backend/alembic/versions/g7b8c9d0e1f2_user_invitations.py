"""Add institutional member accounts and event-scoped invitations.

Revision ID: g7b8c9d0e1f2
Revises: f6a7b8c9d0e1
Create Date: 2026-07-13
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "g7b8c9d0e1f2"
down_revision: Union[str, Sequence[str], None] = "f6a7b8c9d0e1"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        """
        INSERT INTO roles (code, name)
        SELECT 'miembro', 'Miembro institucional'
        WHERE NOT EXISTS (SELECT 1 FROM roles WHERE code = 'miembro')
        """
    )
    op.add_column(
        "users",
        sa.Column("account_status", sa.String(length=32), nullable=False, server_default="active"),
    )
    op.execute("UPDATE users SET account_status = 'suspended' WHERE is_active = false")
    op.create_table(
        "user_invitations",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("ecoe_event_id", sa.Integer(), nullable=False),
        sa.Column("role_code", sa.String(length=64), nullable=False),
        sa.Column("token_hash", sa.String(length=64), nullable=False),
        sa.Column("invited_by_email", sa.String(length=255), nullable=False),
        sa.Column("expires_at", sa.DateTime(), nullable=False),
        sa.Column("accepted_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["ecoe_event_id"], ["ecoe_events.id"]),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("token_hash"),
    )
    op.create_index("ix_user_invitations_event", "user_invitations", ["ecoe_event_id"])
    op.create_index(
        "ix_user_invitations_user_status",
        "user_invitations",
        ["user_id", "accepted_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_user_invitations_user_status", table_name="user_invitations")
    op.drop_index("ix_user_invitations_event", table_name="user_invitations")
    op.drop_table("user_invitations")
    op.drop_column("users", "account_status")
    op.execute("DELETE FROM roles WHERE code = 'miembro'")
