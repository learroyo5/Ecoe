"""Generic normalization and business helpers shared across route modules.

Authorization lives in app.services.authorization, media access control in
app.services.media, and dict serializers in app.utils.serializers — this
module keeps only helpers with no authorization/media concerns.
"""

import re
from datetime import timedelta

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.entities import AssessmentTool, StaffAssignment, Station, StationCheckIn, Student
from app.utils.clock import utcnow_naive  # noqa: F401 — re-exported for existing importers

# ── Normalization helpers ───────────────────────────────────────────────

def normalize_rut(value: str | None) -> str:
    return str(value or "").strip().lower()


def normalize_email(value: str | None) -> str:
    return str(value or "").strip().lower()


_ECOE_NUMBER_TAIL = re.compile(r"^[A-Za-z]*0*(\d+)$")


def normalize_ecoe_lookup(value: str | None) -> str:
    """Forma canónica de un número ECOE para comparar sin fricción.

    Un número tipo ``E007`` / ``e7`` / ``007`` / ``7`` (prefijo de letras
    opcional + ceros a la izquierda + dígitos) se reduce a su valor numérico
    (``"7"``), así el evaluador puede tipear ``7`` o ``E007`` indistintamente.
    Cualquier otro formato (``MED-2026-007``) se compara en minúsculas tal cual.
    """
    text = str(value or "").strip()
    if not text:
        return ""
    match = _ECOE_NUMBER_TAIL.match(text)
    if match:
        return str(int(match.group(1)))
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

def format_ecoe_number(value: int, width: int = 3) -> str:
    """Formato canónico del número ECOE: prefijo ``E`` + valor con ceros
    a la izquierda (``E001``, ``E042``). La búsqueda igual acepta que el
    evaluador tipee ``1`` / ``001`` / ``E001`` (ver ``normalize_ecoe_lookup``)."""
    return f"E{value:0{max(3, width)}d}"


def _ecoe_number_value(text: str) -> int | None:
    """Valor numérico de un número ECOE en cualquier formato (``E007`` -> 7)."""
    match = _ECOE_NUMBER_TAIL.match(str(text or "").strip())
    return int(match.group(1)) if match else None


def next_student_ecoe_number(db: Session, ecoe_event_id: int) -> str:
    numbers = db.scalars(select(Student.ecoe_number).where(Student.ecoe_event_id == ecoe_event_id)).all()
    numeric_values: list[int] = []
    widths: list[int] = []
    for value in numbers:
        parsed = _ecoe_number_value(value)
        if parsed is not None:
            numeric_values.append(parsed)
            widths.append(len(re.sub(r"\D", "", str(value))))

    next_value = (max(numeric_values) if numeric_values else 0) + 1
    width = max(3, max(widths, default=3), len(str(next_value)))
    return format_ecoe_number(next_value, width)


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


def isoformat_or_none(value):
    """Serialize an optional datetime for a JSON response."""
    return value.isoformat() if value is not None else None


LIVE_IDLE_STATUSES = {"idle", "ready"}


def _live_phase_station_deadline(session, *, far_past):
    """Nominal end of the station phase currently governed by ``session``.

    ``None`` means the central clock is paused (no effective deadline);
    ``far_past`` is returned when the phase is definitely closed but no exact
    instant is available (e.g. the operator forced ``expire_phase``).
    """
    status = str(session.status)
    if status == "paused":
        return None
    if status == "running":
        if session.phase_started_at is None:
            # expire_phase / buzzer: the station phase was forced closed.
            return far_past
        return session.phase_started_at + timedelta(seconds=session.remaining_seconds or 0)
    if status == "transition":
        # The station phase ended when the transition phase started.
        return session.phase_started_at or far_past
    # idle / ready / unknown: caller falls back to the per-check-in window.
    return "fallback"


def resolve_submission_deadline(
    db: Session,
    ecoe_event,
    checkin: "StationCheckIn",
    station: "Station",
    *,
    for_evaluator: bool = False,
):
    """Authoritative nominal submission deadline for an operational screen.

    OPT-20 F2 (D1/D2): the effective deadline of any operational submission is
    the end of the current phase of the event's ``LiveSession`` (server clock),
    **not** ``confirmed_at + station_time`` any more. A student who checks in
    late loses that time (D2). Fallbacks:

    - No ``LiveSession`` yet, or ``idle`` / ``ready`` (typical during
      ``en_pilotaje`` when nobody drives ``/live``): fall back to Reloj B
      (``checkin_submission_deadline``) — the historical, low-friction
      behaviour.
    - ``paused``: returns ``None`` — the central clock is stopped, so writes
      are accepted while the pause lasts and the window resumes on ``resume``.

    Returns a naive UTC ``datetime`` or ``None``. The grace period is applied
    by the caller (``ensure_checkin_within_time``), never baked in here.
    """
    from app.models.entities import LiveSession

    extra_minutes = float(station.transition_time_minutes or 0) if for_evaluator else 0.0
    fallback = lambda: checkin_submission_deadline(  # noqa: E731
        checkin, station, extra_minutes=extra_minutes
    )

    session = db.scalar(
        select(LiveSession).where(LiveSession.ecoe_event_id == ecoe_event.id).limit(1)
    )
    if session is None or str(session.status) in LIVE_IDLE_STATUSES:
        return fallback()

    far_past = utcnow_naive() - timedelta(days=1)
    station_deadline = _live_phase_station_deadline(session, far_past=far_past)
    if station_deadline is None:
        return None  # paused
    if station_deadline == "fallback":
        return fallback()

    if not for_evaluator:
        return station_deadline

    # The evaluator records after the student leaves, so the window also spans
    # the transition phase (decision 6: end of the *real* transition phase).
    if str(session.status) == "transition":
        if session.phase_started_at is not None:
            return session.phase_started_at + timedelta(
                seconds=session.remaining_seconds or 0
            )
        return station_deadline
    # running: the transition phase has not started; approximate its end with
    # one full transition duration after the station phase so the evaluator is
    # not blocked before the operator presses ``next_transition``.
    return station_deadline + timedelta(seconds=session.transition_time_seconds or 0)


def ensure_checkin_within_time(
    db: Session,
    ecoe_event,
    checkin: "StationCheckIn",
    station: "Station",
    *,
    for_evaluator: bool = False,
    grace_seconds: int = SUBMISSION_GRACE_SECONDS,
) -> None:
    """Reject submissions after the authoritative submission window expired.

    The window is derived from the event's ``LiveSession`` (see
    ``resolve_submission_deadline``); it falls back to the per-check-in window
    when no live session is driving the event. The client also blocks the UI,
    but the server is the authority: client clocks can be wrong or manipulated.
    A ``paused`` live session has no effective deadline — the write is accepted.
    """
    deadline = resolve_submission_deadline(
        db, ecoe_event, checkin, station, for_evaluator=for_evaluator
    )
    if deadline is None:
        return
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


def live_phase_snapshot(db: Session, ecoe_event_id: int) -> dict:
    """Read-only public view of the live clock for operational screens (OPT-20 F1).

    Purely additive: it does NOT change the submission deadline (writes still
    go through ``ensure_checkin_within_time`` / ``checkin_submission_deadline``).
    The kiosk / evaluador / estudiante screens use this for the first paint and
    as a no-WebSocket fallback so a pause still freezes their local countdown.
    """
    from app.models.entities import LiveSession

    session = db.scalar(
        select(LiveSession).where(LiveSession.ecoe_event_id == ecoe_event_id).limit(1)
    )
    if not session:
        return {"live_status": None, "current_phase_ends_at": None, "paused": False}
    ends_at = None
    if session.status in LIVE_RUNNING_STATUSES and session.phase_started_at:
        ends_at = (
            utcnow_naive() + timedelta(seconds=compute_remaining_seconds(session))
        ).isoformat()
    return {
        "live_status": session.status,
        "current_phase_ends_at": ends_at,
        "paused": session.status == "paused",
    }


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
    raw = str(ecoe_number or "").strip()
    lookup = normalize_ecoe_lookup(raw)
    if not lookup:
        return None

    statement = select(Student).where(Student.ecoe_event_id == ecoe_event_id)
    if active_only:
        statement = statement.where(Student.is_active.is_(True))
    students = list(db.scalars(statement.order_by(Student.id.asc())))

    # Coincidencia exacta (case-insensitive) primero: si el evento distingue
    # "E7" de "E007", gana la que el evaluador tipeó tal cual.
    exact = [s for s in students if (s.ecoe_number or "").strip().lower() == raw.lower()]
    if len(exact) == 1:
        return exact[0]

    # Si no, coincidencia canónica ("7" == "007" == "E007"). Ambigua -> None:
    # nunca adivinar entre dos estudiantes.
    canonical = [s for s in students if normalize_ecoe_lookup(s.ecoe_number) == lookup]
    if len(canonical) == 1:
        return canonical[0]
    return None
