"""Tracker endpoints: follow-ups, refill estimates, medicine history, duplicate ingredients and the fridge sheet."""
from __future__ import annotations

from typing import Literal
from uuid import UUID

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel
from sqlalchemy.orm import Session

from ..services import tracking as svc
from .deps import db, require_member
from .plan import _patient_of

router = APIRouter(tags=["tracking"])


@router.get("/patients/{patient_id}/follow-ups")
def follow_ups(patient_id: UUID, s: Session = Depends(db)):
    require_member(s, patient_id)
    return svc.list_follow_ups(s, patient_id)


class FollowUpAction(BaseModel):
    action: Literal["confirm", "done", "dismiss"]


@router.post("/follow-ups/{follow_up_id}/decision")
def decide_follow_up(follow_up_id: UUID, body: FollowUpAction, request: Request, s: Session = Depends(db)):
    # Confirming needs approval rights (a named person vouches for the date); closing one does not.
    require_member(s, _patient_of(s, "follow_ups", follow_up_id), can_approve=body.action == "confirm")
    return svc.decide_follow_up(s, follow_up_id=follow_up_id, action=body.action, user_id=request.state.user_id)


@router.get("/patients/{patient_id}/supply")
def supply(patient_id: UUID, s: Session = Depends(db)):
    require_member(s, patient_id)
    return svc.list_supply(s, patient_id)


@router.post("/supply/{supply_id}/confirm")
def confirm_supply(supply_id: UUID, request: Request, s: Session = Depends(db)):
    require_member(s, _patient_of(s, "supply_records", supply_id), can_approve=True)
    return svc.confirm_supply(s, supply_id=supply_id, user_id=request.state.user_id)


@router.get("/patients/{patient_id}/medicine-history")
def medicine_history(patient_id: UUID, s: Session = Depends(db)):
    require_member(s, patient_id)
    return svc.medicine_history(s, patient_id)


@router.get("/patients/{patient_id}/duplicates")
def duplicates(patient_id: UUID, s: Session = Depends(db)):
    require_member(s, patient_id)
    return svc.duplicates(s, patient_id)


@router.get("/patients/{patient_id}/fridge-sheet")
def fridge_sheet(patient_id: UUID, s: Session = Depends(db)):
    require_member(s, patient_id)
    return svc.fridge_sheet(s, patient_id)
