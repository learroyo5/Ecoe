"""Station management, templates, instruments, patients, bank, pilotage routes."""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.entities import (
    AssessmentTool,
    AssessmentItem,
    Station,
    StationTemplate,
    SimulatedPatient,
    StationBank,
    PilotRun,
    PilotRecord,
    AuditLog,
    LiveSession,
    ECOEEvent,
)
from app.models.enums import ECOEStatus, RoleCode, StationStatus
from app.schemas.common import (
    AssessmentToolCreate,
    AssessmentToolRead,
    PilotRunCreate,
    PilotRunNotesUpdate,
    PilotRunRead,
    SimulatedPatientCreate,
    SimulatedPatientRead,
    StationBankCreate,
    StationBankRead,
    StationBankStatusUpdate,
    StationCreate,
    StationRead,
    StationTemplateCreate,
    StationTemplateRead,
)
from app.services.dependencies import get_current_user, require_roles
from app.services.ecoe import compute_ecoe_validation
from app.services.authorization import (
    ADMIN_EVENT_ROLE_CODES,
    ensure_event_access,
)

router = APIRouter()

# Roles that may read exam design content (templates, instruments,
# simulated patients, station bank). Students/evaluators receive only
# what they need through /student/access and /evaluator/context.
CONTENT_MANAGER_ROLES = ("admin_ecoe", "coeditor_docente", "coordinador_operativo")

# ── Station Templates ───────────────────────────────────────────────────

@router.get("/templates", response_model=list[StationTemplateRead])
def list_templates(ecoe_event_id: int, db: Session = Depends(get_db), user=Depends(require_roles(*CONTENT_MANAGER_ROLES))):
    ensure_event_access(db, user, ecoe_event_id, *ADMIN_EVENT_ROLE_CODES)
    return db.scalars(select(StationTemplate)).all()


@router.post("/templates", response_model=StationTemplateRead)
def create_template(
    payload: StationTemplateCreate,
    ecoe_event_id: int,
    db: Session = Depends(get_db),
    user=Depends(require_roles("admin_ecoe", "coeditor_docente")),
):
    ensure_event_access(db, user, ecoe_event_id,
                        RoleCode.admin_ecoe.value, RoleCode.coeditor_docente.value)
    template = StationTemplate(**payload.model_dump())
    db.add(template)
    db.commit()
    db.refresh(template)
    return template


# ── Assessment Tools / Instruments ──────────────────────────────────────

@router.get("/instruments", response_model=list[AssessmentToolRead])
def list_instruments(ecoe_event_id: int, db: Session = Depends(get_db), user=Depends(require_roles(*CONTENT_MANAGER_ROLES))):
    ensure_event_access(db, user, ecoe_event_id, *ADMIN_EVENT_ROLE_CODES)
    return db.scalars(select(AssessmentTool)).all()


@router.post("/instruments", response_model=AssessmentToolRead)
def create_instrument(
    payload: AssessmentToolCreate,
    ecoe_event_id: int,
    db: Session = Depends(get_db),
    user=Depends(require_roles("admin_ecoe", "coeditor_docente")),
):
    ensure_event_access(db, user, ecoe_event_id,
                        RoleCode.admin_ecoe.value, RoleCode.coeditor_docente.value)
    tool = AssessmentTool(
        name=payload.name,
        tool_type=payload.tool_type,
        max_score=payload.max_score,
        free_observation=payload.free_observation,
    )
    db.add(tool)
    db.flush()
    for item in payload.items:
        db.add(AssessmentItem(tool_id=tool.id, **item.model_dump()))
    db.commit()
    db.refresh(tool)
    return tool


# ── Simulated Patients ─────────────────────────────────────────────────

@router.get("/simulated-patients", response_model=list[SimulatedPatientRead])
def list_patients(ecoe_event_id: int, db: Session = Depends(get_db), user=Depends(require_roles(*CONTENT_MANAGER_ROLES))):
    ensure_event_access(db, user, ecoe_event_id, *ADMIN_EVENT_ROLE_CODES)
    return db.scalars(select(SimulatedPatient)).all()


@router.post("/simulated-patients", response_model=SimulatedPatientRead)
def create_patient(
    payload: SimulatedPatientCreate,
    ecoe_event_id: int,
    db: Session = Depends(get_db),
    user=Depends(require_roles("admin_ecoe", "coeditor_docente")),
):
    ensure_event_access(db, user, ecoe_event_id,
                        RoleCode.admin_ecoe.value, RoleCode.coeditor_docente.value)
    patient = SimulatedPatient(**payload.model_dump())
    db.add(patient)
    db.commit()
    db.refresh(patient)
    return patient


# ── Station Bank ────────────────────────────────────────────────────────

@router.get("/station-bank", response_model=list[StationBankRead])
def list_station_bank(ecoe_event_id: int, db: Session = Depends(get_db), user=Depends(require_roles(*CONTENT_MANAGER_ROLES))):
    ensure_event_access(db, user, ecoe_event_id, *ADMIN_EVENT_ROLE_CODES)
    return db.scalars(select(StationBank).order_by(StationBank.updated_at.desc(), StationBank.id.desc())).all()


@router.post("/station-bank", response_model=StationBankRead)
def create_station_bank(
    payload: StationBankCreate,
    ecoe_event_id: int,
    db: Session = Depends(get_db),
    user=Depends(require_roles("admin_ecoe", "coeditor_docente")),
):
    ensure_event_access(db, user, ecoe_event_id,
                        RoleCode.admin_ecoe.value, RoleCode.coeditor_docente.value)
    bank_station = StationBank(**payload.model_dump())
    db.add(bank_station)
    db.commit()
    db.refresh(bank_station)
    return bank_station


@router.put("/station-bank/{bank_station_id}", response_model=StationBankRead)
def update_station_bank(
    bank_station_id: int,
    payload: StationBankCreate,
    ecoe_event_id: int,
    db: Session = Depends(get_db),
    user=Depends(require_roles("admin_ecoe", "coeditor_docente")),
):
    ensure_event_access(db, user, ecoe_event_id,
                        RoleCode.admin_ecoe.value, RoleCode.coeditor_docente.value)
    bank_station = db.get(StationBank, bank_station_id)
    if not bank_station:
        raise HTTPException(status_code=404, detail="Estacion de banco no encontrada")
    for field, value in payload.model_dump().items():
        setattr(bank_station, field, value)
    db.add(bank_station)
    db.commit()
    db.refresh(bank_station)
    return bank_station


@router.patch("/station-bank/{bank_station_id}/status", response_model=StationBankRead)
def update_station_bank_status(
    bank_station_id: int,
    payload: StationBankStatusUpdate,
    ecoe_event_id: int,
    db: Session = Depends(get_db),
    user=Depends(require_roles("admin_ecoe", "coeditor_docente")),
):
    ensure_event_access(db, user, ecoe_event_id,
                        RoleCode.admin_ecoe.value, RoleCode.coeditor_docente.value)
    bank_station = db.get(StationBank, bank_station_id)
    if not bank_station:
        raise HTTPException(status_code=404, detail="Estacion de banco no encontrada")
    bank_station.status = payload.status
    db.add(bank_station)
    db.commit()
    db.refresh(bank_station)
    return bank_station


# ── Stations ────────────────────────────────────────────────────────────

@router.get("/stations/{ecoe_event_id}", response_model=list[StationRead])
def list_stations(ecoe_event_id: int, db: Session = Depends(get_db), user=Depends(get_current_user)):
    ensure_event_access(db, user, ecoe_event_id, *ADMIN_EVENT_ROLE_CODES)
    return db.scalars(select(Station).where(Station.ecoe_event_id == ecoe_event_id)).all()


@router.post("/stations", response_model=StationRead)
def create_station(
    payload: StationCreate,
    db: Session = Depends(get_db),
    user=Depends(require_roles("admin_ecoe", "coeditor_docente")),
):
    ensure_event_access(db, user, payload.ecoe_event_id,
                        RoleCode.admin_ecoe.value, RoleCode.coeditor_docente.value)
    ecoe_event = db.get(ECOEEvent, payload.ecoe_event_id)
    if not ecoe_event:
        raise HTTPException(status_code=404, detail="ECOE no encontrado")
    next_station_number = (
        db.scalar(
            select(func.max(Station.station_number)).where(Station.ecoe_event_id == payload.ecoe_event_id)
        ) or 0
    ) + 1
    station = Station(
        **payload.model_dump(exclude={"station_number"}),
        station_number=next_station_number,
        station_time_minutes=ecoe_event.station_time_minutes,
        transition_time_minutes=ecoe_event.transition_time_minutes,
    )
    db.add(station)
    db.commit()
    db.refresh(station)
    return station


@router.put("/stations/{station_id}", response_model=StationRead)
def update_station(
    station_id: int,
    payload: StationCreate,
    db: Session = Depends(get_db),
    user=Depends(require_roles("admin_ecoe", "coeditor_docente")),
):
    station = db.get(Station, station_id)
    if not station:
        raise HTTPException(status_code=404, detail="Estacion no encontrada")
    ensure_event_access(db, user, station.ecoe_event_id,
                        RoleCode.admin_ecoe.value, RoleCode.coeditor_docente.value)
    if payload.ecoe_event_id != station.ecoe_event_id:
        raise HTTPException(
            status_code=400,
            detail="Una estacion no puede trasladarse a otro ECOE mediante una actualizacion",
        )
    ecoe_event = db.get(ECOEEvent, payload.ecoe_event_id)
    if not ecoe_event:
        raise HTTPException(status_code=404, detail="ECOE no encontrado")
    for field, value in payload.model_dump(exclude={"ecoe_event_id"}).items():
        setattr(station, field, value)
    station.station_time_minutes = ecoe_event.station_time_minutes
    station.transition_time_minutes = ecoe_event.transition_time_minutes
    if station.expected_outcomes and station.pre_entry_instruction:
        station.status = (
            StationStatus.lista_para_pilotaje.value
            if station.assessment_tool_id or not station.requires_evaluator
            else StationStatus.incompleta.value
        )
    db.add(station)
    db.commit()
    db.refresh(station)
    return station


@router.delete("/stations/{station_id}")
def delete_station(
    station_id: int,
    db: Session = Depends(get_db),
    user=Depends(require_roles("admin_ecoe", "coeditor_docente")),
):
    station = db.get(Station, station_id)
    if not station:
        raise HTTPException(status_code=404, detail="Estacion no encontrada")
    ensure_event_access(db, user, station.ecoe_event_id,
                        RoleCode.admin_ecoe.value, RoleCode.coeditor_docente.value)
    db.delete(station)
    db.commit()
    return {"deleted": True}


# ── Pilotage ────────────────────────────────────────────────────────────

@router.post("/pilotage", response_model=PilotRunRead)
def create_pilotage(
    payload: PilotRunCreate,
    db: Session = Depends(get_db),
    user=Depends(require_roles("admin_ecoe", "coeditor_docente", "coordinador_operativo")),
):
    ensure_event_access(db, user, payload.ecoe_event_id,
                        RoleCode.admin_ecoe.value,
                        RoleCode.coeditor_docente.value,
                        RoleCode.coordinador_operativo.value)
    ecoe_event = db.get(ECOEEvent, payload.ecoe_event_id)
    if not ecoe_event:
        raise HTTPException(status_code=404, detail="ECOE no encontrado")
    validation = compute_ecoe_validation(db, ecoe_event)
    if not validation["can_pilot"]:
        raise HTTPException(status_code=400,
                            detail="El ECOE aun no cumple condiciones minimas para pilotaje.")
    scope = payload.scope.strip().lower()
    if scope not in {"estacion", "circuito_completo"}:
        raise HTTPException(status_code=400, detail="Alcance de pilotaje no permitido.")
    event_station_ids = set(
        db.scalars(select(Station.id).where(Station.ecoe_event_id == payload.ecoe_event_id)).all()
    )
    if scope == "estacion":
        if len(payload.station_ids) != 1:
            raise HTTPException(status_code=400,
                                detail="Para pilotar una estacion debes seleccionar exactamente una estacion.")
        station_id = int(payload.station_ids[0])
        if station_id not in event_station_ids:
            raise HTTPException(status_code=400, detail="La estacion seleccionada no pertenece a este ECOE.")
        station_issue = next(
            (issue for issue in validation["station_issues"] if int(issue["station_id"]) == station_id), None
        )
        if not station_issue or not station_issue["ready_for_pilot"]:
            raise HTTPException(status_code=400,
                                detail="La estacion seleccionada aun no esta lista para pilotaje individual.")
        station_ids = [station_id]
    else:
        has_station_pilot = db.scalar(
            select(func.count(PilotRun.id)).where(
                PilotRun.ecoe_event_id == payload.ecoe_event_id,
                PilotRun.scope == "estacion",
                PilotRun.archived.is_(False),
            )
        )
        if not has_station_pilot:
            raise HTTPException(status_code=400,
                                detail="No puedes pilotear el circuito completo sin haber realizado antes al menos un pilotaje individual de estacion.")
        station_ids = list(event_station_ids)
    pilot_run = PilotRun(
        ecoe_event_id=payload.ecoe_event_id,
        name=payload.name,
        scope=scope,
        notes=payload.notes.strip(),
    )
    db.add(pilot_run)
    db.flush()
    for sid in station_ids:
        db.add(PilotRecord(pilot_run_id=pilot_run.id, station_id=sid,
                           payload={"status": "prueba"}, is_test=True))
    db.add(AuditLog(
        user_email=user.email, action="create_pilotage", target_type="PilotRun",
        target_id=str(pilot_run.id),
        payload={"ecoe_event_id": payload.ecoe_event_id, "scope": scope,
                 "station_ids": station_ids, "name": payload.name},
    ))
    db.commit()
    return pilot_run


@router.get("/pilotage/{ecoe_event_id}", response_model=list[PilotRunRead])
def list_pilotage(ecoe_event_id: int, db: Session = Depends(get_db), user=Depends(get_current_user)):
    ensure_event_access(db, user, ecoe_event_id, *ADMIN_EVENT_ROLE_CODES)
    return db.scalars(select(PilotRun).where(PilotRun.ecoe_event_id == ecoe_event_id)).all()


@router.patch("/pilotage/{pilot_run_id}/notes", response_model=PilotRunRead)
def update_pilotage_notes(
    pilot_run_id: int,
    payload: PilotRunNotesUpdate,
    db: Session = Depends(get_db),
    user=Depends(require_roles("admin_ecoe", "coeditor_docente", "coordinador_operativo")),
):
    run = db.get(PilotRun, pilot_run_id)
    if not run:
        raise HTTPException(status_code=404, detail="Pilotaje no encontrado")
    ensure_event_access(db, user, run.ecoe_event_id,
                        RoleCode.admin_ecoe.value,
                        RoleCode.coeditor_docente.value,
                        RoleCode.coordinador_operativo.value)
    run.notes = payload.notes.strip()
    db.add(run)
    db.add(AuditLog(
        user_email=user.email,
        action="update_pilotage_notes",
        target_type="PilotRun",
        target_id=str(run.id),
        payload={"ecoe_event_id": run.ecoe_event_id},
    ))
    db.commit()
    db.refresh(run)
    return run


@router.post("/pilotage/{pilot_run_id}/archive")
def archive_pilotage(
    pilot_run_id: int,
    db: Session = Depends(get_db),
    user=Depends(require_roles("admin_ecoe", "coeditor_docente")),
):
    run = db.get(PilotRun, pilot_run_id)
    if not run:
        raise HTTPException(status_code=404, detail="Pilotaje no encontrado")
    ensure_event_access(db, user, run.ecoe_event_id,
                        RoleCode.admin_ecoe.value, RoleCode.coeditor_docente.value)
    run.archived = True
    db.add(run)
    db.commit()
    return {"archived": True}


@router.delete("/pilotage/{pilot_run_id}")
def delete_pilotage(
    pilot_run_id: int,
    db: Session = Depends(get_db),
    user=Depends(require_roles("admin_ecoe")),
):
    run = db.get(PilotRun, pilot_run_id)
    if not run:
        raise HTTPException(status_code=404, detail="Pilotaje no encontrado")
    ensure_event_access(db, user, run.ecoe_event_id, RoleCode.admin_ecoe.value)
    db.delete(run)
    db.commit()
    return {"deleted": True}
