from collections.abc import Callable
from datetime import UTC, datetime

from fastapi import Depends, Header, HTTPException, status
from sqlalchemy.orm import Session
from starlette.websockets import WebSocket

from app.config import Settings, get_settings
from app.database import get_db
from app.models.auth import AuthSession, User
from app.security import decode_token


def _validate_access_token(authorization: str | None, settings: Settings) -> dict:
    if not authorization:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Authorization header required")
    scheme, _, token = authorization.partition(" ")
    if scheme.lower() != "bearer" or not token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid authorization header")

    payload = decode_token(token, settings)
    if payload.get("type") != "access":
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Access token required")
    return payload


def get_current_auth_payload(
    authorization: str | None = Header(default=None),
    settings: Settings = Depends(get_settings),
    db: Session = Depends(get_db),
) -> dict:
    payload = _validate_access_token(authorization, settings)
    return _validate_active_session(payload=payload, db=db)


def require_role(allowed_roles: list[str]) -> Callable:
    def _check_role(payload: dict = Depends(get_current_auth_payload)) -> dict:
        token_roles = payload.get("roles", [])
        if not any(role in token_roles for role in allowed_roles):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Forbidden")
        return payload

    return _check_role


async def authorize_websocket(
    websocket: WebSocket,
    *,
    allowed_roles: list[str],
    settings: Settings,
    db: Session,
) -> dict | None:
    authorization = websocket.headers.get("authorization")
    try:
        payload = _validate_access_token(authorization, settings)
        payload = _validate_active_session(payload=payload, db=db)
        token_roles = payload.get("roles", [])
        if not any(role in token_roles for role in allowed_roles):
            await websocket.close(code=1008, reason="Forbidden")
            return None
        return payload
    except HTTPException:
        await websocket.close(code=1008, reason="Unauthorized")
        return None


def _validate_active_session(*, payload: dict, db: Session) -> dict:
    user_id = str(payload.get("sub", "")).strip()
    session_id = str(payload.get("sid", "")).strip()
    if not user_id or not session_id:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token session")

    session = db.get(AuthSession, session_id)
    if session is None or session.user_id != user_id:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Session revoked")
    if session.revoked_at is not None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Session revoked")
    if _as_utc(session.expires_at) <= datetime.now(UTC):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Session expired")

    user = db.get(User, user_id)
    if user is None or not user.is_active:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User inactive")
    return payload


def _as_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)
