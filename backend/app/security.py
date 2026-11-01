import hashlib
import re
import secrets
import uuid
from datetime import datetime, timedelta, timezone

import bcrypt
import jwt

from app.config import settings

_DUMMY_HASH: str | None = None


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(password: str, password_hash: str) -> bool:
    try:
        return bcrypt.checkpw(password.encode("utf-8"), password_hash.encode("utf-8"))
    except ValueError:
        return False


def dummy_password_hash() -> str:
    global _DUMMY_HASH
    if _DUMMY_HASH is None:
        _DUMMY_HASH = hash_password("not-a-real-password")
    return _DUMMY_HASH


def validate_password(password: str) -> str | None:
    if len(password) < 8:
        return "Password must be at least 8 characters."
    if len(password.encode("utf-8")) > 72:
        return "Password must be at most 72 bytes."
    if not re.search(r"[A-Za-z]", password) or not re.search(r"\d", password):
        return "Password must include a letter and a number."
    return None


def create_access_token(user_id: uuid.UUID, email: str) -> str:
    now = datetime.now(timezone.utc)
    payload = {
        "sub": str(user_id),
        "email": email,
        "type": "access",
        "iat": now,
        "exp": now + timedelta(minutes=settings.access_token_minutes),
    }
    return jwt.encode(payload, settings.jwt_secret, algorithm="HS256")


def decode_access_token(token: str) -> dict:
    payload = jwt.decode(token, settings.jwt_secret, algorithms=["HS256"])
    if payload.get("type") != "access":
        raise jwt.InvalidTokenError("Wrong token type.")
    return payload


def new_refresh_token() -> str:
    return secrets.token_urlsafe(32)


def hash_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def refresh_expiry() -> datetime:
    return datetime.now(timezone.utc) + timedelta(days=settings.refresh_token_days)
