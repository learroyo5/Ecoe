"""Editar las características del ECOE debe cascadear el timing (2026-09-04).

Hallazgo del simulacro: bajar los minutos de estación/transición desde el
formulario general de "características" (``PUT /ecoe/{id}``) no tocaba las
estaciones ya creadas ni el ``LiveSession`` — el panel `/live` seguía
mostrando los minutos viejos. Sólo el endpoint dedicado
``PATCH /ecoe/{id}/timing`` (sin UI que lo llame) hacía ese resync.

``_sync_stations_and_live_session_timing`` ahora corre también desde
``update_ecoe``, así el único formulario real de edición mantiene las
estaciones y la sesión en vivo sincronizadas con el evento.
"""

from app.models.entities import LiveSession, Station
from conftest import ADMIN, TestingSessionLocal, login


def _ecoe_body(name: str, **overrides) -> dict:
    body = {
        "name": name,
        "date": "2026-11-01",
        "course_name": "Curso",
        "school_name": "Escuela",
        "responsible_teacher": "Docente",
        "contact_email": "docente@example.edu",
        "circuit_mode": "paralelo_espejo",
        "station_time_minutes": 8,
        "transition_time_minutes": 2,
        "inter_round_pause_minutes": 5,
        "total_groups": 1,
        "passing_reference_percent": 60,
    }
    body.update(overrides)
    return body


def _create_event(client, name: str, **overrides) -> int:
    resp = client.post("/api/ecoe", json=_ecoe_body(name, **overrides))
    assert resp.status_code == 200, resp.text
    return resp.json()["id"]


def _add_station(db, ecoe_event_id: int, number: int) -> int:
    station = Station(
        ecoe_event_id=ecoe_event_id,
        station_number=number,
        name=f"Estación {number}",
        station_type="clinica",
        circuit_name="Circuito A",
        station_time_minutes=8,
        transition_time_minutes=2,
        expected_outcomes="Resultado",
        student_activity="Actividad",
        pre_entry_instruction="Ingreso",
        evaluator_instruction="Guía",
    )
    db.add(station)
    db.flush()
    return station.id


def test_editing_ecoe_characteristics_updates_existing_station_times(client):
    login(client, ADMIN)
    event_id = _create_event(client, "Cascada timing — estaciones")
    with TestingSessionLocal() as db:
        _add_station(db, event_id, 1)
        db.commit()

    body = _ecoe_body(
        "Cascada timing — estaciones",
        station_time_minutes=2,
        transition_time_minutes=0.5,
    )
    body["status"] = "borrador"
    resp = client.put(f"/api/ecoe/{event_id}", json=body)
    assert resp.status_code == 200, resp.text

    with TestingSessionLocal() as db:
        station = db.query(Station).filter(Station.ecoe_event_id == event_id).one()
        assert station.station_time_minutes == 2
        assert station.transition_time_minutes == 0.5


def test_editing_ecoe_characteristics_resyncs_idle_live_session(client):
    login(client, ADMIN)
    event_id = _create_event(client, "Cascada timing — sesión idle")
    with TestingSessionLocal() as db:
        session = LiveSession(
            ecoe_event_id=event_id,
            status="ready",
            station_time_seconds=480,
            transition_time_seconds=120,
            remaining_seconds=480,
            inter_round_pause_seconds=300,
        )
        db.add(session)
        db.commit()

    body = _ecoe_body(
        "Cascada timing — sesión idle",
        station_time_minutes=2,
        transition_time_minutes=0.5,
        inter_round_pause_minutes=1,
    )
    body["status"] = "borrador"
    resp = client.put(f"/api/ecoe/{event_id}", json=body)
    assert resp.status_code == 200, resp.text

    with TestingSessionLocal() as db:
        session = (
            db.query(LiveSession).filter(LiveSession.ecoe_event_id == event_id).one()
        )
        assert session.station_time_seconds == 120
        assert session.transition_time_seconds == 30
        assert session.inter_round_pause_seconds == 60
        # Sesión quieta (ready): el restante mostrado también se refresca.
        assert session.remaining_seconds == 120


def test_editing_ecoe_characteristics_does_not_yank_a_running_phase(client):
    login(client, ADMIN)
    event_id = _create_event(client, "Cascada timing — sesión corriendo")
    with TestingSessionLocal() as db:
        session = LiveSession(
            ecoe_event_id=event_id,
            status="running",
            station_time_seconds=480,
            transition_time_seconds=120,
            remaining_seconds=200,  # a mitad de la fase de estación
            inter_round_pause_seconds=300,
        )
        db.add(session)
        db.commit()

    body = _ecoe_body(
        "Cascada timing — sesión corriendo",
        station_time_minutes=2,
        transition_time_minutes=0.5,
    )
    body["status"] = "borrador"
    resp = client.put(f"/api/ecoe/{event_id}", json=body)
    assert resp.status_code == 200, resp.text

    with TestingSessionLocal() as db:
        session = (
            db.query(LiveSession).filter(LiveSession.ecoe_event_id == event_id).one()
        )
        # La plantilla para la próxima fase sí se actualiza...
        assert session.station_time_seconds == 120
        # ...pero el restante de la fase en curso no se toca a mitad de camino.
        assert session.remaining_seconds == 200
