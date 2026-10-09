"""Server-side autosave of a student's in-progress station form (OPT-20 F2).

The kiosk / student screens push the current answers here on every change
(debounced) so ``services/live_sweep`` always has something to finalize when
the phase expires. The draft is discarded the moment a definitive
``StudentResponse`` exists for the check-in.
"""

from sqlalchemy import delete, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.entities import StationCheckIn, StationResponseDraft


def upsert_checkin_draft(
    db: Session,
    checkin: StationCheckIn,
    answers: dict | None,
    *,
    client_seq: int | None = None,
) -> tuple[StationResponseDraft, bool]:
    """Guarda el borrador y devuelve ``(borrador, aplicado)``.

    F0.2 (H05): si el dispositivo envía ``client_seq`` y ya hay guardado uno
    mayor o igual, el borrador entrante es viejo (llegó tarde o es un
    reintento) y NO se aplica. Dos primeros guardados simultáneos chocan en la
    unicidad por check-in: el que pierde reintenta como actualización.
    """
    def _current() -> StationResponseDraft | None:
        return db.scalar(
            select(StationResponseDraft).where(StationResponseDraft.checkin_id == checkin.id)
        )

    draft = _current()
    if draft is None:
        draft = StationResponseDraft(
            checkin_id=checkin.id,
            ecoe_event_id=checkin.ecoe_event_id,
            station_id=checkin.station_id,
            student_id=checkin.student_id,
            answers=answers or {},
            client_seq=client_seq,
        )
        try:
            with db.begin_nested():
                db.add(draft)
                db.flush()
            return draft, True
        except IntegrityError:
            draft = _current()
            if draft is None:  # pragma: no cover - se borró entre medio
                raise
    if (
        client_seq is not None
        and draft.client_seq is not None
        and client_seq <= draft.client_seq
    ):
        return draft, False
    draft.answers = answers or {}
    if client_seq is not None:
        draft.client_seq = client_seq
    db.add(draft)
    return draft, True


def discard_checkin_draft(db: Session, checkin_id: int) -> None:
    db.execute(
        delete(StationResponseDraft).where(
            StationResponseDraft.checkin_id == checkin_id
        )
    )
