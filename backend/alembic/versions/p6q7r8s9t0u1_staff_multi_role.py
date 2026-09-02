"""Staff assignments: permitir varios roles por persona en un mismo evento.

B5 (retro del simulacro integral). El candado pasa de ``(ecoe_event_id, email)``
a ``(ecoe_event_id, email, role_code)``: una misma persona puede ser, por
ejemplo, evaluador en vivo y corrector de la evaluación diferida después.
``get_user_event_roles`` ya junta todos los ``role_code`` de la persona, así
que la capa de autorización no cambia.

No hay filas duplicadas que migrar: la constraint vieja las impedía.

Revision ID: p6q7r8s9t0u1
Revises: o5p6q7r8s9t0
Create Date: 2026-09-02
"""
from typing import Sequence, Union

from alembic import op

revision: str = "p6q7r8s9t0u1"
down_revision: Union[str, Sequence[str], None] = "o5p6q7r8s9t0"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_OLD = "uq_staff_event_email"
_NEW = "uq_staff_event_email_role"


def upgrade() -> None:
    with op.batch_alter_table("staff_assignments") as batch:
        batch.drop_constraint(_OLD, type_="unique")
        batch.create_unique_constraint(
            _NEW, ["ecoe_event_id", "email", "role_code"]
        )


def downgrade() -> None:
    # El downgrade solo es seguro si no hay más de un rol por persona/evento.
    with op.batch_alter_table("staff_assignments") as batch:
        batch.drop_constraint(_NEW, type_="unique")
        batch.create_unique_constraint(_OLD, ["ecoe_event_id", "email"])
