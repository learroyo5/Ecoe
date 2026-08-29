"""Station kiosk: token lifecycle, station-scoped context, and submissions."""

from datetime import datetime, timedelta, timezone

from sqlalchemy import select

from app.models.entities import (
    ECOEEvent,
    StationCheckIn,
    StationKioskSession,
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


def _create_checkin(station_id: int, student_id: int, *, minutes_ago: float = 0,
                    status: str = "confirmado") -> int:
    with TestingSessionLocal() as db:
        checkin = StationCheckIn(
            ecoe_event_id=1,
            station_id=station_id,
            student_id=student_id,
            evaluator_email="eval1@ecoe.cl",
            evaluator_name="Enf. Camila Soto",
            status=status,
            confirmed_at=_utcnow_naive() - timedelta(minutes=minutes_ago),
        )
        db.add(checkin)
        db.commit()
        db.refresh(checkin)
        return checkin.id


def _issue_token(client, station_id: int) -> str:
    login(client, COORDINATOR)
    response = client.post(f"/api/kiosk/stations/{station_id}/token")
    assert response.status_code == 200, response.text
    return response.json()["token"]


def _kiosk_headers(token: str) -> dict:
    return {"X-Kiosk-Token": token}


class TestKioskTokenLifecycle:
    def test_evaluator_cannot_issue_token(self, client):
        login(client, ("eval1@ecoe.cl", "test-evaluator-password"))
        response = client.post("/api/kiosk/stations/1/token")
        assert response.status_code == 403

    def test_issuing_new_token_revokes_previous(self, client):
        first = _issue_token(client, 1)
        second = _issue_token(client, 1)
        assert first != second
        denied = client.get("/api/kiosk/context", headers=_kiosk_headers(first))
        assert denied.status_code == 401
        allowed = client.get("/api/kiosk/context", headers=_kiosk_headers(second))
        assert allowed.status_code == 200

    def test_revoked_and_garbage_tokens_rejected(self, client):
        token = _issue_token(client, 1)
        revoke = client.delete("/api/kiosk/stations/1/token")
        assert revoke.status_code == 200
        assert revoke.json()["revoked"] >= 1
        assert client.get(
            "/api/kiosk/context", headers=_kiosk_headers(token)
        ).status_code == 401
        assert client.get(
            "/api/kiosk/context", headers=_kiosk_headers("no-es-un-token")
        ).status_code == 401
        assert client.get("/api/kiosk/context").status_code == 401

    def test_expired_token_rejected(self, client):
        token = _issue_token(client, 1)
        with TestingSessionLocal() as db:
            session = db.scalars(
                select(StationKioskSession).where(
                    StationKioskSession.station_id == 1,
                    StationKioskSession.revoked_at.is_(None),
                )
            ).first()
            session.expires_at = _utcnow_naive() - timedelta(seconds=1)
            db.add(session)
            db.commit()
        assert client.get(
            "/api/kiosk/context", headers=_kiosk_headers(token)
        ).status_code == 401


class TestKioskContext:
    def test_context_waits_without_checkin(self, client):
        # Station 4 has no check-ins in the seed or other tests.
        token = _issue_token(client, 4)
        response = client.get("/api/kiosk/context", headers=_kiosk_headers(token))
        assert response.status_code == 200
        body = response.json()
        assert body["active"] is None
        assert body["station_id"] == 4

    def test_context_shows_station_confirmed_student(self, client):
        original_status = _event_status(1)
        try:
            _set_event_status(1, ECOEStatus.en_ejecucion.value)
            token = _issue_token(client, 2)
            checkin_id = _create_checkin(station_id=2, student_id=3)
            response = client.get("/api/kiosk/context", headers=_kiosk_headers(token))
            assert response.status_code == 200
            active = response.json()["active"]
            assert active is not None
            assert active["checkin_id"] == checkin_id
            assert active["student_id"] == 3
            assert active["submission_deadline"]
            assert active["student_response_exists"] is False
        finally:
            _set_event_status(1, original_status)


class TestKioskSubmit:
    def test_submit_records_response_for_checked_in_student(self, client):
        original_status = _event_status(1)
        try:
            _set_event_status(1, ECOEStatus.en_ejecucion.value)
            token = _issue_token(client, 3)
            checkin_id = _create_checkin(station_id=3, student_id=4)
            response = client.post(
                "/api/kiosk/submit",
                headers=_kiosk_headers(token),
                json={"checkin_id": checkin_id, "answers": {"q1": "desde kiosco"}},
            )
            assert response.status_code == 200, response.text
            with TestingSessionLocal() as db:
                saved = db.get(StudentResponse, response.json()["response_id"])
                assert saved.student_id == 4
                assert saved.station_id == 3
                assert saved.mode == "ejecucion"
                assert saved.locked is True
        finally:
            _set_event_status(1, original_status)

    def test_submit_rejected_for_foreign_station_checkin(self, client):
        original_status = _event_status(1)
        try:
            _set_event_status(1, ECOEStatus.en_ejecucion.value)
            token = _issue_token(client, 3)
            foreign_checkin_id = _create_checkin(station_id=1, student_id=5)
            response = client.post(
                "/api/kiosk/submit",
                headers=_kiosk_headers(token),
                json={"checkin_id": foreign_checkin_id, "answers": {"q1": "x"}},
            )
            assert response.status_code == 400
            assert "no corresponde" in response.json()["detail"]
        finally:
            _set_event_status(1, original_status)

    def test_submit_rejects_previous_checkin_after_rotation(self, client):
        """OPT-8: el evaluador ya confirmó al siguiente estudiante (cerrando
        el ingreso anterior). El kiosco NO debe aceptar un envío atribuido al
        ingreso previo aunque su ventana siga abierta: va por contingencia."""
        original_status = _event_status(1)
        try:
            _set_event_status(1, ECOEStatus.en_ejecucion.value)
            token = _issue_token(client, 5)
            closed_checkin_id = _create_checkin(
                station_id=5, student_id=6, minutes_ago=2, status="cerrado"
            )
            active_checkin_id = _create_checkin(station_id=5, student_id=7)  # siguiente, activo
            rejected = client.post(
                "/api/kiosk/submit",
                headers=_kiosk_headers(token),
                json={"checkin_id": closed_checkin_id, "answers": {"q1": "tarde"}},
            )
            assert rejected.status_code == 409, rejected.text
            assert "ingreso activo" in rejected.json()["detail"]
            with TestingSessionLocal() as db:
                assert db.scalar(
                    select(StudentResponse).where(StudentResponse.student_id == 6)
                ) is None
            # El ingreso vigente sí es aceptado.
            accepted = client.post(
                "/api/kiosk/submit",
                headers=_kiosk_headers(token),
                json={"checkin_id": active_checkin_id, "answers": {"q1": "a tiempo"}},
            )
            assert accepted.status_code == 200, accepted.text
            with TestingSessionLocal() as db:
                saved = db.get(StudentResponse, accepted.json()["response_id"])
                assert saved.student_id == 7
        finally:
            _set_event_status(1, original_status)

    def test_submit_rejected_once_a_newer_checkin_is_confirmed(self, client):
        """Tras confirmar un nuevo check-in, el anterior (que sí fue el
        vigente) deja de aceptar envíos por el kiosco."""
        original_status = _event_status(1)
        try:
            _set_event_status(1, ECOEStatus.en_ejecucion.value)
            token = _issue_token(client, 6)
            first_checkin_id = _create_checkin(station_id=6, student_id=9, minutes_ago=1)
            # Nuevo ingreso confirmado: cierra el anterior en el flujo real,
            # aquí basta con que sea el más reciente `confirmado`.
            _create_checkin(station_id=6, student_id=10)
            response = client.post(
                "/api/kiosk/submit",
                headers=_kiosk_headers(token),
                json={"checkin_id": first_checkin_id, "answers": {}},
            )
            assert response.status_code == 409, response.text
        finally:
            _set_event_status(1, original_status)

    def test_submit_rejected_after_window_and_outside_stage(self, client):
        original_status = _event_status(1)
        try:
            _set_event_status(1, ECOEStatus.en_ejecucion.value)
            token = _issue_token(client, 4)
            expired_checkin_id = _create_checkin(station_id=4, student_id=8, minutes_ago=30)
            expired = client.post(
                "/api/kiosk/submit",
                headers=_kiosk_headers(token),
                json={"checkin_id": expired_checkin_id, "answers": {}},
            )
            assert expired.status_code == 400
            assert "expiró" in expired.json()["detail"]

            _set_event_status(1, ECOEStatus.publicado.value)
            fresh_checkin_id = _create_checkin(station_id=4, student_id=8)
            gated = client.post(
                "/api/kiosk/submit",
                headers=_kiosk_headers(token),
                json={"checkin_id": fresh_checkin_id, "answers": {}},
            )
            assert gated.status_code == 409
        finally:
            _set_event_status(1, original_status)
