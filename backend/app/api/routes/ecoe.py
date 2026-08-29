"""ECOE event CRUD routes."""

from datetime import date

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.entities import (
    AuditLog,
    ECOEPermission,
    ECOEEvent,
    LiveSession,
    StaffAssignment,
    Station,
    Student,
    User,
)
from app.models.enums import ECOEStatus, RoleCode, StationStatus
from app.schemas.common import (
    DashboardSummary,
    ECOEDuplicateOptions,
    ECOEEventCreate,
    ECOEEventRead,
    ECOETimingUpdate,
    ECOEEventUpdate,
)
from app.services.dependencies import get_current_user, require_roles
from app.services.dependencies import require_global_roles
from app.services.ecoe import build_dashboard, update_ecoe_status
from app.services.authorization import (
    ADMIN_EVENT_ROLE_CODES,
    ensure_event_access,
    get_user_event_roles,
    list_accessible_ecoe_events,
)

router = APIRouter()


def _station_count(db: Session, ecoe_event_id: int) -> int:
    return db.scalar(
        select(func.count(Station.id)).where(Station.ecoe_event_id == ecoe_event_id)
    ) or 0


def _active_student_count(db: Session, ecoe_event_id: int) -> int:
    return db.scalar(
        select(func.count(Student.id)).where(
            Student.ecoe_event_id == ecoe_event_id,
            Student.is_active.is_(True),
        )
    ) or 0


def _with_counts(db: Session, event: ECOEEvent) -> ECOEEvent:
    """Deriva ``total_stations`` / ``total_students`` de las filas reales (OPT-11b).

    Se asignan en memoria sobre el objeto ORM justo antes de serializar; no se
    hace ``commit``, así las columnas legadas de ``ecoe_events`` no cambian.
    """
    event.total_stations = _station_count(db, event.id)
    event.total_students = _active_student_count(db, event.id)
    return event


def _with_counts_bulk(db: Session, events: list[ECOEEvent]) -> list[ECOEEvent]:
    """Versión sin N+1 de ``_with_counts``: dos agregadas con ``GROUP BY``."""
    if not events:
        return events
    ids = [e.id for e in events]
    station_counts = dict(
        db.execute(
            select(Station.ecoe_event_id, func.count(Station.id))
            .where(Station.ecoe_event_id.in_(ids))
            .group_by(Station.ecoe_event_id)
        ).all()
    )
    student_counts = dict(
        db.execute(
            select(Student.ecoe_event_id, func.count(Student.id))
            .where(
                Student.ecoe_event_id.in_(ids),
                Student.is_active.is_(True),
            )
            .group_by(Student.ecoe_event_id)
        ).all()
    )
    for event in events:
        event.total_stations = station_counts.get(event.id, 0)
        event.total_students = student_counts.get(event.id, 0)
    return events


@router.get("/dashboard/{ecoe_event_id}", response_model=DashboardSummary)
def dashboard(ecoe_event_id: int, db: Session = Depends(get_db), user=Depends(get_current_user)):
    ensure_event_access(db, user, ecoe_event_id, *ADMIN_EVENT_ROLE_CODES)
    ecoe_event = db.get(ECOEEvent, ecoe_event_id)
    return build_dashboard(db, ecoe_event)


@router.get("/ecoe", response_model=list[ECOEEventRead])
def list_ecoe(db: Session = Depends(get_db), user=Depends(get_current_user)):
    return _with_counts_bulk(db, list_accessible_ecoe_events(db, user))


@router.get("/ecoe/{ecoe_event_id}", response_model=ECOEEventRead)
def get_ecoe(ecoe_event_id: int, db: Session = Depends(get_db), user=Depends(get_current_user)):
    ensure_event_access(
        db, user, ecoe_event_id,
        RoleCode.admin_ecoe.value,
        RoleCode.coeditor_docente.value,
        RoleCode.coordinador_operativo.value,
        RoleCode.evaluador.value,
        RoleCode.corrector.value,
        RoleCode.cronometrador.value,
        RoleCode.estudiante.value,
    )
    ecoe_event = db.get(ECOEEvent, ecoe_event_id)
    return _with_counts(db, ecoe_event)


@router.get("/ecoe/{ecoe_event_id}/roles/me")
def my_ecoe_roles(
    ecoe_event_id: int,
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
):
    ensure_event_access(db, user, ecoe_event_id)
    return {
        "roles": sorted(get_user_event_roles(db, user, ecoe_event_id)),
        "is_global_admin": user.role.code == RoleCode.admin_global.value,
    }


@router.post("/ecoe", response_model=ECOEEventRead)
def create_ecoe(
    payload: ECOEEventCreate,
    db: Session = Depends(get_db),
    user=Depends(require_global_roles(RoleCode.admin_global.value)),
):
    ecoe_event = ECOEEvent(**payload.model_dump(), status=ECOEStatus.borrador.value)
    db.add(ecoe_event)
    db.flush()
    db.add(
        ECOEPermission(
            ecoe_event_id=ecoe_event.id,
            user_id=user.id,
            role_code=RoleCode.admin_ecoe.value,
        )
    )
    db.commit()
    db.refresh(ecoe_event)
    return _with_counts(db, ecoe_event)


@router.get("/ecoe/{ecoe_event_id}/admins")
def list_ecoe_admins(
    ecoe_event_id: int,
    db: Session = Depends(get_db),
    user=Depends(require_global_roles(RoleCode.admin_global.value)),
):
    if not db.get(ECOEEvent, ecoe_event_id):
        raise HTTPException(status_code=404, detail="ECOE no encontrado")
    rows = db.execute(
        select(ECOEPermission, User)
        .join(User, User.id == ECOEPermission.user_id)
        .where(
            ECOEPermission.ecoe_event_id == ecoe_event_id,
            ECOEPermission.role_code == RoleCode.admin_ecoe.value,
        )
        .order_by(User.full_name.asc(), User.id.asc())
    ).all()
    return [
        {
            "permission_id": permission.id,
            "user_id": account.id,
            "email": account.email,
            "full_name": account.full_name,
        }
        for permission, account in rows
    ]


@router.post("/ecoe/{ecoe_event_id}/admins/{user_id}")
def grant_ecoe_admin(
    ecoe_event_id: int,
    user_id: int,
    db: Session = Depends(get_db),
    actor=Depends(require_global_roles(RoleCode.admin_global.value)),
):
    if not db.get(ECOEEvent, ecoe_event_id):
        raise HTTPException(status_code=404, detail="ECOE no encontrado")
    target = db.get(User, user_id)
    if not target or not target.is_active:
        raise HTTPException(status_code=400, detail="El usuario no existe o está inactivo")
    permission = db.scalar(
        select(ECOEPermission).where(
            ECOEPermission.ecoe_event_id == ecoe_event_id,
            ECOEPermission.user_id == user_id,
            ECOEPermission.role_code == RoleCode.admin_ecoe.value,
        )
    )
    if not permission:
        permission = ECOEPermission(
            ecoe_event_id=ecoe_event_id,
            user_id=user_id,
            role_code=RoleCode.admin_ecoe.value,
        )
        db.add(permission)
        db.flush()
        db.add(AuditLog(
            user_email=actor.email,
            action="grant_ecoe_admin",
            target_type="ECOEPermission",
            target_id=str(permission.id),
            payload={"ecoe_event_id": ecoe_event_id, "user_id": user_id},
        ))
        db.commit()
        db.refresh(permission)
    return {"granted": True, "permission_id": permission.id, "user_id": user_id}


@router.delete("/ecoe/{ecoe_event_id}/admins/{user_id}")
def revoke_ecoe_admin(
    ecoe_event_id: int,
    user_id: int,
    db: Session = Depends(get_db),
    actor=Depends(require_global_roles(RoleCode.admin_global.value)),
):
    permission = db.scalar(
        select(ECOEPermission).where(
            ECOEPermission.ecoe_event_id == ecoe_event_id,
            ECOEPermission.user_id == user_id,
            ECOEPermission.role_code == RoleCode.admin_ecoe.value,
        )
    )
    if not permission:
        raise HTTPException(status_code=404, detail="Asignación de administrador no encontrada")
    permission_id = permission.id
    db.delete(permission)
    db.add(AuditLog(
        user_email=actor.email,
        action="revoke_ecoe_admin",
        target_type="ECOEPermission",
        target_id=str(permission_id),
        payload={"ecoe_event_id": ecoe_event_id, "user_id": user_id},
    ))
    db.commit()
    return {"revoked": True, "user_id": user_id}


@router.put("/ecoe/{ecoe_event_id}", response_model=ECOEEventRead)
def update_ecoe(
    ecoe_event_id: int,
    payload: ECOEEventUpdate,
    db: Session = Depends(get_db),
    user=Depends(require_roles("admin_ecoe", "coeditor_docente")),
):
    ensure_event_access(db, user, ecoe_event_id,
                        RoleCode.admin_ecoe.value, RoleCode.coeditor_docente.value)
    ecoe_event = db.get(ECOEEvent, ecoe_event_id)
    previous_status = ecoe_event.status
    for field, value in payload.model_dump(exclude={"status"}).items():
        setattr(ecoe_event, field, value)
    db.add(ecoe_event)
    # Validate the status transition BEFORE committing anything: if it is
    # rejected, the field updates above are rolled back with it.
    try:
        updated_event = update_ecoe_status(
            db, ecoe_event, payload.status, commit=False, actor_email=user.email
        )
    except ValueError as exc:
        db.rollback()
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
    return _with_counts(db, updated_event)


@router.patch("/ecoe/{ecoe_event_id}/timing", response_model=ECOEEventRead)
def update_ecoe_timing(
    ecoe_event_id: int,
    payload: ECOETimingUpdate,
    db: Session = Depends(get_db),
    user=Depends(require_roles("admin_ecoe", "coeditor_docente")),
):
    ensure_event_access(db, user, ecoe_event_id,
                        RoleCode.admin_ecoe.value, RoleCode.coeditor_docente.value)
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
        # La LiveSession copia estos minutos a segundos solo al crearse (o al
        # arrancar/reiniciar el cronometro, que reusa su propio valor
        # guardado): sin este resync queda pegada al timing que tenia el
        # ECOE cuando se creo, aunque luego se edite en la pestaña ECOE.
        live_session = db.scalar(
            select(LiveSession).where(LiveSession.ecoe_event_id == ecoe_event_id).limit(1)
        )
        if live_session:
            live_session.station_time_seconds = max(1, round(payload.station_time_minutes * 60))
            live_session.transition_time_seconds = max(0, round(payload.transition_time_minutes * 60))
            if live_session.status not in {"running", "transition"}:
                live_session.remaining_seconds = live_session.station_time_seconds
            db.add(live_session)
    db.commit()
    db.refresh(ecoe_event)
    return _with_counts(db, ecoe_event)


@router.post("/ecoe/{ecoe_event_id}/duplicate", response_model=ECOEEventRead)
def duplicate_ecoe(
    ecoe_event_id: int,
    payload: ECOEDuplicateOptions = ECOEDuplicateOptions(),
    db: Session = Depends(get_db),
    user=Depends(require_roles("admin_ecoe")),
):
    """Clona la estructura de un ECOE.

    Las estaciones clonadas **comparten** el mismo ``assessment_tool_id`` (no se
    clona el banco de instrumentos, decisión OPT-7). El tool conserva su
    ``origin_event_id`` original, así que la regla de propiedad para
    editar/archivar la pauta sigue apuntando al ECOE que la creó, no a la copia.
    Lo mismo aplica a ``template_id`` y ``simulated_patient_id`` (OPT-7b): se
    comparten sin clonar y conservan su ``origin_event_id``.
    """
    ensure_event_access(db, user, ecoe_event_id, RoleCode.admin_ecoe.value)
    ecoe_event = db.get(ECOEEvent, ecoe_event_id)

    clone_name = payload.name.strip() if payload.name.strip() else f"{ecoe_event.name} (copia)"
    clone_date = payload.new_date if payload.new_date else ecoe_event.date

    clone = ECOEEvent(
        name=clone_name,
        date=clone_date,
        course_name=ecoe_event.course_name,
        school_name=ecoe_event.school_name,
        responsible_teacher=ecoe_event.responsible_teacher,
        contact_email=ecoe_event.contact_email,
        circuit_mode=ecoe_event.circuit_mode,
        station_time_minutes=ecoe_event.station_time_minutes,
        transition_time_minutes=ecoe_event.transition_time_minutes,
        total_groups=ecoe_event.total_groups,
        passing_reference_percent=ecoe_event.passing_reference_percent,
        status=ECOEStatus.borrador.value,
    )
    db.add(clone)
    db.flush()

    # Always copy stations (structure)
    original_stations = db.scalars(
        select(Station).where(Station.ecoe_event_id == ecoe_event_id)
    ).all()
    station_id_map: dict[int, int] = {}
    for st in original_stations:
        new_station = Station(
            ecoe_event_id=clone.id,
            template_id=st.template_id,
            assessment_tool_id=st.assessment_tool_id,
            simulated_patient_id=st.simulated_patient_id,
            station_number=st.station_number,
            name=st.name,
            station_type=st.station_type,
            circuit_name=st.circuit_name,
            station_time_minutes=st.station_time_minutes,
            transition_time_minutes=st.transition_time_minutes,
            expected_outcomes=st.expected_outcomes,
            student_activity=st.student_activity,
            student_station_instruction=st.student_station_instruction,
            pre_entry_instruction=st.pre_entry_instruction,
            evaluator_instruction=st.evaluator_instruction,
            requires_evaluator=st.requires_evaluator,
            requires_student_form=st.requires_student_form,
            requires_deferred_grading=st.requires_deferred_grading,
            uses_multimedia=st.uses_multimedia,
            uses_simulated_patient=st.uses_simulated_patient,
            uses_physical_resources=st.uses_physical_resources,
            max_score=st.max_score,
            materials=st.materials,
            clinical_equipment=st.clinical_equipment,
            simulator=st.simulator,
            ambience=st.ambience,
            multimedia_notes=st.multimedia_notes,
            student_form_definition=st.student_form_definition,
            contingency_ready=st.contingency_ready,
            status=StationStatus.en_diseno.value,
        )
        db.add(new_station)
        db.flush()
        station_id_map[st.id] = new_station.id

    # Optionally copy evaluators with re-mapped station IDs
    if payload.copy_evaluators:
        evaluators = db.scalars(
            select(StaffAssignment).where(
                StaffAssignment.ecoe_event_id == ecoe_event_id,
                StaffAssignment.role_code == RoleCode.evaluador.value,
            )
        ).all()
        for ev in evaluators:
            remapped = [
                station_id_map[sid] for sid in (ev.station_ids or [])
                if sid in station_id_map
            ]
            db.add(StaffAssignment(
                ecoe_event_id=clone.id,
                name=ev.name, last_name=ev.last_name,
                email=ev.email, role_code=ev.role_code,
                station_ids=remapped,
            ))

    db.add(ECOEPermission(
        ecoe_event_id=clone.id,
        user_id=user.id,
        role_code=RoleCode.admin_ecoe.value,
    ))
    db.add(AuditLog(
        user_email=user.email,
        action="duplicate_ecoe",
        target_type="ECOEEvent",
        target_id=str(clone.id),
        payload={
            "source_ecoe_id": ecoe_event_id,
            "stations_copied": len(original_stations),
            "evaluators_copied": payload.copy_evaluators,
        },
    ))
    db.commit()
    db.refresh(clone)
    return _with_counts(db, clone)
