"""Request dependencies: the authenticated user, and a database session with the RLS context set.

The context is set in ONE place (db.request_session). A bug here defeats row-level security, so keep it small."""
from __future__ import annotations

from typing import Iterator
from uuid import UUID

from fastapi import Depends, Header, HTTPException, Request
from sqlalchemy.orm import Session

from ..db import request_session
from ..security import read_access_token


def problem(status: int, type_: str, title: str, detail: str = "") -> HTTPException:
    """RFC 9457 problem details (docs/15-api-spec.md section 3.4); rendered by the handler in main.py."""
    return HTTPException(status_code=status, detail={"type": type_, "title": title, "detail": detail})


def current_user_id(authorization: str | None = Header(default=None)) -> UUID:
    if not authorization or not authorization.lower().startswith("bearer "):
        raise problem(401, "unauthenticated", "Please sign in")
    uid = read_access_token(authorization[7:].strip())
    if uid is None:
        raise problem(401, "unauthenticated", "Your session has expired. Please sign in again.")
    return uid


def db(request: Request, user_id: UUID = Depends(current_user_id)) -> Iterator[Session]:
    with request_session(user_id=user_id) as s:
        request.state.user_id = user_id
        yield s


def require_member(s: Session, patient_id: UUID, *, can_approve: bool = False, can_manage: bool = False) -> dict:
    """RLS already hides other families' patients; this adds the per-member permission flags."""
    from sqlalchemy import text
    row = s.execute(text("""
        SELECT id, member_role, can_approve, can_manage_members, can_view_recordings
        FROM family_members WHERE patient_id = :p AND user_id = app_user_id() AND status = 'active'"""),
        {"p": patient_id}).mappings().first()
    if row is None:
        raise problem(404, "not-a-member", "Not found")      # same answer for "no such patient" and "not yours"
    if can_approve and not row["can_approve"]:
        raise problem(403, "approval-rights-required", "You do not have approval rights for this patient")
    if can_manage and not row["can_manage_members"]:
        raise problem(403, "manage-rights-required", "You cannot manage members for this patient")
    return dict(row)
