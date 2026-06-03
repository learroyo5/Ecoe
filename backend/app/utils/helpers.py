"""Helper functions extracted from routes.py for reuse across route modules."""

import uuid
from pathlib import Path

from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.entities import (
    AssessmentItem,
    AssessmentTool,
    ECOEPermission,
    ECOEEvent,
    EvaluatorRecord,
    MediaAsset,
    StaffAssignment,
    Station,
    StationCheckIn,
    Student,
    StudentResponse,
    User,
)
from app.models.enums import RoleCode

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

# ── Role sets ───────────────────────────────────────────────────────────

STAFF_SCOPED_ROLE_CODES = {
    RoleCode.coeditor_docente.value,
    RoleCode.coordinador_operativo.value,
    RoleCode.evaluador.value,
    RoleCode.cronometrador.value,
}
ADMIN_EVENT_ROLE_CODES = {
    RoleCode.creador_ecoe.value,
    RoleCode.coeditor_docente.value,
    RoleCode.coordinador_operativo.value,
}
ALLOWED_STAFF_ASSIGNMENT_ROLE_CODES = STAFF_SCOPED_ROLE_CODES

# ── Normalization helpers ───────────────────────────────────────────────

def normalize_rut(value: str | None) -> str:
    return str(value or "").strip().lower()


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


# ── Business helpers ────────────────────────────────────────────────────

def next_student_ecoe_number(db: Session, ecoe_event_id: int) -> str:
    numbers = db.scalars(select(Student.ecoe_number).where(Student.ecoe_event_id == ecoe_event_id)).all()
    numeric_values: list[int] = []
    widths: list[int] = []
    for value in numbers:
        text = str(value or "").strip()
        if text.isdigit():
            numeric_values.append(int(text))
            widths.append(len(text))

    next_value = (max(numeric_values) if numeric_values else 0) + 1
    width = max(3, max(widths, default=3), len(str(next_value)))
    return str(next_value).zfill(width)


def ensure_primary_station_assignment(staff: StaffAssignment | None) -> tuple[list[int], bool]:
    if not staff:
        return [], False
    normalized_station_ids = normalize_station_ids(staff.station_ids)
    changed = normalized_station_ids != (staff.station_ids or [])
    if changed:
        staff.station_ids = normalized_station_ids
    return normalized_station_ids, changed


def validate_staff_role_code(role_code: str) -> str:
    normalized_role = str(role_code or "").strip().lower()
    if normalized_role not in ALLOWED_STAFF_ASSIGNMENT_ROLE_CODES:
        raise HTTPException(status_code=400, detail="Rol operativo no permitido para este registro")
    return normalized_role


# ── Authorization helpers ───────────────────────────────────────────────

def get_user_event_roles(db: Session, user: User, ecoe_event_id: int) -> set[str]:
    roles: set[str] = set()
    normalized_email = normalize_email(user.email)
    user_role = str(user.role.code)

    if user_role == RoleCode.creador_ecoe.value:
        creator_permission = db.scalar(
            select(ECOEPermission).where(
                ECOEPermission.ecoe_event_id == ecoe_event_id,
                ECOEPermission.user_id == user.id,
                ECOEPermission.role_code == RoleCode.creador_ecoe.value,
            )
        )
        if creator_permission:
            roles.add(RoleCode.creador_ecoe.value)

    if user_role in STAFF_SCOPED_ROLE_CODES:
        staff_assignment = db.scalar(
            select(StaffAssignment).where(
                StaffAssignment.ecoe_event_id == ecoe_event_id,
                StaffAssignment.email == normalized_email,
                StaffAssignment.role_code == user_role,
            )
        )
        if staff_assignment:
            roles.add(user_role)

    if user_role == RoleCode.estudiante.value:
        student = db.scalar(
            select(Student).where(
                Student.ecoe_event_id == ecoe_event_id,
                func.lower(Student.email) == normalized_email,
                Student.is_active.is_(True),
            )
        )
        if student:
            roles.add(RoleCode.estudiante.value)

    return roles


def ensure_event_access(db: Session, user: User, ecoe_event_id: int, *allowed_roles: str) -> set[str]:
    ecoe_event = db.get(ECOEEvent, ecoe_event_id)
    if not ecoe_event:
        raise HTTPException(status_code=404, detail="ECOE no encontrado")

    event_roles = get_user_event_roles(db, user, ecoe_event_id)
    if not event_roles:
        raise HTTPException(
            status_code=403,
            detail="No tienes permisos para acceder a este ECOE",
        )
    if allowed_roles and not any(role in event_roles for role in allowed_roles):
        raise HTTPException(
            status_code=403,
            detail="No tienes permisos para esta accion en este ECOE",
        )
    return event_roles


def list_accessible_ecoe_events(db: Session, user: User) -> list[ECOEEvent]:
    user_role = str(user.role.code)
    normalized_email = normalize_email(user.email)

    if user_role == RoleCode.creador_ecoe.value:
        event_ids = db.scalars(
            select(ECOEPermission.ecoe_event_id).where(
                ECOEPermission.user_id == user.id,
                ECOEPermission.role_code == RoleCode.creador_ecoe.value,
            )
        ).all()
    elif user_role in STAFF_SCOPED_ROLE_CODES:
        event_ids = db.scalars(
            select(StaffAssignment.ecoe_event_id).where(
                StaffAssignment.email == normalized_email,
                StaffAssignment.role_code == user_role,
            )
        ).all()
    elif user_role == RoleCode.estudiante.value:
        event_ids = db.scalars(
            select(Student.ecoe_event_id).where(
                func.lower(Student.email) == normalized_email,
                Student.is_active.is_(True),
            )
        ).all()
    else:
        event_ids = []

    if not event_ids:
        return []

    return list(
        db.scalars(
            select(ECOEEvent)
            .where(ECOEEvent.id.in_(event_ids))
            .order_by(ECOEEvent.date.desc(), ECOEEvent.id.desc())
        ).all()
    )


def ensure_matching_operational_user(
    db: Session,
    *,
    email: str,
    expected_role: str,
) -> User:
    normalized_email = normalize_email(email)
    user = db.scalar(
        select(User).where(func.lower(User.email) == normalized_email)
    )
    if not user or str(user.role.code) != expected_role:
        raise HTTPException(
            status_code=400,
            detail=f"No existe una cuenta activa con rol {expected_role} para ese correo",
        )
    if not user.is_active:
        raise HTTPException(
            status_code=400,
            detail="La cuenta asociada a este correo se encuentra inactiva",
        )
    return user


# ── Check-in / lookup helpers ───────────────────────────────────────────

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


# ── Serialization helpers ───────────────────────────────────────────────

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
        "file_url": f"/api/media/file/{asset.id}",
    }


# ── Media helpers ───────────────────────────────────────────────────────

def validate_media_type(content: bytes, suffix: str, _declared_content_type: str) -> None:
    """Check that the file's magic bytes are consistent with its extension."""
    signatures = _MAGIC_SIGNATURES.get(suffix)
    if signatures is None:
        return
    if not any(content.startswith(sig) for sig in signatures):
        raise HTTPException(
            status_code=400,
            detail=f"El contenido del archivo no coincide con la extension {suffix}",
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
