"""Event-scoped authorization: role sets, effective roles, and access checks.

Split out of utils/helpers.py to separate "who is allowed to do X" from
media handling and generic normalization/business helpers.
"""

import logging

from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.entities import ECOEPermission, ECOEEvent, StaffAssignment, Student, User
from app.models.enums import RoleCode
from app.utils.helpers import normalize_email

logger = logging.getLogger("ecoe.authz")

# ── Role sets ───────────────────────────────────────────────────────────

STAFF_SCOPED_ROLE_CODES = {
    RoleCode.coeditor_docente.value,
    RoleCode.coordinador_operativo.value,
    RoleCode.evaluador.value,
    RoleCode.cronometrador.value,
}
ADMIN_EVENT_ROLE_CODES = {
    RoleCode.admin_ecoe.value,
    RoleCode.coeditor_docente.value,
    RoleCode.coordinador_operativo.value,
}
ALLOWED_STAFF_ASSIGNMENT_ROLE_CODES = STAFF_SCOPED_ROLE_CODES


def validate_staff_role_code(role_code: str) -> str:
    normalized_role = str(role_code or "").strip().lower()
    if normalized_role not in ALLOWED_STAFF_ASSIGNMENT_ROLE_CODES:
        allowed = ", ".join(sorted(ALLOWED_STAFF_ASSIGNMENT_ROLE_CODES))
        raise HTTPException(status_code=400, detail=f"Rol '{role_code}' no es válido para asignar al equipo. Roles permitidos: {allowed}")
    return normalized_role


# ── Authorization helpers ───────────────────────────────────────────────

def get_user_event_roles(db: Session, user: User, ecoe_event_id: int) -> set[str]:
    """Effective roles of the user within one ECOE event.

    Roles are derived from the event-scoped grants (ECOEPermission,
    StaffAssignment, Student enrollment) without requiring them to match the
    user's global role: the same person can be evaluador in one ECOE and
    coeditor in another. The global role only acts as the account's default.
    """
    # A global administrator has institutional oversight over every event,
    # but is represented as admin_ecoe to keep event policies simple.
    roles: set[str] = (
        {RoleCode.admin_ecoe.value}
        if str(user.role.code) == RoleCode.admin_global.value
        else set()
    )
    normalized_email = normalize_email(user.email)

    permission_roles = db.scalars(
        select(ECOEPermission.role_code).where(
            ECOEPermission.ecoe_event_id == ecoe_event_id,
            ECOEPermission.user_id == user.id,
        )
    ).all()
    roles.update(str(code) for code in permission_roles)

    assignment_roles = db.scalars(
        select(StaffAssignment.role_code).where(
            StaffAssignment.ecoe_event_id == ecoe_event_id,
            StaffAssignment.email == normalized_email,
        )
    ).all()
    roles.update(str(code) for code in assignment_roles)

    student = db.scalar(
        select(Student).where(
            Student.ecoe_event_id == ecoe_event_id,
            func.lower(Student.email) == normalized_email,
            Student.is_active.is_(True),
        )
    )
    if student:
        roles.add(RoleCode.estudiante.value)

    return roles


def ensure_event_access(db: Session, user: User, ecoe_event_id: int, *allowed_roles: str) -> set[str]:
    ecoe_event = db.get(ECOEEvent, ecoe_event_id)
    if not ecoe_event:
        raise HTTPException(status_code=404, detail="ECOE no encontrado")

    event_roles = get_user_event_roles(db, user, ecoe_event_id)
    if not event_roles:
        logger.warning(
            "event_access_denied email=%s ecoe_event_id=%s reason=no_roles",
            user.email, ecoe_event_id,
        )
        raise HTTPException(
            status_code=403,
            detail="No tienes permisos para acceder a este ECOE",
        )
    if allowed_roles and not any(role in event_roles for role in allowed_roles):
        logger.warning(
            "event_access_denied email=%s ecoe_event_id=%s roles=%s required=%s",
            user.email, ecoe_event_id, sorted(event_roles), sorted(allowed_roles),
        )
        raise HTTPException(
            status_code=403,
            detail="No tienes permisos para esta acción en este ECOE",
        )
    return event_roles


def list_accessible_ecoe_events(db: Session, user: User) -> list[ECOEEvent]:
    """Events reachable through any event-scoped grant (see get_user_event_roles)."""
    if str(user.role.code) == RoleCode.admin_global.value:
        return list(
            db.scalars(
                select(ECOEEvent).order_by(ECOEEvent.date.desc(), ECOEEvent.id.desc())
            ).all()
        )
    normalized_email = normalize_email(user.email)

    event_ids: set[int] = set()
    event_ids.update(
        db.scalars(
            select(ECOEPermission.ecoe_event_id).where(ECOEPermission.user_id == user.id)
        ).all()
    )
    event_ids.update(
        db.scalars(
            select(StaffAssignment.ecoe_event_id).where(
                StaffAssignment.email == normalized_email
            )
        ).all()
    )
    event_ids.update(
        db.scalars(
            select(Student.ecoe_event_id).where(
                func.lower(Student.email) == normalized_email,
                Student.is_active.is_(True),
            )
        ).all()
    )

    if not event_ids:
        return []

    return list(
        db.scalars(
            select(ECOEEvent)
            .where(ECOEEvent.id.in_(event_ids))
            .order_by(ECOEEvent.date.desc(), ECOEEvent.id.desc())
        ).all()
    )


def ensure_matching_operational_user(
    db: Session,
    *,
    email: str,
    expected_role: str | None = None,
) -> User:
    normalized_email = normalize_email(email)
    user = db.scalar(
        select(User).where(func.lower(User.email) == normalized_email)
    )
    if not user:
        raise HTTPException(
            status_code=400,
            detail=f"No se encontró un usuario con el correo '{email}'. Debes crearlo primero en la sección Usuarios.",
        )
    if not user.is_active:
        raise HTTPException(
            status_code=400,
            detail=f"La cuenta de {user.full_name} ({email}) está inactiva. Reactívala en la sección Usuarios.",
        )
    return user


def ensure_staff_role_can_be_delegated(actor_event_roles: set[str], target_role: str) -> None:
    """Prevent operational/content roles from granting equal or higher power."""
    if RoleCode.admin_ecoe.value in actor_event_roles:
        return
    limited_roles = {RoleCode.evaluador.value, RoleCode.cronometrador.value}
    if actor_event_roles & {
        RoleCode.coeditor_docente.value,
        RoleCode.coordinador_operativo.value,
    } and target_role in limited_roles:
        return
    raise HTTPException(
        status_code=403,
        detail="No puedes asignar ese rol dentro de este ECOE",
    )


def ensure_staff_assignment_can_be_managed(actor_event_roles: set[str], current_role: str) -> None:
    """Only event admins may alter privileged staff assignments."""
    if RoleCode.admin_ecoe.value in actor_event_roles:
        return
    if current_role in {RoleCode.evaluador.value, RoleCode.cronometrador.value}:
        return
    raise HTTPException(
        status_code=403,
        detail="Solo un administrador del ECOE puede modificar esa asignación",
    )
