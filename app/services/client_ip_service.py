from __future__ import annotations

from fastapi import Request

from app.config import Settings


def resolve_client_ip(*, request: Request, settings: Settings) -> str:
    direct_ip = request.client.host if request.client else "unknown"
    trusted_proxies = _parse_trusted_proxy_ips(settings.auth_trusted_proxy_ips)
    if direct_ip not in trusted_proxies:
        return direct_ip

    forwarded_for = request.headers.get("x-forwarded-for", "")
    if forwarded_for:
        for candidate in forwarded_for.split(","):
            resolved_ip = candidate.strip()
            if resolved_ip:
                return resolved_ip

    real_ip = (request.headers.get("x-real-ip") or "").strip()
    if real_ip:
        return real_ip
    return direct_ip


def _parse_trusted_proxy_ips(raw_value: str) -> set[str]:
    return {value.strip() for value in raw_value.split(",") if value.strip()}

