from collections.abc import Callable

from fastapi import Depends, Header, HTTPException, status
from starlette.websockets import WebSocket

from app.config import Settings, get_settings
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
) -> dict:
    return _validate_access_token(authorization, settings)


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
) -> dict | None:
    authorization = websocket.headers.get("authorization")
    try:
        payload = _validate_access_token(authorization, settings)
        token_roles = payload.get("roles", [])
        if not any(role in token_roles for role in allowed_roles):
            await websocket.close(code=1008, reason="Forbidden")
            return None
        return payload
    except HTTPException:
        await websocket.close(code=1008, reason="Unauthorized")
        return None
