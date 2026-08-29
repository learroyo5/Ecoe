"""Al hacer check-in de un estudiante que ya tiene una evaluación registrada en
esa estación, el backend avisa (409 `student_already_evaluated`) salvo que el
evaluador confirme con `force`."""

from datetime import datetime, timedelta

from conftest import ADMIN, TestingSessionLocal, login
from app.models.entities import ECOEEvent, EvaluatorRecord, LiveSession, Student
from app.models.enums import ECOEStatus, SessionMode
from app.utils.clock import utcnow_naive


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


def _parse(iso: str) -> datetime:
    return datetime.fromisoformat(iso).replace(tzinfo=None)


def test_execution_mode_real_ecoe_behaviour(auth_client):
    """ECOE real (`en_ejecucion`, LiveSession `running`):
    - re-cargar un estudiante ya evaluado avisa (409); con force entra igual;
    - el reloj NO se reinicia: el deadline es el fin de la fase, igual para
      quien entra tarde (D2), no `confirmed_at + tiempo de estación`.
    """
    login(auth_client, ADMIN)
    with TestingSessionLocal() as db:
        event = db.get(ECOEEvent, 1)
        original_status = str(event.status)
        event.status = ECOEStatus.en_ejecucion.value
        ls = db.query(LiveSession).filter_by(ecoe_event_id=1).one()
        orig_ls = (str(ls.status), ls.phase_started_at, ls.remaining_seconds)
        # Fase en curso: arrancó hace 200 s, dura 300 s -> quedan ~100 s.
        ls.status = "running"
        ls.phase_started_at = utcnow_naive() - timedelta(seconds=200)
        ls.remaining_seconds = 300
        db.commit()
    try:
        now = utcnow_naive()
        # 1. Estudiante ya evaluado (seed: E001/est.1/ejecución) -> aviso.
        warn = auth_client.post("/api/station-checkins/confirm", json={
            "ecoe_event_id": 1, "station_id": 1, "ecoe_number": "E001",
        })
        assert warn.status_code == 409, warn.text
        assert warn.json()["detail"]["code"] == "student_already_evaluated"

        # 2. force -> entra; el deadline del evaluador es la fase + transición
        #    (~100 s + 120 s ≈ ahora+220 s), NO confirmed_at + 5 min + 2 min.
        forced = auth_client.post("/api/station-checkins/confirm", json={
            "ecoe_event_id": 1, "station_id": 1, "ecoe_number": "E001", "force": True,
        })
        assert forced.status_code == 200, forced.text
        d_forced = _parse(forced.json()["evaluator_deadline"])
        assert now + timedelta(seconds=150) < d_forced < now + timedelta(seconds=300), d_forced
        # confirmed_at + 5min(+2min transición) sería ~ahora+420s: descartado.
        assert d_forced < now + timedelta(seconds=380)

        # 3. Estudiante distinto que entra "tarde" en la misma fase: mismo
        #    deadline (el reloj no arranca de nuevo por check-in).
        other = auth_client.post("/api/station-checkins/confirm", json={
            "ecoe_event_id": 1, "station_id": 1, "ecoe_number": "E003",
        })
        assert other.status_code == 200, other.text
        d_other = _parse(other.json()["evaluator_deadline"])
        assert abs((d_other - d_forced).total_seconds()) < 3, (d_other, d_forced)
    finally:
        with TestingSessionLocal() as db:
            db.get(ECOEEvent, 1).status = original_status
            ls = db.query(LiveSession).filter_by(ecoe_event_id=1).one()
            ls.status, ls.phase_started_at, ls.remaining_seconds = orig_ls
            db.commit()
