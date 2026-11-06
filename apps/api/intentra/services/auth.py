import hashlib
import os
import secrets
from datetime import datetime, timedelta, timezone

from pwdlib import PasswordHash

SESSION_LIFETIME = timedelta(hours=8)
password_hasher = PasswordHash.recommended()


def hash_password(password: str) -> str:
    return password_hasher.hash(password)


def verify_password(password: str, stored_hash: str) -> bool:
    return password_hasher.verify(password, stored_hash)


def generate_session_token() -> str:
    return secrets.token_urlsafe(32)


def hash_session_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def session_expiry() -> datetime:
    return datetime.now(timezone.utc) + SESSION_LIFETIME


def session_cookie_requires_https() -> bool:
    """Keep local HTTP usable without sending an insecure deployed cookie."""
    if os.getenv("VERCEL") == "1":
        return True
    return os.getenv("INTENTRA_FRONTEND_URL", "").startswith("https://")
