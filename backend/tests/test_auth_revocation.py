"""JWT revocation via token_version (A4)."""

from fastapi.testclient import TestClient

from conftest import ADMIN, COEDITOR, app, login


class TestSessionRevocation:
    def test_deactivating_user_revokes_existing_sessions(self, auth_client):
        users = auth_client.get("/api/users").json()
        coeditor = next(u for u in users if u["email"] == COEDITOR[0])

        with TestClient(app) as victim:
            login(victim, COEDITOR)
            assert victim.get("/api/auth/me").status_code == 200

            deactivate = auth_client.patch(
                f"/api/users/{coeditor['id']}", json={"is_active": False}
            )
            assert deactivate.status_code == 200

            # Existing session must be dead immediately.
            assert victim.get("/api/auth/me").status_code == 401

            # Reactivating does NOT resurrect old tokens (version was bumped).
            reactivate = auth_client.patch(
                f"/api/users/{coeditor['id']}", json={"is_active": True}
            )
            assert reactivate.status_code == 200
            assert victim.get("/api/auth/me").status_code == 401

            # A fresh login works again.
            login(victim, COEDITOR)
            assert victim.get("/api/auth/me").status_code == 200

    def test_password_change_revokes_existing_sessions(self, auth_client):
        users = auth_client.get("/api/users").json()
        coeditor = next(u for u in users if u["email"] == COEDITOR[0])

        with TestClient(app) as victim:
            login(victim, COEDITOR)
            assert victim.get("/api/auth/me").status_code == 200

            change = auth_client.patch(
                f"/api/users/{coeditor['id']}", json={"password": "otra-clave-segura-123"}
            )
            assert change.status_code == 200
            assert victim.get("/api/auth/me").status_code == 401

            # Restore the original password for the rest of the suite.
            restore = auth_client.patch(
                f"/api/users/{coeditor['id']}", json={"password": COEDITOR[1]}
            )
            assert restore.status_code == 200
