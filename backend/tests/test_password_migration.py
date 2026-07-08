"""Legacy pbkdf2_sha256 hashes (passlib) must keep working and get
transparently upgraded to argon2 (pwdlib) on next login — no forced reset
for accounts created before the migration."""

from passlib.context import CryptContext

from conftest import TestingSessionLocal
from app.core.security import get_password_hash, needs_rehash, verify_password
from app.models.entities import Role, User

_legacy_context = CryptContext(schemes=["pbkdf2_sha256"])


class TestPasswordMigration:
    def test_new_hashes_use_argon2(self):
        hashed = get_password_hash("some-password")
        assert hashed.startswith("$argon2")
        assert not needs_rehash(hashed)

    def test_legacy_pbkdf2_hash_still_verifies(self):
        legacy_hash = _legacy_context.hash("legacy-password")
        assert not legacy_hash.startswith("$argon2")
        assert verify_password("legacy-password", legacy_hash) is True
        assert verify_password("wrong-password", legacy_hash) is False
        assert needs_rehash(legacy_hash) is True

    def test_login_upgrades_legacy_hash_to_argon2(self, client, db_factory):
        legacy_hash = _legacy_context.hash("legacy-login-password")
        with db_factory() as db:
            role = db.query(Role).filter(Role.code == "coordinador_operativo").first()
            user = User(
                email="legacy@ecoe.cl",
                full_name="Legacy User",
                hashed_password=legacy_hash,
                role_id=role.id,
                is_active=True,
            )
            db.add(user)
            db.commit()
            user_id = user.id

        response = client.post("/api/auth/login", json={
            "email": "legacy@ecoe.cl",
            "password": "legacy-login-password",
        })
        assert response.status_code == 200, response.text

        with db_factory() as db:
            refreshed = db.get(User, user_id)
            assert refreshed.hashed_password.startswith("$argon2")
            assert refreshed.hashed_password != legacy_hash

        # The upgraded hash must still authenticate with the same password.
        second_login = client.post("/api/auth/login", json={
            "email": "legacy@ecoe.cl",
            "password": "legacy-login-password",
        })
        assert second_login.status_code == 200
