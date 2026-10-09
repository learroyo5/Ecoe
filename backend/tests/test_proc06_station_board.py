"""Tablero de estaciones y verificación previa (propuesta de coordinación B.1/B.2)."""

from datetime import timedelta

from sqlalchemy import select

from app.models.entities import StaffAssignment, Station, StationKioskSession
from app.services.kiosk import issue_kiosk_token
from conftest import EVALUATOR, STUDENT, TestingSessionLocal, login
from test_opt20_f2_deadline_and_sweep import _add_checkin, _build_event, _utcnow_naive


def _assign_evaluator(ctx: dict) -> None:
    with TestingSessionLocal() as db:
        db.add(StaffAssignment(
            ecoe_event_id=ctx["event_id"], name="Camila", last_name="Soto",
            email=EVALUATOR[0], role_code="evaluador", station_ids=[ctx["station_id"]],
        ))
        db.commit()


def _board(client, ctx: dict) -> dict:
    response = client.get(f"/api/live/{ctx['event_id']}/board")
    assert response.status_code == 200, response.text
    return response.json()


def test_board_flags_everything_missing_before_setup(auth_client):
    ctx = _build_event()
    board = _board(auth_client, ctx)
    row = board["stations"][0]
    assert row["alerts"] == ["Sin evaluador asignado", "Kiosco sin vincular"]
    assert board["preflight"]["ready"] is False
    assert board["preflight"]["issues"] == [
        "Estación 1: Sin evaluador asignado", "Estación 1: Kiosco sin vincular",
    ]


def test_board_turns_green_once_evaluator_and_kiosk_report_in(client, auth_client):
    ctx = _build_event()
    _assign_evaluator(ctx)
    with TestingSessionLocal() as db:
        token = issue_kiosk_token(
            db, db.get(Station, ctx["station_id"]), issued_by_email="t@e.edu")["token"]
        db.commit()

    # Asignados pero sin señal: todavía no está listo.
    assert _board(auth_client, ctx)["stations"][0]["alerts"] == [
        "Evaluador sin conexión", "Kiosco sin conexión",
    ]

    assert client.get("/api/kiosk/context", headers={"X-Kiosk-Token": token}).status_code == 200
    login(client, EVALUATOR)
    assert client.get(f"/api/evaluator/context/{ctx['event_id']}").status_code == 200
    login(client, ("admin@ecoe.cl", "test-admin-password"))

    board = _board(client, ctx)
    row = board["stations"][0]
    assert row["alerts"] == []
    assert row["evaluator"]["online"] is True and row["kiosk"]["online"] is True
    assert board["preflight"] == {"ready": True, "issues": []}


def test_stale_heartbeat_goes_offline(auth_client):
    ctx = _build_event()
    _assign_evaluator(ctx)
    with TestingSessionLocal() as db:
        issue_kiosk_token(db, db.get(Station, ctx["station_id"]), issued_by_email="t@e.edu")
        db.commit()
        old = _utcnow_naive() - timedelta(minutes=5)
        kiosk = db.scalar(select(StationKioskSession).where(
            StationKioskSession.station_id == ctx["station_id"]))
        kiosk.last_seen_at = old
        assignment = db.scalar(select(StaffAssignment).where(
            StaffAssignment.ecoe_event_id == ctx["event_id"]))
        assignment.last_seen_at = old
        db.commit()
    row = _board(auth_client, ctx)["stations"][0]
    assert row["evaluator"]["online"] is False and row["kiosk"]["online"] is False
    assert row["alerts"] == ["Evaluador sin conexión", "Kiosco sin conexión"]


def test_board_shows_the_occupant_and_what_is_still_pending(auth_client):
    ctx = _build_event()
    _add_checkin(ctx, minutes_ago=0)
    occupant = _board(auth_client, ctx)["stations"][0]["occupant"]
    assert occupant["ecoe_number"] == "001"
    assert occupant["evaluation"] == "pendiente"
    assert occupant["response"] == "pendiente"


def test_board_is_not_available_to_students_or_evaluators(client):
    ctx = _build_event()
    for credentials in (STUDENT, EVALUATOR):
        login(client, credentials)
        assert client.get(f"/api/live/{ctx['event_id']}/board").status_code == 403
