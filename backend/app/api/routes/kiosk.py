"""Station kiosk: shared per-station device flow.

Issue/revoke lives under normal user auth (event coordination only). The
device endpoints authenticate exclusively with the station-scoped kiosk
token: the kiosk can only ever see and answer for the student its own
station's active check-in points at, so a stolen tablet never becomes an
account and never reaches another station's data.
"""

from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.entities import (
    AuditLog,
    ECOEEvent,
    MediaAsset,
    Station,
    StationCheckIn,
    StationKioskSession,
    Student,
    StudentResponse,
)
from app.models.enums import RoleCode
from app.schemas.common import KioskDraftUpsert, KioskSubmit
from app.services.authorization import ensure_event_access
from app.services.dependencies import require_roles
from app.services.drafts import discard_checkin_draft, upsert_checkin_draft
from app.services.grading import apply_auto_grading
from app.services.live_sweep import sweep_expired_phases
from app.services.live_cycle import advance_if_expired
from app.services.kiosk import (
    authenticate_kiosk_token,
    issue_kiosk_token,
    kiosk_token_header,
)
from app.utils.clock import utcnow_naive
from app.utils.helpers import (
    ensure_checkin_within_time,
    ensure_submission_stage,
    isoformat_or_none as _isoformat_or_none,
    live_phase_snapshot,
    resolve_session_mode,
    resolve_submission_deadline,
)
from app.utils.serializers import serialize_media_asset

router = APIRouter()

KIOSK_MANAGER_ROLES = (RoleCode.admin_ecoe.value, RoleCode.coordinador_operativo.value)


# ── Emisión y revocación (auth de usuario) ──────────────────────────────

@router.post("/kiosk/stations/{station_id}/token")
def issue_station_kiosk_token(
    station_id: int,
    db: Session = Depends(get_db),
    user=Depends(require_roles(*KIOSK_MANAGER_ROLES)),
):
    station = db.get(Station, station_id)
    if not station:
        raise HTTPException(status_code=404, detail="Estación no encontrada")
    ensure_event_access(db, user, station.ecoe_event_id, *KIOSK_MANAGER_ROLES)
    result = issue_kiosk_token(db, station, issued_by_email=user.email)
    db.add(AuditLog(
        user_email=user.email,
        action="issue_kiosk_token",
        target_type="StationKioskSession",
        target_id=str(result["kiosk_session_id"]),
        payload={"ecoe_event_id": station.ecoe_event_id, "station_id": station.id},
    ))
    db.commit()
    return result


@router.delete("/kiosk/stations/{station_id}/token")
def revoke_station_kiosk_token(
    station_id: int,
    db: Session = Depends(get_db),
    user=Depends(require_roles(*KIOSK_MANAGER_ROLES)),
):
    station = db.get(Station, station_id)
    if not station:
        raise HTTPException(status_code=404, detail="Estación no encontrada")
    ensure_event_access(db, user, station.ecoe_event_id, *KIOSK_MANAGER_ROLES)
    now = utcnow_naive()
    revoked = 0
    for session in db.scalars(
        select(StationKioskSession).where(
            StationKioskSession.station_id == station_id,
            StationKioskSession.revoked_at.is_(None),
        )
    ).all():
        session.revoked_at = now
        db.add(session)
        revoked += 1
    db.add(AuditLog(
        user_email=user.email,
        action="revoke_kiosk_token",
        target_type="Station",
        target_id=str(station_id),
        payload={"ecoe_event_id": station.ecoe_event_id, "revoked_sessions": revoked},
    ))
    db.commit()
    return {"revoked": revoked}


# ── Dispositivo (auth por token de kiosco) ──────────────────────────────

def _kiosk_session(
    db: Session = Depends(get_db),
    token: str | None = Depends(kiosk_token_header),
) -> StationKioskSession:
    return authenticate_kiosk_token(db, token)


@router.get("/kiosk/context")
def kiosk_context(
    db: Session = Depends(get_db),
    kiosk: StationKioskSession = Depends(_kiosk_session),
):
    station = db.get(Station, kiosk.station_id)
    ecoe_event = db.get(ECOEEvent, kiosk.ecoe_event_id)
    # OPT-20 F2 safety net: finalize any check-in whose live phase already
    # expired (a tablet that died mid-station, an operator who advanced the
    # clock). Idempotent and a no-op while the phase is still open or paused.
    # M1: roll the automatic circuit forward first so the sweep sees the real
    # current phase.
    advance_if_expired(db, ecoe_event, commit=True)
    sweep_expired_phases(db, ecoe_event)
    base = {
        "station_id": station.id,
        "station_number": station.station_number,
        "station_name": station.name,
        "ecoe_event_id": ecoe_event.id,
        "ecoe_name": ecoe_event.name,
        "ecoe_status": str(ecoe_event.status),
        "server_now": utcnow_naive().isoformat(),
        # OPT-20 F1: live-clock snapshot for the first paint and the no-WS
        # fallback (a kiosk without WebSocket still learns about a pause on the
        # next 3s poll).
        **live_phase_snapshot(db, kiosk.ecoe_event_id),
    }
    checkin = db.scalar(
        select(StationCheckIn)
        .where(
            StationCheckIn.ecoe_event_id == kiosk.ecoe_event_id,
            StationCheckIn.station_id == kiosk.station_id,
            StationCheckIn.status == "confirmado",
        )
        .order_by(StationCheckIn.confirmed_at.desc(), StationCheckIn.id.desc())
    )
    if not checkin:
        return {**base, "active": None}

    student = db.get(Student, checkin.student_id)
    media_assets = db.scalars(
        select(MediaAsset)
        .where(
            MediaAsset.station_id == station.id,
            MediaAsset.target_viewer.in_(["estudiante", "ambos"]),
        )
        .order_by(MediaAsset.created_at.asc(), MediaAsset.id.asc())
    ).all()
    response_exists = db.scalar(
        select(StudentResponse.id).where(
            StudentResponse.ecoe_event_id == kiosk.ecoe_event_id,
            StudentResponse.station_id == station.id,
            StudentResponse.student_id == checkin.student_id,
            StudentResponse.mode == resolve_session_mode(ecoe_event),
        ).limit(1)
    ) is not None
    return {
        **base,
        "active": {
            "checkin_id": checkin.id,
            "student_id": student.id if student else None,
            "student_name": f"{student.name} {student.last_name}" if student else "",
            "student_ecoe_number": student.ecoe_number if student else "",
            "student_activity": station.student_activity,
            "pre_entry_instruction": station.pre_entry_instruction,
            "student_station_instruction": station.student_station_instruction,
            "student_form_definition": station.student_form_definition,
            "media_assets": [serialize_media_asset(asset) for asset in media_assets],
            "station_time_minutes": station.station_time_minutes,
            "confirmed_at": checkin.confirmed_at.isoformat(),
            "submission_deadline": _isoformat_or_none(
                resolve_submission_deadline(db, ecoe_event, checkin, station)
            ),
            "student_response_exists": response_exists,
        },
    }


@router.post("/kiosk/submit")
def kiosk_submit(
    payload: KioskSubmit,
    db: Session = Depends(get_db),
    kiosk: StationKioskSession = Depends(_kiosk_session),
):
    ecoe_event = db.get(ECOEEvent, kiosk.ecoe_event_id)
    session_mode = ensure_submission_stage(ecoe_event)
    station = db.get(Station, kiosk.station_id)
    checkin = db.get(StationCheckIn, payload.checkin_id)
    if not checkin or checkin.station_id != kiosk.station_id:
        raise HTTPException(status_code=400, detail="El check-in no corresponde a esta estación")
    # El kiosco solo acepta el ingreso `confirmado` vigente de la estación.
    # Si la rotación ya avanzó (el evaluador confirmó al siguiente estudiante,
    # cerrando este ingreso), el envío tardío del estudiante anterior va por
    # contingencia, no por el kiosco (ver docs/OPERACION_DIA_EXAMEN.md). Así
    # una request armada a mano no puede atribuir respuestas a un estudiante
    # previo cuya ventana de tiempo siga abierta (OPT-8 / H-vivo-5).
    active_checkin = db.scalar(
        select(StationCheckIn)
        .where(
            StationCheckIn.station_id == kiosk.station_id,
            StationCheckIn.status == "confirmado",
        )
        .order_by(StationCheckIn.confirmed_at.desc(), StationCheckIn.id.desc())
    )
    if not active_checkin or active_checkin.id != payload.checkin_id:
        raise HTTPException(
            status_code=409, detail="No hay un ingreso activo para esta estación"
        )
    ensure_checkin_within_time(db, ecoe_event, checkin, station)
    existing_response = db.scalar(
        select(StudentResponse).where(
            StudentResponse.ecoe_event_id == kiosk.ecoe_event_id,
            StudentResponse.station_id == kiosk.station_id,
            StudentResponse.student_id == checkin.student_id,
            StudentResponse.mode == session_mode,
        )
    )
    if existing_response:
        raise HTTPException(
            status_code=400,
            detail="La respuesta de esta estación ya fue enviada y no puede reemplazarse",
        )
    response = StudentResponse(
        ecoe_event_id=kiosk.ecoe_event_id,
        station_id=kiosk.station_id,
        student_id=checkin.student_id,
        mode=session_mode,
        answers=payload.answers,
        locked=True,
        by_contingency=False,
        submission_kind="manual",
    )
    apply_auto_grading(response, station.student_form_definition)
    db.add(response)
    db.flush()
    discard_checkin_draft(db, checkin.id)
    db.add(AuditLog(
        user_email=f"kiosk:station-{kiosk.station_id}",
        action="submit_student_response_kiosk",
        target_type="StudentResponse",
        target_id=str(response.id),
        payload={
            "ecoe_event_id": kiosk.ecoe_event_id,
            "station_id": kiosk.station_id,
            "student_id": checkin.student_id,
            "checkin_id": checkin.id,
        },
    ))
    db.commit()
    db.refresh(response)
    return {"saved": True, "response_id": response.id}


@router.put("/kiosk/draft")
def kiosk_draft(
    payload: KioskDraftUpsert,
    db: Session = Depends(get_db),
    kiosk: StationKioskSession = Depends(_kiosk_session),
):
    """Best-effort server-side autosave of the kiosk's in-progress answers."""
    ecoe_event = db.get(ECOEEvent, kiosk.ecoe_event_id)
    ensure_submission_stage(ecoe_event)
    checkin = db.get(StationCheckIn, payload.checkin_id)
    if not checkin or checkin.station_id != kiosk.station_id:
        raise HTTPException(status_code=400, detail="El check-in no corresponde a esta estación")
    active_checkin = db.scalar(
        select(StationCheckIn)
        .where(
            StationCheckIn.station_id == kiosk.station_id,
            StationCheckIn.status == "confirmado",
        )
        .order_by(StationCheckIn.confirmed_at.desc(), StationCheckIn.id.desc())
    )
    if not active_checkin or active_checkin.id != payload.checkin_id:
        raise HTTPException(status_code=409, detail="No hay un ingreso activo para esta estación")
    draft = upsert_checkin_draft(db, checkin, payload.answers)
    db.commit()
    db.refresh(draft)
    return {"saved": True, "updated_at": draft.updated_at.isoformat() if draft.updated_at else None}


@router.get("/kiosk/media/{asset_id}")
def kiosk_media_file(
    asset_id: int,
    db: Session = Depends(get_db),
    kiosk: StationKioskSession = Depends(_kiosk_session),
):
    asset = db.get(MediaAsset, asset_id)
    if (
        not asset
        or asset.station_id != kiosk.station_id
        or asset.target_viewer not in {"estudiante", "ambos"}
    ):
        raise HTTPException(status_code=404, detail="Archivo no encontrado")
    active_checkin = db.scalar(
        select(StationCheckIn.id).where(
            StationCheckIn.ecoe_event_id == kiosk.ecoe_event_id,
            StationCheckIn.station_id == kiosk.station_id,
            StationCheckIn.status == "confirmado",
        ).limit(1)
    )
    if active_checkin is None:
        raise HTTPException(
            status_code=403,
            detail="La multimedia solo está disponible con un estudiante confirmado en la estación",
        )
    if not Path(asset.file_path).exists():
        raise HTTPException(status_code=404, detail="Archivo no encontrado")
    return FileResponse(
        path=asset.file_path,
        media_type=asset.content_type,
        filename=asset.original_name,
    )
