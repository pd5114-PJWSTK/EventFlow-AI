from datetime import timedelta

from fastapi import APIRouter, Depends, Header, HTTPException, status

from app.config import Settings, get_settings
from app.schemas.auth import LoginRequest, TokenResponse
from app.security import create_token, decode_token
from app.services.auth_service import User, authenticate_user


router = APIRouter(prefix="/auth", tags=["auth"])


def _create_token_pair(user: User, settings: Settings) -> TokenResponse:
    access_token = create_token(
        subject=user.username,
        token_type="access",
        expires_delta=timedelta(minutes=settings.access_token_expire_minutes),
        settings=settings,
        extra_claims={"roles": user.roles},
    )
    refresh_token = create_token(
        subject=user.username,
        token_type="refresh",
        expires_delta=timedelta(minutes=settings.refresh_token_expire_minutes),
        settings=settings,
    )
    return TokenResponse(access_token=access_token, refresh_token=refresh_token, token_type="bearer")


@router.post("/login", response_model=TokenResponse)
def login(payload: LoginRequest, settings: Settings = Depends(get_settings)) -> TokenResponse:
    user = authenticate_user(payload.username, payload.password, settings)
    if user is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")
    return _create_token_pair(user, settings)


@router.post("/refresh", response_model=TokenResponse)
def refresh(authorization: str = Header(...), settings: Settings = Depends(get_settings)) -> TokenResponse:
    scheme, _, token = authorization.partition(" ")
    if scheme.lower() != "bearer" or not token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid authorization header")

    payload = decode_token(token, settings)
    if payload.get("type") != "refresh":
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Refresh token required")

    username = payload.get("sub")
    if not username:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token subject")

    user = authenticate_user(username, settings.demo_admin_password, settings)
    if user is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Unknown user")

    return _create_token_pair(user, settings)
