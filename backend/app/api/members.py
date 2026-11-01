"""Family members and invitations."""
from __future__ import annotations

from typing import Literal
from uuid import UUID

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from ..services import members as svc
from .deps import db, require_member
from .plan import _patient_of

router = APIRouter(tags=["members"])


@router.get("/patients/{patient_id}/members")
def members(patient_id: UUID, s: Session = Depends(db, scope="function")):
    require_member(s, patient_id)
    return svc.list_members(s, patient_id)


class InviteIn(BaseModel):
    member_role: Literal["patient", "child", "spouse", "relative", "attendant", "nurse", "other"] = "relative"
    relationship_label: str | None = Field(default=None, max_length=60)
    can_approve: bool = False
    can_view_recordings: bool = False
    can_manage_members: bool = False
    expires_in_days: int = Field(default=7, ge=1, le=30)


@router.post("/patients/{patient_id}/invites", status_code=201)
def create_invite(patient_id: UUID, body: InviteIn, request: Request, s: Session = Depends(db, scope="function")):
    require_member(s, patient_id, can_manage=True)
    # The patient is invited as a member of their own circle with no rights over it, whatever the form sent. The database refuses the row
    # too (migration 0015); dropping the flags here means the inviter gets the invitation rather than a constraint error (D-66).
    is_patient = body.member_role == "patient"
    return svc.create_invite(s, patient_id=patient_id, user_id=request.state.user_id, member_role=body.member_role, relationship_label=body.relationship_label,
                             can_approve=body.can_approve and not is_patient, can_view_recordings=body.can_view_recordings and not is_patient,
                             can_manage_members=body.can_manage_members and not is_patient, expires_in_days=body.expires_in_days)


@router.get("/patients/{patient_id}/invites")
def invites(patient_id: UUID, s: Session = Depends(db, scope="function")):
    require_member(s, patient_id, can_manage=True)
    return svc.list_invites(s, patient_id)


@router.post("/invites/{invite_id}/revoke")
def revoke(invite_id: UUID, request: Request, s: Session = Depends(db, scope="function")):
    require_member(s, _patient_of(s, "member_invites", invite_id), can_manage=True)
    return svc.revoke_invite(s, invite_id=invite_id, user_id=request.state.user_id)


class AcceptIn(BaseModel):
    code: str = Field(min_length=8, max_length=200)


@router.post("/invites/accept")
def accept(body: AcceptIn, request: Request, s: Session = Depends(db, scope="function")):
    return svc.accept_invite(s, code=body.code.strip(), user_id=request.state.user_id)


class MemberPatch(BaseModel):
    can_approve: bool | None = None
    can_view_recordings: bool | None = None
    can_manage_members: bool | None = None
    remove: bool = False


@router.patch("/members/{member_id}")
def patch_member(member_id: UUID, body: MemberPatch, request: Request, s: Session = Depends(db, scope="function")):
    require_member(s, _patient_of(s, "family_members", member_id), can_manage=True)
    return svc.update_member(s, member_id=member_id, user_id=request.state.user_id, can_approve=body.can_approve,
                             can_view_recordings=body.can_view_recordings, can_manage_members=body.can_manage_members, remove=body.remove)
