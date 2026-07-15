"""User management routes — admin only."""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session, joinedload

from app.db.session import get_db
from app.models.entities import AuditLog, Role, User
from app.models.enums import RoleCode
from app.schemas.common import UserCreate, UserRead, UserUpdate
from app.services.dependencies import require_global_roles
from app.core.security import get_password_hash

router = APIRouter()


@router.get("/users", response_model=list[UserRead])
def list_users(
    db: Session = Depends(get_db),
    user: User = Depends(require_global_roles(RoleCode.admin_global.value)),
):
    return db.scalars(
        select(User).options(joinedload(User.role)).order_by(User.full_name.asc(), User.id.asc())
    ).unique().all()


@router.post("/users", response_model=UserRead)
def create_user(
    payload: UserCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_global_roles(RoleCode.admin_global.value)),
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
        account_status="active",
    )
    db.add(new_user)
    db.flush()
    db.add(AuditLog(
        user_email=current_user.email,
        action="create_user",
        target_type="User",
        target_id=str(new_user.id),
        payload={"role_code": payload.role_code},
    ))
    db.commit()
    db.refresh(new_user)
    return new_user


@router.patch("/users/{user_id}", response_model=UserRead)
def update_user(
    user_id: int,
    payload: UserUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_global_roles(RoleCode.admin_global.value)),
):
    target = db.get(User, user_id)
    if not target:
        raise HTTPException(status_code=404, detail="Usuario no encontrado")

    revoke_sessions = False
    if target.id == current_user.id and (
        payload.is_active is False
        or (payload.role_code is not None and payload.role_code != RoleCode.admin_global.value)
    ):
        raise HTTPException(
            status_code=400,
            detail="El administrador global no puede desactivar ni quitar su propio rol",
        )
    removes_global_authority = (
        target.role.code == RoleCode.admin_global.value
        and (
            payload.is_active is False
            or (payload.role_code is not None and payload.role_code != RoleCode.admin_global.value)
        )
    )
    if removes_global_authority:
        active_global_admins = db.scalar(
            select(func.count())
            .select_from(User)
            .join(Role, Role.id == User.role_id)
            .where(
                Role.code == RoleCode.admin_global.value,
                User.is_active.is_(True),
            )
        ) or 0
        if active_global_admins <= 1:
            raise HTTPException(
                status_code=400,
                detail="Debe permanecer al menos un administrador global activo",
            )
    if payload.full_name is not None:
        target.full_name = payload.full_name
    if payload.role_code is not None:
        role = db.scalar(select(Role).where(Role.code == payload.role_code))
        if not role:
            raise HTTPException(status_code=400, detail=f"Rol no válido: {payload.role_code}")
        if role.id != target.role_id:
            revoke_sessions = True
        target.role_id = role.id
    if payload.password:
        target.hashed_password = get_password_hash(payload.password)
        revoke_sessions = True
    if payload.is_active is not None:
        if target.is_active and not payload.is_active:
            revoke_sessions = True
        target.is_active = payload.is_active
        target.account_status = "active" if payload.is_active else "suspended"
    if revoke_sessions:
        # Invalidate every JWT issued before this change.
        target.token_version = (target.token_version or 0) + 1

    db.add(target)
    db.add(AuditLog(
        user_email=current_user.email,
        action="update_user",
        target_type="User",
        target_id=str(target.id),
        payload={
            "role_changed": payload.role_code is not None,
            "password_changed": bool(payload.password),
            "active_changed": payload.is_active is not None,
        },
    ))
    db.commit()
    db.refresh(target)
    return target
