"""Event-scoped member assignment and one-time account invitations."""

import hashlib
import secrets
from datetime import timedelta

from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.security import get_password_hash
from app.models.entities import (
    AuditLog,
    Role,
    StaffAssignment,
    Station,
    User,
    UserInvitation,
)
from app.models.enums import RoleCode
from app.schemas.common import EventMemberInvite
from app.services.authorization import validate_staff_role_code
from app.utils.clock import utcnow_naive
from app.utils.helpers import (
    MULTI_STATION_ROLE_CODES,
    normalize_email,
    normalize_station_ids,
)


def hash_invitation_token(token: str) -> str:
    """Hash a high-entropy lookup token; raw invitation tokens are never stored."""
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def split_full_name(full_name: str) -> tuple[str, str]:
    """Split on the last space so name + last_name always rebuilds full_name exactly."""
    parts = (full_name or "").strip().rsplit(" ", 1)
    if len(parts) == 2:
        return parts[0], parts[1]
    return parts[0], ""


def _validated_assignment(
    db: Session,
    payload: EventMemberInvite,
    *,
    require_evaluator_station: bool = True,
) -> tuple[str, list[int]]:
    role_code = validate_staff_role_code(payload.role_code)
    single = role_code not in MULTI_STATION_ROLE_CODES
    station_ids = normalize_station_ids(payload.station_ids, single=single)
    if (
        require_evaluator_station
        and role_code in {RoleCode.evaluador.value, RoleCode.corrector.value}
        and not station_ids
    ):
        detail = (
            "El corrector debe tener al menos una estación de evaluación diferida asignada"
            if role_code == RoleCode.corrector.value
            else "El evaluador debe tener una estación principal asignada"
        )
        raise HTTPException(status_code=400, detail=detail)
    if station_ids:
        found = db.scalars(
            select(Station).where(
                Station.id.in_(station_ids),
                Station.ecoe_event_id == payload.ecoe_event_id,
            )
        ).all()
        if len(found) != len(station_ids):
            raise HTTPException(status_code=400, detail="La estación no pertenece al ECOE indicado")
    return role_code, station_ids


def lookup_member_by_exact_email(db: Session, ecoe_event_id: int, email: str) -> dict:
    normalized_email = normalize_email(email)
    account = db.scalar(select(User).where(func.lower(User.email) == normalized_email))
    if not account:
        return {"exists": False, "assigned_to_event": False}
    assignment = db.scalar(
        select(StaffAssignment.id).where(
            StaffAssignment.ecoe_event_id == ecoe_event_id,
            StaffAssignment.email == normalized_email,
        )
    )
    return {
        "exists": True,
        "full_name": account.full_name,
        "account_status": account.account_status,
        "assigned_to_event": assignment is not None,
    }


def assign_or_invite_member(
    db: Session,
    payload: EventMemberInvite,
    *,
    invited_by_email: str,
    may_create_accounts: bool = True,
    require_evaluator_station: bool = True,
) -> dict:
    """Assign an existing institutional identity, or invite a new one.

    Does not commit: callers own the transaction so bulk imports stay atomic.
    """
    role_code, station_ids = _validated_assignment(
        db, payload, require_evaluator_station=require_evaluator_station
    )
    email = normalize_email(payload.email)
    account = db.scalar(select(User).where(func.lower(User.email) == email))
    created_account = False

    if account and account.account_status == "suspended":
        raise HTTPException(
            status_code=400,
            detail="La cuenta está suspendida institucionalmente; contacta al administrador global",
        )

    if not account:
        if not payload.name.strip() or not payload.last_name.strip():
            raise HTTPException(
                status_code=400,
                detail="No existe una cuenta con ese correo: indica nombre y apellidos para crearla",
            )
        if not may_create_accounts:
            raise HTTPException(
                status_code=403,
                detail="No existe una cuenta institucional con ese correo y este rol no puede crearla",
            )
        member_role = db.scalar(select(Role).where(Role.code == RoleCode.miembro.value))
        if not member_role:
            raise HTTPException(status_code=500, detail="Rol institucional base no configurado")
        # The placeholder is random and never disclosed. Authentication is
        # additionally blocked while the account remains pending.
        account = User(
            email=email,
            full_name=f"{payload.name.strip()} {payload.last_name.strip()}".strip(),
            hashed_password=get_password_hash(secrets.token_urlsafe(48)),
            role_id=member_role.id,
            is_active=False,
            account_status="pending",
        )
        db.add(account)
        db.flush()
        created_account = True

    # The institutional account owns the person's name: a typo in this form must
    # never create a second, divergent identity for the same email.
    if created_account:
        member_name, member_last_name = payload.name.strip(), payload.last_name.strip()
    else:
        member_name, member_last_name = split_full_name(account.full_name)

    # Una persona puede tener varios roles en el mismo evento (p. ej. evaluador
    # en vivo y corrector después): el candado es (evento, email, rol), no
    # (evento, email). Solo se rechaza volver a agregar el MISMO rol.
    assignment = db.scalar(
        select(StaffAssignment).where(
            StaffAssignment.ecoe_event_id == payload.ecoe_event_id,
            StaffAssignment.email == email,
            StaffAssignment.role_code == role_code,
        )
    )
    if assignment and account.account_status == "active":
        raise HTTPException(
            status_code=400,
            detail=f"La persona ya tiene el rol «{role_code}» en este ECOE",
        )
    if not assignment:
        assignment = StaffAssignment(
            ecoe_event_id=payload.ecoe_event_id,
            name=member_name,
            last_name=member_last_name,
            email=email,
            role_code=role_code,
            station_ids=station_ids,
        )
        db.add(assignment)
    else:
        assignment.name = member_name
        assignment.last_name = member_last_name
        assignment.station_ids = station_ids
        db.add(assignment)

    if account.account_status == "active":
        db.flush()
        db.add(AuditLog(
            user_email=invited_by_email,
            action="assign_existing_event_member",
            target_type="StaffAssignment",
            target_id=str(assignment.id),
            payload={
                "ecoe_event_id": payload.ecoe_event_id,
                "user_id": account.id,
                "role_code": role_code,
            },
        ))
        return {
            "status": "assigned",
            "account_created": False,
            "assignment_id": assignment.id,
            "email": email,
        }

    now = utcnow_naive()
    for previous in db.scalars(
        select(UserInvitation).where(
            UserInvitation.user_id == account.id,
            UserInvitation.ecoe_event_id == payload.ecoe_event_id,
            UserInvitation.accepted_at.is_(None),
        )
    ).all():
        previous.accepted_at = now
        db.add(previous)

    raw_token = secrets.token_urlsafe(32)
    invitation = UserInvitation(
        user_id=account.id,
        ecoe_event_id=payload.ecoe_event_id,
        role_code=role_code,
        token_hash=hash_invitation_token(raw_token),
        invited_by_email=invited_by_email,
        expires_at=now + timedelta(hours=get_settings().invitation_expire_hours),
    )
    db.add(invitation)
    db.flush()
    db.add(AuditLog(
        user_email=invited_by_email,
        action="invite_event_member",
        target_type="UserInvitation",
        target_id=str(invitation.id),
        payload={
            "ecoe_event_id": payload.ecoe_event_id,
            "user_id": account.id,
            "role_code": role_code,
            "account_created": created_account,
        },
    ))
    return {
        "status": "invited",
        "account_created": created_account,
        "assignment_id": assignment.id,
        "email": email,
        "role_code": role_code,
        "activation_token": raw_token,
        "activation_path": f"/activate?token={raw_token}",
        "expires_at": invitation.expires_at.isoformat(),
    }


def reset_active_member_access(
    db: Session, ecoe_event_id: int, email: str, invited_by_email: str
) -> dict:
    """Issue a fresh access-reset link for a member already active in this event.

    Scoped to admin_ecoe/coeditor_docente of the event itself (checked by the
    caller via ensure_event_access): an event admin can restore their own
    team's access without escalating to admin_global, who already has an
    institution-wide equivalent via Usuarios. Does not commit: caller owns
    the transaction.
    """
    normalized_email = normalize_email(email)
    assignment = db.scalar(
        select(StaffAssignment).where(
            StaffAssignment.ecoe_event_id == ecoe_event_id,
            StaffAssignment.email == normalized_email,
        )
    )
    if not assignment:
        raise HTTPException(status_code=404, detail="Esta persona no está asignada a este ECOE")
    account = db.scalar(select(User).where(func.lower(User.email) == normalized_email))
    if not account or account.account_status != "active":
        raise HTTPException(
            status_code=400,
            detail="Esta cuenta no está activa: usa la invitación normal en vez de un reinicio de acceso",
        )

    now = utcnow_naive()
    for previous in db.scalars(
        select(UserInvitation).where(
            UserInvitation.user_id == account.id,
            UserInvitation.ecoe_event_id == ecoe_event_id,
            UserInvitation.accepted_at.is_(None),
        )
    ).all():
        previous.accepted_at = now
        db.add(previous)

    raw_token = secrets.token_urlsafe(32)
    invitation = UserInvitation(
        user_id=account.id,
        ecoe_event_id=ecoe_event_id,
        role_code=assignment.role_code,
        token_hash=hash_invitation_token(raw_token),
        invited_by_email=invited_by_email,
        expires_at=now + timedelta(hours=get_settings().invitation_expire_hours),
    )
    db.add(invitation)
    db.flush()
    db.add(AuditLog(
        user_email=invited_by_email,
        action="reset_event_member_access",
        target_type="UserInvitation",
        target_id=str(invitation.id),
        payload={"ecoe_event_id": ecoe_event_id, "user_id": account.id, "email": normalized_email},
    ))
    return {
        "status": "reset",
        "email": normalized_email,
        "role_code": assignment.role_code,
        "activation_token": raw_token,
        "activation_path": f"/activate?token={raw_token}",
        "expires_at": invitation.expires_at.isoformat(),
    }


def activate_invitation(db: Session, token: str, password: str) -> None:
    invitation = db.scalar(
        select(UserInvitation)
        .where(UserInvitation.token_hash == hash_invitation_token(token))
        .with_for_update()
    )
    now = utcnow_naive()
    if not invitation or invitation.accepted_at is not None or invitation.expires_at <= now:
        raise HTTPException(status_code=400, detail="La invitación no es válida o ya expiró")
    account = db.get(User, invitation.user_id)
    # "pending" = primera activacion; "active" = reinicio de acceso de una
    # cuenta ya activa (reset_active_member_access). Cualquier otro estado
    # (p.ej. "suspended") no debe poder tomar un token viejo para reactivarse.
    if not account or account.account_status not in {"pending", "active"}:
        raise HTTPException(status_code=400, detail="La invitación no es válida o ya fue utilizada")

    account.hashed_password = get_password_hash(password)
    account.is_active = True
    account.account_status = "active"
    account.token_version = (account.token_version or 0) + 1
    db.add(account)
    for pending in db.scalars(
        select(UserInvitation).where(
            UserInvitation.user_id == account.id,
            UserInvitation.accepted_at.is_(None),
        )
    ).all():
        pending.accepted_at = now
        db.add(pending)
    db.add(AuditLog(
        user_email=account.email,
        action="activate_invited_account",
        target_type="User",
        target_id=str(account.id),
        payload={"invitation_id": invitation.id},
    ))
    db.commit()
