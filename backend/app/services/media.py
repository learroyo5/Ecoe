"""Media upload validation and per-user media access control.

Split out of utils/helpers.py: this is media-specific authorization (who can
see/write which asset) built on top of the generic event authorization in
services/authorization.py.
"""

import uuid
from pathlib import Path

from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.entities import MediaAsset, StaffAssignment, Station, Student, User
from app.models.enums import RoleCode
from app.services.authorization import ensure_event_access
from app.utils.helpers import (
    ensure_primary_station_assignment,
    get_active_checkin,
    normalize_email,
)

# ── Media upload constants ──────────────────────────────────────────────

ALLOWED_MEDIA_EXTENSIONS = {
    ".jpg", ".jpeg", ".png", ".gif", ".webp", ".svg",
    ".mp3", ".wav", ".ogg", ".m4a",
    ".mp4", ".webm", ".mov",
    ".pdf", ".docx", ".pptx", ".xlsx",
}
MAX_MEDIA_SIZE_BYTES = 50 * 1024 * 1024  # 50 MB
ALLOWED_VIEWERS = {"estudiante", "evaluador", "ambos"}

_MAGIC_SIGNATURES: dict[str, list[bytes]] = {
    ".jpg": [b"\xff\xd8\xff"],
    ".jpeg": [b"\xff\xd8\xff"],
    ".png": [b"\x89PNG\r\n\x1a\n"],
    ".gif": [b"GIF87a", b"GIF89a"],
    ".webp": [b"RIFF"],
    ".pdf": [b"%PDF"],
    ".mp3": [b"\xff\xfb", b"\xff\xf3", b"\xff\xf2", b"ID3"],
    ".mp4": [b"\x00\x00\x00\x18ftypmp42", b"\x00\x00\x00\x1cftypmp42"],
}


def validate_media_type(content: bytes, suffix: str, _declared_content_type: str) -> None:
    """Check that the file's magic bytes are consistent with its extension."""
    signatures = _MAGIC_SIGNATURES.get(suffix)
    if signatures is None:
        return
    if not any(content.startswith(sig) for sig in signatures):
        raise HTTPException(
            status_code=400,
            detail=f"El contenido del archivo no coincide con la extensión {suffix}",
        )


def safe_media_filename(original_name: str | None) -> str:
    raw = str(original_name or "archivo").strip()
    safe_base = Path(raw).name
    if not safe_base:
        safe_base = "archivo"
    safe_base = "".join(char for char in safe_base if char.isprintable() and char not in ("\x00",))
    if not safe_base:
        safe_base = "archivo"
    suffix = Path(safe_base).suffix.lower()
    if suffix not in ALLOWED_MEDIA_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail=f"Tipo de archivo no permitido. Extensiones aceptadas: {', '.join(sorted(ALLOWED_MEDIA_EXTENSIONS))}",
        )
    return f"{uuid.uuid4().hex}_{safe_base}"


def _staff_assignment_for_station(db: Session, user: User, ecoe_event_id: int, role_code: str):
    return db.scalar(
        select(StaffAssignment).where(
            StaffAssignment.ecoe_event_id == ecoe_event_id,
            StaffAssignment.email == normalize_email(user.email),
            StaffAssignment.role_code == role_code,
        )
    )


def can_user_access_station_media(
    db: Session,
    user: User,
    station: Station,
    target_viewer: str,
    *,
    writable: bool = False,
) -> bool:
    event_roles = ensure_event_access(
        db,
        user,
        station.ecoe_event_id,
        RoleCode.admin_ecoe.value,
        RoleCode.coeditor_docente.value,
        RoleCode.coordinador_operativo.value,
        RoleCode.cronometrador.value,
        RoleCode.evaluador.value,
        RoleCode.estudiante.value,
    )

    if writable:
        return bool(event_roles & {RoleCode.admin_ecoe.value, RoleCode.coeditor_docente.value})

    if event_roles & {
        RoleCode.admin_ecoe.value,
        RoleCode.coeditor_docente.value,
        RoleCode.coordinador_operativo.value,
    }:
        return True

    if RoleCode.evaluador.value in event_roles:
        if target_viewer not in {"evaluador", "ambos"}:
            return False
        assignment = _staff_assignment_for_station(
            db, user, station.ecoe_event_id, RoleCode.evaluador.value
        )
        assigned_station_ids, _ = ensure_primary_station_assignment(assignment)
        return station.id in assigned_station_ids

    if RoleCode.estudiante.value in event_roles:
        if target_viewer not in {"estudiante", "ambos"}:
            return False
        student = db.scalar(
            select(Student).where(
                Student.ecoe_event_id == station.ecoe_event_id,
                func.lower(Student.email) == normalize_email(user.email),
                Student.is_active.is_(True),
            )
        )
        if not student:
            return False
        active_checkin = get_active_checkin(
            db,
            station.ecoe_event_id,
            station.id,
            student.id,
        )
        return active_checkin is not None

    return False


def filter_media_for_user(
    db: Session,
    user: User,
    station: Station,
    assets: list[MediaAsset],
) -> list[MediaAsset]:
    return [
        asset for asset in assets
        if can_user_access_station_media(db, user, station, asset.target_viewer)
    ]


def get_media_asset_for_user(
    db: Session,
    user: User,
    asset_id: int,
    *,
    writable: bool = False,
) -> MediaAsset:
    asset = db.get(MediaAsset, asset_id)
    if not asset:
        raise HTTPException(status_code=404, detail="Archivo no encontrado")
    if not asset.station_id:
        raise HTTPException(status_code=403, detail="Archivo sin estación asociada")
    station = db.get(Station, asset.station_id)
    if not station:
        raise HTTPException(status_code=404, detail="Estación no encontrada")
    if not can_user_access_station_media(db, user, station, asset.target_viewer, writable=writable):
        raise HTTPException(status_code=403, detail="No tienes permisos para acceder a este archivo")
    return asset
