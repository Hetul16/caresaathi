"""Doctor link endpoints (C1, D-46). Members create, list, revoke and draft questions; the public page is read-only plus one reply form."""
from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from ..db import request_session
from ..security import hash_token
from ..services import doctor as svc
from .deps import db, require_member

router = APIRouter(tags=["doctor-link"])
_NO_STORE = {"Cache-Control": "no-store", "X-Robots-Tag": "noindex, nofollow"}


class CreateIn(BaseModel):
    doctor_name: str = Field(min_length=1, max_length=120)
    expires_in_days: int = Field(default=7, ge=1, le=30)


class QuestionIn(BaseModel):
    body: str = Field(min_length=1, max_length=svc.MAX_QUESTION)


class ReplyIn(BaseModel):
    body: str = Field(min_length=1, max_length=4000)


@router.post("/patients/{patient_id}/doctor-links", status_code=201)
def create_link(patient_id: UUID, body: CreateIn, request: Request, s: Session = Depends(db, scope="function")):
    require_member(s, patient_id, can_manage=True)
    return svc.create_link(s, patient_id=patient_id, user_id=request.state.user_id, doctor_name=body.doctor_name,
                           expires_in_days=body.expires_in_days)


@router.get("/patients/{patient_id}/doctor-links")
def list_links(patient_id: UUID, s: Session = Depends(db, scope="function")):
    require_member(s, patient_id)
    return {"links": svc.list_links(s, patient_id)}


@router.post("/doctor-links/{link_id}/revoke")
def revoke(link_id: UUID, request: Request, s: Session = Depends(db, scope="function")):
    pid, _, _ = svc.link_patient(s, link_id)
    require_member(s, pid, can_manage=True)
    return svc.revoke_link(s, link_id=link_id, user_id=request.state.user_id)


@router.post("/doctor-links/{link_id}/questions", status_code=202)
def ask(link_id: UUID, body: QuestionIn, request: Request, s: Session = Depends(db, scope="function")):
    """Asks first: this only queues the question. A member with approval rights must approve it before the doctor can see it."""
    pid, _, _ = svc.link_patient(s, link_id)
    require_member(s, pid)
    return svc.propose_question(s, link_id=link_id, user_id=request.state.user_id, body=body.body)


@router.post("/doctor-messages/{message_id}/read-changes")
def read_changes(message_id: UUID, request: Request, s: Session = Depends(db, scope="function")):
    """Read the doctor's reply into PENDING plan changes. Needs approval rights, because the changes then wait for a person to confirm."""
    from sqlalchemy import text
    from .deps import problem
    pid = s.execute(text("SELECT patient_id FROM doctor_messages WHERE id = :i"), {"i": message_id}).scalar()
    if pid is None:
        raise problem(404, "not-found", "Not found")
    require_member(s, pid, can_approve=True)
    return svc.read_reply_changes(s, message_id=message_id, user_id=request.state.user_id)


# ---- public ----------------------------------------------------------------------------------------------------
def _ip(request: Request) -> bytes:
    ip = request.headers.get("x-forwarded-for", "").split(",")[0].strip() or (request.client.host if request.client else "")
    return hash_token(ip)


@router.get("/d/{token}")
def public_page(token: str, request: Request):
    ua = request.headers.get("user-agent", "")
    with request_session() as s:           # committed on exit so every attempt is logged
        outcome, data = svc.doctor_view(s, token=token, ip_hash=_ip(request), ua=ua)
        thread = svc.doctor_thread(s, data["hash"]) if data else []
    if data is None:
        return JSONResponse({"available": False}, status_code=404, headers=_NO_STORE)
    with request_session(public_card_patient_id=data["patient_id"]) as s:
        card = data["build_card"](s, data["patient_id"])
    return JSONResponse({"available": True, "doctor_name": data["doctor_name"], "expires_at": data["expires_at"], "card": card,
                         "thread": thread, "can_reply": any(m["direction"] == "to_doctor" for m in thread),
                         "note": "Read-only. Everything here comes from the family's documents and was not checked by CareSaathi against medical knowledge."},
                        headers=_NO_STORE)


@router.post("/d/{token}/reply")
def public_reply(token: str, body: ReplyIn, request: Request):
    with request_session() as s:
        result = svc.doctor_reply(s, token=token, body=body.body, ip_hash=_ip(request), ua=request.headers.get("user-agent", ""))
    if result == "stored":
        return JSONResponse({"ok": True}, headers=_NO_STORE)
    return JSONResponse({"ok": False}, status_code=404 if result == "unavailable" else 409, headers=_NO_STORE)
