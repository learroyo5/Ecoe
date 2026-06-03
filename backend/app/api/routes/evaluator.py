"""Evaluator workflow routes."""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.entities import (
    AuditLog,
    EvaluatorRecord,
    StaffAssignment,
    Station,
    StationCheckIn,
    Student,
    StudentResponse,
)
from app.models.enums import RoleCode
from app.schemas.common import EvaluatorSubmission, StationCheckInCreate
from app.services.dependencies import get_current_user, require_roles
from app.utils.helpers import (
    ensure_event_access,
    ensure_primary_station_assignment,
    find_student_by_ecoe_number,
    get_active_checkin,
    normalize_email,
    serialize_assessment_tool,
)

router = APIRouter()


@router.get("/evaluator/context/{ecoe_event_id}")
def evaluator_context(ecoe_event_id: int, db: Session = Depends(get_db), user=Depends(get_current_user)):
    ensure_event_access(db, user, ecoe_event_id,
                        RoleCode.admin_ecoe.value,
                        RoleCode.coordinador_operativo.value,
                        RoleCode.evaluador.value)
    assignment = db.scalar(
        select(StaffAssignment).where(
            StaffAssignment.ecoe_event_id == ecoe_event_id,
            StaffAssignment.email == normalize_email(user.email),
            StaffAssignment.role_code == RoleCode.evaluador.value,
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
        if assigned_station_ids else []
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
            select(func.count()).select_from(EvaluatorRecord).where(
                EvaluatorRecord.ecoe_event_id == ecoe_event_id,
                EvaluatorRecord.station_id == active_checkin.station_id,
                EvaluatorRecord.student_id == active_checkin.student_id,
            )
        ) > 0
        student_response_exists = db.scalar(
            select(func.count()).select_from(StudentResponse).where(
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
            "evaluator_instruction": station.evaluator_instruction if station else "",
            "confirmed_at": active_checkin.confirmed_at.isoformat(),
            "station_time_minutes": station.station_time_minutes if station else 0,
            "evaluator_submission_exists": evaluator_submission_exists,
            "student_response_exists": student_response_exists,
        } if active_checkin and student and station else None,
    }


@router.post("/station-checkins/confirm")
def confirm_station_checkin(
    payload: StationCheckInCreate,
    db: Session = Depends(get_db),
    user=Depends(require_roles("evaluador", "coordinador_operativo", "admin_ecoe")),
):
    ensure_event_access(db, user, payload.ecoe_event_id,
                        RoleCode.admin_ecoe.value,
                        RoleCode.coordinador_operativo.value,
                        RoleCode.evaluador.value)
    station = db.get(Station, payload.station_id)
    if not station or station.ecoe_event_id != payload.ecoe_event_id:
        raise HTTPException(status_code=404, detail="Estacion no encontrada")

    if user.role.code == "evaluador":
        assignment = db.scalar(
            select(StaffAssignment).where(
                StaffAssignment.ecoe_event_id == payload.ecoe_event_id,
                StaffAssignment.email == normalize_email(user.email),
                StaffAssignment.role_code == RoleCode.evaluador.value,
            )
        )
        assigned_station_ids, assignment_changed = ensure_primary_station_assignment(assignment)
        if assignment and assignment_changed:
            db.add(assignment)
            db.commit()
            db.refresh(assignment)
        if not assignment or payload.station_id not in assigned_station_ids:
            raise HTTPException(status_code=403, detail="No tienes esa estacion asignada")

    student = find_student_by_ecoe_number(db, payload.ecoe_event_id, payload.ecoe_number, active_only=True)
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
    db.flush()
    db.add(
        AuditLog(
            user_email=user.email,
            action="confirm_station_checkin",
            target_type="StationCheckIn",
            target_id=str(checkin.id),
            payload={
                "ecoe_event_id": payload.ecoe_event_id,
                "station_id": payload.station_id,
                "student_id": student.id,
                "student_ecoe_number": student.ecoe_number,
            },
        )
    )
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


@router.post("/evaluator/submit")
def submit_evaluator_record(
    payload: EvaluatorSubmission,
    db: Session = Depends(get_db),
    user=Depends(require_roles("evaluador", "coordinador_operativo", "admin_ecoe")),
):
    ensure_event_access(db, user, payload.ecoe_event_id,
                        RoleCode.admin_ecoe.value,
                        RoleCode.coordinador_operativo.value,
                        RoleCode.evaluador.value)
    checkin = get_active_checkin(db, payload.ecoe_event_id, payload.station_id,
                                 payload.student_id, payload.checkin_id)
    if not checkin:
        raise HTTPException(
            status_code=400,
            detail="La evaluacion solo puede guardarse para un estudiante previamente confirmado en esta estacion",
        )
    if user.role.code == RoleCode.evaluador.value:
        evaluator_assignment = db.scalar(
            select(StaffAssignment).where(
                StaffAssignment.ecoe_event_id == payload.ecoe_event_id,
                StaffAssignment.email == normalize_email(user.email),
                StaffAssignment.role_code == RoleCode.evaluador.value,
            )
        )
        assigned_station_ids, _ = ensure_primary_station_assignment(evaluator_assignment)
        if not evaluator_assignment or payload.station_id not in assigned_station_ids:
            raise HTTPException(
                status_code=403,
                detail="No puedes enviar evaluaciones para una estacion no asignada a tu cuenta",
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
    db.flush()
    db.add(
        AuditLog(
            user_email=user.email,
            action="submit_evaluation",
            target_type="EvaluatorRecord",
            target_id=str(record.id),
            payload=payload.model_dump(),
        )
    )
    db.commit()
    db.refresh(record)
    return {"saved": True, "record_id": record.id}
