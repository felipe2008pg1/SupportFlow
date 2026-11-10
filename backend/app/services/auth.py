import logging
import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.security import hash_password, needs_rehash, verify_password
from app.core.tokens import (
    create_access_token,
    generate_refresh_token,
    hash_refresh_token,
)
from app.models.refresh_token import RefreshToken
from app.models.user import User

audit = logging.getLogger("supportflow.security")

_dummy_hash: str | None = None


class AuthError(Exception):
    """Authentication failed. Deliberately carries no detail for the client."""


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _aware(dt: datetime) -> datetime:
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


def _get_dummy_hash() -> str:
    global _dummy_hash
    if _dummy_hash is None:
        _dummy_hash = hash_password("timing-equalization-placeholder")
    return _dummy_hash


def authenticate(db: Session, email: str, password: str) -> User:
    """Constant-effort credential check (no user enumeration via timing/messages)."""
    user = db.scalar(select(User).where(User.email == email.strip().lower()))
    if user is None:
        verify_password(password, _get_dummy_hash())
        raise AuthError
    if not verify_password(password, user.hashed_password) or not user.is_active:
        raise AuthError
    if needs_rehash(user.hashed_password):
        user.hashed_password = hash_password(password)
        db.commit()
    return user


def _new_refresh(db: Session, user_id: uuid.UUID, family_id: uuid.UUID) -> str:
    raw = generate_refresh_token()
    db.add(
        RefreshToken(
            user_id=user_id,
            family_id=family_id,
            token_hash=hash_refresh_token(raw),
            expires_at=_now() + timedelta(days=get_settings().refresh_token_expire_days),
        )
    )
    return raw


def start_session(db: Session, user: User) -> tuple[str, int, str]:
    refresh = _new_refresh(db, user.id, uuid.uuid4())
    db.commit()
    access, expires_in = create_access_token(user.id)
    return access, expires_in, refresh


def _revoke_family(db: Session, family_id: uuid.UUID) -> None:
    db.execute(
        update(RefreshToken)
        .where(RefreshToken.family_id == family_id, RefreshToken.revoked_at.is_(None))
        .values(revoked_at=_now())
    )


def rotate_session(db: Session, raw_refresh: str) -> tuple[str, int, str]:
    row = db.scalar(
        select(RefreshToken)
        .where(RefreshToken.token_hash == hash_refresh_token(raw_refresh))
        .with_for_update()
    )
    if row is None:
        raise AuthError

    if row.revoked_at is not None:
        # An already-rotated token is being replayed: assume theft, kill the chain.
        _revoke_family(db, row.family_id)
        db.commit()
        audit.warning("refresh_token_reuse user_id=%s", row.user_id)
        raise AuthError

    if _aware(row.expires_at) <= _now():
        raise AuthError

    user = db.get(User, row.user_id)
    if user is None or not user.is_active:
        _revoke_family(db, row.family_id)
        db.commit()
        raise AuthError

    row.revoked_at = _now()
    new_raw = _new_refresh(db, user.id, row.family_id)
    db.commit()
    access, expires_in = create_access_token(user.id)
    return access, expires_in, new_raw


def end_session(db: Session, raw_refresh: str) -> None:
    row = db.scalar(
        select(RefreshToken).where(RefreshToken.token_hash == hash_refresh_token(raw_refresh))
    )
    if row is not None:
        _revoke_family(db, row.family_id)
        db.commit()
