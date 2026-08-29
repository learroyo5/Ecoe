"""OPT-11b — `total_stations` / `total_students` derivados de las filas reales.

Los campos dejaron de ser input del cliente: la API los calcula al vuelo a
partir de las estaciones del evento y de los estudiantes activos. Las columnas
homónimas de `ecoe_events` siguen existiendo pero nadie las lee.
"""

from datetime import date

from app.models.entities import ECOEEvent, Station, Student
from app.services.validation import compute_ecoe_validation
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
        "total_groups": 1,
        "passing_reference_percent": 60,
    }
    body.update(overrides)
    return body


def _add_station(db, ecoe_event_id: int, number: int) -> None:
    db.add(
        Station(
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
    )


def _add_student(db, ecoe_event_id: int, idx: int, *, is_active: bool = True) -> None:
    db.add(
        Student(
            ecoe_event_id=ecoe_event_id,
            name=f"Est{idx}",
            last_name="Apellido",
            rut=f"{idx}0000000-{idx % 10}",
            email=f"est{idx}-{ecoe_event_id}@example.edu",
            ecoe_number=f"E{ecoe_event_id}-{idx}",
            group_name="G1",
            circuit_name="Circuito A",
            is_active=is_active,
        )
    )


def _create_event(client, name: str, **overrides) -> int:
    resp = client.post("/api/ecoe", json=_ecoe_body(name, **overrides))
    assert resp.status_code == 200, resp.text
    return resp.json()["id"]


def test_create_ecoe_ignores_client_supplied_totals(client):
    """El cliente ya no controla el valor: mandar `total_stations` no hace nada."""
    login(client, ADMIN)
    resp = client.post(
        "/api/ecoe",
        json=_ecoe_body("OPT-11b crea", total_stations=99, total_students=77),
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    # Evento recién creado, sin estaciones ni estudiantes → conteos reales en 0.
    assert body["total_stations"] == 0
    assert body["total_students"] == 0


def test_ecoe_read_reflects_real_station_and_student_counts(client):
    login(client, ADMIN)
    event_id = _create_event(client, "OPT-11b lectura")

    with TestingSessionLocal() as db:
        for number in (1, 2, 3):
            _add_station(db, event_id, number)
        for idx in range(5):
            _add_student(db, event_id, idx, is_active=True)
        _add_student(db, event_id, 99, is_active=False)  # inactivo: NO cuenta
        db.commit()

    body = client.get(f"/api/ecoe/{event_id}").json()
    assert body["total_stations"] == 3
    assert body["total_students"] == 5


def test_adding_a_station_increases_the_count(client):
    login(client, ADMIN)
    event_id = _create_event(client, "OPT-11b suma estación")
    assert client.get(f"/api/ecoe/{event_id}").json()["total_stations"] == 0

    with TestingSessionLocal() as db:
        _add_station(db, event_id, 1)
        db.commit()

    assert client.get(f"/api/ecoe/{event_id}").json()["total_stations"] == 1


def test_ecoe_list_counts_are_per_event_and_not_n_plus_one(client):
    login(client, ADMIN)
    event_a = _create_event(client, "OPT-11b lista A")
    event_b = _create_event(client, "OPT-11b lista B")

    with TestingSessionLocal() as db:
        _add_station(db, event_a, 1)
        _add_station(db, event_a, 2)
        _add_student(db, event_a, 0, is_active=True)
        _add_station(db, event_b, 1)
        _add_student(db, event_b, 0, is_active=True)
        _add_student(db, event_b, 1, is_active=True)
        _add_student(db, event_b, 2, is_active=False)
        db.commit()

    by_id = {e["id"]: e for e in client.get("/api/ecoe").json()}
    assert by_id[event_a]["total_stations"] == 2
    assert by_id[event_a]["total_students"] == 1
    assert by_id[event_b]["total_stations"] == 1
    assert by_id[event_b]["total_students"] == 2


def test_update_ecoe_does_not_accept_totals(client):
    login(client, ADMIN)
    event_id = _create_event(client, "OPT-11b update")
    with TestingSessionLocal() as db:
        _add_station(db, event_id, 1)
        db.commit()

    body = _ecoe_body("OPT-11b update", total_stations=42, total_students=42)
    body["status"] = "borrador"
    resp = client.put(f"/api/ecoe/{event_id}", json=body)
    assert resp.status_code == 200, resp.text
    # El conteo sigue derivándose de las filas, ignora los 42 del body.
    assert resp.json()["total_stations"] == 1
    assert resp.json()["total_students"] == 0

    with TestingSessionLocal() as db:
        stored = db.get(ECOEEvent, event_id)
        # La columna legada tampoco se pisó con el 42 del cliente.
        assert stored.total_stations != 42
        assert stored.total_students != 42


def test_duplicate_ecoe_totals_reflect_copied_stations(client):
    login(client, ADMIN)
    source_id = _create_event(client, "OPT-11b origen")
    with TestingSessionLocal() as db:
        for number in (1, 2, 3, 4):
            _add_station(db, source_id, number)
        for idx in range(3):
            _add_student(db, source_id, idx, is_active=True)
        db.commit()

    resp = client.post(
        f"/api/ecoe/{source_id}/duplicate",
        json={"name": "OPT-11b copia", "copy_evaluators": False},
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    # La copia siempre lleva la estructura de estaciones, nunca los estudiantes.
    assert body["total_stations"] == 4
    assert body["total_students"] == 0


def test_validation_still_uses_row_counts(client):
    """Regresión: `compute_ecoe_validation` no cambió — cuenta filas con func.count."""
    login(client, ADMIN)
    event_id = _create_event(client, "OPT-11b validación")
    with TestingSessionLocal() as db:
        for number in (1, 2):
            _add_station(db, event_id, number)
        for idx in range(4):
            _add_student(db, event_id, idx, is_active=True)
        _add_student(db, event_id, 98, is_active=False)
        db.commit()

    with TestingSessionLocal() as db:
        event = db.get(ECOEEvent, event_id)
        result = compute_ecoe_validation(db, event)
    assert result["station_count"] == 2
    assert result["students_count"] == 4
