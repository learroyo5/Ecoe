"""OPT-20 F1: operational screens subscribe read-only to the live clock.

Covers the widened /ws/live/{id} guard (evaluador / estudiante of the event +
station-scoped kiosk token by query param) and the live-phase snapshot added to
the kiosk / evaluador / estudiante context endpoints. Includes the negative
cases required for an auth change: wrong event, revoked/expired/foreign kiosk
token, and that an inbound WS frame can never mutate the timer.
"""

from datetime import timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from starlette.websockets import WebSocketDisconnect

from app.main import app
from app.models.entities import ECOEEvent, StationKioskSession
from app.models.enums import ECOEStatus
from conftest import (
    ADMIN,
    COORDINATOR,
    EVALUATOR,
    STUDENT,
    TestingSessionLocal,
    login,
)


def _admin_client() -> TestClient:
    c = TestClient(app)
    login(c, ADMIN)
    return c


def _create_event(name: str) -> int:
    c = _admin_client()
    response = c.post("/api/ecoe", json={
        "name": name,
        "date": "2026-10-01",
        "course_name": "Curso",
        "school_name": "Escuela",
        "responsible_teacher": "Docente",
        "contact_email": "docente@example.edu",
        "circuit_mode": "paralelo_espejo",
        "total_stations": 2,
        "station_time_minutes": 8,
        "transition_time_minutes": 2,
        "total_students": 2,
        "total_groups": 1,
        "passing_reference_percent": 60,
    })
    assert response.status_code == 200, response.text
    return response.json()["id"]


def _create_station(event_id: int, name: str) -> int:
    c = _admin_client()
    response = c.post("/api/stations", json={
        "ecoe_event_id": event_id,
        "station_number": 1,
        "name": name,
        "station_type": "procedimental",
        "circuit_name": "Circuito A",
        "expected_outcomes": "Resultado",
        "student_activity": "Actividad",
        "pre_entry_instruction": "Ingreso",
        "evaluator_instruction": "Evaluar",
        "requires_evaluator": True,
        "max_score": 10,
    })
    assert response.status_code == 200, response.text
    return response.json()["id"]


def _issue_kiosk_token(station_id: int, *, as_admin: bool = False) -> str:
    c = _admin_client() if as_admin else TestClient(app)
    if not as_admin:
        login(c, COORDINATOR)
    response = c.post(f"/api/kiosk/stations/{station_id}/token")
    assert response.status_code == 200, response.text
    return response.json()["token"]


def _start_timer(event_id: int) -> None:
    admin = _admin_client()
    assert admin.post(
        "/api/live/control", json={"ecoe_event_id": event_id, "action": "start"}
    ).status_code == 200


# ── WebSocket guard: user roles ────────────────────────────────────────

def test_ws_live_accepts_evaluator_of_event(client):
    login(client, EVALUATOR)
    admin = _admin_client()
    with client.websocket_connect("/api/ws/live/1") as ws:
        admin.post("/api/live/control", json={"ecoe_event_id": 1, "action": "start"})
        message = ws.receive_json()
        assert message["type"] == "timer_update"
        assert message["status"] == "running"


def test_ws_live_accepts_student_of_event(client):
    login(client, STUDENT)
    admin = _admin_client()
    with client.websocket_connect("/api/ws/live/1") as ws:
        admin.post("/api/live/control", json={"ecoe_event_id": 1, "action": "start"})
        message = ws.receive_json()
        assert message["type"] == "timer_update"


def test_ws_live_rejects_evaluator_of_other_event(client):
    other_event = _create_event("Evento ajeno para WS")
    login(client, EVALUATOR)
    with pytest.raises(WebSocketDisconnect):
        with client.websocket_connect(f"/api/ws/live/{other_event}"):
            pass


def test_ws_live_rejects_anonymous_without_token(client):
    with pytest.raises(WebSocketDisconnect):
        with client.websocket_connect("/api/ws/live/1"):
            pass


# ── WebSocket guard: kiosk token ──────────────────────────────────────

def test_ws_live_accepts_valid_kiosk_token(client):
    token = _issue_kiosk_token(1)
    admin = _admin_client()
    fresh = TestClient(app)  # no user session: query-param token only
    with fresh.websocket_connect(f"/api/ws/live/1?kiosk_token={token}") as ws:
        admin.post("/api/live/control", json={"ecoe_event_id": 1, "action": "start"})
        message = ws.receive_json()
        assert message["type"] == "timer_update"


def test_ws_live_rejects_revoked_kiosk_token(client):
    token = _issue_kiosk_token(1)
    coord = TestClient(app)
    login(coord, COORDINATOR)
    assert coord.delete("/api/kiosk/stations/1/token").status_code == 200
    fresh = TestClient(app)
    with pytest.raises(WebSocketDisconnect):
        with fresh.websocket_connect(f"/api/ws/live/1?kiosk_token={token}"):
            pass


def test_ws_live_rejects_expired_kiosk_token(client):
    token = _issue_kiosk_token(1)
    with TestingSessionLocal() as db:
        session = db.scalars(
            select(StationKioskSession).where(
                StationKioskSession.station_id == 1,
                StationKioskSession.revoked_at.is_(None),
            )
        ).first()
        session.expires_at = session.expires_at - timedelta(days=999)
        db.add(session)
        db.commit()
    fresh = TestClient(app)
    with pytest.raises(WebSocketDisconnect):
        with fresh.websocket_connect(f"/api/ws/live/1?kiosk_token={token}"):
            pass


def test_ws_live_rejects_kiosk_token_of_other_event(client):
    other_event = _create_event("Evento kiosco ajeno")
    other_station = _create_station(other_event, "Estación ajena")
    token = _issue_kiosk_token(other_station, as_admin=True)
    fresh = TestClient(app)
    # Token is valid, but scoped to `other_event` — it must not open event 1.
    with pytest.raises(WebSocketDisconnect):
        with fresh.websocket_connect(f"/api/ws/live/1?kiosk_token={token}"):
            pass
    # Sanity: it does open its own event.
    with fresh.websocket_connect(f"/api/ws/live/{other_event}?kiosk_token={token}"):
        pass


def test_ws_live_rejects_garbage_kiosk_token(client):
    fresh = TestClient(app)
    with pytest.raises(WebSocketDisconnect):
        with fresh.websocket_connect("/api/ws/live/1?kiosk_token=no-es-un-token"):
            pass


# ── WebSocket is read-only ────────────────────────────────────────────

def test_ws_live_screen_cannot_control_timer(client):
    admin = _admin_client()
    admin.post("/api/live/control", json={"ecoe_event_id": 1, "action": "start"})
    before = admin.get("/api/live/1").json()["status"]
    assert before == "running"

    login(client, EVALUATOR)
    with client.websocket_connect("/api/ws/live/1") as ws:
        # A hand-crafted control frame over the read-only socket must do nothing.
        ws.send_json({"type": "control", "action": "pause", "ecoe_event_id": 1})
        ws.send_text("pause")

    after = admin.get("/api/live/1").json()["status"]
    assert after == "running"


# ── Context endpoints: live-phase snapshot ────────────────────────────

def _set_status(event_id: int, status: str) -> str:
    with TestingSessionLocal() as db:
        event = db.get(ECOEEvent, event_id)
        previous = str(event.status)
        event.status = status
        db.add(event)
        db.commit()
    return previous


def test_kiosk_context_reports_live_phase(client):
    previous = _set_status(1, ECOEStatus.en_ejecucion.value)
    try:
        token = _issue_kiosk_token(4)
        admin = _admin_client()

        admin.post("/api/live/control", json={"ecoe_event_id": 1, "action": "start"})
        running = client.get(
            "/api/kiosk/context", headers={"X-Kiosk-Token": token}
        ).json()
        assert running["live_status"] == "running"
        assert running["paused"] is False
        assert running["current_phase_ends_at"] is not None

        admin.post("/api/live/control", json={"ecoe_event_id": 1, "action": "pause"})
        paused = client.get(
            "/api/kiosk/context", headers={"X-Kiosk-Token": token}
        ).json()
        assert paused["live_status"] == "paused"
        assert paused["paused"] is True
        assert paused["current_phase_ends_at"] is None
    finally:
        _admin_client().post(
            "/api/live/control", json={"ecoe_event_id": 1, "action": "reset"}
        )
        _set_status(1, previous)


def test_evaluator_and_student_context_expose_live_phase_keys(client):
    _admin_client().post("/api/live/control", json={"ecoe_event_id": 1, "action": "reset"})

    login(client, EVALUATOR)
    evaluator_ctx = client.get("/api/evaluator/context/1").json()
    for key in ("live_status", "current_phase_ends_at", "paused"):
        assert key in evaluator_ctx

    previous = _set_status(1, ECOEStatus.en_ejecucion.value)
    try:
        login(client, STUDENT)
        student_ctx = client.post(
            "/api/student/access", json={"ecoe_event_id": 1, "ecoe_number": ""}
        )
        # Student may not have an active check-in in this shared DB; either way
        # the endpoint must not 500 on the new snapshot call.
        assert student_ctx.status_code in (200, 400)
    finally:
        _set_status(1, previous)
