"""Contingency data entry: out-of-window submissions by event coordination.

The normal endpoints reject submissions once the check-in window expires or
the check-in was closed by the next rotation. During a real ECOE those cases
still need a way in (paper records after an incident, a pause that consumed
the window), so event admins and operational coordinators can register them
here: the time window is skipped, the record is flagged by_contingency and
the action is audited. Everything else (stage gate, duplicate-by-mode check,
authoritative max score) applies exactly like the normal path.
"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.entities import (
    AuditLog,
    ECOEEvent,
    EvaluatorRecord,
    Station,
    Student,
    StudentResponse,
)
from app.models.enums import RoleCode, SessionMode
from app.schemas.common import EvaluatorSubmission, StudentResponseCreate
from app.services.dependencies import require_roles
from app.services.authorization import ensure_event_access
from app.services.grading import apply_auto_grading
from app.utils.helpers import (
    ensure_submission_stage,
    get_latest_checkin_any_status,
    resolve_station_max_score,
)

router = APIRouter()

CONTINGENCY_ROLES = (RoleCode.admin_ecoe.value, RoleCode.coordinador_operativo.value)


def _validated_contingency_target(
    db: Session, ecoe_event_id: int, station_id: int, student_id: int
) -> tuple[str, Station]:
    """Common checks shared by both contingency endpoints."""
    ecoe_event = db.get(ECOEEvent, ecoe_event_id)
    session_mode = ensure_submission_stage(ecoe_event)
    station = db.get(Station, station_id)
    if not station or station.ecoe_event_id != ecoe_event_id:
        raise HTTPException(status_code=400, detail="La estación no pertenece al ECOE indicado")
    student = db.get(Student, student_id)
    if not student or student.ecoe_event_id != ecoe_event_id:
        raise HTTPException(status_code=400, detail="El estudiante no pertenece al ECOE indicado")
    checkin = get_latest_checkin_any_status(db, ecoe_event_id, station_id, student_id)
    if not checkin:
        raise HTTPException(
            status_code=400,
            detail=(
                "No existe ningún check-in del estudiante en esta estación; la contingencia "
                "requiere que el ingreso haya sido confirmado en algun momento"
            ),
        )
    return session_mode, station


@router.get("/contingency/evaluator-drafts/{ecoe_event_id}")
def list_pending_evaluator_drafts(
    ecoe_event_id: int,
    db: Session = Depends(get_db),
    user=Depends(require_roles(*CONTINGENCY_ROLES)),
):
    """Evaluator records left as a draft (OPT-20 F3 / D3), for coordination to
    finalize in the contingency window."""
    ensure_event_access(db, user, ecoe_event_id, *CONTINGENCY_ROLES)
    rows = db.scalars(
        select(EvaluatorRecord)
        .where(
            EvaluatorRecord.ecoe_event_id == ecoe_event_id,
            EvaluatorRecord.mode == SessionMode.ejecucion.value,
            EvaluatorRecord.is_draft.is_(True),
        )
        .order_by(EvaluatorRecord.station_id.asc(), EvaluatorRecord.updated_at.desc())
    ).all()
    stations = {
        s.id: s
        for s in db.scalars(select(Station).where(Station.ecoe_event_id == ecoe_event_id)).all()
    }
    students = {
        s.id: s
        for s in db.scalars(select(Student).where(Student.ecoe_event_id == ecoe_event_id)).all()
    }
    result = []
    for row in rows:
        station = stations.get(row.station_id)
        student = students.get(row.student_id)
        result.append({
            "record_id": row.id,
            "station_id": row.station_id,
            "station_number": station.station_number if station else None,
            "station_name": station.name if station else "",
            "student_id": row.student_id,
            "student_ecoe_number": student.ecoe_number if student else "",
            "student_name": f"{student.name} {student.last_name}" if student else "",
            "score_obtained": row.score_obtained,
            "max_score": row.max_score,
            "evaluator_name": row.evaluator_name,
            "observation": row.observation,
            "updated_at": row.updated_at.isoformat() if row.updated_at else None,
        })
    return {"drafts": result}


@router.post("/contingency/evaluator-record")
def submit_evaluator_record_by_contingency(
    payload: EvaluatorSubmission,
    db: Session = Depends(get_db),
    user=Depends(require_roles(*CONTINGENCY_ROLES)),
):
    ensure_event_access(db, user, payload.ecoe_event_id, *CONTINGENCY_ROLES)
    session_mode, station = _validated_contingency_target(
        db, payload.ecoe_event_id, payload.station_id, payload.student_id
    )
    existing_record = db.scalar(
        select(EvaluatorRecord).where(
            EvaluatorRecord.ecoe_event_id == payload.ecoe_event_id,
            EvaluatorRecord.station_id == payload.station_id,
            EvaluatorRecord.student_id == payload.student_id,
            EvaluatorRecord.mode == session_mode,
        )
    )
    if existing_record is not None and not existing_record.is_draft:
        raise HTTPException(
            status_code=400,
            detail="Ya existe una evaluación registrada para este estudiante en esta estación",
        )
    authoritative_max = resolve_station_max_score(db, station)
    if authoritative_max <= 0:
        raise HTTPException(
            status_code=400,
            detail="La estación no tiene un puntaje máximo válido configurado",
        )
    if payload.score_obtained < 0 or payload.score_obtained > authoritative_max:
        raise HTTPException(
            status_code=400,
            detail=f"El puntaje obtenido debe estar entre 0 y {authoritative_max}",
        )
    if existing_record is not None:
        # OPT-20 F3 (D3): a half-filled draft left by the buzzer is finalized
        # here — coordination sets the authoritative score, the row becomes a
        # definitive by_contingency record and the action is audited.
        record = existing_record
        record.evaluator_name = payload.evaluator_name
        record.score_obtained = payload.score_obtained
        record.max_score = authoritative_max
        record.observation = payload.observation
        record.answers = payload.answers
        record.is_draft = False
        record.by_contingency = True
        record.submission_kind = "contingency"
        action = "finalize_evaluation_draft_contingency"
    else:
        record = EvaluatorRecord(
            **payload.model_dump(exclude={"checkin_id", "max_score", "mode", "by_contingency"}),
            max_score=authoritative_max,
            mode=session_mode,
            by_contingency=True,
        )
        record.submission_kind = "contingency"
        action = "submit_evaluation_contingency"
    db.add(record)
    db.flush()
    db.add(AuditLog(
        user_email=user.email,
        action=action,
        target_type="EvaluatorRecord",
        target_id=str(record.id),
        payload=payload.model_dump(),
    ))
    db.commit()
    db.refresh(record)
    return {
        "saved": True,
        "record_id": record.id,
        "by_contingency": True,
        "finalized_draft": action == "finalize_evaluation_draft_contingency",
    }


@router.post("/contingency/student-response")
def submit_student_response_by_contingency(
    payload: StudentResponseCreate,
    db: Session = Depends(get_db),
    user=Depends(require_roles(*CONTINGENCY_ROLES)),
):
    ensure_event_access(db, user, payload.ecoe_event_id, *CONTINGENCY_ROLES)
    session_mode, station = _validated_contingency_target(
        db, payload.ecoe_event_id, payload.station_id, payload.student_id
    )
    existing_response = db.scalar(
        select(StudentResponse).where(
            StudentResponse.ecoe_event_id == payload.ecoe_event_id,
            StudentResponse.station_id == payload.station_id,
            StudentResponse.student_id == payload.student_id,
            StudentResponse.mode == session_mode,
        )
    )
    if existing_response:
        raise HTTPException(
            status_code=400,
            detail="Ya existe una respuesta registrada para este estudiante en esta estación",
        )
    response = StudentResponse(
        **payload.model_dump(exclude={"checkin_id", "mode", "by_contingency"}),
        mode=session_mode,
        by_contingency=True,
        submission_kind="contingency",
    )
    apply_auto_grading(response, station.student_form_definition)
    db.add(response)
    db.flush()
    db.add(AuditLog(
        user_email=user.email,
        action="submit_student_response_contingency",
        target_type="StudentResponse",
        target_id=str(response.id),
        payload=payload.model_dump(),
    ))
    db.commit()
    db.refresh(response)
    return {"saved": True, "response_id": response.id, "by_contingency": True}
