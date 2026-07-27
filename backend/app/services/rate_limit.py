from datetime import timedelta

from fastapi import HTTPException, Request, status
from sqlalchemy import delete, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.entities import AuthRateLimit
from app.utils.clock import utcnow_naive


LOGIN_IP_MAX_ATTEMPTS = 10
LOGIN_ACCOUNT_MAX_ATTEMPTS = 5
LOGIN_GLOBAL_MAX_ATTEMPTS = 200
LOGIN_WINDOW_SECONDS = 300


def _normalized_login_email(email: str | None) -> str:
    return (email or "unknown").strip().lower()


def _login_buckets(request: Request, email: str | None) -> list[tuple[str, int]]:
    client_ip = request.client.host if request.client else "unknown"
    account = _normalized_login_email(email)
    return [
        (f"ip:{client_ip}", LOGIN_IP_MAX_ATTEMPTS),
        (f"account:{account}", LOGIN_ACCOUNT_MAX_ATTEMPTS),
        ("global", LOGIN_GLOBAL_MAX_ATTEMPTS),
    ]


def _rate_limit_error() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_429_TOO_MANY_REQUESTS,
        detail="Demasiados intentos de inicio de sesión. Intenta de nuevo en unos minutos.",
    )


def _prune_expired_login_buckets(db: Session, window_start_cutoff) -> None:
    db.execute(
        delete(AuthRateLimit).where(AuthRateLimit.window_start < window_start_cutoff)
    )


def _apply_login_rate_limit_once(
    db: Session,
    request: Request,
    email: str | None,
) -> None:
    now = utcnow_naive()
    window_start_cutoff = now - timedelta(seconds=LOGIN_WINDOW_SECONDS)
    buckets = _login_buckets(request, email)
    bucket_keys = [key for key, _max_attempts in buckets]

    _prune_expired_login_buckets(db, window_start_cutoff)
    rows = {
        row.bucket_key: row
        for row in db.scalars(
            select(AuthRateLimit)
            .where(AuthRateLimit.bucket_key.in_(bucket_keys))
            .with_for_update()
        )
    }

    for key, max_attempts in buckets:
        row = rows.get(key)
        if row and row.attempts >= max_attempts:
            db.rollback()
            raise _rate_limit_error()

    for key, _max_attempts in buckets:
        row = rows.get(key)
        if row is None:
            db.add(
                AuthRateLimit(
                    bucket_key=key,
                    attempts=1,
                    window_start=now,
                    created_at=now,
                    updated_at=now,
                )
            )
        else:
            row.attempts += 1
            row.updated_at = now
            db.add(row)
    db.commit()


def enforce_login_rate_limit(
    db: Session,
    request: Request,
    email: str | None,
) -> None:
    """Persist login throttling so restarts do not reset abuse counters."""
    for attempt in range(2):
        try:
            _apply_login_rate_limit_once(db, request, email)
            return
        except IntegrityError:
            db.rollback()
            if attempt == 1:
                raise


def clear_login_account_rate_limit(db: Session, email: str | None = None) -> None:
    db.execute(
        delete(AuthRateLimit).where(
            AuthRateLimit.bucket_key == f"account:{_normalized_login_email(email)}"
        )
    )
    db.commit()
