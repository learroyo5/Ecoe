"""Señal de vida de dispositivos y tablero de estaciones del día del examen.

Los kioscos y las pantallas de evaluador ya consultan su contexto cada pocos
segundos; aquí sólo se anota cuándo fue la última vez (como mucho una
escritura cada ``HEARTBEAT_MIN_SECONDS``) y se arma, para coordinación, la
vista por estación: quién debería estar, quién está, y qué falta.
"""

from datetime import timedelta

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.entities import (
    EvaluatorRecord,
    StaffAssignment,
    Station,
    StationCheckIn,
    StationKioskSession,
    Student,
    StudentResponse,
    User,
)
from app.models.enums import RoleCode
from app.utils.clock import utcnow_naive
from app.utils.helpers import normalize_email, resolve_session_mode

HEARTBEAT_MIN_SECONDS = 15
ONLINE_WINDOW_SECONDS = 45


def touch_last_seen(db: Session, row) -> None:
    """Marca ``row.last_seen_at = ahora`` si la marca anterior ya es vieja."""
    now = utcnow_naive()
    previous = row.last_seen_at
    if previous is not None and (now - previous).total_seconds() < HEARTBEAT_MIN_SECONDS:
        return
    row.last_seen_at = now
    db.add(row)
    db.commit()


def _online(last_seen_at, now) -> bool:
    return last_seen_at is not None and now - last_seen_at <= timedelta(seconds=ONLINE_WINDOW_SECONDS)


def _iso(value):
    return value.isoformat() if value is not None else None


def build_station_board(db: Session, ecoe_event) -> dict:
    """Vista por estación para coordinación + verificación previa."""
    now = utcnow_naive()
    mode = resolve_session_mode(ecoe_event)
    stations = db.scalars(
        select(Station)
        .where(Station.ecoe_event_id == ecoe_event.id)
        .order_by(Station.station_number.asc(), Station.id.asc())
    ).all()
    evaluators = db.scalars(
        select(StaffAssignment).where(
            StaffAssignment.ecoe_event_id == ecoe_event.id,
            StaffAssignment.role_code == RoleCode.evaluador.value,
        )
    ).all()
    evaluator_by_station: dict[int, StaffAssignment] = {}
    for assignment in evaluators:
        for station_id in assignment.station_ids or []:
            if station_id:
                evaluator_by_station.setdefault(int(station_id), assignment)
    emails = {normalize_email(a.email) for a in evaluators if a.email}
    active_accounts = {
        normalize_email(email)
        for (email,) in db.execute(
            select(User.email).where(
                func.lower(User.email).in_(emails or {""}),
                User.is_active.is_(True),
                User.account_status == "active",
            )
        ).all()
    }
    kiosk_by_station: dict[int, StationKioskSession] = {}
    for kiosk in db.scalars(
        select(StationKioskSession)
        .where(
            StationKioskSession.ecoe_event_id == ecoe_event.id,
            StationKioskSession.revoked_at.is_(None),
            StationKioskSession.expires_at > now,
        )
        .order_by(StationKioskSession.id.asc())
    ).all():
        kiosk_by_station[kiosk.station_id] = kiosk
    occupant_by_station: dict[int, StationCheckIn] = {}
    for checkin in db.scalars(
        select(StationCheckIn)
        .where(
            StationCheckIn.ecoe_event_id == ecoe_event.id,
            StationCheckIn.status == "confirmado",
        )
        .order_by(StationCheckIn.confirmed_at.asc(), StationCheckIn.id.asc())
    ).all():
        occupant_by_station[checkin.station_id] = checkin
    students = {
        student.id: student
        for student in db.scalars(
            select(Student).where(Student.ecoe_event_id == ecoe_event.id)
        ).all()
    }

    rows: list[dict] = []
    issues: list[str] = []
    for station in stations:
        needs_kiosk = bool(station.requires_student_form) or bool(station.uses_multimedia)
        alerts: list[str] = []

        evaluator = None
        if station.requires_evaluator:
            assignment = evaluator_by_station.get(station.id)
            if assignment is None:
                alerts.append("Sin evaluador asignado")
            else:
                has_account = normalize_email(assignment.email) in active_accounts
                online = _online(assignment.last_seen_at, now)
                evaluator = {
                    "name": " ".join(p for p in [assignment.name, assignment.last_name] if p).strip(),
                    "email": assignment.email,
                    "has_account": has_account,
                    "last_seen_at": _iso(assignment.last_seen_at),
                    "online": online,
                }
                if not has_account:
                    alerts.append("El evaluador no tiene cuenta activa")
                elif not online:
                    alerts.append("Evaluador sin conexión")

        kiosk = None
        if needs_kiosk:
            session = kiosk_by_station.get(station.id)
            if session is None:
                alerts.append("Kiosco sin vincular")
                kiosk = {"linked": False, "last_seen_at": None, "online": False, "expires_at": None}
            else:
                online = _online(session.last_seen_at, now)
                kiosk = {
                    "linked": True,
                    "last_seen_at": _iso(session.last_seen_at),
                    "online": online,
                    "expires_at": _iso(session.expires_at),
                }
                if not online:
                    alerts.append("Kiosco sin conexión")

        occupant = None
        checkin = occupant_by_station.get(station.id)
        if checkin is not None:
            student = students.get(checkin.student_id)
            evaluation = db.scalar(
                select(EvaluatorRecord).where(
                    EvaluatorRecord.ecoe_event_id == ecoe_event.id,
                    EvaluatorRecord.station_id == station.id,
                    EvaluatorRecord.student_id == checkin.student_id,
                    EvaluatorRecord.mode == mode,
                )
            )
            has_response = db.scalar(
                select(func.count()).select_from(StudentResponse).where(
                    StudentResponse.ecoe_event_id == ecoe_event.id,
                    StudentResponse.station_id == station.id,
                    StudentResponse.student_id == checkin.student_id,
                    StudentResponse.mode == mode,
                )
            ) > 0
            occupant = {
                "checkin_id": checkin.id,
                "ecoe_number": student.ecoe_number if student else "",
                "student_name": f"{student.name} {student.last_name}" if student else "",
                "confirmed_at": _iso(checkin.confirmed_at),
                "evaluation": (
                    None if not station.requires_evaluator
                    else "enviada" if evaluation is not None and not evaluation.is_draft
                    else "borrador" if evaluation is not None
                    else "pendiente"
                ),
                "response": (
                    None if not station.requires_student_form
                    else "enviada" if has_response else "pendiente"
                ),
            }

        rows.append({
            "station_id": station.id,
            "station_number": station.station_number,
            "station_name": station.name,
            "circuit_name": station.circuit_name,
            "requires_evaluator": bool(station.requires_evaluator),
            "needs_kiosk": needs_kiosk,
            "evaluator": evaluator,
            "kiosk": kiosk,
            "occupant": occupant,
            "alerts": alerts,
        })
        issues.extend(f"Estación {station.station_number}: {alert}" for alert in alerts)

    return {
        "server_now": now.isoformat(),
        "stations": rows,
        "preflight": {"ready": not issues, "issues": issues},
    }
