from pathlib import Path

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from fastapi.responses import Response
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.entities import (
    AssessmentItem,
    AssessmentTool,
    AuditLog,
    ECOEEvent,
    EvaluatorRecord,
    Incident,
    LiveSession,
    MediaAsset,
    PilotRecord,
    PilotRun,
    SimulatedPatient,
    StaffAssignment,
    Station,
    StationTemplate,
    Student,
    StudentResponse,
)
from app.models.enums import ECOEStatus, SessionMode, StationStatus
from app.schemas.common import (
    AssessmentToolCreate,
    DashboardSummary,
    ECOEEventCreate,
    ECOEEventRead,
    ECOEEventUpdate,
    EvaluatorSubmission,
    LoginRequest,
    PilotRunCreate,
    SimulatedPatientCreate,
    StaffCreate,
    StationCreate,
    StationTemplateCreate,
    StudentCreate,
    StudentResponseCreate,
    TimerAction,
    Token,
)
from app.services.auth import login_user
from app.services.dependencies import get_current_user, require_roles
from app.services.ecoe import (
    build_dashboard,
    compute_results,
    export_contingency_pdf,
    export_results_excel,
    persist_results,
    update_ecoe_status,
)
from app.utils.files import parse_tabular_file

router = APIRouter()


@router.post("/auth/login", response_model=Token)
def login(payload: LoginRequest, db: Session = Depends(get_db)):
    return login_user(db, payload.email, payload.password)


@router.get("/auth/me")
def me(user=Depends(get_current_user)):
    return {
        "id": user.id,
        "email": user.email,
        "full_name": user.full_name,
        "role": user.role.code,
    }


@router.get("/dashboard/{ecoe_event_id}", response_model=DashboardSummary)
def dashboard(ecoe_event_id: int, db: Session = Depends(get_db), user=Depends(get_current_user)):
    ecoe_event = db.get(ECOEEvent, ecoe_event_id)
    if not ecoe_event:
        raise HTTPException(status_code=404, detail="ECOE no encontrado")
    return build_dashboard(db, ecoe_event)


@router.get("/ecoe", response_model=list[ECOEEventRead])
def list_ecoe(db: Session = Depends(get_db), user=Depends(get_current_user)):
    return db.scalars(select(ECOEEvent).order_by(ECOEEvent.date.desc())).all()


@router.post("/ecoe", response_model=ECOEEventRead)
def create_ecoe(
    payload: ECOEEventCreate,
    db: Session = Depends(get_db),
    user=Depends(require_roles("creador_ecoe", "coeditor_docente")),
):
    ecoe_event = ECOEEvent(**payload.model_dump(), status=ECOEStatus.borrador.value)
    db.add(ecoe_event)
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
    ecoe_event = db.get(ECOEEvent, ecoe_event_id)
    if not ecoe_event:
        raise HTTPException(status_code=404, detail="ECOE no encontrado")
    for field, value in payload.model_dump(exclude={"status"}).items():
        setattr(ecoe_event, field, value)
    db.add(ecoe_event)
    db.commit()
    db.refresh(ecoe_event)
    try:
        return update_ecoe_status(db, ecoe_event, payload.status)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/ecoe/{ecoe_event_id}/duplicate", response_model=ECOEEventRead)
def duplicate_ecoe(
    ecoe_event_id: int,
    db: Session = Depends(get_db),
    user=Depends(require_roles("creador_ecoe")),
):
    ecoe_event = db.get(ECOEEvent, ecoe_event_id)
    if not ecoe_event:
        raise HTTPException(status_code=404, detail="ECOE no encontrado")
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
    db.commit()
    db.refresh(clone)
    return clone


@router.get("/students/{ecoe_event_id}")
def list_students(ecoe_event_id: int, db: Session = Depends(get_db), user=Depends(get_current_user)):
    return db.scalars(select(Student).where(Student.ecoe_event_id == ecoe_event_id)).all()


@router.post("/students")
def create_student(
    payload: StudentCreate,
    db: Session = Depends(get_db),
    user=Depends(require_roles("creador_ecoe", "coeditor_docente", "coordinador_operativo")),
):
    student = Student(**payload.model_dump())
    db.add(student)
    db.commit()
    db.refresh(student)
    return student


@router.post("/students/import")
async def import_students(
    ecoe_event_id: int,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    user=Depends(require_roles("creador_ecoe", "coeditor_docente")),
):
    rows = await parse_tabular_file(file)
    imported = []
    for row in rows:
        student = Student(
            ecoe_event_id=ecoe_event_id,
            name=row.get("nombre", row.get("name", "")),
            last_name=row.get("apellidos", row.get("last_name", "")),
            rut=row.get("rut", ""),
            email=row.get("correo", row.get("email", "")),
            ecoe_number=str(row.get("numero_ecoe", row.get("ecoe_number", ""))),
            group_name=row.get("grupo", row.get("group_name", "Grupo 1")),
            circuit_name=row.get("circuito", row.get("circuit_name", "Circuito A")),
        )
        db.add(student)
        imported.append(student)
    db.commit()
    return {"imported": len(imported)}


@router.get("/staff/{ecoe_event_id}")
def list_staff(ecoe_event_id: int, db: Session = Depends(get_db), user=Depends(get_current_user)):
    return db.scalars(
        select(StaffAssignment).where(StaffAssignment.ecoe_event_id == ecoe_event_id)
    ).all()


@router.post("/staff")
def create_staff(
    payload: StaffCreate,
    db: Session = Depends(get_db),
    user=Depends(require_roles("creador_ecoe", "coeditor_docente", "coordinador_operativo")),
):
    staff = StaffAssignment(**payload.model_dump())
    db.add(staff)
    db.commit()
    db.refresh(staff)
    return staff


@router.post("/staff/import")
async def import_staff(
    ecoe_event_id: int,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    user=Depends(require_roles("creador_ecoe", "coeditor_docente")),
):
    rows = await parse_tabular_file(file)
    imported = 0
    for row in rows:
        db.add(
            StaffAssignment(
                ecoe_event_id=ecoe_event_id,
                name=row.get("nombre", row.get("name", "")),
                last_name=row.get("apellidos", row.get("last_name", "")),
                email=row.get("correo", row.get("email", "")),
                role_code=row.get("rol", row.get("role_code", "evaluador")),
                station_ids=[],
            )
        )
        imported += 1
    db.commit()
    return {"imported": imported}


@router.get("/templates")
def list_templates(db: Session = Depends(get_db), user=Depends(get_current_user)):
    return db.scalars(select(StationTemplate)).all()


@router.post("/templates")
def create_template(
    payload: StationTemplateCreate,
    db: Session = Depends(get_db),
    user=Depends(require_roles("creador_ecoe", "coeditor_docente")),
):
    template = StationTemplate(**payload.model_dump())
    db.add(template)
    db.commit()
    db.refresh(template)
    return template


@router.get("/instruments")
def list_instruments(db: Session = Depends(get_db), user=Depends(get_current_user)):
    return db.scalars(select(AssessmentTool)).all()


@router.post("/instruments")
def create_instrument(
    payload: AssessmentToolCreate,
    db: Session = Depends(get_db),
    user=Depends(require_roles("creador_ecoe", "coeditor_docente")),
):
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


@router.get("/simulated-patients")
def list_patients(db: Session = Depends(get_db), user=Depends(get_current_user)):
    return db.scalars(select(SimulatedPatient)).all()


@router.post("/simulated-patients")
def create_patient(
    payload: SimulatedPatientCreate,
    db: Session = Depends(get_db),
    user=Depends(require_roles("creador_ecoe", "coeditor_docente")),
):
    patient = SimulatedPatient(**payload.model_dump())
    db.add(patient)
    db.commit()
    db.refresh(patient)
    return patient


@router.get("/stations/{ecoe_event_id}")
def list_stations(ecoe_event_id: int, db: Session = Depends(get_db), user=Depends(get_current_user)):
    return db.scalars(select(Station).where(Station.ecoe_event_id == ecoe_event_id)).all()


@router.post("/stations")
def create_station(
    payload: StationCreate,
    db: Session = Depends(get_db),
    user=Depends(require_roles("creador_ecoe", "coeditor_docente")),
):
    station = Station(**payload.model_dump())
    db.add(station)
    db.commit()
    db.refresh(station)
    return station


@router.put("/stations/{station_id}")
def update_station(
    station_id: int,
    payload: StationCreate,
    db: Session = Depends(get_db),
    user=Depends(require_roles("creador_ecoe", "coeditor_docente")),
):
    station = db.get(Station, station_id)
    if not station:
        raise HTTPException(status_code=404, detail="Estacion no encontrada")
    for field, value in payload.model_dump().items():
        setattr(station, field, value)
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


@router.post("/media/upload")
async def upload_media(
    ecoe_event_id: int,
    station_id: int | None = None,
    target_viewer: str = "estudiante",
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    user=Depends(require_roles("creador_ecoe", "coeditor_docente")),
):
    media_dir = Path("/app/storage/media")
    media_dir.mkdir(parents=True, exist_ok=True)
    content = await file.read()
    file_path = media_dir / file.filename
    file_path.write_bytes(content)
    asset = MediaAsset(
        filename=file.filename,
        original_name=file.filename,
        content_type=file.content_type or "application/octet-stream",
        file_path=str(file_path),
        target_viewer=target_viewer,
        station_id=station_id,
    )
    db.add(asset)
    db.commit()
    db.refresh(asset)
    return asset


@router.get("/media/{station_id}")
def list_media(station_id: int, db: Session = Depends(get_db), user=Depends(get_current_user)):
    return db.scalars(select(MediaAsset).where(MediaAsset.station_id == station_id)).all()


@router.get("/validation/{ecoe_event_id}")
def validation(ecoe_event_id: int, db: Session = Depends(get_db), user=Depends(get_current_user)):
    ecoe_event = db.get(ECOEEvent, ecoe_event_id)
    if not ecoe_event:
        raise HTTPException(status_code=404, detail="ECOE no encontrado")
    return build_dashboard(db, ecoe_event)["validation"]


@router.post("/pilotage")
def create_pilotage(
    payload: PilotRunCreate,
    db: Session = Depends(get_db),
    user=Depends(require_roles("creador_ecoe", "coeditor_docente", "coordinador_operativo")),
):
    pilot_run = PilotRun(
        ecoe_event_id=payload.ecoe_event_id,
        name=payload.name,
        scope=payload.scope,
    )
    db.add(pilot_run)
    db.flush()
    station_ids = payload.station_ids or list(
        db.scalars(select(Station.id).where(Station.ecoe_event_id == payload.ecoe_event_id)).all()
    )
    for station_id in station_ids:
        db.add(
            PilotRecord(
                pilot_run_id=pilot_run.id,
                station_id=station_id,
                payload={"status": "prueba"},
                is_test=True,
            )
        )
    db.commit()
    return pilot_run


@router.get("/pilotage/{ecoe_event_id}")
def list_pilotage(ecoe_event_id: int, db: Session = Depends(get_db), user=Depends(get_current_user)):
    return db.scalars(select(PilotRun).where(PilotRun.ecoe_event_id == ecoe_event_id)).all()


@router.post("/pilotage/{pilot_run_id}/archive")
def archive_pilotage(
    pilot_run_id: int,
    db: Session = Depends(get_db),
    user=Depends(require_roles("creador_ecoe", "coeditor_docente")),
):
    run = db.get(PilotRun, pilot_run_id)
    if not run:
        raise HTTPException(status_code=404, detail="Pilotaje no encontrado")
    run.archived = True
    db.add(run)
    db.commit()
    return {"archived": True}


@router.delete("/pilotage/{pilot_run_id}")
def delete_pilotage(
    pilot_run_id: int,
    db: Session = Depends(get_db),
    user=Depends(require_roles("creador_ecoe")),
):
    run = db.get(PilotRun, pilot_run_id)
    if not run:
        raise HTTPException(status_code=404, detail="Pilotaje no encontrado")
    db.delete(run)
    db.commit()
    return {"deleted": True}


@router.get("/live/{ecoe_event_id}")
def get_live_panel(ecoe_event_id: int, db: Session = Depends(get_db), user=Depends(get_current_user)):
    session = db.scalar(select(LiveSession).where(LiveSession.ecoe_event_id == ecoe_event_id).limit(1))
    if not session:
        raise HTTPException(status_code=404, detail="Sesion en vivo no encontrada")
    return session


@router.post("/live/control")
def control_timer(
    payload: TimerAction,
    db: Session = Depends(get_db),
    user=Depends(require_roles("creador_ecoe", "coordinador_operativo", "cronometrador")),
):
    session = db.scalar(
        select(LiveSession).where(LiveSession.ecoe_event_id == payload.ecoe_event_id).limit(1)
    )
    if not session:
        ecoe_event = db.get(ECOEEvent, payload.ecoe_event_id)
        session = LiveSession(
            ecoe_event_id=payload.ecoe_event_id,
            station_time_seconds=ecoe_event.station_time_minutes * 60,
            transition_time_seconds=ecoe_event.transition_time_minutes * 60,
            remaining_seconds=ecoe_event.station_time_minutes * 60,
        )
        db.add(session)
        db.flush()
    if payload.action == "start":
        session.status = "running"
        session.remaining_seconds = session.station_time_seconds
    elif payload.action == "pause":
        session.status = "paused"
    elif payload.action == "resume":
        session.status = "running"
    elif payload.action == "reset":
        session.status = "ready"
        session.current_station_index = 1
        session.remaining_seconds = session.station_time_seconds
    elif payload.action == "next_transition":
        session.status = "transition"
        session.remaining_seconds = session.transition_time_seconds
        session.current_station_index += 1
    else:
        raise HTTPException(status_code=400, detail="Accion no soportada")
    db.add(session)
    db.commit()
    db.refresh(session)
    return session


@router.post("/evaluator/submit")
def submit_evaluator_record(
    payload: EvaluatorSubmission,
    db: Session = Depends(get_db),
    user=Depends(require_roles("evaluador", "coordinador_operativo", "creador_ecoe")),
):
    record = EvaluatorRecord(**payload.model_dump())
    db.add(record)
    db.add(
        AuditLog(
            user_email=user.email,
            action="submit_evaluation",
            target_type="EvaluatorRecord",
            target_id="new",
            payload=payload.model_dump(),
        )
    )
    db.commit()
    db.refresh(record)
    return {"saved": True, "record_id": record.id}


@router.post("/student/submit")
def submit_student_response(
    payload: StudentResponseCreate,
    db: Session = Depends(get_db),
    user=Depends(require_roles("estudiante", "coordinador_operativo", "creador_ecoe")),
):
    response = StudentResponse(**payload.model_dump())
    db.add(response)
    db.commit()
    db.refresh(response)
    return {"saved": True, "response_id": response.id}


@router.get("/results/{ecoe_event_id}")
def get_results(ecoe_event_id: int, db: Session = Depends(get_db), user=Depends(get_current_user)):
    return {"results": persist_results(db, ecoe_event_id)}


@router.get("/results/{ecoe_event_id}/export/excel")
def export_excel(ecoe_event_id: int, db: Session = Depends(get_db), user=Depends(get_current_user)):
    content = export_results_excel(db, ecoe_event_id)
    return Response(
        content=content,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="ecoe-{ecoe_event_id}.xlsx"'},
    )


@router.get("/results/{ecoe_event_id}/export/pdf")
def export_pdf(
    ecoe_event_id: int,
    station_id: int | None = None,
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
):
    content = export_contingency_pdf(db, ecoe_event_id, station_id)
    return Response(
        content=content,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="contingencia-{ecoe_event_id}.pdf"'},
    )


@router.get("/incidents/{ecoe_event_id}")
def list_incidents(ecoe_event_id: int, db: Session = Depends(get_db), user=Depends(get_current_user)):
    return db.scalars(select(Incident).where(Incident.ecoe_event_id == ecoe_event_id)).all()
