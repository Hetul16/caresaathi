"""Passwords, access tokens and random-token hashing (docs/13-architecture.md section 6)."""
from __future__ import annotations

import hashlib
import hmac
import secrets
from datetime import datetime, timedelta, timezone
from uuid import UUID

import jwt
from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError, VerifyMismatchError

from .config import get_settings

_ph = PasswordHasher()  # Argon2id by default


def hash_password(pw: str) -> str:
    return _ph.hash(pw)


def verify_password(stored: str | None, pw: str) -> bool:
    """Constant-ish behaviour for unknown users: verify against a dummy hash so timing does not reveal them."""
    try:
        return _ph.verify(stored or _DUMMY, pw) and stored is not None
    except (VerifyMismatchError, VerificationError, InvalidHashError):
        return False


_DUMMY = _ph.hash("not-a-real-password")


def new_token(nbytes: int = 32) -> str:
    return secrets.token_urlsafe(nbytes)


def hash_token(token: str) -> bytes:
    """Peppered SHA-256. Only the hash is stored (refresh tokens, device tokens, Emergency Card links)."""
    return hmac.new(get_settings().token_pepper.encode(), token.encode(), hashlib.sha256).digest()


def make_access_token(user_id: UUID) -> tuple[str, int]:
    s = get_settings()
    exp = datetime.now(timezone.utc) + timedelta(minutes=s.access_token_minutes)
    tok = jwt.encode({"sub": str(user_id), "exp": exp, "typ": "access"}, s.jwt_secret, algorithm="HS256")
    return tok, s.access_token_minutes * 60


def read_access_token(token: str) -> UUID | None:
    try:
        claims = jwt.decode(token, get_settings().jwt_secret, algorithms=["HS256"])
        if claims.get("typ") != "access":
            return None
        return UUID(claims["sub"])
    except (jwt.PyJWTError, ValueError, KeyError):
        return None
