from collections.abc import Callable

from fastapi import Depends, Header, HTTPException, status

from app.config import Settings, get_settings
from app.security import decode_token


def require_role(allowed_roles: list[str]) -> Callable:
    def _check_role(
        authorization: str = Header(...),
        settings: Settings = Depends(get_settings),
    ) -> dict:
        scheme, _, token = authorization.partition(" ")
        if scheme.lower() != "bearer" or not token:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid authorization header")

        payload = decode_token(token, settings)
        if payload.get("type") != "access":
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Access token required")

        token_roles = payload.get("roles", [])
        if not any(role in token_roles for role in allowed_roles):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Forbidden")

        return payload

    return _check_role
