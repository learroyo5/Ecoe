"""Staff management routes."""

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.entities import StaffAssignment
from app.models.enums import RoleCode
from app.schemas.common import EventMemberInvite, Page, StaffCreate, StaffRead, StaffUpdate
from app.services.dependencies import get_current_user, require_roles
from app.services.invitations import assign_or_invite_member
from app.services.mailer import notify_event_access
from app.utils.files import parse_tabular_file
from app.services.authorization import (
    ensure_event_access,
    ensure_matching_operational_user,
    ensure_staff_assignment_can_be_managed,
    ensure_staff_role_can_be_delegated,
    validate_staff_role_code,
)
from app.utils.helpers import (
    ensure_primary_station_assignment,
    normalize_email,
    normalize_station_ids,
)
from app.utils.pagination import DEFAULT_PAGE_SIZE, MAX_PAGE_SIZE, paginate_query

router = APIRouter()


@router.get("/staff/{ecoe_event_id}", response_model=Page[StaffRead])
def list_staff(
    ecoe_event_id: int,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=DEFAULT_PAGE_SIZE, ge=1, le=MAX_PAGE_SIZE),
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
):
    ensure_event_access(db, user, ecoe_event_id,
                        RoleCode.admin_ecoe.value,
                        RoleCode.coeditor_docente.value,
                        RoleCode.coordinador_operativo.value)
    stmt = (
        select(StaffAssignment)
        .where(StaffAssignment.ecoe_event_id == ecoe_event_id)
        .order_by(StaffAssignment.last_name.asc(), StaffAssignment.name.asc(), StaffAssignment.id.asc())
    )
    result = paginate_query(db, stmt, page=page, page_size=page_size)
    staff_rows = result["items"]
    changed = False
    for staff in staff_rows:
        _, staff_changed = ensure_primary_station_assignment(staff)
        if staff_changed:
            db.add(staff)
            changed = True
    if changed:
        db.commit()
        for staff in staff_rows:
            db.refresh(staff)
    return result




@router.post("/staff", response_model=StaffRead)
def create_staff(
    payload: StaffCreate,
    db: Session = Depends(get_db),
    user=Depends(require_roles("admin_ecoe", "coeditor_docente", "coordinador_operativo")),
):
    actor_roles = ensure_event_access(db, user, payload.ecoe_event_id,
                        RoleCode.admin_ecoe.value,
                        RoleCode.coeditor_docente.value,
                        RoleCode.coordinador_operativo.value)
    email = normalize_email(payload.email)
    normalized_role_code = validate_staff_role_code(payload.role_code)
    ensure_staff_role_can_be_delegated(actor_roles, normalized_role_code)
    ensure_matching_operational_user(db, email=email, expected_role=normalized_role_code)
    existing = db.scalar(
        select(StaffAssignment).where(
            StaffAssignment.ecoe_event_id == payload.ecoe_event_id,
            StaffAssignment.email == email,
        )
    )
    if existing:
        raise HTTPException(
            status_code=400,
            detail="Ya existe un evaluador o colaborador con ese correo en este ECOE",
        )
    station_ids = normalize_station_ids(payload.station_ids)
    if normalized_role_code == RoleCode.evaluador.value and not station_ids:
        raise HTTPException(status_code=400, detail="El evaluador debe tener una estación principal asignada")
    if station_ids:
        from app.models.entities import Station
        station_obj = db.get(Station, station_ids[0])
        if not station_obj or station_obj.ecoe_event_id != payload.ecoe_event_id:
            raise HTTPException(status_code=400, detail="La estación asignada no pertenece a este ECOE")
    staff_data = payload.model_dump()
    staff_data["email"] = email
    staff_data["role_code"] = normalized_role_code
    staff_data["station_ids"] = station_ids
    staff = StaffAssignment(**staff_data)
    db.add(staff)
    db.commit()
    db.refresh(staff)
    return staff


@router.patch("/staff/{staff_id}", response_model=StaffRead)
def update_staff(
    staff_id: int,
    payload: StaffUpdate,
    db: Session = Depends(get_db),
    user=Depends(require_roles("admin_ecoe", "coeditor_docente", "coordinador_operativo")),
):
    staff = db.get(StaffAssignment, staff_id)
    if not staff:
        raise HTTPException(status_code=404, detail="Evaluador o colaborador no encontrado")
    actor_roles = ensure_event_access(db, user, staff.ecoe_event_id,
                        RoleCode.admin_ecoe.value,
                        RoleCode.coeditor_docente.value,
                        RoleCode.coordinador_operativo.value)
    ensure_staff_assignment_can_be_managed(actor_roles, staff.role_code)
    normalized_role_code = validate_staff_role_code(payload.role_code)
    ensure_staff_role_can_be_delegated(actor_roles, normalized_role_code)
    ensure_matching_operational_user(db, email=staff.email, expected_role=normalized_role_code)
    station_ids = normalize_station_ids(payload.station_ids)
    if normalized_role_code == RoleCode.evaluador.value and not station_ids:
        raise HTTPException(status_code=400, detail="El evaluador debe tener una estación principal asignada")
    if station_ids:
        from app.models.entities import Station
        station_obj = db.get(Station, station_ids[0])
        if not station_obj or station_obj.ecoe_event_id != staff.ecoe_event_id:
            raise HTTPException(status_code=400, detail="La estación asignada no pertenece a este ECOE")
    staff.role_code = normalized_role_code
    staff.station_ids = station_ids
    db.add(staff)
    db.commit()
    db.refresh(staff)
    return staff


@router.delete("/staff/{staff_id}")
def delete_staff(
    staff_id: int,
    db: Session = Depends(get_db),
    user=Depends(require_roles("admin_ecoe", "coeditor_docente")),
):
    staff = db.get(StaffAssignment, staff_id)
    if not staff:
        raise HTTPException(status_code=404, detail="Evaluador o colaborador no encontrado")
    actor_roles = ensure_event_access(db, user, staff.ecoe_event_id,
                        RoleCode.admin_ecoe.value, RoleCode.coeditor_docente.value)
    ensure_staff_assignment_can_be_managed(actor_roles, staff.role_code)
    db.delete(staff)
    db.commit()
    return {"deleted": True}


@router.post("/staff/{ecoe_event_id}/deduplicate-email")
def deduplicate_staff_by_email(
    ecoe_event_id: int,
    db: Session = Depends(get_db),
    user=Depends(require_roles("admin_ecoe")),
):
    ensure_event_access(db, user, ecoe_event_id, RoleCode.admin_ecoe.value)
    staff_rows = db.scalars(
        select(StaffAssignment)
        .where(StaffAssignment.ecoe_event_id == ecoe_event_id)
        .order_by(StaffAssignment.created_at.asc(), StaffAssignment.id.asc())
    ).all()
    seen_emails: set[str] = set()
    removed = 0
    for staff in staff_rows:
        email = normalize_email(staff.email)
        if not email:
            continue
        if email in seen_emails:
            db.delete(staff)
            removed += 1
            continue
        seen_emails.add(email)
    db.commit()
    return {"removed": removed}


@router.post("/staff/import")
async def import_staff(
    ecoe_event_id: int,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    user=Depends(require_roles("admin_ecoe", "coeditor_docente")),
):
    actor_roles = ensure_event_access(db, user, ecoe_event_id,
                        RoleCode.admin_ecoe.value, RoleCode.coeditor_docente.value)
    rows = await parse_tabular_file(file)
    # Minting institutional identities stays an admin_ecoe power: a coeditor may
    # only import people who already have an account.
    may_create_accounts = RoleCode.admin_ecoe.value in actor_roles
    imported = 0
    invited: list[dict] = []
    skipped_duplicate = 0
    skipped_no_account = 0
    skipped_forbidden_role = 0
    skipped_missing_data = 0
    existing_emails = {
        normalize_email(email)
        for email in db.scalars(
            select(StaffAssignment.email).where(StaffAssignment.ecoe_event_id == ecoe_event_id)
        ).all()
    }
    for row in rows:
        email = normalize_email(row.get("correo", row.get("email", "")))
        name = str(row.get("nombre", row.get("name", ""))).strip()
        last_name = str(row.get("apellidos", row.get("last_name", ""))).strip()
        if not email or not name or not last_name:
            skipped_missing_data += 1
            continue
        if email in existing_emails:
            skipped_duplicate += 1
            continue
        role_code = validate_staff_role_code(row.get("rol", row.get("role_code", "evaluador")))
        try:
            ensure_staff_role_can_be_delegated(actor_roles, role_code)
        except HTTPException:
            skipped_forbidden_role += 1
            continue
        payload = EventMemberInvite(
            ecoe_event_id=ecoe_event_id,
            name=name,
            last_name=last_name,
            email=email,
            role_code=role_code,
            station_ids=[],
        )
        try:
            # A savepoint keeps a rejected row from discarding the rows already
            # staged in this import.
            with db.begin_nested():
                result = assign_or_invite_member(
                    db,
                    payload,
                    invited_by_email=user.email,
                    may_create_accounts=may_create_accounts,
                    # The file carries no station; evaluators get their primary
                    # station afterwards in the Evaluadores screen.
                    require_evaluator_station=False,
                )
        except HTTPException:
            skipped_no_account += 1
            continue
        if result["status"] == "invited":
            invited.append({
                "email": result["email"],
                "role_code": result["role_code"],
                "activation_path": result["activation_path"],
                "expires_at": result["expires_at"],
            })
        imported += 1
        existing_emails.add(email)
    db.commit()
    for entry in invited:
        entry["email_sent"] = notify_event_access(db, ecoe_event_id, entry, is_reset=False)
    return {
        "imported": imported,
        "invited": invited,
        "skipped": skipped_duplicate + skipped_no_account + skipped_forbidden_role + skipped_missing_data,
        "skipped_duplicate": skipped_duplicate,
        "skipped_no_account": skipped_no_account,
        "skipped_forbidden_role": skipped_forbidden_role,
        "skipped_missing_data": skipped_missing_data,
    }
