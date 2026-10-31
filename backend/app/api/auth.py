"""Registration, login, refresh and logout (docs/15-api-spec.md section 2).

Access token (short-lived JWT) in the response body; refresh token in an HttpOnly, SameSite cookie, stored
only as a peppered hash. Refresh tokens rotate on every use. The auth role can touch users and refresh_tokens only."""
from __future__ import annotations

import re
from datetime import datetime, timedelta, timezone
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, Request, Response
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError

from ..config import get_settings
from ..db import auth_session
from ..safety.ratelimit import client_key, limiter
from ..security import hash_password, hash_token, make_access_token, new_token, verify_password
from .deps import current_user_id, problem

router = APIRouter(prefix="/auth", tags=["auth"])

COOKIE = "cs_refresh"
REFRESH_DAYS = 30
_PHONE = re.compile(r"^\+[1-9][0-9]{6,14}$")


class RegisterIn(BaseModel):
    display_name: str = Field(min_length=1, max_length=120)
    email: str | None = Field(default=None, max_length=254)
    phone: str | None = None
    password: str = Field(min_length=10, max_length=200)
    preferred_language: str = "en"

    @field_validator("email")
    @classmethod
    def _email(cls, v: str | None) -> str | None:
        if v is None or v == "":
            return None
        if not re.match(r"^[^@\s]+@[^@\s]+\.[^@\s]+$", v):
            raise ValueError("enter a valid email address")
        return v.strip().lower()

    @field_validator("phone")
    @classmethod
    def _phone(cls, v: str | None) -> str | None:
        if v is None or v == "":
            return None
        v = re.sub(r"[\s-]", "", v)
        if not _PHONE.match(v):
            raise ValueError("use international format, for example +919876543210")
        return v

    @field_validator("preferred_language")
    @classmethod
    def _lang(cls, v: str) -> str:
        if v not in ("en", "hi", "mr"):
            raise ValueError("language must be en, hi or mr")
        return v


class LoginIn(BaseModel):
    identifier: str = Field(min_length=3, max_length=254)   # email or phone
    password: str = Field(min_length=1, max_length=200)


def _cookie(resp: Response, token: str) -> None:
    resp.set_cookie(COOKIE, token, max_age=REFRESH_DAYS * 86400, httponly=True, samesite="lax",
                    secure=get_settings().public_base_url.startswith("https"), path="/api/v1/auth")


def _issue(resp: Response, s, user_id: UUID, user_agent: str | None) -> dict:
    refresh = new_token()
    s.execute(text("""INSERT INTO refresh_tokens (user_id, token_hash, expires_at, user_agent)
                      VALUES (:u, :h, :e, :ua)"""),
              {"u": user_id, "h": hash_token(refresh), "e": datetime.now(timezone.utc) + timedelta(days=REFRESH_DAYS),
               "ua": (user_agent or "")[:300]})
    _cookie(resp, refresh)
    access, ttl = make_access_token(user_id)
    return {"access_token": access, "token_type": "bearer", "expires_in": ttl}


def _user_out(row) -> dict:
    return {"id": str(row["id"]), "display_name": row["display_name"], "email": row["email"],
            "phone": row["phone_e164"], "preferred_language": row["preferred_language"]}


def _too_many(seconds: int):
    """Same wording for a locked account and a wrong password, so the reply never says whether an account exists."""
    return problem(429, "too-many-attempts", "Too many attempts. Please wait and try again.",
                   f"Try again in about {max(1, seconds // 60)} minute{'s' if seconds >= 120 else ''}.")


@router.post("/register", status_code=201)
def register(body: RegisterIn, request: Request, response: Response):
    if not body.email and not body.phone:
        raise problem(422, "validation-failed", "Enter an email address or a phone number")
    ip = client_key(request)
    if (wait := limiter.retry_after("register_ip", ip)):
        raise _too_many(wait)
    uid = uuid4()
    with auth_session() as s:
        try:
            s.execute(text("""INSERT INTO users (id, email, phone_e164, display_name, preferred_language, password_hash)
                              VALUES (:i, :e, :p, :n, CAST(:l AS pref_lang), :h)"""),
                      {"i": uid, "e": body.email, "p": body.phone, "n": body.display_name.strip(),
                       "l": body.preferred_language, "h": hash_password(body.password)})
        except IntegrityError:
            s.rollback()
            limiter.record_failure("register_ip", ip)
            raise problem(409, "account-exists", "An account with these details already exists",
                          "Try signing in instead.")
        limiter.record_failure("register_ip", ip)        # every creation counts toward the per-address cap, success or not
        tokens = _issue(response, s, uid, request.headers.get("user-agent"))
        row = s.execute(text("SELECT * FROM users WHERE id=:i"), {"i": uid}).mappings().one()
    return {**tokens, "user": _user_out(row)}


@router.post("/login")
def login(body: LoginIn, request: Request, response: Response):
    ident = body.identifier.strip()
    phone = re.sub(r"[\s-]", "", ident)
    ip, who = client_key(request), ident.lower()
    # Checked before the password is verified, so a locked account costs an attacker a request and no Argon2 work.
    for rule, key in (("login_identifier", who), ("login_ip", ip)):
        if (wait := limiter.retry_after(rule, key)):
            raise _too_many(wait)
    with auth_session() as s:
        row = s.execute(text("""SELECT * FROM users WHERE is_active AND (email = :e OR phone_e164 = :p)"""),
                        {"e": who, "p": phone}).mappings().first()
        ok = verify_password(row["password_hash"] if row else None, body.password)
        if not row or not ok:
            w = max(limiter.record_failure("login_identifier", who), limiter.record_failure("login_ip", ip))
            if w:
                raise _too_many(w)
            raise problem(401, "invalid-credentials", "Email, phone or password is not right")
        limiter.clear("login_identifier", who)
        limiter.clear("login_ip", ip)
        tokens = _issue(response, s, row["id"], request.headers.get("user-agent"))
    return {**tokens, "user": _user_out(row)}


@router.post("/refresh")
def refresh(request: Request, response: Response):
    old = request.cookies.get(COOKIE)
    if not old:
        raise problem(401, "unauthenticated", "Please sign in")
    with auth_session() as s:
        row = s.execute(text("""UPDATE refresh_tokens SET revoked_at = now()
                                WHERE token_hash = :h AND revoked_at IS NULL AND expires_at > now()
                                RETURNING user_id"""), {"h": hash_token(old)}).first()
        if not row:
            response.delete_cookie(COOKIE, path="/api/v1/auth")
            raise problem(401, "unauthenticated", "Your session has expired. Please sign in again.")
        tokens = _issue(response, s, row[0], request.headers.get("user-agent"))
        user = s.execute(text("SELECT * FROM users WHERE id=:i"), {"i": row[0]}).mappings().one()
    return {**tokens, "user": _user_out(user)}


@router.post("/logout", status_code=204)
def logout(request: Request, response: Response):
    old = request.cookies.get(COOKIE)
    if old:
        with auth_session() as s:
            s.execute(text("UPDATE refresh_tokens SET revoked_at = now() WHERE token_hash = :h AND revoked_at IS NULL"),
                      {"h": hash_token(old)})
    response.delete_cookie(COOKIE, path="/api/v1/auth")


@router.get("/me")
def me(user_id: UUID = Depends(current_user_id)):
    with auth_session() as s:
        row = s.execute(text("SELECT * FROM users WHERE id=:i AND is_active"), {"i": user_id}).mappings().first()
    if not row:
        raise problem(401, "unauthenticated", "Please sign in")
    return _user_out(row)
