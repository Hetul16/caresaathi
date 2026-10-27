"""Loads the fictional demo family for the signed-in user. Synthetic data only; switched off with ALLOW_DEMO_SEED=false."""
from __future__ import annotations

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from ..config import get_settings
from ..demo import start_demo
from .deps import db, problem

router = APIRouter(tags=["demo"])


class SeedIn(BaseModel):
    # The users table is out of reach of the app role, so the caller sends the name to record on the mock visit's consent.
    display_name: str = Field(default="A family member", max_length=120)


@router.post("/demo/seed", status_code=202)
def seed(body: SeedIn, request: Request, s: Session = Depends(db)):
    if not get_settings().allow_demo_seed:
        raise problem(404, "not-found", "Not found")
    return start_demo(s, user_id=request.state.user_id, display_name=body.display_name.strip() or "A family member")
