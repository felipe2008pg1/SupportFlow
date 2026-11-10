import hashlib
import secrets
import uuid
from datetime import datetime, timedelta, timezone

import jwt

from app.core.config import get_settings

ALGORITHM = "HS256"
ISSUER = "supportflow"
TOKEN_TYPE_ACCESS = "access"  # noqa: S105


class TokenError(Exception):
    """Raised for any invalid, expired or malformed token. Never carries details."""


def create_access_token(user_id: uuid.UUID) -> tuple[str, int]:
    settings = get_settings()
    now = datetime.now(timezone.utc)
    lifetime = timedelta(minutes=settings.access_token_expire_minutes)
    payload = {
        "sub": str(user_id),
        "iss": ISSUER,
        "iat": now,
        "exp": now + lifetime,
        "jti": uuid.uuid4().hex,
        "typ": TOKEN_TYPE_ACCESS,
    }
    token = jwt.encode(payload, settings.secret_key, algorithm=ALGORITHM)
    return token, int(lifetime.total_seconds())


def decode_access_token(token: str) -> uuid.UUID:
    try:
        claims = jwt.decode(
            token,
            get_settings().secret_key,
            algorithms=[ALGORITHM],  # pinned: rejects "none" and algorithm confusion
            issuer=ISSUER,
            options={"require": ["exp", "iat", "sub", "iss", "typ"]},
        )
        if claims.get("typ") != TOKEN_TYPE_ACCESS:
            raise TokenError
        return uuid.UUID(claims["sub"])
    except (jwt.PyJWTError, ValueError, KeyError) as exc:
        raise TokenError from exc


def generate_refresh_token() -> str:
    return secrets.token_urlsafe(48)


def hash_refresh_token(raw: str) -> str:
    # Token has 384 bits of entropy, so a fast hash is sufficient (no brute force).
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()
