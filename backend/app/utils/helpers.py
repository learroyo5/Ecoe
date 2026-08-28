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


def normalize_station_ids(
    raw_station_ids: list[int] | None, *, single: bool = True
) -> list[int]:
    """Clean a station-id list, de-duplicating and dropping falsy values.

    `single=True` (default) keeps only the first id: most staff roles have at
    most one meaningful station (the evaluador's principal station). A
    `corrector` may cover several deferred-grading stations, so the staff
    routes pass `single=False` for that role.
    """
    seen: set[int] = set()
    station_ids: list[int] = []
    for station_id in raw_station_ids or []:
        if not station_id or station_id in seen:
            continue
        seen.add(station_id)
        station_ids.append(station_id)
    return station_ids[:1] if single else station_ids


# Roles cuyo `station_ids` puede tener más de una estación.
MULTI_STATION_ROLE_CODES = {"corrector"}


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
    single = str(staff.role_code) not in MULTI_STATION_ROLE_CODES
    normalized_station_ids = normalize_station_ids(staff.station_ids, single=single)
    changed = normalized_station_ids != (staff.station_ids or [])
    if changed:
        staff.station_ids = normalized_station_ids
    return normalized_station_ids, changed


# ── Submission integrity helpers ────────────────────────────────────────

# Tolerance for network latency / clock skew between client and server.
SUBMISSION_GRACE_SECONDS = 30


def checkin_submission_deadline(
    checkin: "StationCheckIn",
    station: "Station",
    *,
    extra_minutes: float = 0.0,
):
    """Nominal end of the submission window (without the latency grace).

    This is the deadline the UI should display and enforce; the server
    accepts up to SUBMISSION_GRACE_SECONDS beyond it to absorb network
    latency and clock skew.
    """
    return checkin.confirmed_at + timedelta(
        minutes=float(station.station_time_minutes or 0) + float(extra_minutes),
    )


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
    deadline = checkin_submission_deadline(checkin, station, extra_minutes=extra_minutes)
    if utcnow_naive() > deadline + timedelta(seconds=grace_seconds):
        raise HTTPException(
            status_code=400,
            detail="El tiempo de la estación ya expiró; el envío no puede aceptarse.",
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
    """Server-side session mode for READS: en_pilotaje maps to pilotaje.

    Non-raising: use it to scope queries (duplicate checks, exists flags).
    Writes must go through ensure_submission_stage instead, which rejects
    every state outside en_pilotaje / en_ejecucion.
    """
    from app.models.enums import ECOEStatus, SessionMode

    if str(ecoe_event.status) == ECOEStatus.en_pilotaje.value:
        return SessionMode.pilotaje.value
    return SessionMode.ejecucion.value


def ensure_submission_stage(ecoe_event) -> str:
    """Authoritative mode for WRITES (check-ins and submissions).

    Operational records are only accepted while the ECOE is formally in
    pilotaje or in real execution; anything recorded outside those states
    would contaminate results (e.g. a rehearsal while "publicado" would be
    stored as ejecucion). Returns the mode to record with.
    """
    from app.models.enums import ECOEStatus, SessionMode

    status = str(ecoe_event.status)
    if status == ECOEStatus.en_pilotaje.value:
        return SessionMode.pilotaje.value
    if status == ECOEStatus.en_ejecucion.value:
        return SessionMode.ejecucion.value
    raise HTTPException(
        status_code=409,
        detail=(
            "Los registros operativos solo se aceptan con el ECOE en pilotaje o en ejecución real "
            f"(estado actual: {status})."
        ),
    )


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


def get_latest_checkin_any_status(
    db: Session,
    ecoe_event_id: int,
    station_id: int,
    student_id: int,
) -> StationCheckIn | None:
    """Latest check-in for the tuple regardless of status.

    Contingency submissions arrive after the rotation moved on: the original
    check-in is usually already "cerrado" (or its window expired), so the
    active-only lookup would reject exactly the cases contingency exists for.
    """
    return db.scalar(
        select(StationCheckIn)
        .where(
            StationCheckIn.ecoe_event_id == ecoe_event_id,
            StationCheckIn.station_id == station_id,
            StationCheckIn.student_id == student_id,
        )
        .order_by(StationCheckIn.confirmed_at.desc(), StationCheckIn.id.desc())
    )


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
