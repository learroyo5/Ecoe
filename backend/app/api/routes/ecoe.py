"""ECOE event CRUD routes."""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.entities import (
    AuditLog,
    ECOEPermission,
    ECOEEvent,
    Station,
)
from app.models.enums import ECOEStatus, RoleCode
from app.schemas.common import (
    DashboardSummary,
    ECOEEventCreate,
    ECOEEventRead,
    ECOETimingUpdate,
    ECOEEventUpdate,
)
from app.services.dependencies import get_current_user, require_roles
from app.services.ecoe import build_dashboard, update_ecoe_status
from app.utils.helpers import (
    ADMIN_EVENT_ROLE_CODES,
    ensure_event_access,
    list_accessible_ecoe_events,
)

router = APIRouter()


@router.get("/dashboard/{ecoe_event_id}", response_model=DashboardSummary)
def dashboard(ecoe_event_id: int, db: Session = Depends(get_db), user=Depends(get_current_user)):
    ensure_event_access(db, user, ecoe_event_id, *ADMIN_EVENT_ROLE_CODES)
    ecoe_event = db.get(ECOEEvent, ecoe_event_id)
    return build_dashboard(db, ecoe_event)


@router.get("/ecoe", response_model=list[ECOEEventRead])
def list_ecoe(db: Session = Depends(get_db), user=Depends(get_current_user)):
    return list_accessible_ecoe_events(db, user)


@router.get("/ecoe/{ecoe_event_id}", response_model=ECOEEventRead)
def get_ecoe(ecoe_event_id: int, db: Session = Depends(get_db), user=Depends(get_current_user)):
    ensure_event_access(
        db, user, ecoe_event_id,
        RoleCode.creador_ecoe.value,
        RoleCode.coeditor_docente.value,
        RoleCode.coordinador_operativo.value,
        RoleCode.evaluador.value,
        RoleCode.cronometrador.value,
        RoleCode.estudiante.value,
    )
    ecoe_event = db.get(ECOEEvent, ecoe_event_id)
    return ecoe_event


@router.post("/ecoe", response_model=ECOEEventRead)
def create_ecoe(
    payload: ECOEEventCreate,
    db: Session = Depends(get_db),
    user=Depends(require_roles("creador_ecoe")),
):
    ecoe_event = ECOEEvent(**payload.model_dump(), status=ECOEStatus.borrador.value)
    db.add(ecoe_event)
    db.flush()
    db.add(
        ECOEPermission(
            ecoe_event_id=ecoe_event.id,
            user_id=user.id,
            role_code=RoleCode.creador_ecoe.value,
        )
    )
    db.commit()
    db.refresh(ecoe_event)
    return ecoe_event


@router.put("/ecoe/{ecoe_event_id}", response_model=ECOEEventRead)
def update_ecoe(
    ecoe_event_id: int,
    payload: ECOEEventUpdate,
    db: Session = Depends(get_db),
    user=Depends(require_roles("creador_ecoe", "coeditor_docente")),
):
    ensure_event_access(db, user, ecoe_event_id,
                        RoleCode.creador_ecoe.value, RoleCode.coeditor_docente.value)
    ecoe_event = db.get(ECOEEvent, ecoe_event_id)
    for field, value in payload.model_dump(exclude={"status"}).items():
        setattr(ecoe_event, field, value)
    db.add(ecoe_event)
    db.commit()
    db.refresh(ecoe_event)
    previous_status = ecoe_event.status
    try:
        updated_event = update_ecoe_status(db, ecoe_event, payload.status)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    if previous_status != payload.status:
        db.add(
            AuditLog(
                user_email=user.email,
                action="update_ecoe_status",
                target_type="ECOEEvent",
                target_id=str(updated_event.id),
                payload={
                    "ecoe_event_id": updated_event.id,
                    "previous_status": previous_status,
                    "new_status": payload.status,
                },
            )
        )
        db.commit()
        db.refresh(updated_event)
    return updated_event


@router.patch("/ecoe/{ecoe_event_id}/timing", response_model=ECOEEventRead)
def update_ecoe_timing(
    ecoe_event_id: int,
    payload: ECOETimingUpdate,
    db: Session = Depends(get_db),
    user=Depends(require_roles("creador_ecoe", "coeditor_docente")),
):
    ensure_event_access(db, user, ecoe_event_id,
                        RoleCode.creador_ecoe.value, RoleCode.coeditor_docente.value)
    ecoe_event = db.get(ECOEEvent, ecoe_event_id)
    ecoe_event.station_time_minutes = payload.station_time_minutes
    ecoe_event.transition_time_minutes = payload.transition_time_minutes
    db.add(ecoe_event)
    if payload.sync_existing_stations:
        stations = db.scalars(select(Station).where(Station.ecoe_event_id == ecoe_event_id)).all()
        for station in stations:
            station.station_time_minutes = payload.station_time_minutes
            station.transition_time_minutes = payload.transition_time_minutes
            db.add(station)
    db.commit()
    db.refresh(ecoe_event)
    return ecoe_event


@router.post("/ecoe/{ecoe_event_id}/duplicate", response_model=ECOEEventRead)
def duplicate_ecoe(
    ecoe_event_id: int,
    db: Session = Depends(get_db),
    user=Depends(require_roles("creador_ecoe")),
):
    ensure_event_access(db, user, ecoe_event_id, RoleCode.creador_ecoe.value)
    ecoe_event = db.get(ECOEEvent, ecoe_event_id)
    clone = ECOEEvent(
        name=f"{ecoe_event.name} (copia)",
        date=ecoe_event.date,
        course_name=ecoe_event.course_name,
        school_name=ecoe_event.school_name,
        responsible_teacher=ecoe_event.responsible_teacher,
        contact_email=ecoe_event.contact_email,
        circuit_mode=ecoe_event.circuit_mode,
        total_stations=ecoe_event.total_stations,
        station_time_minutes=ecoe_event.station_time_minutes,
        transition_time_minutes=ecoe_event.transition_time_minutes,
        total_students=ecoe_event.total_students,
        total_groups=ecoe_event.total_groups,
        passing_reference_percent=ecoe_event.passing_reference_percent,
        status=ECOEStatus.borrador.value,
    )
    db.add(clone)
    db.flush()
    db.add(
        ECOEPermission(
            ecoe_event_id=clone.id,
            user_id=user.id,
            role_code=RoleCode.creador_ecoe.value,
        )
    )
    db.commit()
    db.refresh(clone)
    return clone
