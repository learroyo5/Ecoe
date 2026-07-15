"""Station kiosk sessions: issue/authenticate the shared per-station device.

The kiosk model inverts the student flow: instead of each student logging in
on a rotating shared tablet, the device holds one station-scoped token and
the person answering is always whoever the evaluator confirmed in that
station's active check-in. The raw token is returned once at issue time and
only its SHA-256 lands in the database (same pattern as user invitations).
"""

import hashlib
import secrets
from datetime import timedelta

from fastapi import Header, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models.entities import Station, StationKioskSession
from app.utils.clock import utcnow_naive

KIOSK_TOKEN_HEADER = "X-Kiosk-Token"


def hash_kiosk_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def issue_kiosk_token(db: Session, station: Station, *, issued_by_email: str) -> dict:
    """Create a fresh kiosk session for the station, revoking previous ones.

    One active device per station keeps the operational story simple: if a
    tablet is replaced or a token leaks, re-issuing invalidates the old one.
    """
    now = utcnow_naive()
    for previous in db.scalars(
        select(StationKioskSession).where(
            StationKioskSession.station_id == station.id,
            StationKioskSession.revoked_at.is_(None),
        )
    ).all():
        previous.revoked_at = now
        db.add(previous)

    raw_token = secrets.token_urlsafe(32)
    session = StationKioskSession(
        ecoe_event_id=station.ecoe_event_id,
        station_id=station.id,
        token_hash=hash_kiosk_token(raw_token),
        issued_by_email=issued_by_email,
        expires_at=now + timedelta(hours=get_settings().kiosk_token_expire_hours),
    )
    db.add(session)
    db.flush()
    return {
        "kiosk_session_id": session.id,
        "station_id": station.id,
        "token": raw_token,
        "kiosk_path": f"/kiosk?token={raw_token}",
        "expires_at": session.expires_at.isoformat(),
    }


def authenticate_kiosk_token(db: Session, token: str | None) -> StationKioskSession:
    if not token:
        raise HTTPException(status_code=401, detail="Falta el token del kiosco")
    session = db.scalar(
        select(StationKioskSession).where(
            StationKioskSession.token_hash == hash_kiosk_token(token)
        )
    )
    now = utcnow_naive()
    if not session or session.revoked_at is not None or session.expires_at <= now:
        raise HTTPException(
            status_code=401,
            detail="El token del kiosco no es valido o expiro; solicita uno nuevo a coordinacion",
        )
    return session


def kiosk_token_header(
    x_kiosk_token: str | None = Header(default=None, alias=KIOSK_TOKEN_HEADER),
) -> str | None:
    return x_kiosk_token
