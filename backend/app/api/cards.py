"""Emergency Card endpoints (S6). Members create, list, revoke and share; the public link reads a live card.

The public route validates the token inside one SECURITY DEFINER function that logs every attempt, then reads
through a session whose row-level security shows only what the card shows. Every refusal looks the same."""
from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from sqlalchemy import text
from sqlalchemy.orm import Session

from ..db import request_session
from ..security import hash_token
from ..services import actions as action_svc
from ..services import card as card_svc
from .deps import db, problem, require_member

router = APIRouter(tags=["emergency-card"])


class CreateCardIn(BaseModel):
    expires_in_days: int | None = Field(default=None, ge=1, le=365)


@router.post("/patients/{patient_id}/emergency-card", status_code=201)
def create_card(patient_id: UUID, body: CreateCardIn, request: Request, s: Session = Depends(db)):
    require_member(s, patient_id, can_manage=True)
    return card_svc.create_card(s, patient_id=patient_id, user_id=request.state.user_id, expires_in_days=body.expires_in_days)


@router.get("/patients/{patient_id}/emergency-card")
def list_cards(patient_id: UUID, s: Session = Depends(db)):
    require_member(s, patient_id)
    return {"cards": card_svc.list_cards(s, patient_id), "preview": card_svc.build_card(s, patient_id)}


def _card_patient(s: Session, card_id: UUID) -> UUID:
    pid = s.execute(text("SELECT patient_id FROM emergency_cards WHERE id = :i"), {"i": card_id}).scalar()
    if pid is None:
        raise problem(404, "not-found", "Not found")
    return pid


@router.post("/emergency-cards/{card_id}/revoke")
def revoke_card(card_id: UUID, request: Request, s: Session = Depends(db)):
    require_member(s, _card_patient(s, card_id))
    return card_svc.revoke_card(s, card_id=card_id, user_id=request.state.user_id)


class ShareIn(BaseModel):
    contact_name: str = Field(min_length=1, max_length=120)


@router.post("/emergency-cards/{card_id}/share", status_code=202)
def share_card(card_id: UUID, body: ShareIn, request: Request, s: Session = Depends(db)):
    """Asks first: this only queues the request. A member with approval rights must approve it before anything is sent."""
    pid = _card_patient(s, card_id)
    require_member(s, pid)
    return action_svc.propose_action(s, patient_id=pid, tool="share_emergency_card", actor_id=request.state.user_id,
                                     input={"card_id": str(card_id), "contact_name": body.contact_name.strip()})


# ---- public ----------------------------------------------------------------------------------------------------
_NO_STORE = {"Cache-Control": "no-store", "X-Robots-Tag": "noindex, nofollow"}


@router.get("/e/{token}")
def public_card(token: str, request: Request):
    # The web server forwards the visitor's address. It only feeds a hashed access-log column, never a decision.
    ip = request.headers.get("x-forwarded-for", "").split(",")[0].strip() or (request.client.host if request.client else "")
    with request_session() as s:     # committed on exit, so the access row is kept for every outcome
        row = s.execute(text("SELECT r_patient_id, r_outcome FROM app_resolve_emergency_card(:h, :ip, :ua)"),
                        {"h": hash_token(token[:200]), "ip": hash_token(ip), "ua": request.headers.get("user-agent", "")}).first()
    if row is None or row[1] != "ok" or row[0] is None:
        return JSONResponse({"available": False}, status_code=404, headers=_NO_STORE)
    with request_session(public_card_patient_id=row[0]) as s:
        data = card_svc.build_card(s, row[0])
    return JSONResponse({"available": True, **data}, headers=_NO_STORE)
