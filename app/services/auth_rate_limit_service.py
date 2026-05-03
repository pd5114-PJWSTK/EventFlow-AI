from __future__ import annotations

from collections import deque
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from threading import Lock

from app.config import Settings


@dataclass(frozen=True)
class LoginThrottleState:
    allowed: bool
    retry_after_seconds: int = 0


@dataclass
class _Bucket:
    attempts: deque[datetime]
    locked_until: datetime | None = None


class LoginThrottleService:
    def __init__(self) -> None:
        self._buckets: dict[str, _Bucket] = {}
        self._lock = Lock()

    def check_allowed(self, *, key: str, settings: Settings) -> LoginThrottleState:
        now = datetime.now(UTC)
        window = timedelta(seconds=settings.auth_login_rate_limit_window_seconds)
        with self._lock:
            bucket = self._buckets.get(key)
            if bucket is None:
                return LoginThrottleState(allowed=True)
            self._prune(bucket=bucket, now=now, window=window)
            if bucket.locked_until is not None and bucket.locked_until > now:
                retry_after = int((bucket.locked_until - now).total_seconds())
                return LoginThrottleState(allowed=False, retry_after_seconds=max(retry_after, 1))
            if bucket.locked_until is not None and bucket.locked_until <= now:
                bucket.locked_until = None
            return LoginThrottleState(allowed=True)

    def register_failure(self, *, key: str, settings: Settings) -> None:
        now = datetime.now(UTC)
        window = timedelta(seconds=settings.auth_login_rate_limit_window_seconds)
        with self._lock:
            bucket = self._buckets.get(key)
            if bucket is None:
                bucket = _Bucket(attempts=deque())
                self._buckets[key] = bucket
            self._prune(bucket=bucket, now=now, window=window)
            bucket.attempts.append(now)
            if len(bucket.attempts) >= settings.auth_login_rate_limit_max_attempts:
                bucket.locked_until = now + timedelta(seconds=settings.auth_login_lockout_seconds)

    def register_success(self, *, key: str) -> None:
        with self._lock:
            if key in self._buckets:
                del self._buckets[key]

    def clear(self) -> None:
        with self._lock:
            self._buckets.clear()

    @staticmethod
    def _prune(*, bucket: _Bucket, now: datetime, window: timedelta) -> None:
        cutoff = now - window
        while bucket.attempts and bucket.attempts[0] < cutoff:
            bucket.attempts.popleft()


login_throttle_service = LoginThrottleService()
