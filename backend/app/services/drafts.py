"""Server-side autosave of a student's in-progress station form (OPT-20 F2).

The kiosk / student screens push the current answers here on every change
(debounced) so ``services/live_sweep`` always has something to finalize when
the phase expires. The draft is discarded the moment a definitive
``StudentResponse`` exists for the check-in.
"""

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.models.entities import StationCheckIn, StationResponseDraft


def upsert_checkin_draft(
    db: Session, checkin: StationCheckIn, answers: dict | None
) -> StationResponseDraft:
    draft = db.scalar(
        select(StationResponseDraft).where(
            StationResponseDraft.checkin_id == checkin.id
        )
    )
    if draft is None:
        draft = StationResponseDraft(
            checkin_id=checkin.id,
            ecoe_event_id=checkin.ecoe_event_id,
            station_id=checkin.station_id,
            student_id=checkin.student_id,
            answers=answers or {},
        )
    else:
        draft.answers = answers or {}
    db.add(draft)
    return draft


def discard_checkin_draft(db: Session, checkin_id: int) -> None:
    db.execute(
        delete(StationResponseDraft).where(
            StationResponseDraft.checkin_id == checkin_id
        )
    )
