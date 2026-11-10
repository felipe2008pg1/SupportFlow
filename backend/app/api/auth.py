import hashlib
import logging

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from sqlalchemy.orm import Session

from app.core import ratelimit
from app.core.config import get_settings
from app.db.session import get_db
from app.schemas.auth import LoginRequest, TokenResponse
from app.services import auth as service

router = APIRouter(prefix="/auth", tags=["auth"])
audit = logging.getLogger("supportflow.security")

REFRESH_COOKIE = "refresh_token"
_COOKIE_PATH = "/auth"


def _no_store(response: Response) -> None:
    response.headers["Cache-Control"] = "no-store"
    response.headers["Pragma"] = "no-cache"


def _invalid_credentials() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )


def _set_refresh_cookie(response: Response, raw: str) -> None:
    settings = get_settings()
    response.set_cookie(
        REFRESH_COOKIE,
        raw,
        max_age=settings.refresh_token_expire_days * 86400,
        path=_COOKIE_PATH,
        httponly=True,
        secure=settings.cookie_secure,
        samesite="strict",
    )


def _clear_refresh_cookie(response: Response) -> None:
    settings = get_settings()
    response.delete_cookie(
        REFRESH_COOKIE,
        path=_COOKIE_PATH,
        httponly=True,
        secure=settings.cookie_secure,
        samesite="strict",
    )


def _enforce_origin(request: Request) -> None:
    """CSRF defense in depth for cookie-authenticated endpoints."""
    origin = request.headers.get("origin")
    if origin is not None and origin not in get_settings().cors_origins:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Forbidden")


def _client_ip(request: Request) -> str:
    return request.client.host if request.client else "unknown"


def _email_tag(email: str) -> str:
    return hashlib.sha256(email.strip().lower().encode()).hexdigest()[:12]


@router.post("/login", response_model=TokenResponse)
def login(
    body: LoginRequest,
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
) -> TokenResponse:
    _no_store(response)
    ip = _client_ip(request)
    tag = _email_tag(body.email)
    account_key, ip_key = f"{ip}|{tag}", ip

    wait = max(
        ratelimit.login_by_account.retry_after(account_key),
        ratelimit.login_by_ip.retry_after(ip_key),
    )
    if wait:
        audit.warning("login_rate_limited ip=%s email=%s", ip, tag)
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many attempts. Try again later.",
            headers={"Retry-After": str(wait)},
        )

    try:
        user = service.authenticate(db, body.email, body.password)
    except service.AuthError:
        ratelimit.login_by_account.register_failure(account_key)
        ratelimit.login_by_ip.register_failure(ip_key)
        audit.warning("login_failed ip=%s email=%s", ip, tag)
        raise _invalid_credentials() from None

    ratelimit.login_by_account.reset(account_key)
    access, expires_in, refresh = service.start_session(db, user)
    _set_refresh_cookie(response, refresh)
    audit.info("login_success user_id=%s ip=%s", user.id, ip)
    return TokenResponse(access_token=access, expires_in=expires_in)


@router.post("/refresh", response_model=TokenResponse)
def refresh(
    request: Request, response: Response, db: Session = Depends(get_db)
) -> TokenResponse:
    _no_store(response)
    _enforce_origin(request)
    raw = request.cookies.get(REFRESH_COOKIE)
    if not raw or len(raw) > 256:
        raise _invalid_credentials()
    try:
        access, expires_in, new_refresh = service.rotate_session(db, raw)
    except service.AuthError:
        _clear_refresh_cookie(response)
        raise _invalid_credentials() from None
    _set_refresh_cookie(response, new_refresh)
    return TokenResponse(access_token=access, expires_in=expires_in)


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout(request: Request, response: Response, db: Session = Depends(get_db)) -> Response:
    _enforce_origin(request)
    raw = request.cookies.get(REFRESH_COOKIE)
    if raw and len(raw) <= 256:
        service.end_session(db, raw)
    out = Response(status_code=status.HTTP_204_NO_CONTENT)
    _clear_refresh_cookie(out)
    _no_store(out)
    return out
