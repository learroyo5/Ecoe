"""User management routes — admin only."""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.entities import Role, User
from app.models.enums import RoleCode
from app.schemas.common import UserCreate, UserRead, UserUpdate
from app.services.dependencies import get_current_user, require_roles
from app.core.security import get_password_hash

router = APIRouter()


@router.get("/users", response_model=list[UserRead])
def list_users(
    db: Session = Depends(get_db),
    user: User = Depends(require_roles("admin_ecoe")),
):
    return db.scalars(
        select(User).order_by(User.full_name.asc(), User.id.asc())
    ).all()


@router.post("/users", response_model=UserRead)
def create_user(
    payload: UserCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("admin_ecoe")),
):
    existing = db.scalar(select(User).where(User.email == payload.email))
    if existing:
        raise HTTPException(status_code=400, detail="Ya existe un usuario con ese correo")

    role = db.scalar(select(Role).where(Role.code == payload.role_code))
    if not role:
        raise HTTPException(status_code=400, detail=f"Rol no válido: {payload.role_code}")

    new_user = User(
        email=payload.email,
        full_name=payload.full_name,
        hashed_password=get_password_hash(payload.password),
        role_id=role.id,
        is_active=True,
    )
    db.add(new_user)
    db.commit()
    db.refresh(new_user)
    return new_user


@router.patch("/users/{user_id}", response_model=UserRead)
def update_user(
    user_id: int,
    payload: UserUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("admin_ecoe")),
):
    target = db.get(User, user_id)
    if not target:
        raise HTTPException(status_code=404, detail="Usuario no encontrado")

    if payload.full_name is not None:
        target.full_name = payload.full_name
    if payload.role_code is not None:
        role = db.scalar(select(Role).where(Role.code == payload.role_code))
        if not role:
            raise HTTPException(status_code=400, detail=f"Rol no válido: {payload.role_code}")
        target.role_id = role.id
    if payload.password:
        target.hashed_password = get_password_hash(payload.password)
    if payload.is_active is not None:
        target.is_active = payload.is_active

    db.add(target)
    db.commit()
    db.refresh(target)
    return target
