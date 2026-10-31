"""Outcomes board endpoints (C6, D-52): the board, and recording a named person's answer to a flag."""
from __future__ import annotations

from typing import Literal
from uuid import UUID

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from ..services import outcomes as svc
from .deps import db, require_member

router = APIRouter(tags=["outcomes"])


class AnswerIn(BaseModel):
    subject_kind: Literal["allergy_conflict", "reconciliation_flag"]
    subject_id: UUID
    doctor_message_id: UUID | None = None
    answer_text: str | None = Field(default=None, max_length=1500)
    answered_by: str | None = Field(default=None, max_length=80)


@router.get("/patients/{patient_id}/outcomes")
def board(patient_id: UUID, s: Session = Depends(db, scope="function")):
    require_member(s, patient_id)
    return svc.board(s, patient_id)


@router.post("/patients/{patient_id}/outcomes/answers", status_code=201)
def answer(patient_id: UUID, body: AnswerIn, request: Request, s: Session = Depends(db, scope="function")):
    """Needs approval rights: recording an answer closes the flag, so it is a named person's decision."""
    require_member(s, patient_id, can_approve=True)
    return svc.record_answer(s, patient_id=patient_id, user_id=request.state.user_id, subject_kind=body.subject_kind, subject_id=body.subject_id,
                             answer_text=body.answer_text, answered_by=body.answered_by, doctor_message_id=body.doctor_message_id)
