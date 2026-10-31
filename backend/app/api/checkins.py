"""Daily check-in endpoints (C7, D-58): today's doses and how the patient says they feel. Any member of the family may record; the
screen for the elder uses the family's signed-in session on the elder's device."""
from __future__ import annotations

from typing import Literal
from uuid import UUID

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from ..services import checkins as svc
from .deps import db, require_member

router = APIRouter(tags=["check-ins"])


class DoseIn(BaseModel):
    item_key: UUID
    slot: Literal["morning", "noon", "evening", "night"]
    status: Literal["taken", "not_taken"]


class WellbeingIn(BaseModel):
    pain: int | None = Field(default=None, ge=0, le=10)
    note: str | None = Field(default=None, max_length=300)


@router.get("/patients/{patient_id}/today")
def today(patient_id: UUID, s: Session = Depends(db, scope="function")):
    require_member(s, patient_id)
    return svc.today_view(s, patient_id)


@router.post("/patients/{patient_id}/doses", status_code=201)
def dose(patient_id: UUID, body: DoseIn, request: Request, s: Session = Depends(db, scope="function")):
    require_member(s, patient_id)
    return svc.log_dose(s, patient_id=patient_id, user_id=request.state.user_id, item_key=body.item_key, slot=body.slot, status=body.status)


@router.post("/patients/{patient_id}/wellbeing", status_code=201)
def wellbeing(patient_id: UUID, body: WellbeingIn, request: Request, s: Session = Depends(db, scope="function")):
    require_member(s, patient_id)
    return svc.save_wellbeing(s, patient_id=patient_id, user_id=request.state.user_id, pain=body.pain, note=body.note)


@router.get("/patients/{patient_id}/wellbeing")
def history(patient_id: UUID, days: int = 14, s: Session = Depends(db, scope="function")):
    require_member(s, patient_id)
    return svc.wellbeing_history(s, patient_id, days=max(1, min(days, 90)))
