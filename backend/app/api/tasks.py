"""Family task board endpoints (C8, D-59). Any member can add, assign and finish a task."""
from __future__ import annotations

from datetime import date
from uuid import UUID

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel, Field
from sqlalchemy import text
from sqlalchemy.orm import Session

from ..services import tasks as svc
from .deps import db, problem, require_member

router = APIRouter(tags=["tasks"])


class TaskIn(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    assigned_to: UUID | None = None
    due_date: date | None = None


@router.get("/patients/{patient_id}/tasks")
def list_tasks(patient_id: UUID, s: Session = Depends(db, scope="function")):
    require_member(s, patient_id)
    return {"tasks": svc.list_tasks(s, patient_id)}


@router.post("/patients/{patient_id}/tasks", status_code=201)
def create(patient_id: UUID, body: TaskIn, request: Request, s: Session = Depends(db, scope="function")):
    require_member(s, patient_id)
    return svc.create_task(s, patient_id=patient_id, user_id=request.state.user_id, title=body.title, assigned_to=body.assigned_to, due_date=body.due_date)


@router.post("/tasks/{task_id}/done")
def done(task_id: UUID, request: Request, s: Session = Depends(db, scope="function")):
    pid = s.execute(text("SELECT patient_id FROM care_tasks WHERE id = :i"), {"i": task_id}).scalar()
    if pid is None:
        raise problem(404, "not-found", "Not found")
    require_member(s, pid)
    return svc.complete_task(s, task_id=task_id, user_id=request.state.user_id)
