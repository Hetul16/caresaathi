"""Two-reader check endpoints (A5, D-54): list the medicines on which two readings differ, and let a named person choose."""
from __future__ import annotations

from typing import Literal
from uuid import UUID

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.orm import Session

from ..clients.models import get_model_client
from ..services import second_reads as svc
from .deps import db, problem, require_member

router = APIRouter(tags=["two-reader"])


class ChooseIn(BaseModel):
    choice: Literal["a", "b", "neither"]


@router.get("/patients/{patient_id}/second-reads")
def list_reads(patient_id: UUID, s: Session = Depends(db, scope="function")):
    require_member(s, patient_id)
    return {"reads": svc.list_second_reads(s, patient_id)}


@router.post("/second-reads/{read_id}/choose")
def choose(read_id: UUID, body: ChooseIn, request: Request, s: Session = Depends(db, scope="function")):
    """Needs approval rights: choosing a reading puts a medicine into the plan, so it is a named person's decision."""
    pid = s.execute(text("SELECT patient_id FROM second_reads WHERE id = :i"), {"i": read_id}).scalar()
    if pid is None:
        raise problem(404, "not-found", "Not found")
    require_member(s, pid, can_approve=True)
    return svc.choose(s, second_read_id=read_id, choice=body.choice, user_id=request.state.user_id, client=get_model_client())
