from datetime import datetime, timedelta, timezone

import jwt
import pytest
from sqlalchemy import select

from app.core.config import get_settings
from app.core.security import hash_password
from app.core.tokens import ALGORITHM, ISSUER, create_access_token
from app.models.refresh_token import RefreshToken
from app.models.user import Role, User

EMAIL = "ana@example.com"
PASSWORD = "correct horse battery staple"
ORIGIN = {"Origin": "http://localhost:8080"}


def make_user(client, email=EMAIL, role=Role.REQUESTER, active=True):
    with client.session_factory() as db:
        user = User(email=email, hashed_password=hash_password(PASSWORD), role=role, is_active=active)
        db.add(user)
        db.commit()
        return user.id


def login(client, email=EMAIL, password=PASSWORD):
    return client.post("/auth/login", json={"email": email, "password": password})


def test_login_success_sets_hardened_cookie(client):
    make_user(client)
    r = login(client)
    assert r.status_code == 200
    body = r.json()
    assert body["token_type"] == "bearer" and body["expires_in"] == 900
    cookie = r.headers["set-cookie"].lower()
    assert "httponly" in cookie and "samesite=strict" in cookie and "path=/auth" in cookie
    assert r.headers["cache-control"] == "no-store"


def test_login_email_is_case_insensitive(client):
    make_user(client)
    assert login(client, email="ANA@Example.com").status_code == 200


def test_login_failures_are_indistinguishable(client):
    make_user(client)
    make_user(client, email="off@example.com", active=False)
    a = login(client, password="wrong-password-123")
    b = login(client, email="ghost@example.com")
    c = login(client, email="off@example.com")
    assert a.status_code == b.status_code == c.status_code == 401
    assert a.json() == b.json() == c.json() == {"detail": "Invalid credentials"}


def test_login_rejects_extra_fields_and_oversized_password(client):
    make_user(client)
    assert client.post("/auth/login", json={"email": EMAIL, "password": PASSWORD, "role": "admin"}).status_code == 422
    assert login(client, password="a" * 129).status_code == 422


def test_login_rate_limit_per_account(client):
    make_user(client)
    for _ in range(5):
        assert login(client, password="wrong-password-123").status_code == 401
    r = login(client)  # correct password, but locked
    assert r.status_code == 429 and int(r.headers["retry-after"]) > 0


def test_me_requires_valid_token(client):
    assert client.get("/users/me").status_code == 401
    assert client.get("/users/me", headers={"Authorization": "Bearer garbage"}).status_code == 401
    uid = make_user(client)
    token = login(client).json()["access_token"]
    r = client.get("/users/me", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 200
    assert r.json()["id"] == str(uid) and "hashed_password" not in r.json()


def _forge(alg_key, **overrides):
    now = datetime.now(timezone.utc)
    claims = {"sub": "00000000-0000-0000-0000-000000000001", "iss": ISSUER, "iat": now,
              "exp": now + timedelta(minutes=5), "typ": "access"}
    claims.update(overrides)
    return jwt.encode(claims, alg_key, algorithm=ALGORITHM)


@pytest.mark.parametrize("mutator", ["expired", "wrong_key", "wrong_type", "wrong_issuer", "alg_none"])
def test_forged_or_invalid_tokens_rejected(client, mutator):
    uid = make_user(client)
    key = get_settings().secret_key
    now = datetime.now(timezone.utc)
    if mutator == "expired":
        t = _forge(key, sub=str(uid), exp=now - timedelta(seconds=1))
    elif mutator == "wrong_key":
        t = _forge("x" * 40, sub=str(uid))
    elif mutator == "wrong_type":
        t = _forge(key, sub=str(uid), typ="refresh")
    elif mutator == "wrong_issuer":
        t = _forge(key, sub=str(uid), iss="evil")
    else:
        t = jwt.encode({"sub": str(uid), "iss": ISSUER, "iat": now, "exp": now + timedelta(minutes=5), "typ": "access"}, None, algorithm="none")
    r = client.get("/users/me", headers={"Authorization": f"Bearer {t}"})
    assert r.status_code == 401


def test_token_of_deactivated_user_rejected(client):
    uid = make_user(client)
    token, _ = create_access_token(uid)
    with client.session_factory() as db:
        db.get(User, uid).is_active = False
        db.commit()
    assert client.get("/users/me", headers={"Authorization": f"Bearer {token}"}).status_code == 401


def test_refresh_rotates_and_reuse_revokes_family(client):
    make_user(client)
    login(client)
    old = client.cookies.get("refresh_token")
    r = client.post("/auth/refresh", headers=ORIGIN)
    assert r.status_code == 200
    new = client.cookies.get("refresh_token")
    assert new and new != old

    # Replay the already-rotated token (attacker) -> chain revoked.
    client.cookies.set("refresh_token", old, path="/auth")
    assert client.post("/auth/refresh", headers=ORIGIN).status_code == 401
    # Legit holder of the newest token is now logged out too.
    client.cookies.set("refresh_token", new, path="/auth")
    assert client.post("/auth/refresh", headers=ORIGIN).status_code == 401
    with client.session_factory() as db:
        assert all(t.revoked_at for t in db.scalars(select(RefreshToken)))


def test_refresh_without_cookie_or_bad_origin(client):
    assert client.post("/auth/refresh", headers=ORIGIN).status_code == 401
    make_user(client)
    login(client)
    assert client.post("/auth/refresh", headers={"Origin": "http://evil.example"}).status_code == 403


def test_expired_refresh_rejected(client):
    make_user(client)
    login(client)
    with client.session_factory() as db:
        for t in db.scalars(select(RefreshToken)):
            t.expires_at = datetime.now(timezone.utc) - timedelta(seconds=1)
        db.commit()
    assert client.post("/auth/refresh", headers=ORIGIN).status_code == 401


def test_logout_revokes_session(client):
    make_user(client)
    login(client)
    assert client.post("/auth/logout", headers=ORIGIN).status_code == 204
    r = client.post("/auth/refresh", headers=ORIGIN)
    assert r.status_code == 401
    with client.session_factory() as db:
        assert all(t.revoked_at for t in db.scalars(select(RefreshToken)))
