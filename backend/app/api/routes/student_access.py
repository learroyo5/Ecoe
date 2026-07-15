"""Student access and response submission routes."""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.entities import (
    AuditLog,
    ECOEEvent,
    MediaAsset,
    Station,
    StationCheckIn,
    Student,
    StudentResponse,
)
from app.models.enums import RoleCode
from app.schemas.common import StudentAccessRequest, StudentResponseCreate
from app.services.dependencies import get_current_user, require_roles
from app.services.authorization import ensure_event_access
from app.services.grading import apply_auto_grading
from app.utils.helpers import (
    checkin_submission_deadline,
    ensure_checkin_within_time,
    ensure_submission_stage,
    get_active_checkin,
    normalize_ecoe_lookup,
    normalize_email,
    resolve_session_mode,
    utcnow_naive,
)
from app.utils.serializers import serialize_media_asset

router = APIRouter()


@router.post("/student/access")
def student_access_context(
    payload: StudentAccessRequest,
    db: Session = Depends(get_db),
    user=Depends(require_roles("estudiante", "coordinador_operativo", "admin_ecoe")),
):
    ensure_event_access(db, user, payload.ecoe_event_id,
                        RoleCode.admin_ecoe.value,
                        RoleCode.coordinador_operativo.value,
                        RoleCode.estudiante.value)
    student = db.scalar(
        select(Student).where(
            Student.ecoe_event_id == payload.ecoe_event_id,
            func.lower(Student.email) == normalize_email(user.email),
            Student.is_active.is_(True),
        )
    )
    if not student:
        raise HTTPException(status_code=404,
                            detail="No existe un estudiante activo asociado a tu cuenta en este ECOE")
    if payload.ecoe_number and normalize_ecoe_lookup(student.ecoe_number) != normalize_ecoe_lookup(payload.ecoe_number):
        raise HTTPException(status_code=403,
                            detail="El Numero ECOE ingresado no corresponde a tu cuenta para este evento")

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
        .where(MediaAsset.station_id == station.id, MediaAsset.target_viewer == "estudiante")
        .order_by(MediaAsset.created_at.asc(), MediaAsset.id.asc())
    ).all()
    ecoe_event = db.get(ECOEEvent, payload.ecoe_event_id)
    # Scoped by mode: a pilotaje submission must not mark the station as
    # already answered during the real execution.
    student_response_exists = db.scalar(
        select(func.count()).select_from(StudentResponse).where(
            StudentResponse.ecoe_event_id == payload.ecoe_event_id,
            StudentResponse.station_id == checkin.station_id,
            StudentResponse.student_id == student.id,
            StudentResponse.mode == resolve_session_mode(ecoe_event),
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
        "pre_entry_instruction": station.pre_entry_instruction,
        "student_station_instruction": station.student_station_instruction,
        "student_form_definition": station.student_form_definition,
        "media_assets": [serialize_media_asset(asset) for asset in student_media_assets],
        "station_time_minutes": station.station_time_minutes,
        "confirmed_at": checkin.confirmed_at.isoformat(),
        "submission_deadline": checkin_submission_deadline(checkin, station).isoformat(),
        "server_now": utcnow_naive().isoformat(),
        "student_response_exists": student_response_exists,
    }


@router.post("/student/submit")
def submit_student_response(
    payload: StudentResponseCreate,
    db: Session = Depends(get_db),
    user=Depends(require_roles("estudiante", "coordinador_operativo", "admin_ecoe")),
):
    event_roles = ensure_event_access(db, user, payload.ecoe_event_id,
                        RoleCode.admin_ecoe.value,
                        RoleCode.coordinador_operativo.value,
                        RoleCode.estudiante.value)
    ecoe_event = db.get(ECOEEvent, payload.ecoe_event_id)
    session_mode = ensure_submission_stage(ecoe_event)
    if not event_roles & {
        RoleCode.admin_ecoe.value,
        RoleCode.coordinador_operativo.value,
    }:
        student = db.scalar(
            select(Student).where(
                Student.ecoe_event_id == payload.ecoe_event_id,
                func.lower(Student.email) == normalize_email(user.email),
                Student.is_active.is_(True),
            )
        )
        if not student or student.id != payload.student_id:
            raise HTTPException(status_code=403,
                                detail="Tu cuenta no puede responder por otro estudiante en este ECOE")
    checkin = get_active_checkin(db, payload.ecoe_event_id, payload.station_id,
                                 payload.student_id, payload.checkin_id)
    if not checkin:
        raise HTTPException(
            status_code=400,
            detail="La respuesta solo puede enviarse despues de que el evaluador confirme tu ingreso a la estacion",
        )
    station = db.get(Station, payload.station_id)
    if not station or station.ecoe_event_id != payload.ecoe_event_id:
        raise HTTPException(status_code=400, detail="La estacion no pertenece al ECOE indicado")
    ensure_checkin_within_time(checkin, station)
    # Duplicates are scoped by mode: a pilotaje response must not block the
    # same student/station during the real execution.
    existing_response = db.scalar(
        select(StudentResponse).where(
            StudentResponse.ecoe_event_id == payload.ecoe_event_id,
            StudentResponse.station_id == payload.station_id,
            StudentResponse.student_id == payload.student_id,
            StudentResponse.mode == session_mode,
        )
    )
    if existing_response:
        raise HTTPException(status_code=400,
                            detail="La respuesta de esta estacion ya fue enviada y no puede reemplazarse")
    response = StudentResponse(
        **payload.model_dump(exclude={"checkin_id", "mode", "by_contingency"}),
        mode=session_mode,
        by_contingency=False,
    )
    apply_auto_grading(response, station.student_form_definition)
    db.add(response)
    db.flush()
    db.add(
        AuditLog(
            user_email=user.email,
            action="submit_student_response",
            target_type="StudentResponse",
            target_id=str(response.id),
            payload=payload.model_dump(),
        )
    )
    db.commit()
    db.refresh(response)
    return {"saved": True, "response_id": response.id}
