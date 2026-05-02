from __future__ import annotations

from pydantic import BaseModel, Field


class AdminUserCreateRequest(BaseModel):
    username: str = Field(min_length=3, max_length=120)
    password: str = Field(min_length=12, max_length=256)
    roles: list[str] = Field(default_factory=list)
    is_superadmin: bool = False


class AdminUserUpdateRequest(BaseModel):
    roles: list[str] | None = None
    is_active: bool | None = None
    is_superadmin: bool | None = None


class AdminUserResetPasswordRequest(BaseModel):
    password: str = Field(min_length=12, max_length=256)


class AdminUserRead(BaseModel):
    user_id: str
    username: str
    roles: list[str] = Field(default_factory=list)
    is_active: bool
    is_superadmin: bool

