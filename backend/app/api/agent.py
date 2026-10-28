"""Care crew endpoints (C2, D-47): start a run, and read the live trace."""
from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from ..agent import runner
from .deps import db, require_member

router = APIRouter(tags=["care-crew"])


class RunIn(BaseModel):
    goal: str = Field(min_length=1, max_length=300)


@router.post("/patients/{patient_id}/agent/runs", status_code=202)
def start(patient_id: UUID, body: RunIn, request: Request, s: Session = Depends(db)):
    require_member(s, patient_id)
    return runner.start_run(s, patient_id=patient_id, user_id=request.state.user_id, goal=body.goal)


@router.get("/patients/{patient_id}/agent/runs")
def runs(patient_id: UUID, s: Session = Depends(db)):
    require_member(s, patient_id)
    return {"runs": runner.list_runs(s, patient_id)}
