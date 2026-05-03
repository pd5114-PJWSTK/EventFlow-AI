from __future__ import annotations

from fastapi import APIRouter, Depends, Header, HTTPException, Request, status
from sqlalchemy.orm import Session

from app.config import Settings, get_settings
from app.database import get_db
from app.middleware.rbac import get_current_auth_payload
from app.schemas.auth import LoginRequest, TokenResponse, UserMeResponse
from app.services.auth_service import (
    authenticate_user,
    create_session_tokens,
    get_user_by_id,
    revoke_all_user_sessions,
    revoke_refresh_session,
    rotate_refresh_session,
)
from app.services.auth_rate_limit_service import (
    LOGIN_IP_SCOPE,
    LOGIN_USER_SCOPE,
    REFRESH_IP_SCOPE,
    login_throttle_service,
)


router = APIRouter(prefix="/auth", tags=["auth"])


def _parse_bearer(authorization: str | None) -> str:
    if not authorization:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Authorization header required")
    scheme, _, token = authorization.partition(" ")
    if scheme.lower() != "bearer" or not token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid authorization header")
    return token


def _token_response(tokens) -> TokenResponse:
    return TokenResponse(
        access_token=tokens.access_token,
        refresh_token=tokens.refresh_token,
        token_type="bearer",
    )


@router.post("/login", response_model=TokenResponse)
def login(
    payload: LoginRequest,
    request: Request,
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> TokenResponse:
    client_ip = request.client.host if request.client else "unknown"
    username_key = payload.username.strip().lower()
    user_throttle_state = login_throttle_service.check_allowed(
        scope=LOGIN_USER_SCOPE,
        key=username_key,
        settings=settings,
    )
    ip_throttle_state = login_throttle_service.check_allowed(
        scope=LOGIN_IP_SCOPE,
        key=client_ip,
        settings=settings,
    )
    if not user_throttle_state.allowed or not ip_throttle_state.allowed:
        retry_after = max(user_throttle_state.retry_after_seconds, ip_throttle_state.retry_after_seconds)
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many failed login attempts. Try again later.",
            headers={"Retry-After": str(retry_after)},
        )

    user = authenticate_user(
        db,
        username=payload.username,
        password=payload.password,
        settings=settings,
    )
    if user is None:
        login_throttle_service.register_failure(scope=LOGIN_USER_SCOPE, key=username_key, settings=settings)
        login_throttle_service.register_failure(scope=LOGIN_IP_SCOPE, key=client_ip, settings=settings)
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")
    login_throttle_service.register_success(scope=LOGIN_USER_SCOPE, key=username_key)
    tokens = create_session_tokens(
        db,
        user=user,
        settings=settings,
        user_agent=request.headers.get("user-agent"),
        ip_address=client_ip if request.client else None,
    )
    return _token_response(tokens)


@router.post("/refresh", response_model=TokenResponse)
def refresh(
    request: Request,
    authorization: str | None = Header(default=None),
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> TokenResponse:
    client_ip = request.client.host if request.client else "unknown"
    refresh_throttle_state = login_throttle_service.check_allowed(
        scope=REFRESH_IP_SCOPE,
        key=client_ip,
        settings=settings,
    )
    if not refresh_throttle_state.allowed:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many failed refresh attempts. Try again later.",
            headers={"Retry-After": str(refresh_throttle_state.retry_after_seconds)},
        )
    refresh_token = _parse_bearer(authorization)
    tokens = rotate_refresh_session(
        db,
        refresh_token=refresh_token,
        settings=settings,
        user_agent=request.headers.get("user-agent"),
        ip_address=client_ip if request.client else None,
    )
    if tokens is None:
        login_throttle_service.register_failure(scope=REFRESH_IP_SCOPE, key=client_ip, settings=settings)
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid refresh token")
    login_throttle_service.register_success(scope=REFRESH_IP_SCOPE, key=client_ip)
    return _token_response(tokens)


@router.get("/me", response_model=UserMeResponse)
def me(
    payload: dict = Depends(get_current_auth_payload),
) -> UserMeResponse:
    return UserMeResponse(
        user_id=str(payload.get("sub", "")),
        username=str(payload.get("username", "")),
        roles=list(payload.get("roles", [])),
        is_superadmin=bool(payload.get("is_superadmin", False)),
    )


@router.post("/logout")
def logout(
    authorization: str | None = Header(default=None),
    db: Session = Depends(get_db),
) -> dict[str, str]:
    refresh_token = _parse_bearer(authorization)
    revoke_refresh_session(db, refresh_token=refresh_token)
    return {"status": "ok"}


@router.post("/logout-all")
def logout_all(
    payload: dict = Depends(get_current_auth_payload),
    db: Session = Depends(get_db),
) -> dict[str, str]:
    user_id = str(payload.get("sub", ""))
    user = get_user_by_id(db, user_id)
    if user is None:
        return {"status": "ok"}
    revoke_all_user_sessions(db, user_id=user.user_id)
    return {"status": "ok"}

