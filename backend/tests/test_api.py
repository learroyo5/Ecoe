"""Tests for security and core API functionality."""

import pytest
from starlette.websockets import WebSocketDisconnect

from conftest import ADMIN, EVALUATOR, STUDENT, login
import app.services.dependencies as deps
from app.models.entities import ECOEResult, MediaAsset, StationCheckIn


def ecoe_payload(name: str = "ECOE Aislado") -> dict:
    return {
        "name": name,
        "date": "2026-08-01",
        "course_name": "Curso Test",
        "school_name": "Escuela Test",
        "responsible_teacher": "Admin Test",
        "contact_email": "test@ecoe.cl",
        "circuit_mode": "paralelo_espejo",
        "total_stations": 4,
        "station_time_minutes": 8,
        "transition_time_minutes": 2,
        "total_students": 10,
        "total_groups": 2,
        "passing_reference_percent": 60,
    }


class TestHealth:
    def test_health_check(self, client):
        response = client.get("/health")
        assert response.status_code == 200
        assert response.json() == {"status": "ok"}

    def test_api_health_check(self, client):
        response = client.get("/api/health")
        assert response.status_code == 200


class TestAuth:
    def test_login_success(self, client):
        response = client.post("/api/auth/login", json={
            "email": ADMIN[0],
            "password": ADMIN[1],
        })
        assert response.status_code == 200
        data = response.json()
        assert data["token_type"] == "bearer"
        assert data["user"]["email"] == "admin@ecoe.cl"

    def test_login_invalid_credentials(self, client):
        response = client.post("/api/auth/login", json={
            "email": ADMIN[0],
            "password": "wrong-password",
        })
        assert response.status_code == 401

    def test_login_rate_limit_by_ip(self, client, monkeypatch):
        deps._login_attempts.clear()
        monkeypatch.setattr(deps, "_LOGIN_MAX_ATTEMPTS", 2)
        monkeypatch.setattr(deps, "_LOGIN_ACCOUNT_MAX_ATTEMPTS", 9999)
        monkeypatch.setattr(deps, "_LOGIN_GLOBAL_MAX_ATTEMPTS", 9999)

        for idx in range(2):
            response = client.post("/api/auth/login", json={
                "email": f"missing{idx}@ecoe.cl",
                "password": "wrong-password",
            })
            assert response.status_code == 401

        blocked = client.post("/api/auth/login", json={
            "email": "another-missing@ecoe.cl",
            "password": "wrong-password",
        })
        assert blocked.status_code == 429

    def test_login_rate_limit_by_account(self, client, monkeypatch):
        deps._login_attempts.clear()
        monkeypatch.setattr(deps, "_LOGIN_MAX_ATTEMPTS", 9999)
        monkeypatch.setattr(deps, "_LOGIN_ACCOUNT_MAX_ATTEMPTS", 2)
        monkeypatch.setattr(deps, "_LOGIN_GLOBAL_MAX_ATTEMPTS", 9999)

        for _idx in range(2):
            response = client.post("/api/auth/login", json={
                "email": ADMIN[0].upper(),
                "password": "wrong-password",
            })
            assert response.status_code == 401

        blocked = client.post("/api/auth/login", json={
            "email": ADMIN[0],
            "password": "wrong-password",
        })
        assert blocked.status_code == 429

    def test_successful_login_clears_account_rate_limit(self, client, monkeypatch):
        deps._login_attempts.clear()
        monkeypatch.setattr(deps, "_LOGIN_MAX_ATTEMPTS", 9999)
        monkeypatch.setattr(deps, "_LOGIN_ACCOUNT_MAX_ATTEMPTS", 2)
        monkeypatch.setattr(deps, "_LOGIN_GLOBAL_MAX_ATTEMPTS", 9999)

        failed = client.post("/api/auth/login", json={
            "email": ADMIN[0],
            "password": "wrong-password",
        })
        assert failed.status_code == 401

        successful = client.post("/api/auth/login", json={
            "email": ADMIN[0],
            "password": ADMIN[1],
        })
        assert successful.status_code == 200

        for _idx in range(2):
            failed_after_success = client.post("/api/auth/login", json={
                "email": ADMIN[0],
                "password": "wrong-password",
            })
            assert failed_after_success.status_code == 401

        blocked = client.post("/api/auth/login", json={
            "email": ADMIN[0],
            "password": "wrong-password",
        })
        assert blocked.status_code == 429

    def test_me_authenticated(self, auth_client):
        response = auth_client.get("/api/auth/me")
        assert response.status_code == 200
        assert response.json()["email"] == "admin@ecoe.cl"

    def test_me_unauthenticated(self, client):
        response = client.get("/api/auth/me")
        assert response.status_code == 401

    def test_logout(self, auth_client):
        response = auth_client.post("/api/auth/logout")
        assert response.status_code == 200
        assert response.json() == {"logged_out": True}


class TestECOE:
    def test_list_ecoe(self, auth_client):
        response = auth_client.get("/api/ecoe")
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        assert len(data) >= 1

    def test_get_ecoe(self, auth_client):
        response = auth_client.get("/api/ecoe/1")
        assert response.status_code == 200
        assert response.json()["name"] == "ECOE Medicina Interna 2026"

    def test_create_ecoe(self, auth_client):
        response = auth_client.post("/api/ecoe", json=ecoe_payload("ECOE Test"))
        assert response.status_code == 200
        assert response.json()["name"] == "ECOE Test"

    def test_duplicate_ecoe(self, auth_client):
        response = auth_client.post("/api/ecoe/1/duplicate", json={
            "name": "ECOE Duplicado",
            "new_date": "2026-07-01",
            "copy_evaluators": False,
        })
        assert response.status_code == 200
        data = response.json()
        assert data["name"] == "ECOE Duplicado"
        assert data["status"] == "borrador"

    def test_dashboard(self, auth_client):
        response = auth_client.get("/api/dashboard/1")
        assert response.status_code == 200
        data = response.json()
        assert "active_ecoe" in data


class TestStations:
    def test_list_stations(self, auth_client):
        response = auth_client.get("/api/stations/1")
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        assert len(data) >= 1

    def test_create_station(self, auth_client):
        response = auth_client.post("/api/stations", json={
            "ecoe_event_id": 1,
            "station_number": 1,
            "name": "Estación Test",
            "station_type": "procedimental",
            "circuit_name": "Circuito A",
            "expected_outcomes": "Resultado esperado",
            "student_activity": "",
            "student_station_instruction": "",
            "pre_entry_instruction": "",
            "evaluator_instruction": "",
            "max_score": 20,
            "materials": "",
            "multimedia_notes": "",
            "requires_evaluator": True,
            "requires_student_form": False,
            "uses_multimedia": False,
            "uses_simulated_patient": False,
            "uses_physical_resources": False,
            "contingency_ready": False,
            "student_form_definition": {"questions": []},
            "status": "en_diseno",
        })
        assert response.status_code == 200
        assert response.json()["name"] == "Estación Test"


class TestIncidents:
    def test_list_incidents(self, auth_client):
        response = auth_client.get("/api/incidents/1")
        assert response.status_code == 200
        data = response.json()
        assert "items" in data

    def test_create_incident(self, auth_client):
        response = auth_client.post("/api/incidents", json={
            "ecoe_event_id": 1,
            "title": "Incidencia de prueba",
            "detail": "Detalle de la incidencia",
            "severity": "alta",
        })
        assert response.status_code == 200
        data = response.json()
        assert data["title"] == "Incidencia de prueba"
        assert data["severity"] == "alta"
        assert data["resolved"] == False

    def test_resolve_incident(self, auth_client):
        create_resp = auth_client.post("/api/incidents", json={
            "ecoe_event_id": 1,
            "title": "Para resolver",
            "severity": "media",
        })
        assert create_resp.status_code == 200
        incident_id = create_resp.json()["id"]

        resolve_resp = auth_client.patch(f"/api/incidents/{incident_id}/resolve", json={
            "resolved": True,
        })
        assert resolve_resp.status_code == 200
        assert resolve_resp.json()["resolved"] == True
        assert resolve_resp.json()["resolved_at"] is not None

    def test_reopen_incident(self, auth_client):
        create_resp = auth_client.post("/api/incidents", json={
            "ecoe_event_id": 1,
            "title": "Para reabrir",
            "severity": "baja",
        })
        incident_id = create_resp.json()["id"]
        auth_client.patch(f"/api/incidents/{incident_id}/resolve", json={"resolved": True})

        reopen_resp = auth_client.patch(f"/api/incidents/{incident_id}/resolve", json={
            "resolved": False,
        })
        assert reopen_resp.status_code == 200
        assert reopen_resp.json()["resolved"] == False


class TestPagination:
    def test_students_paginated(self, auth_client):
        response = auth_client.get("/api/students/1?page=1&page_size=10")
        assert response.status_code == 200
        data = response.json()
        assert "items" in data
        assert "total" in data

    def test_staff_paginated(self, auth_client):
        response = auth_client.get("/api/staff/1?page=1&page_size=10")
        assert response.status_code == 200
        data = response.json()
        assert "items" in data

    def test_incidents_paginated(self, auth_client):
        response = auth_client.get("/api/incidents/1?page=1&page_size=10")
        assert response.status_code == 200
        data = response.json()
        assert "items" in data


class TestMediaSecurity:
    def test_upload_invalid_extension(self, auth_client):
        response = auth_client.post(
            "/api/media/upload?ecoe_event_id=1",
            files={"file": ("test.exe", b"malicious", "application/octet-stream")},
        )
        assert response.status_code == 400

    def test_upload_oversized(self, auth_client):
        big_content = b"x" * (51 * 1024 * 1024)
        response = auth_client.post(
            "/api/media/upload?ecoe_event_id=1",
            files={"file": ("big.pdf", big_content, "application/pdf")},
        )
        assert response.status_code == 400

    def test_student_cannot_access_evaluator_media(self, client, db_factory):
        with db_factory() as db:
            checkin = StationCheckIn(
                ecoe_event_id=1,
                station_id=1,
                student_id=1,
                evaluator_email="eval1@ecoe.cl",
                evaluator_name="Enf. Camila Soto",
                status="confirmado",
            )
            db.add(checkin)
            asset = MediaAsset(
                filename="evaluador.pdf",
                original_name="evaluador.pdf",
                content_type="application/pdf",
                file_path="/tmp/ecoe-test-storage/evaluador.pdf",
                target_viewer="evaluador",
                station_id=1,
            )
            db.add(asset)
            db.commit()
            db.refresh(asset)
            asset_id = asset.id

        login(client, STUDENT)
        response = client.get(f"/api/media/file/{asset_id}")
        assert response.status_code == 403


class TestP0Permissions:
    def test_user_without_event_access_cannot_read_ecoe(self, client):
        login(client, ADMIN)
        create_resp = client.post("/api/ecoe", json=ecoe_payload("ECOE Sin Evaluador"))
        assert create_resp.status_code == 200
        isolated_event_id = create_resp.json()["id"]

        login(client, EVALUATOR)
        response = client.get(f"/api/ecoe/{isolated_event_id}")
        assert response.status_code == 403

    def test_evaluator_cannot_access_other_ecoe_dashboard(self, client):
        login(client, ADMIN)
        create_resp = client.post("/api/ecoe", json=ecoe_payload("ECOE Dashboard Aislado"))
        assert create_resp.status_code == 200
        isolated_event_id = create_resp.json()["id"]

        login(client, EVALUATOR)
        response = client.get(f"/api/dashboard/{isolated_event_id}")
        assert response.status_code == 403

    def test_websocket_rejects_missing_token(self, unauth_client):
        with pytest.raises(WebSocketDisconnect):
            with unauth_client.websocket_connect("/api/ws/live/1"):
                pass

    def test_websocket_rejects_token_without_event_permission(self, client):
        login(client, ADMIN)
        create_resp = client.post("/api/ecoe", json=ecoe_payload("ECOE WS Aislado"))
        assert create_resp.status_code == 200
        isolated_event_id = create_resp.json()["id"]

        login(client, EVALUATOR)
        with pytest.raises(WebSocketDisconnect):
            with client.websocket_connect(f"/api/ws/live/{isolated_event_id}"):
                pass

    def test_get_results_does_not_persist_or_delete_results(self, auth_client, db_factory):
        with db_factory() as db:
            before = db.query(ECOEResult).filter(ECOEResult.ecoe_event_id == 1).count()

        response = auth_client.get("/api/results/1")
        assert response.status_code == 200
        assert "results" in response.json()

        with db_factory() as db:
            after = db.query(ECOEResult).filter(ECOEResult.ecoe_event_id == 1).count()

        assert after == before

    def test_consolidate_results_is_explicit_mutation(self, auth_client, db_factory):
        response = auth_client.post("/api/results/1/consolidate")
        assert response.status_code == 200
        assert response.json()["consolidated"] is True

        with db_factory() as db:
            count = db.query(ECOEResult).filter(ECOEResult.ecoe_event_id == 1).count()

        assert count > 0
