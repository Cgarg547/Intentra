from datetime import datetime, timezone

from intentra.services.auth import (
    generate_session_token,
    hash_password,
    hash_session_token,
    session_expiry,
    verify_password,
)


def test_password_hash_is_not_plaintext():
    password = "IntentraTestPassword2026!"
    stored = hash_password(password)

    assert stored != password
    assert stored.startswith("$argon2id$")
    assert verify_password(password, stored)


def test_wrong_password_is_rejected():
    stored = hash_password("CorrectPassword2026!")

    assert not verify_password("IncorrectPassword2026!", stored)


def test_session_tokens_are_unique():
    tokens = {generate_session_token() for _ in range(100)}

    assert len(tokens) == 100


def test_session_token_is_not_stored_raw():
    token = generate_session_token()
    digest = hash_session_token(token)

    assert digest != token
    assert len(digest) == 64
    assert digest == hash_session_token(token)


def test_session_expires_in_future():
    expiry = session_expiry()

    assert expiry.tzinfo is not None
    assert expiry > datetime.now(timezone.utc)
