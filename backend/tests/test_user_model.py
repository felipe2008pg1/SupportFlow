import uuid

import pytest
from sqlalchemy.exc import IntegrityError

from app.core.security import hash_password
from app.models.user import User


def _make_user(db_session, email="user@example.com", password="correct horse battery staple"):  # noqa: S107
    user = User(email=email, hashed_password=hash_password(password))
    db_session.add(user)
    db_session.commit()
    return user


def test_email_is_normalized_to_lowercase_and_stripped(db_session):
    user = _make_user(db_session, email="  Test@Example.COM  ")
    assert user.email == "test@example.com"


def test_invalid_email_is_rejected(db_session):
    with pytest.raises(ValueError):
        User(email="not-an-email", hashed_password=hash_password("x" * 12))


def test_duplicate_email_is_rejected_case_insensitively(db_session):
    _make_user(db_session, email="dup@example.com")
    with pytest.raises(IntegrityError):
        _make_user(db_session, email="DUP@example.com")


def test_user_has_uuid_primary_key(db_session):
    user = _make_user(db_session, email="uuid@example.com")
    assert isinstance(user.id, uuid.UUID)


def test_user_is_active_by_default(db_session):
    user = _make_user(db_session, email="active@example.com")
    assert user.is_active is True


def test_password_is_never_stored_in_plaintext(db_session):
    plain = "super-secret-password"
    user = _make_user(db_session, email="plain@example.com", password=plain)
    assert user.hashed_password != plain
    assert user.hashed_password.startswith("$argon2id$")


def test_repr_does_not_leak_password_hash(db_session):
    user = _make_user(db_session, email="repr@example.com")
    assert user.hashed_password not in repr(user)



def test_role_defaults_to_requester(db_session):
    from app.models.user import Role

    user = _make_user(db_session, email="role@example.com")
    assert user.role is Role.REQUESTER


def test_invalid_role_is_rejected_by_database(db_session):
    from sqlalchemy import text

    user = _make_user(db_session, email="badrole@example.com")
    with pytest.raises(IntegrityError):
        db_session.execute(
            text("UPDATE users SET role = 'root' WHERE id = :id"), {"id": user.id.hex}
        )