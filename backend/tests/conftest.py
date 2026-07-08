"""Shared test setup.

By default tests run on SQLite (fast local loop). Set TEST_DATABASE_URL to a
PostgreSQL URL to run the same suite against the real engine applying the
Alembic migrations (this is what CI does), which also exercises the unique
constraints that SQLite skips.
"""

import os
from pathlib import Path

TEST_DATABASE_URL = os.environ.get("TEST_DATABASE_URL", "sqlite:///./test.db")

# Environment must be ready BEFORE importing app modules.
os.environ["SECRET_KEY"] = "test-secret-key-for-testing-only"
os.environ["DATABASE_URL"] = TEST_DATABASE_URL
os.environ["ENVIRONMENT"] = "development"
# SQLite cannot run the baseline migration (ALTER ADD CONSTRAINT); allow the
# dev-only create_all fallback in the app lifespan.
os.environ["ALLOW_CREATE_ALL_FALLBACK"] = "true"
os.environ["ADMIN_PASSWORD"] = "test-admin-password"
os.environ["COEDITOR_PASSWORD"] = "test-coeditor-password"
os.environ["EVALUATOR_PASSWORD"] = "test-evaluator-password"
os.environ["STUDENT_PASSWORD"] = "test-student-password"
os.environ["COORDINATOR_PASSWORD"] = "test-coordinator-password"
os.environ["TIMER_PASSWORD"] = "test-timer-password"
os.environ["STORAGE_PATH"] = "/tmp/ecoe-test-storage"

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

from app.db.session import Base, get_db
from app.main import app
from app.db.seed import seed_data

# Disable rate limiting for tests
import app.services.dependencies as deps

deps._LOGIN_MAX_ATTEMPTS = 9999
deps._LOGIN_ACCOUNT_MAX_ATTEMPTS = 9999
deps._LOGIN_GLOBAL_MAX_ATTEMPTS = 9999
deps._login_attempts.clear()

IS_SQLITE = TEST_DATABASE_URL.startswith("sqlite")

if IS_SQLITE:
    engine = create_engine(TEST_DATABASE_URL, connect_args={"check_same_thread": False})
else:
    engine = create_engine(TEST_DATABASE_URL)

TestingSessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)


def _prepare_schema() -> None:
    if IS_SQLITE:
        db_path = TEST_DATABASE_URL.replace("sqlite:///", "")
        if os.path.exists(db_path):
            os.remove(db_path)
        Base.metadata.create_all(bind=engine)
        return
    # PostgreSQL: recreate the schema and apply the real migrations.
    with engine.begin() as conn:
        conn.execute(text("DROP SCHEMA public CASCADE"))
        conn.execute(text("CREATE SCHEMA public"))
    from alembic import command
    from alembic.config import Config as AlembicConfig

    alembic_cfg = AlembicConfig(str(Path(__file__).resolve().parents[1] / "alembic.ini"))
    alembic_cfg.set_main_option("sqlalchemy.url", TEST_DATABASE_URL)
    command.upgrade(alembic_cfg, "head")


_prepare_schema()

with TestingSessionLocal() as _db:
    seed_data(_db)


def override_get_db():
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()


app.dependency_overrides[get_db] = override_get_db

# Credentials used across test modules
ADMIN = ("admin@ecoe.cl", os.environ["ADMIN_PASSWORD"])
COEDITOR = ("coeditor@ecoe.cl", os.environ["COEDITOR_PASSWORD"])
EVALUATOR = ("eval1@ecoe.cl", os.environ["EVALUATOR_PASSWORD"])
STUDENT = ("student1@ecoe.cl", os.environ["STUDENT_PASSWORD"])
COORDINATOR = ("coord@ecoe.cl", os.environ["COORDINATOR_PASSWORD"])
TIMER = ("timer@ecoe.cl", os.environ["TIMER_PASSWORD"])


def login(client: TestClient, credentials: tuple[str, str]) -> None:
    email, password = credentials
    response = client.post("/api/auth/login", json={"email": email, "password": password})
    assert response.status_code == 200, f"login failed for {email}: {response.text}"


@pytest.fixture
def db_factory():
    """Session factory for tests that need direct DB access."""
    return TestingSessionLocal


@pytest.fixture
def client():
    with TestClient(app) as c:
        yield c


@pytest.fixture
def auth_client(client):
    """Client with authenticated admin session via cookie."""
    login(client, ADMIN)
    return client


@pytest.fixture(scope="module")
def unauth_client():
    """Separate unauthenticated client for tests that need no session."""
    with TestClient(app) as c:
        yield c


def pytest_sessionfinish(session, exitstatus):
    import shutil

    if IS_SQLITE:
        db_path = TEST_DATABASE_URL.replace("sqlite:///", "")
        if os.path.exists(db_path):
            os.remove(db_path)
    storage = "/tmp/ecoe-test-storage"
    if os.path.exists(storage):
        shutil.rmtree(storage, ignore_errors=True)
