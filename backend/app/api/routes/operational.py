"""Live panel, timer control, media, validation, results, and incidents routes."""

import logging
from datetime import timedelta
from http.cookies import SimpleCookie
from pathlib import Path

from fastapi import APIRouter, BackgroundTasks, Depends, File, HTTPException, Query, UploadFile, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse, Response as FastAPIResponse
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.db.session import SessionLocal, get_db
from app.models.entities import (
    ECOEEvent,
    Incident,
    LiveSession,
    MediaAsset,
    Station,
    Student,
)
from app.models.enums import RoleCode
from app.schemas.common import (
    IncidentCreate,
    IncidentRead,
    IncidentResolve,
    MediaAssetRead,
    Page,
    TimerAction,
)
from app.services.dependencies import authenticate_session_token, get_current_user, require_roles
from app.services.kiosk import authenticate_kiosk_token
from app.services.ecoe import (
    build_dashboard,
    build_station_score_block,
    build_traceability_report,
    export_contingency_pdf,
    export_results_excel,
    persist_results,
    read_results,
    read_station_results,
)
from app.services.authorization import ADMIN_EVENT_ROLE_CODES, ensure_event_access
from app.services.media import (
    ALLOWED_VIEWERS,
    MAX_MEDIA_SIZE_BYTES,
    filter_media_for_user,
    get_media_asset_for_user,
    safe_media_filename,
    validate_media_type,
)
from app.utils.helpers import SUBMISSION_GRACE_SECONDS, compute_remaining_seconds, utcnow_naive
from app.utils.pagination import DEFAULT_PAGE_SIZE, MAX_PAGE_SIZE, paginate_query
from app.services.live_sweep import sweep_expired_phases
from app.services.live_cycle import (
    advance_if_expired,
    compute_total_rounds,
    station_slot_count,
)
from app.services.websocket import live_timer

# Timer actions accepted by POST /live/control. `expire_phase` (OPT-20 F2)
# ends the current phase without advancing the station index — the buzzer,
# and the trigger for the server-side auto-submit sweep (H-opt20-6 / H-vivo-8).
# M1: `enable_auto` / `disable_auto` toggle the automatic circuit; `skip_phase`
# ends the current auto phase now and rolls to the next one.
TIMER_ACTIONS = {
    "start", "pause", "resume", "reset", "next_transition", "expire_phase",
    "enable_auto", "disable_auto", "skip_phase",
}
_SWEEP_TIMER_ACTIONS = {"start", "reset", "next_transition", "expire_phase"}

logger = logging.getLogger("ecoe.operational")

router = APIRouter()

# ── WebSocket: Live Timer ──────────────────────────────────────────────

@router.websocket("/ws/live/{ecoe_event_id}")
async def websocket_live_timer(
    websocket: WebSocket,
    ecoe_event_id: int,
    kiosk_token: str | None = Query(default=None),
):
    settings = get_settings()
    origin = websocket.headers.get("origin")
    allowed_origins = {
        item.strip().rstrip("/")
        for item in settings.cors_origins.split(",")
        if item.strip()
    }
    if origin and origin.rstrip("/") not in allowed_origins:
        await websocket.close(code=1008)
        return

    # OPT-20 F1: besides event coordination, the operational screens
    # (kiosko / evaluador / estudiante) subscribe here read-only to follow the
    # central clock and freeze on pause. This handler never mutates state:
    # inbound frames are keep-alive only and are ignored. Timer control stays
    # exclusively on the authenticated POST /live/control.
    with SessionLocal() as db:
        try:
            if kiosk_token is not None:
                # A browser cannot attach custom headers to a WebSocket, so the
                # station-scoped kiosk token travels as a query param. Risk: it
                # may land in reverse-proxy / access logs; accepted because the
                # token has a short TTL and is scoped to a single station.
                kiosk = authenticate_kiosk_token(db, kiosk_token)
                if kiosk.ecoe_event_id != ecoe_event_id:
                    raise HTTPException(status_code=403, detail="Token de otro evento")
            else:
                token = None
                authorization = websocket.headers.get("authorization", "")
                if authorization.lower().startswith("bearer "):
                    token = authorization.split(" ", 1)[1].strip()
                if not token:
                    token = websocket.cookies.get(settings.auth_cookie_name)
                if not token:
                    cookie_header = websocket.headers.get("cookie", "")
                    parsed_cookie = SimpleCookie()
                    parsed_cookie.load(cookie_header)
                    morsel = parsed_cookie.get(settings.auth_cookie_name)
                    token = morsel.value if morsel else None
                user = authenticate_session_token(db, token)
                ensure_event_access(
                    db,
                    user,
                    ecoe_event_id,
                    RoleCode.admin_ecoe.value,
                    RoleCode.coeditor_docente.value,
                    RoleCode.coordinador_operativo.value,
                    RoleCode.cronometrador.value,
                    RoleCode.evaluador.value,
                    RoleCode.estudiante.value,
                )
        except HTTPException:
            await websocket.close(code=1008)
            return

    await live_timer.connect(ecoe_event_id, websocket)
    try:
        while True:
            # Keep connection alive; any received frame is ignored (read-only).
            await websocket.receive_text()
    except WebSocketDisconnect:
        live_timer.disconnect(ecoe_event_id, websocket)
    except Exception:
        live_timer.disconnect(ecoe_event_id, websocket)


# ── Live Panel & Timer ─────────────────────────────────────────────────

def live_session_state(session: LiveSession) -> dict:
    return {
        "id": session.id,
        "ecoe_event_id": session.ecoe_event_id,
        "mode": session.mode,
        "status": session.status,
        "station_time_seconds": session.station_time_seconds,
        "transition_time_seconds": session.transition_time_seconds,
        "current_station_index": session.current_station_index,
        "remaining_seconds": compute_remaining_seconds(session),
        "phase_started_at": session.phase_started_at.isoformat() if session.phase_started_at else None,
        "server_now": utcnow_naive().isoformat(),
        # M1: ciclo automático del circuito.
        "auto_mode": session.auto_mode,
        "current_round": session.current_round,
        "total_rounds": session.total_rounds,
        "inter_round_pause_seconds": session.inter_round_pause_seconds,
    }


@router.get("/live/{ecoe_event_id}")
def get_live_panel(ecoe_event_id: int, db: Session = Depends(get_db), user=Depends(get_current_user)):
    ensure_event_access(db, user, ecoe_event_id,
                        RoleCode.admin_ecoe.value,
                        RoleCode.coeditor_docente.value,
                        RoleCode.coordinador_operativo.value,
                        RoleCode.cronometrador.value)
    session = db.scalar(select(LiveSession).where(LiveSession.ecoe_event_id == ecoe_event_id).limit(1))
    if not session:
        raise HTTPException(status_code=404, detail="Sesión en vivo no encontrada")
    # OPT-20 F2 safety net: the live panel is polled continuously, so use it to
    # finalize any expired phase. Idempotent, no-op while the phase is open.
    ecoe_event = db.get(ECOEEvent, ecoe_event_id)
    if ecoe_event is not None:
        # M1: also roll the automatic circuit forward past any expired phase.
        advance_if_expired(db, ecoe_event, commit=True)
        sweep_expired_phases(db, ecoe_event)
    db.refresh(session)
    return live_session_state(session)


@router.post("/live/control")
def control_timer(
    payload: TimerAction,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    user=Depends(require_roles("admin_ecoe", "coeditor_docente", "coordinador_operativo", "cronometrador")),
):
    ensure_event_access(db, user, payload.ecoe_event_id,
                        RoleCode.admin_ecoe.value,
                        RoleCode.coeditor_docente.value,
                        RoleCode.coordinador_operativo.value,
                        RoleCode.cronometrador.value)
    if payload.action not in TIMER_ACTIONS:
        raise HTTPException(status_code=400, detail="Acción no soportada")
    ecoe_event = db.get(ECOEEvent, payload.ecoe_event_id)
    if ecoe_event is None:
        # Defensive: ensure_event_access already 404s on a missing event, but a
        # bare db.get here would otherwise reach ecoe_event.station_time_minutes
        # and raise 500 (H-vivo-8 a).
        raise HTTPException(status_code=404, detail="ECOE no encontrado")
    session = db.scalar(
        select(LiveSession).where(LiveSession.ecoe_event_id == payload.ecoe_event_id).limit(1)
    )
    if not session:
        session = LiveSession(
            ecoe_event_id=payload.ecoe_event_id,
            station_time_seconds=max(1, round(ecoe_event.station_time_minutes * 60)),
            transition_time_seconds=max(0, round(ecoe_event.transition_time_minutes * 60)),
            remaining_seconds=max(1, round(ecoe_event.station_time_minutes * 60)),
            inter_round_pause_seconds=max(
                0, round((ecoe_event.inter_round_pause_minutes or 0) * 60)
            ),
        )
        db.add(session)
        db.flush()
    now = utcnow_naive()
    if payload.action == "enable_auto":
        # M1: sólo antes de arrancar el circuito; congela el nº de rondas y la
        # pausa entre rondas, y resincroniza los tiempos desde el evento.
        if str(session.status) not in ("idle", "ready"):
            raise HTTPException(
                status_code=409,
                detail="El circuito automático se activa antes de iniciar el cronómetro.",
            )
        session.auto_mode = True
        session.current_round = 1
        session.total_rounds = compute_total_rounds(db, payload.ecoe_event_id)
        session.station_time_seconds = max(1, round(ecoe_event.station_time_minutes * 60))
        session.transition_time_seconds = max(
            0, round(ecoe_event.transition_time_minutes * 60)
        )
        session.inter_round_pause_seconds = max(
            0, round((ecoe_event.inter_round_pause_minutes or 0) * 60)
        )
        session.remaining_seconds = session.station_time_seconds
    elif payload.action == "disable_auto":
        session.auto_mode = False
    elif payload.action == "start":
        session.status = "running"
        session.remaining_seconds = session.station_time_seconds
        session.phase_started_at = now
        if session.auto_mode:
            session.current_round = 1
            if session.total_rounds is None:
                session.total_rounds = compute_total_rounds(db, payload.ecoe_event_id)
    elif payload.action == "pause":
        # Freeze the authoritative remaining time at the moment of pausing.
        session.remaining_seconds = compute_remaining_seconds(session)
        session.status = "paused"
        session.phase_started_at = None
    elif payload.action == "resume":
        session.status = "running"
        session.phase_started_at = now
    elif payload.action == "reset":
        session.status = "ready"
        session.current_station_index = 1
        session.remaining_seconds = session.station_time_seconds
        session.phase_started_at = None
        # M1: limpiar el progreso de rondas; conservar la preferencia auto_mode.
        session.current_round = 1
        session.total_rounds = (
            compute_total_rounds(db, payload.ecoe_event_id)
            if session.auto_mode
            else None
        )
    elif payload.action == "skip_phase":
        # M1: terminar la fase automática actual ahora y rodar a la siguiente.
        if not session.auto_mode or str(session.status) not in (
            "running", "transition", "round_pause",
        ):
            raise HTTPException(
                status_code=409,
                detail="No hay una fase automática en curso para adelantar.",
            )
        session.phase_started_at = now - timedelta(
            seconds=(session.remaining_seconds or 0) + 1
        )
    elif payload.action == "next_transition":
        # H-vivo-8 (c): cap the rotation index at the number of station slots
        # (distinct station_number) so a stray click can't run the circuit past
        # its last station and desync every panel.
        station_slots = station_slot_count(db, payload.ecoe_event_id)
        if station_slots and session.current_station_index >= station_slots:
            raise HTTPException(
                status_code=409,
                detail=(
                    f"El circuito tiene {station_slots} estaciones; "
                    "el cronómetro ya está en la última."
                ),
            )
        session.status = "transition"
        session.remaining_seconds = session.transition_time_seconds
        session.current_station_index += 1
        session.phase_started_at = now
    elif payload.action == "expire_phase":
        # Buzzer: end the current phase now, WITHOUT advancing the station
        # index. The countdown freezes at 0 and the sweep below finalizes the
        # check-ins whose phase just ended.
        session.remaining_seconds = 0
        session.phase_started_at = None
    db.add(session)
    db.flush()

    # M1: tras aplicar la acción, dejar que el ciclo automático avance las
    # fases vencidas (imprescindible para `skip_phase`; inofensivo si no aplica).
    if session.auto_mode and ecoe_event is not None:
        advance_if_expired(db, ecoe_event)

    if payload.action in _SWEEP_TIMER_ACTIONS and ecoe_event is not None:
        forced = payload.action == "expire_phase"
        sweep_expired_phases(
            db,
            ecoe_event,
            force=forced,
            grace_seconds=0 if forced else SUBMISSION_GRACE_SECONDS,
            commit=False,
        )

    db.commit()
    db.refresh(session)

    state = live_session_state(session)
    # Broadcast timer state to all WebSocket clients
    background_tasks.add_task(
        live_timer.broadcast,
        payload.ecoe_event_id,
        {"type": "timer_update", **state},
    )

    return state


# ── Media ──────────────────────────────────────────────────────────────

@router.post("/media/upload", response_model=MediaAssetRead)
async def upload_media(
    ecoe_event_id: int,
    station_id: int | None = None,
    target_viewer: str = "estudiante",
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    user=Depends(require_roles("admin_ecoe", "coeditor_docente")),
):
    if target_viewer not in ALLOWED_VIEWERS:
        raise HTTPException(
            status_code=400,
            detail=f"target_viewer debe ser uno de: {', '.join(sorted(ALLOWED_VIEWERS))}",
        )
    ensure_event_access(
        db, user, ecoe_event_id,
        RoleCode.admin_ecoe.value,
        RoleCode.coeditor_docente.value,
    )
    if not station_id:
        raise HTTPException(status_code=400, detail="El archivo debe asociarse a una estación")
    station = db.get(Station, station_id)
    if not station or station.ecoe_event_id != ecoe_event_id:
        raise HTTPException(status_code=400, detail="La estación no pertenece al ECOE indicado")
    secure_name = safe_media_filename(file.filename)
    settings = get_settings()
    media_dir = Path(settings.storage_path) / "media"
    media_dir.mkdir(parents=True, exist_ok=True)
    content = await file.read()
    if len(content) > MAX_MEDIA_SIZE_BYTES:
        raise HTTPException(
            status_code=400,
            detail=f"El archivo excede el tamaño máximo de {MAX_MEDIA_SIZE_BYTES // (1024 * 1024)} MB",
        )
    suffix = Path(secure_name).suffix.lower()
    validate_media_type(content, suffix, file.content_type or "")
    file_path = media_dir / secure_name
    file_path.write_bytes(content)
    logger.info(
        "media_upload email=%s ecoe_event_id=%s station_id=%s filename=%s bytes=%s",
        user.email, ecoe_event_id, station_id, secure_name, len(content),
    )
    asset = MediaAsset(
        filename=secure_name,
        original_name=Path(file.filename or "archivo").name,
        content_type=file.content_type or "application/octet-stream",
        file_path=str(file_path),
        target_viewer=target_viewer,
        station_id=station_id,
    )
    db.add(asset)
    db.commit()
    db.refresh(asset)
    return asset


@router.get("/media/{station_id}", response_model=list[MediaAssetRead])
def list_media(station_id: int, db: Session = Depends(get_db), user=Depends(get_current_user)):
    station = db.get(Station, station_id)
    if not station:
        raise HTTPException(status_code=404, detail="Estación no encontrada")
    ensure_event_access(
        db, user, station.ecoe_event_id,
        RoleCode.admin_ecoe.value,
        RoleCode.coeditor_docente.value,
        RoleCode.coordinador_operativo.value,
        RoleCode.cronometrador.value,
        RoleCode.evaluador.value,
        RoleCode.estudiante.value,
    )
    assets = db.scalars(select(MediaAsset).where(MediaAsset.station_id == station_id)).all()
    return filter_media_for_user(db, user, station, assets)


@router.delete("/media/{asset_id}")
def delete_media(
    asset_id: int,
    db: Session = Depends(get_db),
    user=Depends(require_roles("admin_ecoe", "coeditor_docente")),
):
    asset = db.get(MediaAsset, asset_id)
    if not asset:
        raise HTTPException(status_code=404, detail="Archivo no encontrado")
    get_media_asset_for_user(
        db,
        user,
        asset_id,
        writable=True,
    )
    file_path = Path(asset.file_path)
    # Commit the DB deletion first: if it fails, the file on disk is still
    # referenced by a valid row. Deleting the file afterwards is best-effort
    # and never leaves an orphaned row pointing at a missing file.
    db.delete(asset)
    db.commit()
    if file_path.exists():
        try:
            file_path.unlink()
        except OSError:
            logger.warning(
                "media_delete_file_failed asset_id=%s path=%s", asset_id, file_path,
            )
    return {"deleted": True, "asset_id": asset_id}


@router.get("/media/file/{asset_id}")
def get_media_file(asset_id: int, db: Session = Depends(get_db), user=Depends(get_current_user)):
    asset = get_media_asset_for_user(db, user, asset_id)
    return FileResponse(path=asset.file_path, media_type=asset.content_type, filename=asset.original_name)


# ── Validation ─────────────────────────────────────────────────────────

@router.get("/validation/{ecoe_event_id}")
def validation(ecoe_event_id: int, db: Session = Depends(get_db), user=Depends(get_current_user)):
    ensure_event_access(db, user, ecoe_event_id, *ADMIN_EVENT_ROLE_CODES)
    ecoe_event = db.get(ECOEEvent, ecoe_event_id)
    return build_dashboard(db, ecoe_event)["validation"]


# ── Results & Exports ──────────────────────────────────────────────────

def _by_station_block(db: Session, ecoe_event_id: int) -> dict:
    """OPT-16: bloque `by_station` (agregado + nota larga por estudiante).

    Sigue el patrón `frozen` de OPT-1 vía `read_station_results`: snapshot con el
    evento cerrado, recálculo en vivo antes. Sin `response_model` → aditivo.
    """
    station_rows, _ = read_station_results(db, ecoe_event_id)
    stations = db.scalars(
        select(Station).where(Station.ecoe_event_id == ecoe_event_id)
        .order_by(Station.station_number.asc(), Station.id.asc())
    ).all()
    students = {
        s.id: s
        for s in db.scalars(
            select(Student).where(Student.ecoe_event_id == ecoe_event_id)
        ).all()
    }
    return build_station_score_block(station_rows, list(stations), students)


@router.get("/results/{ecoe_event_id}")
def get_results(ecoe_event_id: int, db: Session = Depends(get_db), user=Depends(get_current_user)):
    ensure_event_access(db, user, ecoe_event_id, *ADMIN_EVENT_ROLE_CODES)
    results, frozen, consolidated_at = read_results(db, ecoe_event_id)
    return {
        "results": results,
        "frozen": frozen,
        "consolidated_at": consolidated_at.isoformat() if consolidated_at else None,
        "by_station": _by_station_block(db, ecoe_event_id),
        **build_traceability_report(db, ecoe_event_id, consolidated_results=results),
    }


@router.post("/results/{ecoe_event_id}/consolidate")
def consolidate_results(ecoe_event_id: int, db: Session = Depends(get_db), user=Depends(get_current_user)):
    ensure_event_access(db, user, ecoe_event_id, *ADMIN_EVENT_ROLE_CODES)
    results = persist_results(db, ecoe_event_id, actor_email=user.email)
    return {
        "consolidated": True,
        "results": results,
        "by_station": _by_station_block(db, ecoe_event_id),
        **build_traceability_report(db, ecoe_event_id, consolidated_results=results),
    }


@router.get("/results/{ecoe_event_id}/export/excel")
def export_excel(ecoe_event_id: int, db: Session = Depends(get_db), user=Depends(get_current_user)):
    ensure_event_access(db, user, ecoe_event_id, *ADMIN_EVENT_ROLE_CODES)
    content = export_results_excel(db, ecoe_event_id)
    return FastAPIResponse(
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
    ensure_event_access(db, user, ecoe_event_id, *ADMIN_EVENT_ROLE_CODES)
    if station_id is not None:
        station = db.get(Station, station_id)
        if not station or station.ecoe_event_id != ecoe_event_id:
            raise HTTPException(status_code=404, detail="Estación no encontrada en este ECOE")
    content = export_contingency_pdf(db, ecoe_event_id, station_id)
    return FastAPIResponse(
        content=content,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="contingencia-{ecoe_event_id}.pdf"'},
    )


# ── Incidents ──────────────────────────────────────────────────────────

@router.post("/incidents", response_model=IncidentRead)
def create_incident(
    payload: IncidentCreate,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    user=Depends(require_roles("admin_ecoe", "coeditor_docente", "coordinador_operativo", "cronometrador")),
):
    ensure_event_access(db, user, payload.ecoe_event_id,
                        RoleCode.admin_ecoe.value,
                        RoleCode.coeditor_docente.value,
                        RoleCode.coordinador_operativo.value,
                        RoleCode.cronometrador.value)
    if payload.station_id is not None:
        station = db.get(Station, payload.station_id)
        if not station or station.ecoe_event_id != payload.ecoe_event_id:
            raise HTTPException(status_code=400, detail="La estación no pertenece al ECOE indicado")
    incident = Incident(
        ecoe_event_id=payload.ecoe_event_id,
        station_id=payload.station_id,
        title=payload.title,
        detail=payload.detail,
        severity=payload.severity,
    )
    db.add(incident)
    db.commit()
    db.refresh(incident)

    # Broadcast to WebSocket clients
    background_tasks.add_task(
        live_timer.broadcast,
        payload.ecoe_event_id,
        {
            "type": "incident_created",
            "ecoe_event_id": payload.ecoe_event_id,
            "incident": {
                "id": incident.id,
                "station_id": incident.station_id,
                "title": incident.title,
                "detail": incident.detail,
                "severity": incident.severity,
                "resolved": incident.resolved,
                "created_at": str(incident.created_at),
            },
        },
    )

    return incident


@router.patch("/incidents/{incident_id}/resolve", response_model=IncidentRead)
def resolve_incident(
    incident_id: int,
    payload: IncidentResolve,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    user=Depends(require_roles("admin_ecoe", "coordinador_operativo", "cronometrador")),
):
    incident = db.get(Incident, incident_id)
    if not incident:
        raise HTTPException(status_code=404, detail="Incidencia no encontrada")
    ensure_event_access(db, user, incident.ecoe_event_id,
                        RoleCode.admin_ecoe.value,
                        RoleCode.coordinador_operativo.value,
                        RoleCode.cronometrador.value)

    incident.resolved = payload.resolved
    incident.resolved_at = utcnow_naive() if payload.resolved else None
    db.add(incident)
    db.commit()
    db.refresh(incident)

    # Broadcast update to WebSocket clients
    background_tasks.add_task(
        live_timer.broadcast,
        incident.ecoe_event_id,
        {
            "type": "incident_resolved",
            "ecoe_event_id": incident.ecoe_event_id,
            "incident_id": incident.id,
            "resolved": incident.resolved,
        },
    )

    return incident


@router.get("/incidents/{ecoe_event_id}", response_model=Page[IncidentRead])
def list_incidents(
    ecoe_event_id: int,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=DEFAULT_PAGE_SIZE, ge=1, le=MAX_PAGE_SIZE),
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
):
    ensure_event_access(db, user, ecoe_event_id,
                        RoleCode.admin_ecoe.value,
                        RoleCode.coordinador_operativo.value,
                        RoleCode.cronometrador.value)
    stmt = select(Incident).where(Incident.ecoe_event_id == ecoe_event_id).order_by(Incident.created_at.desc())
    return paginate_query(db, stmt, page=page, page_size=page_size)
