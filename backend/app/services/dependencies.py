import time
from collections import defaultdict

from fastapi import Cookie, Depends, HTTPException, Request, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.security import decode_token
from app.db.session import get_db
from app.models.entities import User

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login", auto_error=False)

# In-memory rate limiter for auth endpoints
_login_attempts: dict[str, list[float]] = defaultdict(list)
_LOGIN_MAX_ATTEMPTS = 10
_LOGIN_WINDOW_SECONDS = 300  # 5 minutes


def rate_limit_login(request: Request) -> None:
    client_ip = request.client.host if request.client else "unknown"
    now = time.time()
    window_start = now - _LOGIN_WINDOW_SECONDS
    _login_attempts[client_ip] = [
        ts for ts in _login_attempts[client_ip] if ts > window_start
    ]
    if len(_login_attempts[client_ip]) >= _LOGIN_MAX_ATTEMPTS:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Demasiados intentos de inicio de sesion. Intenta de nuevo en unos minutos.",
        )
    _login_attempts[client_ip].append(now)


def authenticate_session_token(db: Session, session_token: str | None) -> User:
    if not session_token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Sesion no autenticada",
        )
    claims = decode_token(session_token)
    if not claims or not claims.get("sub"):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token invalido")
    user = db.scalar(select(User).where(User.email == claims["sub"]))
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Usuario no existe")
    if not user.is_active:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Usuario inactivo")
    if int(claims.get("ver", 0)) != int(user.token_version or 0):
        # Token issued before a deactivation/password change: revoked.
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Sesion revocada")
    return user


def get_current_user(
    token: str | None = Depends(oauth2_scheme),
    db: Session = Depends(get_db),
    auth_cookie: str | None = Cookie(default=None, alias=get_settings().auth_cookie_name),
) -> User:
    return authenticate_session_token(db, token or auth_cookie)


def require_roles(*roles: str):
    """Coarse role gate.

    Accepts the user's global role, or any per-event role granted via
    StaffAssignment / ECOEPermission (a user can be evaluador in one ECOE
    and coeditor in another). Fine-grained, per-event authorization is
    always enforced afterwards by ensure_event_access.
    """

    def dependency(
        user: User = Depends(get_current_user),
        db: Session = Depends(get_db),
    ) -> User:
        if user.role.code in roles:
            return user
        from app.models.entities import ECOEPermission, StaffAssignment

        has_assignment = db.scalar(
            select(StaffAssignment.id).where(
                StaffAssignment.email == user.email.strip().lower(),
                StaffAssignment.role_code.in_(roles),
            ).limit(1)
        )
        if has_assignment:
            return user
        has_permission = db.scalar(
            select(ECOEPermission.id).where(
                ECOEPermission.user_id == user.id,
                ECOEPermission.role_code.in_(roles),
            ).limit(1)
        )
        if has_permission:
            return user
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="No tiene permisos para esta accion",
        )

    return dependency
