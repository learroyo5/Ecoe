"""El seed de la instancia demo deja dos ECOE coherentes y es idempotente."""

from sqlalchemy import select

from app.db.seed_demo import CLOSED_EVENT_NAME, LIVE_EVENT_NAME, seed_demo
from app.models.entities import ECOEEvent, ECOEResult, StationCheckIn, Student
from app.services.results import compute_missing_station_scores
from app.services.validation import compute_ecoe_validation
from conftest import TestingSessionLocal


def test_seed_demo_builds_a_closed_event_with_a_complete_acta_and_is_idempotent(client):
    with TestingSessionLocal() as db:
        seed_demo(db)
        seed_demo(db)  # segunda corrida: no duplica nada
        closed = db.scalars(select(ECOEEvent).where(ECOEEvent.name == CLOSED_EVENT_NAME)).all()
        assert len(closed) == 1 and str(closed[0].status) == "cerrado"
        event_id = closed[0].id
        students = db.scalars(select(Student).where(Student.ecoe_event_id == event_id)).all()
        acta = db.scalars(select(ECOEResult).where(ECOEResult.ecoe_event_id == event_id)).all()
        assert len(students) == 12 and len(acta) == 12
        assert all(row.stations_counted == 5 and row.stations_expected == 5 for row in acta)
        grades = sorted(row.equivalent_grade for row in acta)
        assert grades[0] < grades[-1]  # hay dispersión que mostrar
        assert compute_missing_station_scores(db, event_id) == []
        # Nada queda "confirmado": no interfiere con las invariantes de ingreso.
        assert db.scalars(select(StationCheckIn).where(
            StationCheckIn.ecoe_event_id == event_id, StationCheckIn.status == "confirmado")).all() == []

    response = client.post("/api/auth/login", json={"email": "admin@ecoe.cl", "password": "test-admin-password"})
    assert response.status_code == 200
    body = client.get(f"/api/results/{event_id}").json()
    assert body["frozen"] is True and len(body["results"]) == 12


def test_seed_demo_leaves_the_live_event_running_and_presentable(client):
    with TestingSessionLocal() as db:
        seed_demo(db)
        live = db.scalar(select(ECOEEvent).where(ECOEEvent.name == LIVE_EVENT_NAME))
        assert str(live.status) == "en_ejecucion"
        validation = compute_ecoe_validation(db, live)
        assert not any("sin cuenta" in warning for warning in validation["warnings"])
