from __future__ import annotations

from collections import deque
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from threading import Lock

from redis import Redis
from redis.exceptions import RedisError

from app.config import Settings, get_settings


LOGIN_USER_SCOPE = "login_user"
LOGIN_IP_SCOPE = "login_ip"
REFRESH_IP_SCOPE = "refresh_ip"


@dataclass(frozen=True)
class LoginThrottleState:
    allowed: bool
    retry_after_seconds: int = 0


@dataclass
class _Bucket:
    attempts: deque[datetime]
    locked_until: datetime | None = None


@dataclass(frozen=True)
class _ThrottlePolicy:
    window_seconds: int
    max_attempts: int
    lockout_seconds: int


class LoginThrottleService:
    def __init__(self) -> None:
        self._buckets: dict[str, _Bucket] = {}
        self._lock = Lock()
        self._redis_clients: dict[str, Redis] = {}
        self._redis_lock = Lock()

    def check_allowed(self, *, scope: str, key: str, settings: Settings) -> LoginThrottleState:
        redis_state = self._check_allowed_redis(scope=scope, key=key, settings=settings)
        if redis_state is not None:
            return redis_state
        if self._is_non_development(settings):
            return LoginThrottleState(allowed=False, retry_after_seconds=1)
        return self._check_allowed_memory(scope=scope, key=key, settings=settings)

    def register_failure(self, *, scope: str, key: str, settings: Settings) -> None:
        if self._register_failure_redis(scope=scope, key=key, settings=settings):
            return
        if self._is_non_development(settings):
            return
        self._register_failure_memory(scope=scope, key=key, settings=settings)

    def register_success(self, *, scope: str, key: str) -> None:
        if self._register_success_redis(scope=scope, key=key):
            return
        with self._lock:
            self._buckets.pop(self._memory_bucket_key(scope=scope, key=key), None)

    def clear(self) -> None:
        with self._lock:
            self._buckets.clear()
        with self._redis_lock:
            clients = list(self._redis_clients.values())
        try:
            settings = get_settings()
            redis = self._get_redis_client(settings)
            if redis is not None and redis not in clients:
                clients.append(redis)
        except Exception:
            pass
        for client in clients:
            try:
                cursor = 0
                while True:
                    cursor, keys = client.scan(cursor=cursor, match="auth_throttle:*", count=200)
                    if keys:
                        client.delete(*keys)
                    if cursor == 0:
                        break
            except RedisError:
                continue

    def _check_allowed_redis(self, *, scope: str, key: str, settings: Settings) -> LoginThrottleState | None:
        redis = self._get_redis_client(settings)
        if redis is None:
            return None
        _, lock_key = self._redis_keys(scope=scope, key=key)
        try:
            lock_ttl = int(redis.ttl(lock_key))
        except RedisError:
            return None
        if lock_ttl > 0:
            return LoginThrottleState(allowed=False, retry_after_seconds=lock_ttl)
        return LoginThrottleState(allowed=True)

    def _register_failure_redis(self, *, scope: str, key: str, settings: Settings) -> bool:
        redis = self._get_redis_client(settings)
        if redis is None:
            return False
        policy = self._resolve_policy(scope=scope, settings=settings)
        attempts_key, lock_key = self._redis_keys(scope=scope, key=key)
        try:
            pipeline = redis.pipeline(transaction=True)
            pipeline.incr(attempts_key)
            pipeline.ttl(attempts_key)
            attempts, attempts_ttl = pipeline.execute()
            attempts_count = int(attempts)
            attempts_ttl = int(attempts_ttl)
            if attempts_count == 1 or attempts_ttl < 0:
                redis.expire(attempts_key, policy.window_seconds)
            if attempts_count >= policy.max_attempts:
                redis.set(lock_key, "1", ex=policy.lockout_seconds)
                redis.delete(attempts_key)
            return True
        except RedisError:
            return False

    def _register_success_redis(self, *, scope: str, key: str) -> bool:
        redis = self._get_cached_redis_client()
        if redis is None:
            return False
        attempts_key, lock_key = self._redis_keys(scope=scope, key=key)
        try:
            redis.delete(attempts_key, lock_key)
            return True
        except RedisError:
            return False

    def _check_allowed_memory(self, *, scope: str, key: str, settings: Settings) -> LoginThrottleState:
        policy = self._resolve_policy(scope=scope, settings=settings)
        now = datetime.now(UTC)
        window = timedelta(seconds=policy.window_seconds)
        memory_key = self._memory_bucket_key(scope=scope, key=key)
        with self._lock:
            bucket = self._buckets.get(memory_key)
            if bucket is None:
                return LoginThrottleState(allowed=True)
            self._prune(bucket=bucket, now=now, window=window)
            if bucket.locked_until is not None and bucket.locked_until > now:
                retry_after = int((bucket.locked_until - now).total_seconds())
                return LoginThrottleState(allowed=False, retry_after_seconds=max(retry_after, 1))
            if bucket.locked_until is not None and bucket.locked_until <= now:
                bucket.locked_until = None
            return LoginThrottleState(allowed=True)

    def _register_failure_memory(self, *, scope: str, key: str, settings: Settings) -> None:
        policy = self._resolve_policy(scope=scope, settings=settings)
        now = datetime.now(UTC)
        window = timedelta(seconds=policy.window_seconds)
        memory_key = self._memory_bucket_key(scope=scope, key=key)
        with self._lock:
            bucket = self._buckets.get(memory_key)
            if bucket is None:
                bucket = _Bucket(attempts=deque())
                self._buckets[memory_key] = bucket
            self._prune(bucket=bucket, now=now, window=window)
            bucket.attempts.append(now)
            if len(bucket.attempts) >= policy.max_attempts:
                bucket.locked_until = now + timedelta(seconds=policy.lockout_seconds)

    def _get_redis_client(self, settings: Settings) -> Redis | None:
        url = settings.redis_url.strip()
        if not url:
            return None
        with self._redis_lock:
            cached = self._redis_clients.get(url)
            if cached is not None:
                return cached
            try:
                client = Redis.from_url(url, decode_responses=True, socket_timeout=0.25)
                client.ping()
            except RedisError:
                return None
            self._redis_clients[url] = client
            return client

    def _get_cached_redis_client(self) -> Redis | None:
        with self._redis_lock:
            for client in self._redis_clients.values():
                return client
        return None

    @staticmethod
    def _resolve_policy(*, scope: str, settings: Settings) -> _ThrottlePolicy:
        if scope == LOGIN_USER_SCOPE:
            return _ThrottlePolicy(
                window_seconds=settings.auth_login_rate_limit_window_seconds,
                max_attempts=settings.auth_login_rate_limit_max_attempts,
                lockout_seconds=settings.auth_login_lockout_seconds,
            )
        if scope == LOGIN_IP_SCOPE:
            return _ThrottlePolicy(
                window_seconds=settings.auth_login_ip_rate_limit_window_seconds,
                max_attempts=settings.auth_login_ip_rate_limit_max_attempts,
                lockout_seconds=settings.auth_login_ip_lockout_seconds,
            )
        if scope == REFRESH_IP_SCOPE:
            return _ThrottlePolicy(
                window_seconds=settings.auth_refresh_ip_rate_limit_window_seconds,
                max_attempts=settings.auth_refresh_ip_rate_limit_max_attempts,
                lockout_seconds=settings.auth_refresh_ip_lockout_seconds,
            )
        raise ValueError(f"Unsupported throttle scope: {scope}")

    @staticmethod
    def _redis_keys(*, scope: str, key: str) -> tuple[str, str]:
        prefix = f"auth_throttle:{scope}:{key}"
        return (f"{prefix}:attempts", f"{prefix}:lock")

    @staticmethod
    def _memory_bucket_key(*, scope: str, key: str) -> str:
        return f"{scope}|{key}"

    @staticmethod
    def _is_non_development(settings: Settings) -> bool:
        return settings.app_env.strip().lower() != "development"

    @staticmethod
    def _prune(*, bucket: _Bucket, now: datetime, window: timedelta) -> None:
        cutoff = now - window
        while bucket.attempts and bucket.attempts[0] < cutoff:
            bucket.attempts.popleft()


login_throttle_service = LoginThrottleService()
