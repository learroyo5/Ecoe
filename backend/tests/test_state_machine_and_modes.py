"""Fase 1 regressions: lifecycle state machine, stage gate for operational
records, pilotaje/ejecucion mode isolation, contingency entry, and the
freeze-on-close behavior."""

from datetime import datetime, timedelta, timezone

from sqlalchemy import select

from app.models.entities import (
    ECOEEvent,
    ECOEResult,
    EvaluatorRecord,
    StationCheckIn,
    StudentResponse,
)
from app.models.enums import ECOEStatus
from conftest import ADMIN, COORDINATOR, TestingSessionLocal, login


def _utcnow_naive() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _set_event_status(event_id: int, status: str) -> None:
    with TestingSessionLocal() as db:
        event = db.get(ECOEEvent, event_id)
        event.status = status
        db.add(event)
        db.commit()


def _event_status(event_id: int) -> str:
    with TestingSessionLocal() as db:
        return str(db.get(ECOEEvent, event_id).status)


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


def _evaluator_payload(station_id: int, student_id: int, checkin_id: int | None, **overrides) -> dict:
    payload = {
        "checkin_id": checkin_id,
        "ecoe_event_id": 1,
        "station_id": station_id,
        "student_id": student_id,
        "evaluator_name": "Test Evaluator",
        "score_obtained": 10,
        "max_score": 99,
        "observation": "",
        "answers": {},
    }
    payload.update(overrides)
    return payload


def _current_event_payload(client, event_id: int, status: str) -> dict:
    """Full PUT payload for the event with the requested target status."""
    event = client.get(f"/api/ecoe/{event_id}").json()
    return {
        "name": event["name"],
        "date": event["date"],
        "course_name": event["course_name"],
        "school_name": event["school_name"],
        "responsible_teacher": event["responsible_teacher"],
        "contact_email": event["contact_email"],
        "circuit_mode": event["circuit_mode"],
        "total_stations": event["total_stations"],
        "station_time_minutes": event["station_time_minutes"],
        "transition_time_minutes": event["transition_time_minutes"],
        "total_students": event["total_students"],
        "total_groups": event["total_groups"],
        "passing_reference_percent": event["passing_reference_percent"],
        "status": status,
    }


class TestModeIsolation:
    """A pilotaje record must never block or contaminate the real run."""

    def test_pilot_then_execution_submission_succeeds(self, auth_client):
        original_status = _event_status(1)
        try:
            _set_event_status(1, ECOEStatus.en_pilotaje.value)
            pilot_checkin = _create_checkin(station_id=1, student_id=6)
            pilot = auth_client.post(
                "/api/evaluator/submit",
                json=_evaluator_payload(1, 6, pilot_checkin),
            )
            assert pilot.status_code == 200, pilot.text

            _set_event_status(1, ECOEStatus.en_ejecucion.value)
            real_checkin = _create_checkin(station_id=1, student_id=6)
            real = auth_client.post(
                "/api/evaluator/submit",
                json=_evaluator_payload(1, 6, real_checkin, score_obtained=18),
            )
            assert real.status_code == 200, real.text

            with TestingSessionLocal() as db:
                modes = set(db.scalars(
                    select(EvaluatorRecord.mode).where(
                        EvaluatorRecord.ecoe_event_id == 1,
                        EvaluatorRecord.station_id == 1,
                        EvaluatorRecord.student_id == 6,
                    )
                ).all())
            assert modes == {"pilotaje", "ejecucion"}
        finally:
            _set_event_status(1, original_status)

    def test_pilot_student_response_does_not_block_execution(self, client):
        original_status = _event_status(1)
        login(client, ADMIN)
        try:
            _set_event_status(1, ECOEStatus.en_pilotaje.value)
            pilot_checkin = _create_checkin(station_id=2, student_id=7)
            pilot = client.post("/api/student/submit", json={
                "checkin_id": pilot_checkin,
                "ecoe_event_id": 1,
                "station_id": 2,
                "student_id": 7,
                "answers": {"q1": "piloto"},
            })
            assert pilot.status_code == 200, pilot.text

            _set_event_status(1, ECOEStatus.en_ejecucion.value)
            real_checkin = _create_checkin(station_id=2, student_id=7)
            real = client.post("/api/student/submit", json={
                "checkin_id": real_checkin,
                "ecoe_event_id": 1,
                "station_id": 2,
                "student_id": 7,
                "answers": {"q1": "real"},
            })
            assert real.status_code == 200, real.text

            with TestingSessionLocal() as db:
                modes = set(db.scalars(
                    select(StudentResponse.mode).where(
                        StudentResponse.ecoe_event_id == 1,
                        StudentResponse.station_id == 2,
                        StudentResponse.student_id == 7,
                    )
                ).all())
            assert modes == {"pilotaje", "ejecucion"}
        finally:
            _set_event_status(1, original_status)


class TestStageGate:
    """Operational records are rejected outside en_pilotaje/en_ejecucion."""

    def test_submission_rejected_while_publicado(self, auth_client):
        original_status = _event_status(1)
        try:
            _set_event_status(1, ECOEStatus.publicado.value)
            checkin_id = _create_checkin(station_id=1, student_id=8)
            response = auth_client.post(
                "/api/evaluator/submit",
                json=_evaluator_payload(1, 8, checkin_id),
            )
            assert response.status_code == 409
            assert "pilotaje o en ejecucion" in response.json()["detail"]
        finally:
            _set_event_status(1, original_status)

    def test_checkin_rejected_while_publicado(self, auth_client):
        original_status = _event_status(1)
        try:
            _set_event_status(1, ECOEStatus.publicado.value)
            response = auth_client.post("/api/station-checkins/confirm", json={
                "ecoe_event_id": 1,
                "station_id": 1,
                "ecoe_number": "001",
            })
            assert response.status_code == 409
        finally:
            _set_event_status(1, original_status)


class TestStatusTransitions:
    """The lifecycle graph rejects arbitrary jumps."""

    def test_invalid_jump_rejected(self, auth_client):
        created = auth_client.post("/api/ecoe", json={
            "name": "Grafo de estados",
            "date": "2026-12-01",
            "course_name": "Curso",
            "school_name": "Escuela",
            "responsible_teacher": "Docente",
            "contact_email": "docente@example.edu",
            "circuit_mode": "paralelo_espejo",
            "total_stations": 1,
            "station_time_minutes": 8,
            "transition_time_minutes": 2,
            "total_students": 1,
            "total_groups": 1,
            "passing_reference_percent": 60,
        })
        assert created.status_code == 200, created.text
        event_id = created.json()["id"]

        jump = auth_client.put(
            f"/api/ecoe/{event_id}",
            json=_current_event_payload(auth_client, event_id, ECOEStatus.archivado.value),
        )
        assert jump.status_code == 400
        assert "no permitida" in jump.json()["detail"]

        forward = auth_client.put(
            f"/api/ecoe/{event_id}",
            json=_current_event_payload(auth_client, event_id, ECOEStatus.en_configuracion.value),
        )
        assert forward.status_code == 200, forward.text
        assert forward.json()["status"] == ECOEStatus.en_configuracion.value

    def test_same_state_put_is_allowed(self, auth_client):
        """Full-form edits resend the current status; that must never fail."""
        original_status = _event_status(1)
        response = auth_client.put(
            "/api/ecoe/1",
            json=_current_event_payload(auth_client, 1, original_status),
        )
        assert response.status_code == 200, response.text

    def test_closed_event_cannot_reopen_to_borrador(self, auth_client):
        original_status = _event_status(1)
        try:
            _set_event_status(1, ECOEStatus.cerrado.value)
            response = auth_client.put(
                "/api/ecoe/1",
                json=_current_event_payload(auth_client, 1, ECOEStatus.borrador.value),
            )
            assert response.status_code == 400
        finally:
            _set_event_status(1, original_status)


class TestContingency:
    """Coordination can register out-of-window records, audited and flagged."""

    def test_contingency_accepts_expired_window(self, client):
        original_status = _event_status(1)
        login(client, COORDINATOR)
        try:
            _set_event_status(1, ECOEStatus.en_ejecucion.value)
            # 30 minutes ago: far beyond the 8+2 minute window.
            _create_checkin(station_id=1, student_id=9, minutes_ago=30)
            normal = client.post(
                "/api/evaluator/submit",
                json=_evaluator_payload(1, 9, None),
            )
            assert normal.status_code == 400  # expired for the normal path

            contingency = client.post(
                "/api/contingency/evaluator-record",
                json=_evaluator_payload(1, 9, None, score_obtained=12),
            )
            assert contingency.status_code == 200, contingency.text
            assert contingency.json()["by_contingency"] is True

            with TestingSessionLocal() as db:
                record = db.get(EvaluatorRecord, contingency.json()["record_id"])
                assert record.by_contingency is True
                assert record.mode == "ejecucion"
                assert record.max_score == 20  # authoritative, not client's 99
        finally:
            _set_event_status(1, original_status)

    def test_contingency_requires_coordination_role(self, client):
        original_status = _event_status(1)
        try:
            _set_event_status(1, ECOEStatus.en_ejecucion.value)
            _create_checkin(station_id=2, student_id=9, minutes_ago=30)
            login(client, ("eval1@ecoe.cl", "test-evaluator-password"))
            response = client.post(
                "/api/contingency/evaluator-record",
                json=_evaluator_payload(2, 9, None),
            )
            assert response.status_code == 403
        finally:
            _set_event_status(1, original_status)

    def test_contingency_requires_some_checkin(self, client):
        original_status = _event_status(1)
        login(client, COORDINATOR)
        try:
            _set_event_status(1, ECOEStatus.en_ejecucion.value)
            # Student 10 never checked in at station 3.
            response = client.post(
                "/api/contingency/evaluator-record",
                json=_evaluator_payload(3, 10, None),
            )
            assert response.status_code == 400
            assert "check-in" in response.json()["detail"]
        finally:
            _set_event_status(1, original_status)


class TestCloseFreezes:
    """Closing the event consolidates results and closes open check-ins."""

    def test_close_persists_results_and_closes_checkins(self, auth_client):
        original_status = _event_status(1)
        try:
            _set_event_status(1, ECOEStatus.en_ejecucion.value)
            open_checkin_id = _create_checkin(station_id=1, student_id=10)

            response = auth_client.put(
                "/api/ecoe/1",
                json=_current_event_payload(auth_client, 1, ECOEStatus.cerrado.value),
            )
            assert response.status_code == 200, response.text
            assert response.json()["status"] == ECOEStatus.cerrado.value

            with TestingSessionLocal() as db:
                checkin = db.get(StationCheckIn, open_checkin_id)
                assert checkin.status == "cerrado"
                consolidated = db.scalars(
                    select(ECOEResult).where(ECOEResult.ecoe_event_id == 1)
                ).all()
                assert len(consolidated) > 0

            # And the freeze holds: no new evaluations while cerrado.
            blocked = auth_client.post(
                "/api/evaluator/submit",
                json=_evaluator_payload(1, 10, None),
            )
            assert blocked.status_code == 409
        finally:
            _set_event_status(1, original_status)
