"""Al hacer check-in de un estudiante que ya tiene una evaluación registrada en
esa estación, el backend avisa (409 `student_already_evaluated`) salvo que el
evaluador confirme con `force`."""

from conftest import ADMIN, TestingSessionLocal, login
from app.models.entities import ECOEEvent, EvaluatorRecord, Student
from app.models.enums import ECOEStatus, SessionMode


def _seeded_evaluated(db):
    """Student E001 tiene un EvaluatorRecord de ejecución en la estación 1 (seed)."""
    return db.query(Student).filter_by(ecoe_event_id=1, ecoe_number="E001").one()


def test_checkin_warns_when_student_already_evaluated(auth_client):
    login(auth_client, ADMIN)
    with TestingSessionLocal() as db:
        original = str(db.get(ECOEEvent, 1).status)
        db.get(ECOEEvent, 1).status = ECOEStatus.en_ejecucion.value
        db.commit()
    try:
        resp = auth_client.post("/api/station-checkins/confirm", json={
            "ecoe_event_id": 1, "station_id": 1, "ecoe_number": "E001",
        })
        assert resp.status_code == 409, resp.text
        body = resp.json()["detail"]
        assert body["code"] == "student_already_evaluated"
        assert "estación" in body["message"]

        # con force: crea el check-in igual
        forced = auth_client.post("/api/station-checkins/confirm", json={
            "ecoe_event_id": 1, "station_id": 1, "ecoe_number": "E001", "force": True,
        })
        assert forced.status_code == 200, forced.text
        assert forced.json()["student_id"] == _get_e001_id()
    finally:
        with TestingSessionLocal() as db:
            db.get(ECOEEvent, 1).status = original
            db.commit()


def test_checkin_ok_for_student_without_evaluation(auth_client):
    login(auth_client, ADMIN)
    with TestingSessionLocal() as db:
        original = str(db.get(ECOEEvent, 1).status)
        db.get(ECOEEvent, 1).status = ECOEStatus.en_ejecucion.value
        db.commit()
    try:
        resp = auth_client.post("/api/station-checkins/confirm", json={
            "ecoe_event_id": 1, "station_id": 1, "ecoe_number": "E003",
        })
        assert resp.status_code == 200, resp.text
    finally:
        with TestingSessionLocal() as db:
            db.get(ECOEEvent, 1).status = original
            db.commit()


def test_checkin_warning_is_mode_scoped(auth_client):
    """El registro seed es de ejecución: en pilotaje NO debe avisar por E001."""
    login(auth_client, ADMIN)
    with TestingSessionLocal() as db:
        original = str(db.get(ECOEEvent, 1).status)
        db.get(ECOEEvent, 1).status = ECOEStatus.en_pilotaje.value
        db.commit()
        # sanity: no hay EvaluatorRecord de pilotaje para E001/estación 1
        assert db.query(EvaluatorRecord).filter_by(
            ecoe_event_id=1, station_id=1,
            student_id=_seeded_evaluated(db).id, mode=SessionMode.pilotaje.value,
        ).count() == 0
    try:
        resp = auth_client.post("/api/station-checkins/confirm", json={
            "ecoe_event_id": 1, "station_id": 1, "ecoe_number": "E001",
        })
        assert resp.status_code == 200, resp.text
    finally:
        with TestingSessionLocal() as db:
            db.get(ECOEEvent, 1).status = original
            db.commit()


def _get_e001_id():
    with TestingSessionLocal() as db:
        return _seeded_evaluated(db).id
