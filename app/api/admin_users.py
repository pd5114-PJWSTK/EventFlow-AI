from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.middleware.rbac import require_role
from app.models.auth import User
from app.schemas.admin_users import (
    AdminUserCreateRequest,
    AdminUserRead,
    AdminUserResetPasswordRequest,
    AdminUserUpdateRequest,
)
from app.services.auth_service import (
    create_user,
    list_user_roles,
    reset_user_password,
    update_user_roles,
)


router = APIRouter(
    prefix="/admin/users",
    tags=["admin-users"],
    dependencies=[Depends(require_role(["admin"]))],
)


def _to_read(user: User) -> AdminUserRead:
    return AdminUserRead(
        user_id=user.user_id,
        username=user.username,
        roles=list_user_roles(user),
        is_active=user.is_active,
        is_superadmin=user.is_superadmin,
    )


@router.post("", response_model=AdminUserRead, status_code=status.HTTP_201_CREATED)
def create_user_endpoint(payload: AdminUserCreateRequest, db: Session = Depends(get_db)) -> AdminUserRead:
    roles = payload.roles or ["manager"]
    try:
        user = create_user(
            db,
            username=payload.username,
            password=payload.password,
            role_names=roles,
            is_superadmin=payload.is_superadmin,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    return _to_read(user)


@router.patch("/{user_id}", response_model=AdminUserRead)
def update_user_endpoint(
    user_id: str,
    payload: AdminUserUpdateRequest,
    db: Session = Depends(get_db),
) -> AdminUserRead:
    user = db.get(User, user_id)
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    if payload.roles is not None:
        try:
            user = update_user_roles(db, user=user, role_names=payload.roles)
        except ValueError as exc:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    if payload.is_active is not None:
        user.is_active = payload.is_active
    if payload.is_superadmin is not None:
        user.is_superadmin = payload.is_superadmin
    db.add(user)
    db.commit()
    db.refresh(user)
    return _to_read(user)


@router.post("/{user_id}/reset-password", response_model=AdminUserRead)
def reset_password_endpoint(
    user_id: str,
    payload: AdminUserResetPasswordRequest,
    db: Session = Depends(get_db),
) -> AdminUserRead:
    user = db.get(User, user_id)
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    try:
        user = reset_user_password(db, user=user, password=payload.password)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    return _to_read(user)

