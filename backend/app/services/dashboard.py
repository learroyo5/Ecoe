"""Dashboard data aggregation service."""

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.entities import (
    ECOEEvent,
    EvaluatorRecord,
    Incident,
    LiveSession,
    Station,
    StudentResponse,
)
from app.services.validation import compute_ecoe_validation


def build_dashboard(db: Session, ecoe_event: ECOEEvent) -> dict:
    validation = compute_ecoe_validation(db, ecoe_event)
    stations = db.scalars(select(Station).where(Station.ecoe_event_id == ecoe_event.id)).all()
    live_session = db.scalar(
        select(LiveSession).where(LiveSession.ecoe_event_id == ecoe_event.id).limit(1)
    )
    evaluator_records = db.scalar(
        select(func.count(EvaluatorRecord.id)).where(EvaluatorRecord.ecoe_event_id == ecoe_event.id)
    )
    student_responses = db.scalar(
        select(func.count(StudentResponse.id)).where(StudentResponse.ecoe_event_id == ecoe_event.id)
    )
    incidents = db.scalar(
        select(func.count(Incident.id)).where(Incident.ecoe_event_id == ecoe_event.id)
    )
    return {
        "active_ecoe": {
            "id": ecoe_event.id,
            "name": ecoe_event.name,
            "status": ecoe_event.status,
            "date": ecoe_event.date.isoformat(),
            "course_name": ecoe_event.course_name,
        },
        "totals": {
            "students": validation["students_count"],
            "stations": validation["station_count"],
            "pilot_runs": validation["pilot_count"],
            "evaluations": evaluator_records,
            "student_submissions": student_responses,
            "incidents": incidents,
        },
        "validation": validation,
        "timeline": [
            {"label": station.name, "status": station.status, "circuit": station.circuit_name}
            for station in stations
        ],
        "live_panel": {
            "status": live_session.status if live_session else "sin_sesion",
            "current_station_index": live_session.current_station_index if live_session else 0,
            "remaining_seconds": live_session.remaining_seconds if live_session else 0,
        },
    }
