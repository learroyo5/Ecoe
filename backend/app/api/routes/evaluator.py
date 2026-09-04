"""Evaluator workflow routes."""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.entities import (
    AuditLog,
    ECOEEvent,
    EvaluatorRecord,
    StaffAssignment,
    Station,
    StationCheckIn,
    Student,
    StudentResponse,
)
from app.models.enums import RoleCode
from app.schemas.common import (
    EvaluatorDraftUpsert,
    EvaluatorSubmission,
    StationCheckInCreate,
)
from app.services.dependencies import get_current_user, require_roles
from app.services.authorization import ensure_event_access
from app.services.live_sweep import sweep_expired_phases
from app.services.live_cycle import advance_if_expired
from app.utils.helpers import (
    ensure_checkin_within_time,
    ensure_primary_station_assignment,
    ensure_submission_stage,
    find_student_by_ecoe_number,
    isoformat_or_none,
    live_phase_snapshot,
    get_active_checkin,
    normalize_email,
    resolve_session_mode,
    resolve_station_max_score,
    resolve_submission_deadline,
    utcnow_naive,
)
from app.utils.serializers import serialize_assessment_tool

router = APIRouter()


@router.get("/evaluator/context/{ecoe_event_id}")
def evaluator_context(
    ecoe_event_id: int,
    station_id: int | None = None,
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
):
    event_roles = ensure_event_access(db, user, ecoe_event_id,
                        RoleCode.admin_ecoe.value,
                        RoleCode.coordinador_operativo.value,
                        RoleCode.evaluador.value)

    # admin_ecoe/coordinador_operativo need to be able to check a student in
    # at ANY station, not just one they're personally assigned to (e.g. a
    # station left without its own evaluador, or filling in during
    # contingency). An evaluador stays scoped to their single principal
    # station, same as before.
    assignment = None
    can_operate_any_station = bool(
        event_roles & {RoleCode.admin_ecoe.value, RoleCode.coordinador_operativo.value}
    )
    if can_operate_any_station:
        assigned_stations = db.scalars(
            select(Station)
            .where(Station.ecoe_event_id == ecoe_event_id)
            .order_by(Station.station_number.asc())
        ).all()
    else:
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

    focus_station = next((s for s in assigned_stations if s.id == station_id), None)
    if focus_station is None:
        focus_station = assigned_stations[0] if assigned_stations else None

    active_checkin = None
    if focus_station:
        active_checkin = db.scalar(
            select(StationCheckIn)
            .where(
                StationCheckIn.ecoe_event_id == ecoe_event_id,
                StationCheckIn.station_id == focus_station.id,
                StationCheckIn.status == "confirmado",
            )
            .order_by(StationCheckIn.confirmed_at.desc(), StationCheckIn.id.desc())
        )

    ecoe_event = db.get(ECOEEvent, ecoe_event_id)
    # OPT-20 F2 safety net: finalize expired student phases before reporting
    # the evaluator's window. Idempotent; never touches evaluator records.
    # M1: roll the automatic circuit forward first.
    advance_if_expired(db, ecoe_event, commit=True)
    if sweep_expired_phases(db, ecoe_event).get("closed_checkins"):
        # A swept check-in may have been this station's active one.
        if focus_station:
            active_checkin = db.scalar(
                select(StationCheckIn)
                .where(
                    StationCheckIn.ecoe_event_id == ecoe_event_id,
                    StationCheckIn.station_id == focus_station.id,
                    StationCheckIn.status == "confirmado",
                )
                .order_by(StationCheckIn.confirmed_at.desc(), StationCheckIn.id.desc())
            )

    student = db.get(Student, active_checkin.student_id) if active_checkin else None
    station = db.get(Station, active_checkin.station_id) if active_checkin else None
    assessment_tool = serialize_assessment_tool(db, station.assessment_tool_id if station else None)
    # Scoped by the current session mode: a submission recorded during the
    # pilotaje must not mark the station as "already sent" for the real run.
    current_mode = resolve_session_mode(ecoe_event)
    evaluator_submission_exists = False
    student_response_exists = False
    if active_checkin and student and station:
        evaluator_submission_exists = db.scalar(
            select(func.count()).select_from(EvaluatorRecord).where(
                EvaluatorRecord.ecoe_event_id == ecoe_event_id,
                EvaluatorRecord.station_id == active_checkin.station_id,
                EvaluatorRecord.student_id == active_checkin.student_id,
                EvaluatorRecord.mode == current_mode,
            )
        ) > 0
        student_response_exists = db.scalar(
            select(func.count()).select_from(StudentResponse).where(
                StudentResponse.ecoe_event_id == ecoe_event_id,
                StudentResponse.station_id == active_checkin.station_id,
                StudentResponse.student_id == active_checkin.student_id,
                StudentResponse.mode == current_mode,
            )
        ) > 0

    return {
        "assignment": assignment,
        "stations": assigned_stations,
        "selected_station_id": focus_station.id if focus_station else None,
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
            "submission_deadline": isoformat_or_none(
                resolve_submission_deadline(db, ecoe_event, active_checkin, station)
            ),
            "evaluator_deadline": isoformat_or_none(
                resolve_submission_deadline(
                    db, ecoe_event, active_checkin, station, for_evaluator=True
                )
            ),
            "evaluator_submission_exists": evaluator_submission_exists,
            "student_response_exists": student_response_exists,
        } if active_checkin and student and station else None,
        "server_now": utcnow_naive().isoformat(),
        # OPT-20 F1: live-clock snapshot for the first paint + no-WS fallback.
        **live_phase_snapshot(db, ecoe_event_id),
    }


@router.post("/station-checkins/confirm")
def confirm_station_checkin(
    payload: StationCheckInCreate,
    db: Session = Depends(get_db),
    user=Depends(require_roles("evaluador", "coordinador_operativo", "admin_ecoe")),
):
    event_roles = ensure_event_access(db, user, payload.ecoe_event_id,
                        RoleCode.admin_ecoe.value,
                        RoleCode.coordinador_operativo.value,
                        RoleCode.evaluador.value)
    ecoe_event = db.get(ECOEEvent, payload.ecoe_event_id)
    session_mode = ensure_submission_stage(ecoe_event)
    station = db.get(Station, payload.station_id)
    if not station or station.ecoe_event_id != payload.ecoe_event_id:
        raise HTTPException(status_code=404, detail="Estación no encontrada")

    if not event_roles & {
        RoleCode.admin_ecoe.value,
        RoleCode.coordinador_operativo.value,
    }:
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
            raise HTTPException(status_code=403, detail="No tienes esa estación asignada")

    student = find_student_by_ecoe_number(db, payload.ecoe_event_id, payload.ecoe_number, active_only=True)
    if not student:
        raise HTTPException(status_code=404, detail="No existe un estudiante activo con ese Número ECOE")

    if not payload.force:
        already_evaluated = (
            db.scalar(
                select(func.count()).select_from(EvaluatorRecord).where(
                    EvaluatorRecord.ecoe_event_id == payload.ecoe_event_id,
                    EvaluatorRecord.station_id == payload.station_id,
                    EvaluatorRecord.student_id == student.id,
                    EvaluatorRecord.mode == session_mode,
                )
            )
            or 0
        ) + (
            db.scalar(
                select(func.count()).select_from(StudentResponse).where(
                    StudentResponse.ecoe_event_id == payload.ecoe_event_id,
                    StudentResponse.station_id == payload.station_id,
                    StudentResponse.student_id == student.id,
                    StudentResponse.mode == session_mode,
                )
            )
            or 0
        )
        if already_evaluated:
            mode_label = "el pilotaje" if session_mode == "pilotaje" else "la ejecución"
            raise HTTPException(
                status_code=409,
                detail={
                    "code": "student_already_evaluated",
                    "message": (
                        f"Este estudiante ya tiene una evaluación registrada en esta "
                        f"estación para {mode_label}. Confirmar de todas formas crea un "
                        f"ingreso nuevo pero el formulario queda cerrado para edición."
                    ),
                },
            )

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
        mode=session_mode,
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
        "submission_deadline": isoformat_or_none(
            resolve_submission_deadline(db, ecoe_event, checkin, station)
        ),
        "evaluator_deadline": isoformat_or_none(
            resolve_submission_deadline(
                db, ecoe_event, checkin, station, for_evaluator=True
            )
        ),
        "server_now": utcnow_naive().isoformat(),
        "evaluator_submission_exists": False,
        "student_response_exists": False,
    }


def _ensure_station_assigned_to_evaluator(
    db: Session, user, event_roles: set[str], ecoe_event_id: int, station_id: int
) -> None:
    """An evaluador may only write for their own principal station.

    admin_ecoe / coordinador_operativo operate any station (contingency,
    an unstaffed station); an evaluador stays scoped to their assignment.
    """
    if event_roles & {RoleCode.admin_ecoe.value, RoleCode.coordinador_operativo.value}:
        return
    assignment = db.scalar(
        select(StaffAssignment).where(
            StaffAssignment.ecoe_event_id == ecoe_event_id,
            StaffAssignment.email == normalize_email(user.email),
            StaffAssignment.role_code == RoleCode.evaluador.value,
        )
    )
    assigned_station_ids, _ = ensure_primary_station_assignment(assignment)
    if not assignment or station_id not in assigned_station_ids:
        raise HTTPException(
            status_code=403,
            detail="No puedes registrar evaluaciones para una estación no asignada a tu cuenta",
        )


@router.put("/evaluator/draft")
def upsert_evaluator_draft(
    payload: EvaluatorDraftUpsert,
    db: Session = Depends(get_db),
    user=Depends(require_roles("evaluador", "coordinador_operativo", "admin_ecoe")),
):
    """Best-effort server-side autosave of a half-filled evaluator record (D3).

    The unique key (event, station, student, mode) means the draft *is* the
    row: a later ``POST /evaluator/submit`` (or a contingency finalization)
    promotes it to ``is_draft=False``. Passes through the stage gate, the
    evaluator's own station scope and the evaluator submission window.
    """
    event_roles = ensure_event_access(db, user, payload.ecoe_event_id,
                        RoleCode.admin_ecoe.value,
                        RoleCode.coordinador_operativo.value,
                        RoleCode.evaluador.value)
    ecoe_event = db.get(ECOEEvent, payload.ecoe_event_id)
    session_mode = ensure_submission_stage(ecoe_event)
    station = db.get(Station, payload.station_id)
    if not station or station.ecoe_event_id != payload.ecoe_event_id:
        raise HTTPException(status_code=400, detail="La estación no pertenece al ECOE indicado")
    _ensure_station_assigned_to_evaluator(
        db, user, event_roles, payload.ecoe_event_id, payload.station_id
    )
    checkin = get_active_checkin(db, payload.ecoe_event_id, payload.station_id,
                                 payload.student_id, payload.checkin_id)
    if not checkin:
        raise HTTPException(
            status_code=400,
            detail="El borrador solo puede guardarse para un estudiante confirmado en esta estación",
        )
    ensure_checkin_within_time(db, ecoe_event, checkin, station, for_evaluator=True)
    authoritative_max = resolve_station_max_score(db, station)
    if authoritative_max <= 0:
        raise HTTPException(
            status_code=400,
            detail="La estación no tiene un puntaje máximo válido configurado",
        )
    provisional_score = max(0.0, min(float(payload.score_obtained), authoritative_max))

    record = db.scalar(
        select(EvaluatorRecord).where(
            EvaluatorRecord.ecoe_event_id == payload.ecoe_event_id,
            EvaluatorRecord.station_id == payload.station_id,
            EvaluatorRecord.student_id == payload.student_id,
            EvaluatorRecord.mode == session_mode,
        )
    )
    if record is not None and not record.is_draft:
        raise HTTPException(
            status_code=409,
            detail="La evaluación de esta estación ya fue enviada y no admite borrador",
        )
    if record is None:
        record = EvaluatorRecord(
            ecoe_event_id=payload.ecoe_event_id,
            station_id=payload.station_id,
            student_id=payload.student_id,
            mode=session_mode,
            is_draft=True,
            by_contingency=False,
            submission_kind="manual",
        )
    record.evaluator_name = payload.evaluator_name
    record.score_obtained = provisional_score
    record.max_score = authoritative_max
    record.observation = payload.observation
    record.answers = payload.answers
    db.add(record)
    db.flush()
    db.add(
        AuditLog(
            user_email=user.email,
            action="save_evaluation_draft",
            target_type="EvaluatorRecord",
            target_id=str(record.id),
            payload={
                "ecoe_event_id": payload.ecoe_event_id,
                "station_id": payload.station_id,
                "student_id": payload.student_id,
            },
        )
    )
    db.commit()
    db.refresh(record)
    return {
        "saved": True,
        "record_id": record.id,
        "is_draft": True,
        "updated_at": isoformat_or_none(record.updated_at),
    }


@router.post("/evaluator/submit")
def submit_evaluator_record(
    payload: EvaluatorSubmission,
    db: Session = Depends(get_db),
    user=Depends(require_roles("evaluador", "coordinador_operativo", "admin_ecoe")),
):
    event_roles = ensure_event_access(db, user, payload.ecoe_event_id,
                        RoleCode.admin_ecoe.value,
                        RoleCode.coordinador_operativo.value,
                        RoleCode.evaluador.value)
    ecoe_event = db.get(ECOEEvent, payload.ecoe_event_id)
    session_mode = ensure_submission_stage(ecoe_event)
    checkin = get_active_checkin(db, payload.ecoe_event_id, payload.station_id,
                                 payload.student_id, payload.checkin_id)
    if not checkin:
        raise HTTPException(
            status_code=400,
            detail="La evaluación solo puede guardarse para un estudiante previamente confirmado en esta estación",
        )
    station = db.get(Station, payload.station_id)
    if not station or station.ecoe_event_id != payload.ecoe_event_id:
        raise HTTPException(status_code=400, detail="La estación no pertenece al ECOE indicado")
    # The evaluator records after the student leaves, so the window also
    # spans the transition phase (see resolve_submission_deadline).
    ensure_checkin_within_time(db, ecoe_event, checkin, station, for_evaluator=True)
    _ensure_station_assigned_to_evaluator(
        db, user, event_roles, payload.ecoe_event_id, payload.station_id
    )
    # Duplicates are scoped by mode: a record saved during the pilotaje must
    # not block the same student/station during the real execution.
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
            detail="La evaluación de esta estación ya fue enviada y no puede modificarse durante el ECOE",
        )
    # Never trust client-supplied scoring metadata: the max score comes from
    # the station's assessment tool and the mode from the ECOE state.
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
        # OPT-20 F3: promote an autosaved draft to a final record. The max
        # score is recomputed authoritatively, never trusting the draft.
        record = existing_record
        record.evaluator_name = payload.evaluator_name
        record.score_obtained = payload.score_obtained
        record.max_score = authoritative_max
        record.observation = payload.observation
        record.answers = payload.answers
        record.is_draft = False
        # OPT-20 F4 (D4): a record that started as a buzzer-time autosave and
        # was completed afterwards is traceable as `draft_finalized`, distinct
        # from a `manual` submit made within the window.
        record.submission_kind = "draft_finalized"
        action = "submit_evaluation_from_draft"
    else:
        record = EvaluatorRecord(
            **payload.model_dump(exclude={"checkin_id", "max_score", "mode", "by_contingency"}),
            max_score=authoritative_max,
            mode=session_mode,
            by_contingency=False,
            submission_kind="manual",
        )
        action = "submit_evaluation"
    db.add(record)
    db.flush()
    db.add(
        AuditLog(
            user_email=user.email,
            action=action,
            target_type="EvaluatorRecord",
            target_id=str(record.id),
            payload=payload.model_dump(),
        )
    )
    db.commit()
    db.refresh(record)
    return {"saved": True, "record_id": record.id}
