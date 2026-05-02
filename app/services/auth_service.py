from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
import hashlib
import secrets

from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError
from sqlalchemy.orm import Session

from app.config import Settings
from app.models.auth import AuthSession, Role, User, UserRole
from app.security import create_token


DEFAULT_ROLES = ("admin", "manager", "coordinator", "technician")
BUSINESS_ROLES = ("manager", "coordinator", "technician")

_password_hasher = PasswordHasher()


@dataclass
class UserContext:
    user_id: str
    username: str
    roles: list[str]
    is_superadmin: bool = False


@dataclass
class SessionTokens:
    access_token: str
    refresh_token: str


def ensure_default_roles(db: Session) -> None:
    existing = {
        role.name for role in db.query(Role).filter(Role.name.in_(DEFAULT_ROLES)).all()
    }
    for role_name in DEFAULT_ROLES:
        if role_name not in existing:
            db.add(Role(name=role_name))
    db.commit()


def hash_password(password: str) -> str:
    return _password_hasher.hash(password)


def verify_password(password_hash: str, password: str) -> bool:
    try:
        return _password_hasher.verify(password_hash, password)
    except VerifyMismatchError:
        return False


def password_needs_rehash(password_hash: str) -> bool:
    return _password_hasher.check_needs_rehash(password_hash)


def hash_refresh_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def generate_refresh_token() -> str:
    return secrets.token_urlsafe(64)


def get_user_by_username(db: Session, username: str) -> User | None:
    return db.query(User).filter(User.username == username).first()


def get_user_by_id(db: Session, user_id: str) -> User | None:
    return db.get(User, user_id)


def list_user_roles(user: User) -> list[str]:
    return sorted(role_link.role.name for role_link in user.roles)


def user_to_context(user: User) -> UserContext:
    return UserContext(
        user_id=user.user_id,
        username=user.username,
        roles=list_user_roles(user),
        is_superadmin=user.is_superadmin,
    )


def create_user(
    db: Session,
    *,
    username: str,
    password: str,
    role_names: list[str],
    is_superadmin: bool = False,
) -> User:
    normalized_username = username.strip()
    if not normalized_username:
        raise ValueError("username cannot be empty")
    if get_user_by_username(db, normalized_username) is not None:
        raise ValueError("username already exists")
    if len(password) < 12:
        raise ValueError("password must be at least 12 characters long")

    roles = (
        db.query(Role)
        .filter(Role.name.in_(role_names))
        .all()
    )
    missing_roles = sorted(set(role_names) - {role.name for role in roles})
    if missing_roles:
        raise ValueError(f"unknown roles: {', '.join(missing_roles)}")

    user = User(
        username=normalized_username,
        password_hash=hash_password(password),
        is_active=True,
        is_superadmin=is_superadmin,
    )
    db.add(user)
    db.flush()
    for role in roles:
        db.add(UserRole(user_id=user.user_id, role_id=role.role_id))
    db.commit()
    db.refresh(user)
    return user


def update_user_roles(
    db: Session,
    *,
    user: User,
    role_names: list[str],
) -> User:
    roles = db.query(Role).filter(Role.name.in_(role_names)).all()
    missing_roles = sorted(set(role_names) - {role.name for role in roles})
    if missing_roles:
        raise ValueError(f"unknown roles: {', '.join(missing_roles)}")

    db.query(UserRole).filter(UserRole.user_id == user.user_id).delete()
    db.flush()
    for role in roles:
        db.add(UserRole(user_id=user.user_id, role_id=role.role_id))
    db.commit()
    db.refresh(user)
    return user


def reset_user_password(db: Session, *, user: User, password: str) -> User:
    if len(password) < 12:
        raise ValueError("password must be at least 12 characters long")
    user.password_hash = hash_password(password)
    user.updated_at = datetime.now(UTC)
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def authenticate_user(
    db: Session,
    *,
    username: str,
    password: str,
    settings: Settings,
) -> UserContext | None:
    user = get_user_by_username(db, username.strip())
    if user is not None and user.is_active:
        if verify_password(user.password_hash, password):
            if password_needs_rehash(user.password_hash):
                user.password_hash = hash_password(password)
            user.last_login_at = datetime.now(UTC)
            db.add(user)
            db.commit()
            db.refresh(user)
            return user_to_context(user)
    return None


def create_session_tokens(
    db: Session,
    *,
    user: UserContext,
    settings: Settings,
    user_agent: str | None = None,
    ip_address: str | None = None,
    rotated_from_session_id: str | None = None,
) -> SessionTokens:
    now = datetime.now(UTC)
    access_token = create_token(
        subject=user.user_id,
        token_type="access",
        expires_delta=timedelta(minutes=settings.access_token_expire_minutes),
        settings=settings,
        extra_claims={
            "username": user.username,
            "roles": user.roles,
            "is_superadmin": user.is_superadmin,
            "jti": secrets.token_hex(16),
        },
    )
    refresh_token = generate_refresh_token()
    expires_at = now + timedelta(minutes=settings.refresh_token_expire_minutes)
    session = AuthSession(
        user_id=user.user_id,
        refresh_token_hash=hash_refresh_token(refresh_token),
        refresh_jti=secrets.token_hex(16),
        expires_at=expires_at,
        rotated_from_session_id=rotated_from_session_id,
        user_agent=user_agent,
        ip_address=ip_address,
    )
    db.add(session)
    db.commit()
    return SessionTokens(access_token=access_token, refresh_token=refresh_token)


def rotate_refresh_session(
    db: Session,
    *,
    refresh_token: str,
    settings: Settings,
    user_agent: str | None = None,
    ip_address: str | None = None,
) -> SessionTokens | None:
    now = datetime.now(UTC)
    session = (
        db.query(AuthSession)
        .filter(AuthSession.refresh_token_hash == hash_refresh_token(refresh_token))
        .first()
    )
    if session is None:
        return None
    expires_at = _as_utc(session.expires_at)
    if session.revoked_at is not None or expires_at <= now:
        return None

    user = get_user_by_id(db, session.user_id)
    if user is None or not user.is_active:
        return None

    context = user_to_context(user)
    session.revoked_at = now
    session.revoked_reason = "rotated"
    session.last_used_at = now
    db.add(session)
    db.commit()
    return create_session_tokens(
        db,
        user=context,
        settings=settings,
        user_agent=user_agent,
        ip_address=ip_address,
        rotated_from_session_id=session.session_id,
    )


def revoke_refresh_session(db: Session, *, refresh_token: str, reason: str = "logout") -> None:
    session = (
        db.query(AuthSession)
        .filter(AuthSession.refresh_token_hash == hash_refresh_token(refresh_token))
        .first()
    )
    if session is None or session.revoked_at is not None:
        return
    session.revoked_at = datetime.now(UTC)
    session.revoked_reason = reason
    db.add(session)
    db.commit()


def revoke_all_user_sessions(db: Session, *, user_id: str, reason: str = "logout_all") -> None:
    now = datetime.now(UTC)
    sessions = (
        db.query(AuthSession)
        .filter(
            AuthSession.user_id == user_id,
            AuthSession.revoked_at.is_(None),
        )
        .all()
    )
    for session in sessions:
        session.revoked_at = now
        session.revoked_reason = reason
        db.add(session)
    db.commit()


def bootstrap_initial_admin(db: Session, *, settings: Settings) -> None:
    if settings.app_env.lower() == "production" and not settings.auth_bootstrap_admin_username:
        return
    ensure_default_roles(db)
    user_count = db.query(User).count()
    if user_count > 0:
        return
    username = settings.auth_bootstrap_admin_username
    password = settings.auth_bootstrap_admin_password
    if settings.app_env.lower() == "development" and settings.demo_admin_enabled:
        username = username or settings.demo_admin_username
        password = password or settings.demo_admin_password
    if not username or not password:
        return
    create_user(
        db,
        username=username,
        password=password,
        role_names=["admin", *BUSINESS_ROLES],
        is_superadmin=True,
    )


def _as_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)
