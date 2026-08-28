"""Manual grading of student form responses (content managers and correctores)."""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.entities import AuditLog, StaffAssignment, Station, Student, StudentResponse
from app.models.enums import RoleCode
from app.schemas.common import ManualGradeSubmit
from app.services.authorization import ensure_event_access
from app.services.dependencies import require_roles
from app.services.grading import apply_manual_scores, pending_manual_keys
from app.utils.helpers import normalize_email

router = APIRouter()

# admin_ecoe / coeditor_docente corrigen cualquier estación del evento; un
# `corrector` solo las estaciones de evaluación diferida que tiene asignadas.
GRADING_ROLES = (
    RoleCode.admin_ecoe.value,
    RoleCode.coeditor_docente.value,
    RoleCode.corrector.value,
)
FULL_GRADING_ROLES = {RoleCode.admin_ecoe.value, RoleCode.coeditor_docente.value}


def _corrector_station_scope(
    db: Session, user, ecoe_event_id: int, event_roles: set[str]
) -> set[int] | None:
    """Estaciones que el actor puede corregir, o None si puede corregir todas."""
    if event_roles & FULL_GRADING_ROLES:
        return None
    assignment = db.scalar(
        select(StaffAssignment).where(
            StaffAssignment.ecoe_event_id == ecoe_event_id,
            StaffAssignment.email == normalize_email(user.email),
            StaffAssignment.role_code == RoleCode.corrector.value,
        )
    )
    return {int(sid) for sid in (assignment.station_ids or []) if sid} if assignment else set()


@router.get("/grading/{ecoe_event_id}")
def list_gradable_responses(
    ecoe_event_id: int,
    db: Session = Depends(get_db),
    user=Depends(require_roles(*GRADING_ROLES)),
):
    event_roles = ensure_event_access(db, user, ecoe_event_id, *GRADING_ROLES)
    station_scope = _corrector_station_scope(db, user, ecoe_event_id, event_roles)
    filters = [
        StudentResponse.ecoe_event_id == ecoe_event_id,
        StudentResponse.max_score.is_not(None),
    ]
    if station_scope is not None:
        if not station_scope:
            return {"responses": [], "pending_count": 0}
        filters.append(StudentResponse.station_id.in_(station_scope))
    responses = db.scalars(
        select(StudentResponse)
        .where(*filters)
        .order_by(StudentResponse.submitted_at.asc(), StudentResponse.id.asc())
    ).all()
    students = {
        student.id: student
        for student in db.scalars(
            select(Student).where(Student.ecoe_event_id == ecoe_event_id)
        ).all()
    }
    stations = {
        station.id: station
        for station in db.scalars(
            select(Station).where(Station.ecoe_event_id == ecoe_event_id)
        ).all()
    }
    rows = []
    for response in responses:
        student = students.get(response.student_id)
        station = stations.get(response.station_id)
        pending = pending_manual_keys(response)
        rows.append({
            "response_id": response.id,
            "mode": str(response.mode),
            "student_id": response.student_id,
            "student_name": f"{student.name} {student.last_name}" if student else "",
            "student_ecoe_number": student.ecoe_number if student else "",
            "station_id": response.station_id,
            "station_number": station.station_number if station else None,
            "station_name": station.name if station else "",
            "submitted_at": response.submitted_at.isoformat(),
            "answers": response.answers,
            "grading": response.grading,
            "pending_questions": pending,
            "score_obtained": response.score_obtained,
            "max_score": response.max_score,
            "graded_by_email": response.graded_by_email,
            "graded_at": response.graded_at.isoformat() if response.graded_at else None,
            "questions": (
                (station.student_form_definition or {}).get("questions", []) if station else []
            ),
        })
    pending_count = sum(1 for row in rows if row["pending_questions"])
    return {"responses": rows, "pending_count": pending_count}


@router.post("/grading/responses/{response_id}")
def grade_response(
    response_id: int,
    payload: ManualGradeSubmit,
    db: Session = Depends(get_db),
    user=Depends(require_roles(*GRADING_ROLES)),
):
    response = db.get(StudentResponse, response_id)
    if not response:
        raise HTTPException(status_code=404, detail="Respuesta no encontrada")
    event_roles = ensure_event_access(db, user, response.ecoe_event_id, *GRADING_ROLES)
    station_scope = _corrector_station_scope(db, user, response.ecoe_event_id, event_roles)
    if station_scope is not None and response.station_id not in station_scope:
        raise HTTPException(
            status_code=403,
            detail="No tienes esta estación asignada para corrección diferida",
        )
    apply_manual_scores(response, payload.scores, graded_by_email=user.email)
    db.add(response)
    db.add(AuditLog(
        user_email=user.email,
        action="grade_student_response",
        target_type="StudentResponse",
        target_id=str(response.id),
        payload={
            "ecoe_event_id": response.ecoe_event_id,
            "scores": payload.scores,
            "score_obtained": response.score_obtained,
        },
    ))
    db.commit()
    db.refresh(response)
    return {
        "graded": True,
        "response_id": response.id,
        "score_obtained": response.score_obtained,
        "max_score": response.max_score,
    }
