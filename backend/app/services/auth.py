import logging

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.security import create_access_token, get_password_hash, needs_rehash, verify_password
from app.models.entities import User

logger = logging.getLogger("ecoe.auth")


def login_user(db: Session, email: str, password: str) -> dict:
    user = db.scalar(select(User).where(User.email == email))
    if not user or not verify_password(password, user.hashed_password):
        logger.warning("login_failed email=%s", email)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Credenciales invalidas",
        )
    if not user.is_active:
        logger.warning("login_inactive_account email=%s", email)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="La cuenta se encuentra inactiva",
        )
    if needs_rehash(user.hashed_password):
        # Transparent migration off the legacy passlib hash: no forced
        # password reset needed for accounts created before the argon2 move.
        user.hashed_password = get_password_hash(password)
        db.add(user)
        db.commit()
    logger.info("login_ok email=%s role=%s", user.email, user.role.code)
    return {
        "access_token": None,
        "token_type": "bearer",
        "user": {
            "id": user.id,
            "email": user.email,
            "full_name": user.full_name,
            "role": user.role.code,
        },
    }


def issue_login_token(db: Session, email: str, password: str) -> tuple[dict, str]:
    payload = login_user(db, email, password)
    user = db.scalar(select(User).where(User.email == payload["user"]["email"]))
    token = create_access_token(
        user.email,
        role=str(user.role.code),
        token_version=user.token_version,
    )
    return payload, token
