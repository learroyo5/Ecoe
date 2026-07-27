from datetime import datetime, timedelta, timezone

from jose import JWTError, jwt
from passlib.context import CryptContext
from pwdlib import PasswordHash
from pwdlib.hashers.argon2 import Argon2Hasher

from app.core.config import get_settings

# All new hashes use argon2 via pwdlib (passlib has been unmaintained since
# 2020). passlib is kept only to verify pbkdf2_sha256 hashes created before
# this migration — accounts get transparently upgraded to argon2 the next
# time they log in successfully (see needs_rehash / services/auth.py).
_password_hash = PasswordHash([Argon2Hasher()])
_legacy_pwd_context = CryptContext(schemes=["pbkdf2_sha256"], deprecated="auto")


def verify_password(plain_password: str, hashed_password: str) -> bool:
    if hashed_password.startswith("$argon2"):
        return _password_hash.verify(plain_password, hashed_password)
    return _legacy_pwd_context.verify(plain_password, hashed_password)


def needs_rehash(hashed_password: str) -> bool:
    """True for legacy pbkdf2_sha256 hashes that should be upgraded to argon2."""
    return not hashed_password.startswith("$argon2")


def get_password_hash(password: str) -> str:
    return _password_hash.hash(password)


def create_access_token(subject: str, *, role: str = "", token_version: int = 0) -> str:
    settings = get_settings()
    expire = datetime.now(timezone.utc) + timedelta(
        minutes=settings.access_token_expire_minutes
    )
    payload = {
        "sub": subject,
        "exp": expire,
        "iss": settings.jwt_issuer,
        "aud": settings.jwt_audience,
        # role: consumido por el middleware del frontend para gating de rutas.
        "role": role,
        # ver: invalida el token cuando el usuario es desactivado o cambia clave.
        "ver": token_version,
    }
    return jwt.encode(payload, settings.secret_key, algorithm="HS256")


def decode_token(token: str) -> dict | None:
    """Return the verified claims dict, or None if the token is invalid."""
    settings = get_settings()
    try:
        return jwt.decode(
            token,
            settings.secret_key,
            algorithms=["HS256"],
            issuer=settings.jwt_issuer,
            audience=settings.jwt_audience,
        )
    except JWTError:
        return None
