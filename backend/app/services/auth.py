from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.security import create_access_token, verify_password
from app.models.entities import User


def login_user(db: Session, email: str, password: str) -> dict:
    user = db.scalar(select(User).where(User.email == email))
    if not user or not verify_password(password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Credenciales invalidas",
        )
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
    token = create_access_token(payload["user"]["email"])
    return payload, token
