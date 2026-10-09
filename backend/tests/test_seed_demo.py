"""El seed de la instancia demo deja dos ECOE coherentes y es idempotente.

La base de tests es compartida y otros tests dependen de la forma del evento
demo (id 1), así que aquí no se reestructura ese evento: el ECOE cerrado se
crea aparte y el armado en espejo se prueba sobre una copia.
"""

from sqlalchemy import select

from app.db.seed_demo import CLOSED_EVENT_NAME, _create_closed_event, _polish_live_event
from app.models.entities import ECOEEvent, ECOEResult, Station, StationCheckIn, Student, User
from app.services.mirrors import mirror_structure_issues
from app.services.results import compute_missing_station_scores
from conftest import TestingSessionLocal


def test_closed_demo_event_has_a_complete_acta_and_is_idempotent(auth_client):
    with TestingSessionLocal() as db:
        admin = db.scalar(select(User).where(User.email == "admin@ecoe.cl"))
        _create_closed_event(db, admin, "test-admin-password")
        _create_closed_event(db, admin, "test-admin-password")  # no duplica
        db.commit()
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
        assert db.scalars(select(StationCheckIn).where(
            StationCheckIn.ecoe_event_id == event_id, StationCheckIn.status == "confirmado")).all() == []

    body = auth_client.get(f"/api/results/{event_id}").json()
    assert body["frozen"] is True and len(body["results"]) == 12


def test_live_demo_event_is_rebuilt_as_a_real_mirror(auth_client):
    # Copia del evento demo (misma forma que deja el seed base): 6 estaciones.
    clone = auth_client.post("/api/ecoe/1/duplicate", json={"name": "Copia para armar espejo"})
    assert clone.status_code == 200, clone.text
    clone_id = clone.json()["id"]
    with TestingSessionLocal() as db:
        base_numbers = sorted(
            s.station_number
            for s in db.scalars(select(Station).where(Station.ecoe_event_id == clone_id))
        )
        if base_numbers[:6] != [1, 2, 3, 4, 5, 6]:
            return  # otros tests ya alteraron el evento demo en esta corrida
        _polish_live_event(db, "test-admin-password", event_name="Copia para armar espejo")
        _polish_live_event(db, "test-admin-password", event_name="Copia para armar espejo")
        stations = db.scalars(select(Station).where(Station.ecoe_event_id == clone_id)).all()
        originals = [s for s in stations if s.mirror_of_id is None and s.circuit_name == "Circuito A"]
        mirrors = [s for s in stations if s.mirror_of_id]
        assert len(originals) == 4 and len(mirrors) == 4
        assert {s.circuit_name for s in mirrors} == {"Circuito B"}
        assert mirror_structure_issues(db, clone_id) == []
