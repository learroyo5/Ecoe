"""Live panel, timer control, media, validation, results, and incidents routes."""

import logging
from http.cookies import SimpleCookie
from pathlib import Path

from fastapi import APIRouter, BackgroundTasks, Depends, File, HTTPException, Query, UploadFile, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse, Response as FastAPIResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.db.session import SessionLocal, get_db
from app.models.entities import (
    ECOEEvent,
    Incident,
    LiveSession,
    MediaAsset,
    Station,
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
from app.services.ecoe import (
    build_dashboard,
    build_traceability_report,
    export_contingency_pdf,
    export_results_excel,
    persist_results,
    read_results,
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
from app.utils.helpers import compute_remaining_seconds, utcnow_naive
from app.utils.pagination import DEFAULT_PAGE_SIZE, MAX_PAGE_SIZE, paginate_query
from app.services.websocket import live_timer

logger = logging.getLogger("ecoe.operational")

router = APIRouter()

# ── WebSocket: Live Timer ──────────────────────────────────────────────

@router.websocket("/ws/live/{ecoe_event_id}")
async def websocket_live_timer(websocket: WebSocket, ecoe_event_id: int):
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

    with SessionLocal() as db:
        try:
            user = authenticate_session_token(db, token)
            ensure_event_access(
                db,
                user,
                ecoe_event_id,
                RoleCode.admin_ecoe.value,
                RoleCode.coordinador_operativo.value,
                RoleCode.cronometrador.value,
            )
        except HTTPException:
            await websocket.close(code=1008)
            return

    await live_timer.connect(ecoe_event_id, websocket)
    try:
        while True:
            # Keep connection alive; client can send ping/pong
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
    }


@router.get("/live/{ecoe_event_id}")
def get_live_panel(ecoe_event_id: int, db: Session = Depends(get_db), user=Depends(get_current_user)):
    ensure_event_access(db, user, ecoe_event_id,
                        RoleCode.admin_ecoe.value,
                        RoleCode.coordinador_operativo.value,
                        RoleCode.cronometrador.value)
    session = db.scalar(select(LiveSession).where(LiveSession.ecoe_event_id == ecoe_event_id).limit(1))
    if not session:
        raise HTTPException(status_code=404, detail="Sesión en vivo no encontrada")
    return live_session_state(session)


@router.post("/live/control")
def control_timer(
    payload: TimerAction,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    user=Depends(require_roles("admin_ecoe", "coordinador_operativo", "cronometrador")),
):
    ensure_event_access(db, user, payload.ecoe_event_id,
                        RoleCode.admin_ecoe.value,
                        RoleCode.coordinador_operativo.value,
                        RoleCode.cronometrador.value)
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
    now = utcnow_naive()
    if payload.action == "start":
        session.status = "running"
        session.remaining_seconds = session.station_time_seconds
        session.phase_started_at = now
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
    elif payload.action == "next_transition":
        session.status = "transition"
        session.remaining_seconds = session.transition_time_seconds
        session.current_station_index += 1
        session.phase_started_at = now
    else:
        raise HTTPException(status_code=400, detail="Acción no soportada")
    db.add(session)
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

@router.get("/results/{ecoe_event_id}")
def get_results(ecoe_event_id: int, db: Session = Depends(get_db), user=Depends(get_current_user)):
    ensure_event_access(db, user, ecoe_event_id, *ADMIN_EVENT_ROLE_CODES)
    results, frozen, consolidated_at = read_results(db, ecoe_event_id)
    return {
        "results": results,
        "frozen": frozen,
        "consolidated_at": consolidated_at.isoformat() if consolidated_at else None,
        **build_traceability_report(db, ecoe_event_id, consolidated_results=results),
    }


@router.post("/results/{ecoe_event_id}/consolidate")
def consolidate_results(ecoe_event_id: int, db: Session = Depends(get_db), user=Depends(get_current_user)):
    ensure_event_access(db, user, ecoe_event_id, *ADMIN_EVENT_ROLE_CODES)
    results = persist_results(db, ecoe_event_id, actor_email=user.email)
    return {
        "consolidated": True,
        "results": results,
        **build_traceability_report(db, ecoe_event_id, consolidated_results=results),
    }


@router.get("/results/{ecoe_event_id}/export/excel")
def export_excel(ecoe_event_id: int, db: Session = Depends(get_db), user=Depends(get_current_user)):
    ensure_event_access(db, user, ecoe_event_id, *ADMIN_EVENT_ROLE_CODES)
    content = export_results_excel(db, ecoe_event_id, persist=False)
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
    user=Depends(require_roles("admin_ecoe", "coordinador_operativo", "cronometrador")),
):
    ensure_event_access(db, user, payload.ecoe_event_id,
                        RoleCode.admin_ecoe.value,
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
