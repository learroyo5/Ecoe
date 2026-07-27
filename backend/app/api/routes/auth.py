"""Authentication routes."""

from fastapi import APIRouter, Depends, Request, Response
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.schemas.common import LoginRequest, Token
from app.core.config import get_settings
from app.services.auth import issue_login_token
from app.services.dependencies import get_current_user
from app.services.rate_limit import clear_login_account_rate_limit, enforce_login_rate_limit

router = APIRouter()
settings = get_settings()


@router.post("/auth/login", response_model=Token)
def login(
    payload: LoginRequest,
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
):
    enforce_login_rate_limit(db, request, payload.email)
    auth_payload, auth_token = issue_login_token(db, payload.email, payload.password)
    clear_login_account_rate_limit(db, payload.email)
    forwarded_proto = request.headers.get("x-forwarded-proto", request.url.scheme)
    secure_cookie = forwarded_proto == "https"
    response.set_cookie(
        key=settings.auth_cookie_name,
        value=auth_token,
        httponly=True,
        secure=secure_cookie,
        samesite=settings.auth_cookie_samesite,
        max_age=settings.access_token_expire_minutes * 60,
        path="/",
    )
    return auth_payload


@router.post("/auth/logout")
def logout(response: Response):
    response.delete_cookie(key=settings.auth_cookie_name, path="/")
    return {"logged_out": True}


@router.get("/auth/me")
def me(user=Depends(get_current_user)):
    return {
        "id": user.id,
        "email": user.email,
        "full_name": user.full_name,
        "role": user.role.code,
    }
