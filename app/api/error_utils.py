from __future__ import annotations

from fastapi import HTTPException


def http_error(*, status_code: int, error_code: str, message: str) -> HTTPException:
    return HTTPException(
        status_code=status_code,
        detail=message,
        headers={"X-Error-Code": error_code},
    )
