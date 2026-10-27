"""Decisions on the care plan: confirm items, decide pending changes, acknowledge allergy conflicts, omission flags,
and the approvals screen (docs/15-api-spec.md). Reads need membership; every decision needs approval rights."""
from __future__ import annotations

from typing import Literal
from uuid import UUID

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel, Field
from sqlalchemy import text
from sqlalchemy.orm import Session

from ..clients.models import get_model_client
from ..services import actions as action_svc
from ..services import changes as change_svc
from ..services import omissions as omission_svc
from ..services.audit import write_audit
from ..services.readmodel import source_of
from .deps import db, problem, require_member

router = APIRouter(tags=["plan"])


def _patient_of(s: Session, table: str, row_id: UUID) -> UUID:
    """Which patient a row belongs to. RLS already hides other families' rows, so a miss is a 404."""
    pid = s.execute(text(f"SELECT patient_id FROM {table} WHERE id = :i"), {"i": row_id}).scalar()  # table is a literal below
    if pid is None:
        raise problem(404, "not-found", "Not found")
    return pid


# ---- confirming plan items -------------------------------------------------------------------------------------
@router.post("/patients/{patient_id}/plan-items/{item_key}/confirm")
def confirm_item(patient_id: UUID, item_key: UUID, request: Request, s: Session = Depends(db)):
    require_member(s, patient_id, can_approve=True)
    return change_svc.confirm_item(s, patient_id=patient_id, item_key=item_key, user_id=request.state.user_id)


# ---- pending changes -------------------------------------------------------------------------------------------
def pending_changes(s: Session, patient_id: UUID) -> list[dict]:
    rows = s.execute(text("""
        SELECT pc.id, pc.change_type, pc.before_state, pc.after_state, pc.requires_confirmation, sr.kind AS source_kind, sr.document_id,
               sr.page, sr.line_start, sr.quote, coalesce(d.original_filename, d.doc_type::text) AS doc_title
        FROM plan_changes pc JOIN source_refs sr ON sr.id = pc.source_ref_id LEFT JOIN documents d ON d.id = sr.document_id
        WHERE pc.patient_id = :p AND pc.status = 'pending' ORDER BY pc.created_at"""), {"p": patient_id}).mappings().all()
    out = []
    for r in rows:
        before, after = r["before_state"] or {}, r["after_state"] or {}
        out.append({"id": str(r["id"]), "change_type": r["change_type"],
                    "title": after.get("title") or before.get("title") or after.get("substance") or "Change",
                    "before": _summary(before), "after": _summary(after),
                    "source": source_of(r), "requires_confirmation": r["requires_confirmation"]})
    return out


def _summary(state: dict) -> str | None:
    det = state.get("details") or {}
    parts = [det.get("dose_text"), det.get("frequency_text"), det.get("instructions_text")]
    text_ = ", ".join(str(p) for p in parts if p)
    return text_ or state.get("reaction") or None


@router.get("/patients/{patient_id}/plan-changes")
def list_plan_changes(patient_id: UUID, s: Session = Depends(db)):
    require_member(s, patient_id)
    return pending_changes(s, patient_id)


class DecisionIn(BaseModel):
    decision: Literal["confirm", "reject"]
    comment: str | None = Field(default=None, max_length=500)


@router.post("/plan-changes/{change_id}/decision")
def decide_change(change_id: UUID, body: DecisionIn, request: Request, s: Session = Depends(db)):
    require_member(s, _patient_of(s, "plan_changes", change_id), can_approve=True)
    return change_svc.decide_change(s, change_id=change_id, decision=body.decision, comment=body.comment,
                                    user_id=request.state.user_id, client=get_model_client())


# ---- allergy conflicts -----------------------------------------------------------------------------------------
class AckIn(BaseModel):
    note: str | None = Field(default=None, max_length=500)


@router.post("/allergy-conflicts/{conflict_id}/acknowledge")
def acknowledge_conflict(conflict_id: UUID, body: AckIn, request: Request, s: Session = Depends(db)):
    require_member(s, _patient_of(s, "allergy_conflicts", conflict_id))
    return change_svc.acknowledge_conflict(s, conflict_id=conflict_id, user_id=request.state.user_id, note=body.note)


# ---- omission flags (S10) --------------------------------------------------------------------------------------
def omission_list(s: Session, patient_id: UUID) -> list[dict]:
    rows = s.execute(text("""
        SELECT f.id, f.medicine_title, f.state, qo.body AS question, qo.guard_status, nd.original_filename AS new_doc,
               sr.kind AS source_kind, sr.document_id, sr.page, sr.line_start, sr.quote,
               coalesce(od.original_filename, od.doc_type::text) AS doc_title
        FROM reconciliation_flags f
        JOIN source_refs sr ON sr.id = f.previous_source_ref_id
        LEFT JOIN documents od ON od.id = sr.document_id
        JOIN documents nd ON nd.id = f.new_document_id
        LEFT JOIN generated_outputs qo ON qo.id = f.question_output_id
        WHERE f.patient_id = :p AND f.state <> 'resolved' ORDER BY f.created_at"""), {"p": patient_id}).mappings().all()
    fallback = "Could you confirm whether this medicine is meant to continue, or was left off on purpose or by mistake? We are only asking."
    return [{"id": str(r["id"]), "medicine": r["medicine_title"], "state": r["state"], "previous_source": source_of(r),
             "new_document": r["new_doc"] or "the new document",
             "question": r["question"] if r["guard_status"] == "pass" and r["question"] else fallback} for r in rows]


@router.get("/patients/{patient_id}/reconciliation")
def reconciliation(patient_id: UUID, s: Session = Depends(db)):
    require_member(s, patient_id)
    return omission_list(s, patient_id)


class FlagStateIn(BaseModel):
    state: Literal["asked", "resolved"]


@router.post("/reconciliation-flags/{flag_id}/state")
def set_flag_state(flag_id: UUID, body: FlagStateIn, request: Request, s: Session = Depends(db)):
    require_member(s, _patient_of(s, "reconciliation_flags", flag_id))
    return omission_svc.set_flag_state(s, flag_id=flag_id, state=body.state, user_id=request.state.user_id)


# ---- a person vouches that a document is whole -------------------------------------------------------------------
class CompletenessIn(BaseModel):
    completeness: Literal["complete", "incomplete", "unknown"]


@router.post("/documents/{doc_id}/completeness")
def set_completeness(doc_id: UUID, body: CompletenessIn, request: Request, s: Session = Depends(db)):
    pid = _patient_of(s, "documents", doc_id)
    require_member(s, pid, can_approve=True)
    s.execute(text("UPDATE documents SET completeness = :c WHERE id = :i"), {"c": body.completeness, "i": doc_id})
    write_audit(s, actor_type="user", actor_id=request.state.user_id, patient_id=pid, action="document.completeness_set",
                entity_type="document", entity_id=doc_id, after={"completeness": body.completeness})
    return {"id": str(doc_id), "completeness": body.completeness}


# ---- approvals -------------------------------------------------------------------------------------------------
def awaiting_actions(s: Session, patient_id: UUID) -> list[dict]:
    rows = s.execute(text("""SELECT id, tool, input, created_at FROM actions
                             WHERE patient_id = :p AND status = 'awaiting_approval' ORDER BY created_at"""), {"p": patient_id}).mappings().all()
    return [{"id": str(r["id"]), "tool": r["tool"], "summary": action_svc.describe_action(r["tool"], r["input"] or {}),
             "requested_at": r["created_at"].isoformat(), "status": "awaiting_approval"} for r in rows]


@router.get("/patients/{patient_id}/actions")
def list_actions(patient_id: UUID, s: Session = Depends(db)):
    require_member(s, patient_id, can_approve=True)
    return awaiting_actions(s, patient_id)


class ActionDecisionIn(BaseModel):
    comment: str | None = Field(default=None, max_length=500)


@router.post("/actions/{action_id}/approve")
def approve_action(action_id: UUID, body: ActionDecisionIn, request: Request, s: Session = Depends(db)):
    require_member(s, _patient_of(s, "actions", action_id), can_approve=True)
    return action_svc.decide_action(s, action_id=action_id, approve=True, user_id=request.state.user_id, comment=body.comment)


@router.post("/actions/{action_id}/refuse")
def refuse_action(action_id: UUID, body: ActionDecisionIn, request: Request, s: Session = Depends(db)):
    require_member(s, _patient_of(s, "actions", action_id), can_approve=True)
    return action_svc.decide_action(s, action_id=action_id, approve=False, user_id=request.state.user_id, comment=body.comment)
