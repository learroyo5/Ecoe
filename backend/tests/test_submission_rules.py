"""Server-side integrity of submissions: time window (C3) and scores (C4)."""

from datetime import datetime, timedelta, timezone

from conftest import ADMIN, STUDENT, TestingSessionLocal, login
from app.models.entities import EvaluatorRecord, StationCheckIn


def _utcnow_naive() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _create_checkin(station_id: int, student_id: int, *, minutes_ago: float = 0) -> int:
    with TestingSessionLocal() as db:
        checkin = StationCheckIn(
            ecoe_event_id=1,
            station_id=station_id,
            student_id=student_id,
            evaluator_email="eval1@ecoe.cl",
            evaluator_name="Enf. Camila Soto",
            status="confirmado",
            confirmed_at=_utcnow_naive() - timedelta(minutes=minutes_ago),
        )
        db.add(checkin)
        db.commit()
        db.refresh(checkin)
        return checkin.id


def evaluator_payload(station_id: int, student_id: int, checkin_id: int, **overrides) -> dict:
    payload = {
        "checkin_id": checkin_id,
        "ecoe_event_id": 1,
        "station_id": station_id,
        "student_id": student_id,
        "evaluator_name": "Test Evaluator",
        "score_obtained": 15,
        "max_score": 99,  # client-supplied garbage: the server must ignore it
        "observation": "",
        "answers": {},
    }
    payload.update(overrides)
    return payload


class TestEvaluatorSubmissionRules:
    def test_submit_after_time_window_rejected(self, auth_client):
        # Station 1 lasts 8 min + 2 transition; 30 minutes is far past the window.
        checkin_id = _create_checkin(station_id=1, student_id=2, minutes_ago=30)
        response = auth_client.post(
            "/api/evaluator/submit",
            json=evaluator_payload(1, 2, checkin_id),
        )
        assert response.status_code == 400
        assert "expiro" in response.json()["detail"]

    def test_score_above_authoritative_max_rejected(self, auth_client):
        checkin_id = _create_checkin(station_id=1, student_id=3)
        response = auth_client.post(
            "/api/evaluator/submit",
            json=evaluator_payload(1, 3, checkin_id, score_obtained=25),
        )
        assert response.status_code == 400
        assert "puntaje" in response.json()["detail"].lower()

    def test_negative_score_rejected(self, auth_client):
        checkin_id = _create_checkin(station_id=1, student_id=3)
        response = auth_client.post(
            "/api/evaluator/submit",
            json=evaluator_payload(1, 3, checkin_id, score_obtained=-1),
        )
        assert response.status_code == 400

    def test_valid_submit_uses_server_side_max_score_and_mode(self, auth_client):
        checkin_id = _create_checkin(station_id=1, student_id=4)
        response = auth_client.post(
            "/api/evaluator/submit",
            json=evaluator_payload(1, 4, checkin_id, score_obtained=15, mode="pilotaje"),
        )
        assert response.status_code == 200, response.text
        record_id = response.json()["record_id"]

        with TestingSessionLocal() as db:
            record = db.get(EvaluatorRecord, record_id)
            # Seed tool items sum to 20; client sent max_score=99.
            assert record.max_score == 20
            # ECOE 1 is "publicado": mode is ejecucion regardless of the payload.
            assert record.mode == "ejecucion"

    def test_duplicate_submit_rejected(self, auth_client):
        checkin_id = _create_checkin(station_id=1, student_id=5)
        first = auth_client.post(
            "/api/evaluator/submit", json=evaluator_payload(1, 5, checkin_id)
        )
        assert first.status_code == 200
        second = auth_client.post(
            "/api/evaluator/submit", json=evaluator_payload(1, 5, checkin_id)
        )
        assert second.status_code == 400


class TestStudentSubmissionRules:
    def test_student_submit_after_time_window_rejected(self, client):
        _create_checkin(station_id=2, student_id=1, minutes_ago=30)
        login(client, STUDENT)
        response = client.post("/api/student/submit", json={
            "ecoe_event_id": 1,
            "station_id": 2,
            "student_id": 1,
            "answers": {"q1": "SCA"},
        })
        assert response.status_code == 400
        assert "expiro" in response.json()["detail"]

    def test_student_submit_within_window_succeeds_once(self, client):
        _create_checkin(station_id=2, student_id=1)
        login(client, STUDENT)
        response = client.post("/api/student/submit", json={
            "ecoe_event_id": 1,
            "station_id": 2,
            "student_id": 1,
            "answers": {"q1": "SCA"},
        })
        assert response.status_code == 200, response.text

        duplicate = client.post("/api/student/submit", json={
            "ecoe_event_id": 1,
            "station_id": 2,
            "student_id": 1,
            "answers": {"q1": "TEP"},
        })
        assert duplicate.status_code == 400

    def test_student_cannot_submit_for_another_student(self, client):
        _create_checkin(station_id=3, student_id=2)
        login(client, STUDENT)  # student1 account
        response = client.post("/api/student/submit", json={
            "ecoe_event_id": 1,
            "station_id": 3,
            "student_id": 2,
            "answers": {},
        })
        assert response.status_code == 403
