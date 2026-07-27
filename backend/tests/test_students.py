"""Regression tests for student management (C1)."""

from conftest import ADMIN, login


def student_payload(rut: str, email: str) -> dict:
    return {
        "ecoe_event_id": 1,
        "name": "Nuevo",
        "last_name": "Estudiante",
        "rut": rut,
        "email": email,
        "group_name": "Grupo 1",
        "circuit_name": "Circuito A",
    }


class TestCreateStudent:
    def test_create_student_succeeds(self, auth_client):
        """Regression C1: POST /students crashed with a duplicate kwarg TypeError."""
        response = auth_client.post(
            "/api/students", json=student_payload("22222222-2", "nuevo1@test.cl")
        )
        assert response.status_code == 200, response.text
        data = response.json()
        assert data["rut"] == "22222222-2"
        assert data["email"] == "nuevo1@test.cl"
        assert data["ecoe_number"]  # assigned automatically

    def test_create_student_normalizes_rut_and_email(self, auth_client):
        response = auth_client.post(
            "/api/students", json=student_payload("  33333333-K ", "MAYUSCULAS@TEST.CL")
        )
        assert response.status_code == 200, response.text
        data = response.json()
        assert data["rut"] == "33333333-k"
        assert data["email"] == "mayusculas@test.cl"

    def test_create_student_duplicate_rut_rejected(self, auth_client):
        first = auth_client.post(
            "/api/students", json=student_payload("44444444-4", "dup1@test.cl")
        )
        assert first.status_code == 200
        second = auth_client.post(
            "/api/students", json=student_payload("44444444-4", "dup2@test.cl")
        )
        assert second.status_code == 400
