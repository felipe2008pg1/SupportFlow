import pytest

from app.core.security import hash_password, needs_rehash, verify_password


def test_hash_password_produces_argon2id_hash():
    hashed = hash_password("correct horse battery staple")
    assert hashed.startswith("$argon2id$")


def test_same_password_produces_different_hashes():
    h1 = hash_password("same-password")
    h2 = hash_password("same-password")
    assert h1 != h2


def test_verify_password_succeeds_for_correct_password():
    hashed = hash_password("my-password")
    assert verify_password("my-password", hashed) is True


def test_verify_password_fails_for_incorrect_password():
    hashed = hash_password("my-password")
    assert verify_password("wrong-password", hashed) is False


def test_verify_password_fails_gracefully_for_malformed_hash():
    assert verify_password("anything", "not-a-real-hash") is False


def test_hash_password_rejects_empty_password():
    with pytest.raises(ValueError):
        hash_password("")


def test_needs_rehash_false_for_freshly_hashed_password():
    hashed = hash_password("my-password")
    assert needs_rehash(hashed) is False