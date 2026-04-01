from pathlib import Path

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from fastapi.responses import FileResponse, Response
from sqlalchemy import func, select
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
    StationBank,
    StationCheckIn,
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
    ECOETimingUpdate,
    ECOEEventUpdate,
    EvaluatorSubmission,
    LoginRequest,
    PilotRunCreate,
    SimulatedPatientCreate,
    StaffCreate,
    StationCreate,
    StationBankCreate,
    StationBankStatusUpdate,
    StationTemplateCreate,
    StudentCreate,
    StudentAccessRequest,
    StudentStatusUpdate,
    StudentResponseCreate,
    StaffUpdate,
    StationCheckInCreate,
    TimerAction,
    Token,
)
from app.services.auth import login_user
from app.services.dependencies import get_current_user, require_roles
from app.services.ecoe import (
    build_dashboard,
    compute_ecoe_validation,
    compute_results,
    export_contingency_pdf,
    export_results_excel,
    persist_results,
    update_ecoe_status,
)
from app.utils.files import parse_tabular_file

router = APIRouter()


def normalize_rut(value: str | None) -> str:
    return str(value or "").strip().lower()


def next_student_ecoe_number(db: Session, ecoe_event_id: int) -> str:
    numbers = db.scalars(select(Student.ecoe_number).where(Student.ecoe_event_id == ecoe_event_id)).all()
    numeric_values = []
    widths = []
    for value in numbers:
        text = str(value or "").strip()
        if text.isdigit():
            numeric_values.append(int(text))
            widths.append(len(text))

    next_value = (max(numeric_values) if numeric_values else 0) + 1
    width = max(3, max(widths, default=3), len(str(next_value)))
    return str(next_value).zfill(width)


def normalize_email(value: str | None) -> str:
    return str(value or "").strip().lower()


def normalize_ecoe_lookup(value: str | None) -> str:
    text = str(value or "").strip()
    if not text:
        return ""
    if text.isdigit():
        return str(int(text))
    return text.lower()


def normalize_station_ids(raw_station_ids: list[int] | None) -> list[int]:
    station_ids = [station_id for station_id in (raw_station_ids or []) if station_id]
    return station_ids[:1]


def ensure_primary_station_assignment(staff: StaffAssignment | None) -> tuple[list[int], bool]:
    if not staff:
        return [], False
    normalized_station_ids = normalize_station_ids(staff.station_ids)
    changed = normalized_station_ids != (staff.station_ids or [])
    if changed:
        staff.station_ids = normalized_station_ids
    return normalized_station_ids, changed


def get_active_checkin(
    db: Session,
    ecoe_event_id: int,
    station_id: int,
    student_id: int,
    checkin_id: int | None = None,
) -> StationCheckIn | None:
    statement = select(StationCheckIn).where(
        StationCheckIn.ecoe_event_id == ecoe_event_id,
        StationCheckIn.station_id == station_id,
        StationCheckIn.student_id == student_id,
        StationCheckIn.status == "confirmado",
    )
    if checkin_id is not None:
        statement = statement.where(StationCheckIn.id == checkin_id)
    return db.scalar(statement.order_by(StationCheckIn.confirmed_at.desc(), StationCheckIn.id.desc()))


def find_student_by_ecoe_number(
    db: Session,
    ecoe_event_id: int,
    ecoe_number: str,
    *,
    active_only: bool = True,
) -> Student | None:
    lookup = normalize_ecoe_lookup(ecoe_number)
    if not lookup:
        return None

    statement = select(Student).where(Student.ecoe_event_id == ecoe_event_id)
    if active_only:
        statement = statement.where(Student.is_active.is_(True))

    students = db.scalars(statement.order_by(Student.id.asc())).all()
    for student in students:
        if normalize_ecoe_lookup(student.ecoe_number) == lookup:
            return student
    return None


def serialize_assessment_tool(db: Session, tool_id: int | None) -> dict | None:
    if not tool_id:
        return None
    tool = db.get(AssessmentTool, tool_id)
    if not tool:
        return None
    items = db.scalars(
        select(AssessmentItem)
        .where(AssessmentItem.tool_id == tool.id)
        .order_by(AssessmentItem.order_index.asc(), AssessmentItem.id.asc())
    ).all()
    return {
        "id": tool.id,
        "name": tool.name,
        "tool_type": tool.tool_type,
        "max_score": tool.max_score,
        "free_observation": tool.free_observation,
        "items": [
            {
                "id": item.id,
                "label": item.label,
                "score_per_item": item.score_per_item,
                "order_index": item.order_index,
            }
            for item in items
        ],
    }


def serialize_media_asset(asset: MediaAsset) -> dict:
    return {
        "id": asset.id,
        "filename": asset.filename,
        "original_name": asset.original_name,
        "content_type": asset.content_type,
        "target_viewer": asset.target_viewer,
        "station_id": asset.station_id,
        "file_url": f"/backend/api/media/file/{asset.id}",
    }


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


@router.get("/ecoe/{ecoe_event_id}", response_model=ECOEEventRead)
def get_ecoe(ecoe_event_id: int, db: Session = Depends(get_db), user=Depends(get_current_user)):
    ecoe_event = db.get(ECOEEvent, ecoe_event_id)
    if not ecoe_event:
        raise HTTPException(status_code=404, detail="ECOE no encontrado")
    return ecoe_event


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


@router.patch("/ecoe/{ecoe_event_id}/timing", response_model=ECOEEventRead)
def update_ecoe_timing(
    ecoe_event_id: int,
    payload: ECOETimingUpdate,
    db: Session = Depends(get_db),
    user=Depends(require_roles("creador_ecoe", "coeditor_docente")),
):
    ecoe_event = db.get(ECOEEvent, ecoe_event_id)
    if not ecoe_event:
        raise HTTPException(status_code=404, detail="ECOE no encontrado")

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
    return db.scalars(
        select(Student)
        .where(Student.ecoe_event_id == ecoe_event_id)
        .order_by(Student.is_active.desc(), Student.ecoe_number.asc(), Student.id.asc())
    ).all()


@router.post("/students")
def create_student(
    payload: StudentCreate,
    db: Session = Depends(get_db),
    user=Depends(require_roles("creador_ecoe", "coeditor_docente", "coordinador_operativo")),
):
    rut = normalize_rut(payload.rut)
    existing = db.scalar(
        select(Student).where(
            Student.ecoe_event_id == payload.ecoe_event_id,
            Student.rut == rut,
        )
    )
    if existing:
        raise HTTPException(status_code=400, detail="Ya existe un estudiante con ese RUT en este ECOE")

    student = Student(
        **payload.model_dump(),
        rut=rut,
        ecoe_number=next_student_ecoe_number(db, payload.ecoe_event_id),
    )
    db.add(student)
    db.commit()
    db.refresh(student)
    return student


@router.patch("/students/{student_id}/status")
def update_student_status(
    student_id: int,
    payload: StudentStatusUpdate,
    db: Session = Depends(get_db),
    user=Depends(require_roles("creador_ecoe", "coeditor_docente", "coordinador_operativo")),
):
    student = db.get(Student, student_id)
    if not student:
        raise HTTPException(status_code=404, detail="Estudiante no encontrado")
    student.is_active = payload.is_active
    db.add(student)
    db.commit()
    db.refresh(student)
    return student


@router.delete("/students/{student_id}")
def delete_student(
    student_id: int,
    db: Session = Depends(get_db),
    user=Depends(require_roles("creador_ecoe", "coeditor_docente")),
):
    student = db.get(Student, student_id)
    if not student:
        raise HTTPException(status_code=404, detail="Estudiante no encontrado")
    db.delete(student)
    db.commit()
    return {"deleted": True}


@router.post("/students/{ecoe_event_id}/deduplicate-rut")
def deduplicate_students_by_rut(
    ecoe_event_id: int,
    db: Session = Depends(get_db),
    user=Depends(require_roles("creador_ecoe", "coeditor_docente")),
):
    students = db.scalars(
        select(Student)
        .where(Student.ecoe_event_id == ecoe_event_id)
        .order_by(Student.created_at.asc(), Student.id.asc())
    ).all()

    seen_ruts: set[str] = set()
    removed = 0
    for student in students:
        rut = normalize_rut(student.rut)
        if not rut:
            continue
        if rut in seen_ruts:
            db.delete(student)
            removed += 1
            continue
        seen_ruts.add(rut)

    db.commit()
    return {"removed": removed}


@router.post("/students/{ecoe_event_id}/renumber")
def renumber_students(
    ecoe_event_id: int,
    db: Session = Depends(get_db),
    user=Depends(require_roles("creador_ecoe", "coeditor_docente")),
):
    students = db.scalars(
        select(Student)
        .where(Student.ecoe_event_id == ecoe_event_id)
        .order_by(Student.created_at.asc(), Student.id.asc())
    ).all()

    if not students:
        return {"updated": 0}

    width = max(3, len(str(len(students))))
    for index, student in enumerate(students, start=1):
        student.ecoe_number = str(index).zfill(width)
        db.add(student)

    db.commit()
    return {"updated": len(students)}


@router.post("/students/import")
async def import_students(
    ecoe_event_id: int,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    user=Depends(require_roles("creador_ecoe", "coeditor_docente")),
):
    rows = await parse_tabular_file(file)
    imported = []
    skipped = 0
    next_number = next_student_ecoe_number(db, ecoe_event_id)
    next_numeric_value = int(next_number)
    next_width = len(next_number)
    existing_ruts = {
        normalize_rut(rut)
        for rut in db.scalars(select(Student.rut).where(Student.ecoe_event_id == ecoe_event_id)).all()
    }
    for row in rows:
        rut = normalize_rut(row.get("rut"))
        if not rut or rut in existing_ruts:
            skipped += 1
            continue

        student = Student(
            ecoe_event_id=ecoe_event_id,
            name=row.get("nombre", row.get("name", "")),
            last_name=row.get("apellidos", row.get("last_name", "")),
            rut=rut,
            email=row.get("correo", row.get("email", "")),
            ecoe_number=str(next_numeric_value).zfill(next_width),
            group_name=row.get("grupo", row.get("group_name", "Grupo 1")),
            circuit_name=row.get("circuito", row.get("circuit_name", "Circuito A")),
        )
        db.add(student)
        imported.append(student)
        existing_ruts.add(rut)
        next_numeric_value += 1
    db.commit()
    return {"imported": len(imported), "skipped": skipped}


@router.get("/staff/{ecoe_event_id}")
def list_staff(ecoe_event_id: int, db: Session = Depends(get_db), user=Depends(get_current_user)):
    staff_rows = db.scalars(
        select(StaffAssignment)
        .where(StaffAssignment.ecoe_event_id == ecoe_event_id)
        .order_by(StaffAssignment.last_name.asc(), StaffAssignment.name.asc(), StaffAssignment.id.asc())
    ).all()
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
    return staff_rows


@router.post("/staff")
def create_staff(
    payload: StaffCreate,
    db: Session = Depends(get_db),
    user=Depends(require_roles("creador_ecoe", "coeditor_docente", "coordinador_operativo")),
):
    email = normalize_email(payload.email)
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
    if station_ids:
        station = db.get(Station, station_ids[0])
        if not station or station.ecoe_event_id != payload.ecoe_event_id:
            raise HTTPException(status_code=400, detail="La estacion asignada no pertenece a este ECOE")

    staff = StaffAssignment(**payload.model_dump(), email=email, station_ids=station_ids)
    db.add(staff)
    db.commit()
    db.refresh(staff)
    return staff


@router.patch("/staff/{staff_id}")
def update_staff(
    staff_id: int,
    payload: StaffUpdate,
    db: Session = Depends(get_db),
    user=Depends(require_roles("creador_ecoe", "coeditor_docente", "coordinador_operativo")),
):
    staff = db.get(StaffAssignment, staff_id)
    if not staff:
        raise HTTPException(status_code=404, detail="Evaluador o colaborador no encontrado")
    station_ids = normalize_station_ids(payload.station_ids)
    if station_ids:
        station = db.get(Station, station_ids[0])
        if not station or station.ecoe_event_id != staff.ecoe_event_id:
            raise HTTPException(status_code=400, detail="La estacion asignada no pertenece a este ECOE")
    staff.role_code = payload.role_code
    staff.station_ids = station_ids
    db.add(staff)
    db.commit()
    db.refresh(staff)
    return staff


@router.delete("/staff/{staff_id}")
def delete_staff(
    staff_id: int,
    db: Session = Depends(get_db),
    user=Depends(require_roles("creador_ecoe", "coeditor_docente")),
):
    staff = db.get(StaffAssignment, staff_id)
    if not staff:
        raise HTTPException(status_code=404, detail="Evaluador o colaborador no encontrado")
    db.delete(staff)
    db.commit()
    return {"deleted": True}


@router.post("/staff/{ecoe_event_id}/deduplicate-email")
def deduplicate_staff_by_email(
    ecoe_event_id: int,
    db: Session = Depends(get_db),
    user=Depends(require_roles("creador_ecoe", "coeditor_docente")),
):
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
    user=Depends(require_roles("creador_ecoe", "coeditor_docente")),
):
    rows = await parse_tabular_file(file)
    imported = 0
    skipped = 0
    existing_emails = {
        normalize_email(email)
        for email in db.scalars(
            select(StaffAssignment.email).where(StaffAssignment.ecoe_event_id == ecoe_event_id)
        ).all()
    }
    for row in rows:
        email = normalize_email(row.get("correo", row.get("email", "")))
        if not email or email in existing_emails:
            skipped += 1
            continue
        db.add(
            StaffAssignment(
                ecoe_event_id=ecoe_event_id,
                name=row.get("nombre", row.get("name", "")),
                last_name=row.get("apellidos", row.get("last_name", "")),
                email=email,
                role_code=row.get("rol", row.get("role_code", "evaluador")),
                station_ids=[],
            )
        )
        imported += 1
        existing_emails.add(email)
    db.commit()
    return {"imported": imported, "skipped": skipped}


@router.get("/evaluator/context/{ecoe_event_id}")
def evaluator_context(
    ecoe_event_id: int,
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
):
    assignment = db.scalar(
        select(StaffAssignment).where(
            StaffAssignment.ecoe_event_id == ecoe_event_id,
            StaffAssignment.email == normalize_email(user.email),
        )
    )
    assigned_station_ids, assignment_changed = ensure_primary_station_assignment(assignment)
    if assignment and assignment_changed:
        db.add(assignment)
        db.commit()
        db.refresh(assignment)
    assigned_stations = (
        db.scalars(
            select(Station)
            .where(Station.ecoe_event_id == ecoe_event_id, Station.id.in_(assigned_station_ids))
            .order_by(Station.station_number.asc())
        ).all()
        if assigned_station_ids
        else []
    )

    active_checkin = None
    if assigned_station_ids:
        active_checkin = db.scalar(
            select(StationCheckIn)
            .where(
                StationCheckIn.ecoe_event_id == ecoe_event_id,
                StationCheckIn.station_id.in_(assigned_station_ids),
                StationCheckIn.status == "confirmado",
            )
            .order_by(StationCheckIn.confirmed_at.desc(), StationCheckIn.id.desc())
        )

    student = db.get(Student, active_checkin.student_id) if active_checkin else None
    station = db.get(Station, active_checkin.station_id) if active_checkin else None
    assessment_tool = serialize_assessment_tool(db, station.assessment_tool_id if station else None)
    evaluator_submission_exists = False
    student_response_exists = False
    if active_checkin and student and station:
        evaluator_submission_exists = db.scalar(
            select(func.count())
            .select_from(EvaluatorRecord)
            .where(
                EvaluatorRecord.ecoe_event_id == ecoe_event_id,
                EvaluatorRecord.station_id == active_checkin.station_id,
                EvaluatorRecord.student_id == active_checkin.student_id,
            )
        ) > 0
        student_response_exists = db.scalar(
            select(func.count())
            .select_from(StudentResponse)
            .where(
                StudentResponse.ecoe_event_id == ecoe_event_id,
                StudentResponse.station_id == active_checkin.station_id,
                StudentResponse.student_id == active_checkin.student_id,
            )
        ) > 0

    return {
        "assignment": assignment,
        "stations": assigned_stations,
        "active_checkin": {
            "id": active_checkin.id,
            "station_id": active_checkin.station_id,
            "student_id": active_checkin.student_id,
            "status": active_checkin.status,
            "student_name": f"{student.name} {student.last_name}" if student else "",
            "student_ecoe_number": student.ecoe_number if student else "",
            "station_name": station.name if station else "",
            "station_number": station.station_number if station else "",
            "assessment_tool": assessment_tool,
            "confirmed_at": active_checkin.confirmed_at.isoformat(),
            "station_time_minutes": station.station_time_minutes if station else 0,
            "evaluator_submission_exists": evaluator_submission_exists,
            "student_response_exists": student_response_exists,
        }
        if active_checkin and student and station
        else None,
    }


@router.post("/station-checkins/confirm")
def confirm_station_checkin(
    payload: StationCheckInCreate,
    db: Session = Depends(get_db),
    user=Depends(require_roles("evaluador", "coordinador_operativo", "creador_ecoe")),
):
    station = db.get(Station, payload.station_id)
    if not station or station.ecoe_event_id != payload.ecoe_event_id:
        raise HTTPException(status_code=404, detail="Estacion no encontrada")

    if user.role.code == "evaluador":
        assignment = db.scalar(
            select(StaffAssignment).where(
                StaffAssignment.ecoe_event_id == payload.ecoe_event_id,
                StaffAssignment.email == normalize_email(user.email),
            )
        )
        assigned_station_ids, assignment_changed = ensure_primary_station_assignment(assignment)
        if assignment and assignment_changed:
            db.add(assignment)
            db.commit()
            db.refresh(assignment)
        if not assignment or payload.station_id not in assigned_station_ids:
            raise HTTPException(status_code=403, detail="No tienes esa estacion asignada")

    student = find_student_by_ecoe_number(
        db,
        payload.ecoe_event_id,
        payload.ecoe_number,
        active_only=True,
    )
    if not student:
        raise HTTPException(status_code=404, detail="No existe un estudiante activo con ese Numero ECOE")

    existing_station_checkins = db.scalars(
        select(StationCheckIn).where(
            StationCheckIn.ecoe_event_id == payload.ecoe_event_id,
            StationCheckIn.station_id == payload.station_id,
            StationCheckIn.status == "confirmado",
        )
    ).all()
    for item in existing_station_checkins:
        item.status = "cerrado"
        db.add(item)

    checkin = StationCheckIn(
        ecoe_event_id=payload.ecoe_event_id,
        station_id=payload.station_id,
        student_id=student.id,
        evaluator_email=normalize_email(user.email),
        evaluator_name=user.full_name,
        status="confirmado",
    )
    db.add(checkin)
    db.commit()
    db.refresh(checkin)
    return {
        "checkin_id": checkin.id,
        "student_id": student.id,
        "student_name": f"{student.name} {student.last_name}",
        "student_ecoe_number": student.ecoe_number,
        "station_id": station.id,
        "station_name": station.name,
        "station_number": station.station_number,
        "assessment_tool": serialize_assessment_tool(db, station.assessment_tool_id),
        "station_time_minutes": station.station_time_minutes,
        "confirmed_at": checkin.confirmed_at.isoformat(),
        "evaluator_submission_exists": False,
        "student_response_exists": False,
    }


@router.post("/student/access")
def student_access_context(
    payload: StudentAccessRequest,
    db: Session = Depends(get_db),
    user=Depends(require_roles("estudiante", "coordinador_operativo", "creador_ecoe")),
):
    student = find_student_by_ecoe_number(
        db,
        payload.ecoe_event_id,
        payload.ecoe_number,
        active_only=True,
    )
    if not student:
        raise HTTPException(status_code=404, detail="No existe un estudiante activo con ese Numero ECOE")

    checkin = db.scalar(
        select(StationCheckIn)
        .where(
            StationCheckIn.ecoe_event_id == payload.ecoe_event_id,
            StationCheckIn.student_id == student.id,
            StationCheckIn.status == "confirmado",
        )
        .order_by(StationCheckIn.confirmed_at.desc(), StationCheckIn.id.desc())
    )
    if not checkin:
        raise HTTPException(status_code=400, detail="Tu ingreso aun no ha sido confirmado por el evaluador")

    station = db.get(Station, checkin.station_id)
    student_media_assets = db.scalars(
        select(MediaAsset)
        .where(
            MediaAsset.station_id == station.id,
            MediaAsset.target_viewer == "estudiante",
        )
        .order_by(MediaAsset.created_at.asc(), MediaAsset.id.asc())
    ).all()
    student_response_exists = db.scalar(
        select(func.count())
        .select_from(StudentResponse)
        .where(
            StudentResponse.ecoe_event_id == payload.ecoe_event_id,
            StudentResponse.station_id == checkin.station_id,
            StudentResponse.student_id == student.id,
        )
    ) > 0
    return {
        "checkin_id": checkin.id,
        "student_id": student.id,
        "student_name": f"{student.name} {student.last_name}",
        "student_ecoe_number": student.ecoe_number,
        "station_id": station.id,
        "station_name": station.name,
        "station_number": station.station_number,
        "student_activity": station.student_activity,
        "student_station_instruction": station.student_station_instruction,
        "student_form_definition": station.student_form_definition,
        "media_assets": [serialize_media_asset(asset) for asset in student_media_assets],
        "station_time_minutes": station.station_time_minutes,
        "confirmed_at": checkin.confirmed_at.isoformat(),
        "student_response_exists": student_response_exists,
    }


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


@router.get("/station-bank")
def list_station_bank(db: Session = Depends(get_db), user=Depends(get_current_user)):
    return db.scalars(select(StationBank).order_by(StationBank.updated_at.desc(), StationBank.id.desc())).all()


@router.post("/station-bank")
def create_station_bank(
    payload: StationBankCreate,
    db: Session = Depends(get_db),
    user=Depends(require_roles("creador_ecoe", "coeditor_docente")),
):
    bank_station = StationBank(**payload.model_dump())
    db.add(bank_station)
    db.commit()
    db.refresh(bank_station)
    return bank_station


@router.put("/station-bank/{bank_station_id}")
def update_station_bank(
    bank_station_id: int,
    payload: StationBankCreate,
    db: Session = Depends(get_db),
    user=Depends(require_roles("creador_ecoe", "coeditor_docente")),
):
    bank_station = db.get(StationBank, bank_station_id)
    if not bank_station:
        raise HTTPException(status_code=404, detail="Estacion de banco no encontrada")

    for field, value in payload.model_dump().items():
        setattr(bank_station, field, value)
    db.add(bank_station)
    db.commit()
    db.refresh(bank_station)
    return bank_station


@router.patch("/station-bank/{bank_station_id}/status")
def update_station_bank_status(
    bank_station_id: int,
    payload: StationBankStatusUpdate,
    db: Session = Depends(get_db),
    user=Depends(require_roles("creador_ecoe", "coeditor_docente")),
):
    bank_station = db.get(StationBank, bank_station_id)
    if not bank_station:
        raise HTTPException(status_code=404, detail="Estacion de banco no encontrada")

    bank_station.status = payload.status
    db.add(bank_station)
    db.commit()
    db.refresh(bank_station)
    return bank_station


@router.get("/stations/{ecoe_event_id}")
def list_stations(ecoe_event_id: int, db: Session = Depends(get_db), user=Depends(get_current_user)):
    return db.scalars(select(Station).where(Station.ecoe_event_id == ecoe_event_id)).all()


@router.post("/stations")
def create_station(
    payload: StationCreate,
    db: Session = Depends(get_db),
    user=Depends(require_roles("creador_ecoe", "coeditor_docente")),
):
    ecoe_event = db.get(ECOEEvent, payload.ecoe_event_id)
    if not ecoe_event:
        raise HTTPException(status_code=404, detail="ECOE no encontrado")

    next_station_number = (
        db.scalar(
            select(func.max(Station.station_number)).where(
                Station.ecoe_event_id == payload.ecoe_event_id
            )
        )
        or 0
    ) + 1

    station = Station(
        **payload.model_dump(),
        station_number=next_station_number,
        station_time_minutes=ecoe_event.station_time_minutes,
        transition_time_minutes=ecoe_event.transition_time_minutes,
    )
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
    ecoe_event = db.get(ECOEEvent, payload.ecoe_event_id)
    if not ecoe_event:
        raise HTTPException(status_code=404, detail="ECOE no encontrado")

    for field, value in payload.model_dump().items():
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


@router.delete("/media/{asset_id}")
def delete_media(
    asset_id: int,
    db: Session = Depends(get_db),
    user=Depends(require_roles("creador_ecoe", "coeditor_docente")),
):
    asset = db.get(MediaAsset, asset_id)
    if not asset:
        raise HTTPException(status_code=404, detail="Archivo no encontrado")

    file_path = Path(asset.file_path)
    if file_path.exists():
        file_path.unlink()

    db.delete(asset)
    db.commit()
    return {"deleted": True, "asset_id": asset_id}


@router.get("/media/file/{asset_id}")
def get_media_file(asset_id: int, db: Session = Depends(get_db), user=Depends(get_current_user)):
    asset = db.get(MediaAsset, asset_id)
    if not asset:
        raise HTTPException(status_code=404, detail="Archivo no encontrado")
    return FileResponse(
        path=asset.file_path,
        media_type=asset.content_type,
        filename=asset.original_name,
    )


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
    ecoe_event = db.get(ECOEEvent, payload.ecoe_event_id)
    if not ecoe_event:
        raise HTTPException(status_code=404, detail="ECOE no encontrado")

    validation = compute_ecoe_validation(db, ecoe_event)
    if not validation["can_pilot"]:
        raise HTTPException(
            status_code=400,
            detail="El ECOE aun no cumple condiciones minimas para pilotaje.",
        )

    scope = payload.scope.strip().lower()
    if scope not in {"estacion", "circuito_completo"}:
        raise HTTPException(status_code=400, detail="Alcance de pilotaje no permitido.")

    event_station_ids = set(
        db.scalars(select(Station.id).where(Station.ecoe_event_id == payload.ecoe_event_id)).all()
    )

    if scope == "estacion":
        if len(payload.station_ids) != 1:
            raise HTTPException(
                status_code=400,
                detail="Para pilotar una estacion debes seleccionar exactamente una estacion.",
            )
        station_id = int(payload.station_ids[0])
        if station_id not in event_station_ids:
            raise HTTPException(
                status_code=400,
                detail="La estacion seleccionada no pertenece a este ECOE.",
            )
        station_issue = next(
            (
                issue
                for issue in validation["station_issues"]
                if int(issue["station_id"]) == station_id
            ),
            None,
        )
        if not station_issue or not station_issue["ready_for_pilot"]:
            raise HTTPException(
                status_code=400,
                detail="La estacion seleccionada aun no esta lista para pilotaje individual.",
            )
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
            raise HTTPException(
                status_code=400,
                detail="No puedes pilotear el circuito completo sin haber realizado antes al menos un pilotaje individual de estacion.",
            )
        station_ids = list(event_station_ids)

    pilot_run = PilotRun(
        ecoe_event_id=payload.ecoe_event_id,
        name=payload.name,
        scope=scope,
    )
    db.add(pilot_run)
    db.flush()
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
            station_time_seconds=max(1, round(ecoe_event.station_time_minutes * 60)),
            transition_time_seconds=max(0, round(ecoe_event.transition_time_minutes * 60)),
            remaining_seconds=max(1, round(ecoe_event.station_time_minutes * 60)),
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
    checkin = get_active_checkin(
        db,
        payload.ecoe_event_id,
        payload.station_id,
        payload.student_id,
        payload.checkin_id,
    )
    if not checkin:
        raise HTTPException(
            status_code=400,
            detail="La evaluacion solo puede guardarse para un estudiante previamente confirmado en esta estacion",
        )
    existing_record = db.scalar(
        select(EvaluatorRecord).where(
            EvaluatorRecord.ecoe_event_id == payload.ecoe_event_id,
            EvaluatorRecord.station_id == payload.station_id,
            EvaluatorRecord.student_id == payload.student_id,
        )
    )
    if existing_record:
        raise HTTPException(
            status_code=400,
            detail="La evaluacion de esta estacion ya fue enviada y no puede modificarse durante el ECOE",
        )
    record = EvaluatorRecord(**payload.model_dump(exclude={"checkin_id"}))
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
    checkin = get_active_checkin(
        db,
        payload.ecoe_event_id,
        payload.station_id,
        payload.student_id,
        payload.checkin_id,
    )
    if not checkin:
        raise HTTPException(
            status_code=400,
            detail="La respuesta solo puede enviarse despues de que el evaluador confirme tu ingreso a la estacion",
        )
    existing_response = db.scalar(
        select(StudentResponse).where(
            StudentResponse.ecoe_event_id == payload.ecoe_event_id,
            StudentResponse.station_id == payload.station_id,
            StudentResponse.student_id == payload.student_id,
        )
    )
    if existing_response:
        raise HTTPException(
            status_code=400,
            detail="La respuesta de esta estacion ya fue enviada y no puede reemplazarse",
        )
    response = StudentResponse(**payload.model_dump(exclude={"checkin_id"}))
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
