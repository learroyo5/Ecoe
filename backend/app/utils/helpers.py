"""Generic normalization and business helpers shared across route modules.

Authorization lives in app.services.authorization, media access control in
app.services.media, and dict serializers in app.utils.serializers — this
module keeps only helpers with no authorization/media concerns.
"""

from datetime import timedelta

from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.entities import AssessmentTool, StaffAssignment, Station, StationCheckIn, Student
from app.utils.clock import utcnow_naive  # noqa: F401 — re-exported for existing importers

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


# ── Submission integrity helpers ────────────────────────────────────────

# Tolerance for network latency / clock skew between client and server.
SUBMISSION_GRACE_SECONDS = 30


def ensure_checkin_within_time(
    checkin: "StationCheckIn",
    station: "Station",
    *,
    extra_minutes: float = 0.0,
    grace_seconds: int = SUBMISSION_GRACE_SECONDS,
) -> None:
    """Reject submissions after the station time window has expired.

    The window starts when the evaluator confirms the check-in. The client
    also blocks the UI, but the server is the authority: client clocks can
    be wrong or manipulated.
    """
    window = timedelta(
        minutes=float(station.station_time_minutes or 0) + float(extra_minutes),
        seconds=grace_seconds,
    )
    if utcnow_naive() > checkin.confirmed_at + window:
        raise HTTPException(
            status_code=400,
            detail="El tiempo de la estacion ya expiro; el envio no puede aceptarse.",
        )


def resolve_station_max_score(db: Session, station: "Station") -> float:
    """Authoritative max score for a station, never trusting the client.

    Preference order: sum of the assessment tool items, the tool's declared
    max score, then the station's own max score.
    """
    if station.assessment_tool_id:
        tool = db.get(AssessmentTool, station.assessment_tool_id)
        if tool:
            items_total = sum(item.score_per_item for item in tool.items)
            if items_total > 0:
                return float(items_total)
            if tool.max_score and tool.max_score > 0:
                return float(tool.max_score)
    return float(station.max_score or 0)


LIVE_RUNNING_STATUSES = {"running", "transition"}


def compute_remaining_seconds(session) -> int:
    """Authoritative remaining time of a LiveSession: server clock, not clients'."""
    if session.status in LIVE_RUNNING_STATUSES and session.phase_started_at:
        elapsed = (utcnow_naive() - session.phase_started_at).total_seconds()
        return max(0, round(session.remaining_seconds - elapsed))
    return session.remaining_seconds


def resolve_session_mode(ecoe_event) -> str:
    """Server-side session mode: piloting states record as pilotaje."""
    from app.models.enums import ECOEStatus, SessionMode

    piloting = {
        ECOEStatus.listo_para_pilotaje.value,
        ECOEStatus.en_pilotaje.value,
    }
    if str(ecoe_event.status) in piloting:
        return SessionMode.pilotaje.value
    return SessionMode.ejecucion.value


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

    raw = str(ecoe_number or "").strip()
    if raw.isdigit():
        # Numeric lookups match regardless of zero padding: "7" == "007".
        statement = statement.where(
            func.ltrim(Student.ecoe_number, "0") == lookup
        )
    else:
        statement = statement.where(func.lower(Student.ecoe_number) == lookup)

    return db.scalar(statement.order_by(Student.id.asc()).limit(1))
