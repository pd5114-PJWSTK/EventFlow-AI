from __future__ import annotations

from datetime import UTC, datetime


def to_utc(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


def utc_now() -> datetime:
    return datetime.now(UTC)


def minutes_between_utc(later: datetime, earlier: datetime) -> int:
    later_utc = to_utc(later)
    earlier_utc = to_utc(earlier)
    if later_utc is None or earlier_utc is None:
        return 0
    return int((later_utc - earlier_utc).total_seconds() // 60)
