"""Tests for security and core API functionality."""

import os

os.environ["SECRET_KEY"] = "test-secret-key-for-testing-only"
os.environ["DATABASE_URL"] = "sqlite:///./test.db"
os.environ["CREATOR_PASSWORD"] = "test-creator"
os.environ["COEDITOR_PASSWORD"] = "test-coeditor"
os.environ["EVALUATOR_PASSWORD"] = "test-evaluator"
os.environ["STUDENT_PASSWORD"] = "test-student"
os.environ["COORDINATOR_PASSWORD"] = "test-coordinator"
os.environ["TIMER_PASSWORD"] = "test-timer"
os.environ["STORAGE_PATH"] = "/tmp/ecoe-test-storage"

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db.session import Base, get_db
from app.main import app
from app.db.seed import seed_data

engine = create_engine("sqlite:///./test.db", connect_args={"check_same_thread": False})
TestingSessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)

Base.metadata.create_all(bind=engine)

with TestingSessionLocal() as db:
    seed_data(db)


def override_get_db():
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()


app.dependency_overrides[get_db] = override_get_db


@pytest.fixture
def client():
    with TestClient(app) as c:
        yield c


@pytest.fixture
def auth_client(client):
    """Client with authenticated session."""
    client.post("/api/auth/login", json={
        "email": "creator@ecoe.cl",
        "password": "test-creator",
    })
    return client


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
            "email": "creator@ecoe.cl",
            "password": "test-creator",
        })
        assert response.status_code == 200
        data = response.json()
        assert data["token_type"] == "bearer"
        assert data["user"]["email"] == "creator@ecoe.cl"

    def test_login_invalid_credentials(self, client):
        response = client.post("/api/auth/login", json={
            "email": "creator@ecoe.cl",
            "password": "wrong-password",
        })
        assert response.status_code == 401

    def test_me_authenticated(self, auth_client):
        response = auth_client.get("/api/auth/me")
        assert response.status_code == 200
        assert response.json()["email"] == "creator@ecoe.cl"

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
        response = auth_client.post("/api/ecoe", json={
            "name": "ECOE Test",
            "date": "2026-06-15",
            "course_name": "Test Course",
            "school_name": "Test School",
            "responsible_teacher": "Dr. Test",
            "contact_email": "test@ecoe.cl",
            "circuit_mode": "paralelo_espejo",
            "total_stations": 4,
            "station_time_minutes": 10,
            "transition_time_minutes": 2,
            "total_students": 20,
            "total_groups": 4,
            "passing_reference_percent": 60,
        })
        assert response.status_code == 200
        assert response.json()["name"] == "ECOE Test"

    def test_dashboard(self, auth_client):
        response = auth_client.get("/api/dashboard/1")
        assert response.status_code == 200
        data = response.json()
        assert "active_ecoe" in data


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


def teardown_module():
    import shutil
    db_path = "./test.db"
    if os.path.exists(db_path):
        os.remove(db_path)
    storage = "/tmp/ecoe-test-storage"
    if os.path.exists(storage):
        shutil.rmtree(storage, ignore_errors=True)
