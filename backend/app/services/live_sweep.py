"""Server-side finalization of expired live phases (OPT-20 F2, R3/R5).

Hybrid trigger, no scheduler (decision 1):

- **Primary** — ``POST /live/control`` (``start`` / ``next_transition`` /
  ``reset`` / the new ``expire_phase``) runs the sweep after applying the
  timer action.
- **Safety net** — a lazy sweep on the operational context endpoints
  (``/kiosk/context``, ``/evaluator/context/{id}``, ``/live/{id}``) which the
  live circuit polls continuously, so a tablet that dies mid-station is still
  captured within a few seconds. (Not ``/student/access``: that screen sees one
  student / one station and closing the student's own check-in mid-poll would
  flip them back to "waiting for confirmation".)

For every ``confirmado`` check-in that is the current occupant of its station,
whose live phase has expired, whose station requires a student form and which
has no definitive ``StudentResponse`` for the event's mode, the sweep:

- creates a locked ``submission_kind="auto"`` ``StudentResponse`` with the
  server-side draft answers (or ``{}`` — marked but scoring 0, D4),
- auto-grades it (``apply_auto_grading``),
- closes the check-in and discards the draft.

Evaluator records are deliberately left untouched (D3, OPT-20 F3): the
evaluator screen autosaves its own ``is_draft=True`` row via
``PUT /evaluator/draft`` while filling it in, so when the phase expires that
draft simply stays a draft — the sweep neither promotes it nor creates a
blank one. A station with no evaluator draft at all shows up in the
traceability report as a missing evaluation, to be resolved by contingency.

The sweep never runs once the event is ``cerrado`` / ``archivado``
(``FROZEN_RESULT_STATUSES``); the close transition already consolidates and
closes every check-in.
"""

from datetime import timedelta

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.entities import (
    LiveSession,
    Station,
    StationCheckIn,
    StationResponseDraft,
    StudentResponse,
)
from app.models.enums import ECOEStatus
from app.services.drafts import discard_checkin_draft
from app.services.grading import apply_auto_grading
from app.utils.clock import utcnow_naive
from app.utils.helpers import (
    SUBMISSION_GRACE_SECONDS,
    resolve_session_mode,
    resolve_submission_deadline,
)

_SUBMISSION_STAGES = {ECOEStatus.en_pilotaje.value, ECOEStatus.en_ejecucion.value}


def sweep_expired_phases(
    db: Session,
    ecoe_event,
    *,
    grace_seconds: int = SUBMISSION_GRACE_SECONDS,
    force: bool = False,
    commit: bool = True,
) -> dict:
    """Finalize check-ins whose live phase already expired. Idempotent.

    ``force`` skips the time check (used by ``expire_phase`` — the operator
    explicitly ended the phase). Returns ``{"auto_responses": n,
    "closed_checkins": n}``.
    """
    result = {"auto_responses": 0, "closed_checkins": 0}

    # Re-read the status to shrink the race window against the close
    # transition (which consolidates + closes check-ins in its own tx).
    try:
        db.refresh(ecoe_event)
    except Exception:  # pragma: no cover - detached/pending object
        pass
    if str(ecoe_event.status) not in _SUBMISSION_STAGES:
        return result

    mode = resolve_session_mode(ecoe_event)
    session = db.scalar(
        select(LiveSession).where(LiveSession.ecoe_event_id == ecoe_event.id).limit(1)
    )
    # Nothing to do while the central clock is stopped: the window is frozen
    # for everyone and resumes on `resume`.
    if not force and session is not None and str(session.status) == "paused":
        return result

    checkins = db.scalars(
        select(StationCheckIn)
        .where(
            StationCheckIn.ecoe_event_id == ecoe_event.id,
            StationCheckIn.status == "confirmado",
        )
        .order_by(StationCheckIn.confirmed_at.desc(), StationCheckIn.id.desc())
    ).all()

    now = utcnow_naive()
    seen_stations: set[int] = set()
    for checkin in checkins:
        # Only the current occupant of a station is auto-finalized; older
        # `confirmado` rows are rotation residue (already logically closed).
        if checkin.station_id in seen_stations:
            continue
        seen_stations.add(checkin.station_id)

        station = db.get(Station, checkin.station_id)
        if station is None or not station.requires_student_form:
            continue

        if not force:
            deadline = resolve_submission_deadline(db, ecoe_event, checkin, station)
            if deadline is None or now <= deadline + timedelta(seconds=grace_seconds):
                continue

        existing = db.scalar(
            select(StudentResponse.id)
            .where(
                StudentResponse.ecoe_event_id == ecoe_event.id,
                StudentResponse.station_id == checkin.station_id,
                StudentResponse.student_id == checkin.student_id,
                StudentResponse.mode == mode,
            )
            .limit(1)
        )
        if existing is not None:
            continue

        draft = db.scalar(
            select(StationResponseDraft).where(
                StationResponseDraft.checkin_id == checkin.id
            )
        )
        answers = dict(draft.answers or {}) if draft is not None else {}

        response = StudentResponse(
            ecoe_event_id=ecoe_event.id,
            station_id=checkin.station_id,
            student_id=checkin.student_id,
            mode=mode,
            answers=answers,
            locked=True,
            by_contingency=False,
            submission_kind="auto",
        )
        apply_auto_grading(response, station.student_form_definition)
        try:
            with db.begin_nested():
                db.add(response)
                db.flush()
        except IntegrityError:
            # A manual submit / contingency / the old client autosubmit won
            # the race on the unique key — the station is already answered.
            db.expunge(response)
            continue

        checkin.status = "cerrado"
        db.add(checkin)
        discard_checkin_draft(db, checkin.id)
        result["auto_responses"] += 1
        result["closed_checkins"] += 1

    if commit and (result["auto_responses"] or result["closed_checkins"]):
        db.commit()
    return result
