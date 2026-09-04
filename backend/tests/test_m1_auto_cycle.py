"""M1 F1 · Ciclo automático del circuito.

``advance_if_expired``: máquina de fases explícita, determinista, idempotente,
con *fast-forward* por varias fases vencidas. Acciones ``enable_auto`` /
``disable_auto`` / ``skip_phase`` de ``POST /live/control``.

Negativos (toca tiempo + datos operativos): ``auto_mode`` apagado no avanza,
``paused`` no avanza, ``enable_auto`` rechazado en marcha, ``round_pause`` /
``circuit_complete`` rechazan envíos, respeta el cierre del evento.

El evento sembrado 1 tiene 5 estaciones y 10 estudiantes activos
→ ``total_rounds`` = ⌈10/5⌉ = 2.
"""

from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import select

from app.models.entities import ECOEEvent, LiveSession
from app.models.enums import ECOEStatus
from app.services.live_cycle import (
    advance_if_expired,
    compute_total_rounds,
    station_slot_count,
)
from app.utils.helpers import _live_phase_station_deadline
from conftest import ADMIN, TestingSessionLocal, login

STATION_S, TRANSITION_S, PAUSE_S = 480, 120, 300
_REMAINING = {"running": STATION_S, "transition": TRANSITION_S, "round_pause": PAUSE_S}


def _naive_now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


@pytest.fixture
def restore_event_1():
    """Deja la LiveSession y el estado del evento 1 como estaban."""
    yield
    with TestingSessionLocal() as db:
        event = db.get(ECOEEvent, 1)
        event.status = ECOEStatus.en_ejecucion.value
        s = db.scalar(select(LiveSession).where(LiveSession.ecoe_event_id == 1))
        s.status = "ready"
        s.auto_mode = False
        s.current_station_index = 1
        s.current_round = 1
        s.total_rounds = None
        s.remaining_seconds = STATION_S
        s.phase_started_at = None
        db.add_all([event, s])
        db.commit()


def _setup(db, *, status="running", station_index=1, current_round=1,
           total_rounds=2, expired_by=None, auto=True):
    s = db.scalar(select(LiveSession).where(LiveSession.ecoe_event_id == 1))
    s.auto_mode = auto
    s.status = status
    s.current_station_index = station_index
    s.current_round = current_round
    s.total_rounds = total_rounds
    s.station_time_seconds = STATION_S
    s.transition_time_seconds = TRANSITION_S
    s.inter_round_pause_seconds = PAUSE_S
    s.remaining_seconds = _REMAINING.get(status, STATION_S)
    if status == "paused":
        s.phase_started_at = None
    elif expired_by is None:
        s.phase_started_at = _naive_now()
    else:
        s.phase_started_at = _naive_now() - timedelta(
            seconds=s.remaining_seconds + expired_by
        )
    db.add(s)
    db.commit()
    return s


def _advance():
    with TestingSessionLocal() as db:
        event = db.get(ECOEEvent, 1)
        return advance_if_expired(db, event, commit=True)


def _slots() -> int:
    with TestingSessionLocal() as db:
        return station_slot_count(db, 1)


def _state():
    with TestingSessionLocal() as db:
        s = db.scalar(select(LiveSession).where(LiveSession.ecoe_event_id == 1))
        return {
            "status": s.status,
            "station": s.current_station_index,
            "round": s.current_round,
            "phase_started_at": s.phase_started_at,
        }


# ── advance_if_expired: transiciones básicas ────────────────────────────

def test_running_expiry_starts_transition(restore_event_1):
    with TestingSessionLocal() as db:
        _setup(db, status="running", station_index=1, expired_by=1)
    result = _advance()
    assert result["advanced"] == 1
    assert result["bells"] == ["end"]
    st = _state()
    assert st["status"] == "transition"
    assert st["station"] == 2


def test_transition_expiry_starts_next_station(restore_event_1):
    with TestingSessionLocal() as db:
        # running de estación 1 vencida hace 121s → también vence la transición.
        _setup(db, status="running", station_index=1, expired_by=TRANSITION_S + 1)
    result = _advance()
    assert result["advanced"] == 2
    assert result["bells"] == ["end", "start"]
    st = _state()
    assert st["status"] == "running"
    assert st["station"] == 2
    assert st["round"] == 1


def test_last_station_of_round_goes_to_round_pause(restore_event_1):
    with TestingSessionLocal() as db:
        _setup(db, status="running", station_index=_slots(), current_round=1,
               total_rounds=2, expired_by=1)
    result = _advance()
    assert result["advanced"] == 1
    st = _state()
    assert st["status"] == "round_pause"
    assert st["station"] == 1
    assert st["round"] == 1  # la ronda sube recién al reanudar


def test_round_pause_expiry_starts_next_round(restore_event_1):
    with TestingSessionLocal() as db:
        _setup(db, status="round_pause", station_index=1, current_round=1,
               total_rounds=2, expired_by=1)
    result = _advance()
    assert result["advanced"] == 1
    assert result["bells"] == ["start"]
    st = _state()
    assert st["status"] == "running"
    assert st["round"] == 2
    assert st["station"] == 1


def test_last_round_last_station_completes_circuit(restore_event_1):
    with TestingSessionLocal() as db:
        _setup(db, status="running", station_index=_slots(), current_round=2,
               total_rounds=2, expired_by=1)
    result = _advance()
    assert result["advanced"] == 1
    st = _state()
    assert st["status"] == "circuit_complete"
    assert st["phase_started_at"] is None


# ── fast-forward, idempotencia, no-op ──────────────────────────────────

def test_fast_forwards_multiple_expired_phases(restore_event_1):
    with TestingSessionLocal() as db:
        # 1 día atrás: el circuito entero (2 rondas) ya debería haber terminado.
        _setup(db, status="running", station_index=1, current_round=1,
               total_rounds=2, expired_by=86400)
    result = _advance()
    assert result["advanced"] >= 1
    assert _state()["status"] == "circuit_complete"
    # idempotente: una segunda pasada no cambia nada.
    again = _advance()
    assert again["advanced"] == 0
    assert _state()["status"] == "circuit_complete"


def test_no_advance_before_deadline(restore_event_1):
    with TestingSessionLocal() as db:
        _setup(db, status="running", station_index=2, expired_by=None)
    result = _advance()
    assert result["advanced"] == 0
    assert _state()["status"] == "running"
    assert _state()["station"] == 2


def test_idempotent_single_step(restore_event_1):
    with TestingSessionLocal() as db:
        _setup(db, status="transition", station_index=3, expired_by=1)
    first = _advance()
    assert first["advanced"] == 1
    snapshot = _state()
    second = _advance()
    # Puede avanzar 0 (la nueva fase running no venció) y el estado se mantiene.
    assert second["advanced"] == 0
    assert _state()["status"] == snapshot["status"] == "running"
    assert _state()["station"] == 3


# ── negativos ──────────────────────────────────────────────────────────

def test_auto_mode_off_never_advances(restore_event_1):
    with TestingSessionLocal() as db:
        _setup(db, status="running", station_index=1, expired_by=9999, auto=False)
    result = _advance()
    assert result["advanced"] == 0
    assert _state()["status"] == "running"
    assert _state()["station"] == 1


def test_paused_never_advances(restore_event_1):
    with TestingSessionLocal() as db:
        _setup(db, status="paused", station_index=2)
    result = _advance()
    assert result["advanced"] == 0
    assert _state()["status"] == "paused"


def test_frozen_event_never_advances(restore_event_1):
    with TestingSessionLocal() as db:
        _setup(db, status="running", station_index=1, expired_by=9999)
        event = db.get(ECOEEvent, 1)
        event.status = ECOEStatus.cerrado.value
        db.add(event)
        db.commit()
    result = _advance()
    assert result["advanced"] == 0
    assert _state()["status"] == "running"


def test_round_pause_and_complete_reject_submissions():
    far = _naive_now() - timedelta(days=1)

    class _S:
        phase_started_at = _naive_now()

    for status in ("round_pause", "circuit_complete"):
        s = _S()
        s.status = status
        assert _live_phase_station_deadline(s, far_past=far) == far


# ── compute_total_rounds ───────────────────────────────────────────────

def test_total_rounds_is_ceil_students_over_stations():
    with TestingSessionLocal() as db:
        assert compute_total_rounds(db, 1) == 2  # 10 estudiantes / 5 estaciones


# ── endpoints /live/control ────────────────────────────────────────────

def test_enable_auto_freezes_rounds(auth_client, restore_event_1):
    auth_client.post("/api/live/control", json={"ecoe_event_id": 1, "action": "reset"})
    r = auth_client.post(
        "/api/live/control", json={"ecoe_event_id": 1, "action": "enable_auto"}
    )
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["auto_mode"] is True
    assert data["total_rounds"] == 2
    assert data["status"] == "ready"


def test_enable_auto_rejected_while_running(auth_client, restore_event_1):
    auth_client.post("/api/live/control", json={"ecoe_event_id": 1, "action": "start"})
    r = auth_client.post(
        "/api/live/control", json={"ecoe_event_id": 1, "action": "enable_auto"}
    )
    assert r.status_code == 409, r.text


def test_disable_auto(auth_client, restore_event_1):
    auth_client.post("/api/live/control", json={"ecoe_event_id": 1, "action": "reset"})
    auth_client.post("/api/live/control", json={"ecoe_event_id": 1, "action": "enable_auto"})
    r = auth_client.post(
        "/api/live/control", json={"ecoe_event_id": 1, "action": "disable_auto"}
    )
    assert r.status_code == 200, r.text
    assert r.json()["auto_mode"] is False


def test_skip_phase_rolls_to_next_phase(auth_client, restore_event_1):
    auth_client.post("/api/live/control", json={"ecoe_event_id": 1, "action": "reset"})
    auth_client.post("/api/live/control", json={"ecoe_event_id": 1, "action": "enable_auto"})
    auth_client.post("/api/live/control", json={"ecoe_event_id": 1, "action": "start"})
    r = auth_client.post(
        "/api/live/control", json={"ecoe_event_id": 1, "action": "skip_phase"}
    )
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["status"] == "transition"
    assert data["current_station_index"] == 2


def test_skip_phase_rejected_without_auto(auth_client, restore_event_1):
    auth_client.post("/api/live/control", json={"ecoe_event_id": 1, "action": "reset"})
    auth_client.post("/api/live/control", json={"ecoe_event_id": 1, "action": "disable_auto"})
    auth_client.post("/api/live/control", json={"ecoe_event_id": 1, "action": "start"})
    r = auth_client.post(
        "/api/live/control", json={"ecoe_event_id": 1, "action": "skip_phase"}
    )
    assert r.status_code == 409, r.text
