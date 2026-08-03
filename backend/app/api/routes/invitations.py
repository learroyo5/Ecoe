"""Event member lookup, invitation, assignment, and public activation."""

from fastapi import APIRouter, Depends, Query, Response
from pydantic import EmailStr
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.enums import RoleCode
from app.schemas.common import EventMemberInvite, InvitationActivation
from app.services.authorization import ensure_event_access
from app.services.dependencies import get_current_user, require_roles
from app.services.invitations import (
    activate_invitation,
    assign_or_invite_member,
    lookup_member_by_exact_email,
)

router = APIRouter()


@router.get("/event-members/lookup")
def lookup_event_member(
    ecoe_event_id: int,
    email: EmailStr = Query(...),
    db: Session = Depends(get_db),
    user=Depends(require_roles(RoleCode.admin_ecoe.value)),
):
    ensure_event_access(db, user, ecoe_event_id, RoleCode.admin_ecoe.value)
    return lookup_member_by_exact_email(db, ecoe_event_id, str(email))


@router.post("/event-members/invite")
def invite_event_member(
    payload: EventMemberInvite,
    response: Response,
    db: Session = Depends(get_db),
    user=Depends(require_roles(RoleCode.admin_ecoe.value)),
):
    ensure_event_access(db, user, payload.ecoe_event_id, RoleCode.admin_ecoe.value)
    result = assign_or_invite_member(db, payload, invited_by_email=user.email)
    db.commit()
    response.headers["Cache-Control"] = "no-store"
    return result


@router.post("/auth/activate-invitation")
def activate_account(
    payload: InvitationActivation,
    response: Response,
    db: Session = Depends(get_db),
):
    activate_invitation(db, payload.token, payload.password)
    response.headers["Cache-Control"] = "no-store"
    return {"activated": True}
