"""Patients, documents and the care plan read model (docs/15-api-spec.md)."""
from __future__ import annotations

import json
from datetime import date
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, File, Form, Request, UploadFile
from pydantic import BaseModel, Field
from sqlalchemy import text
from sqlalchemy.orm import Session

from ..clients.storage import get_storage, new_key, sha256, sniff_mime
from ..config import get_settings
from ..db import run_after_commit
from ..pipelines.documents import process_document
from ..services.documents import ingest_document
from ..services.patients import create_patient as new_patient
from ..services.audit import timeline, write_audit
from ..services.readmodel import age_of, item_detail, source_of
from .deps import db, problem, require_member
from ..services.tracking import duplicates as dup_groups
from .plan import awaiting_actions, omission_list, pending_changes

router = APIRouter(tags=["patients"])


class PatientIn(BaseModel):
    full_name: str = Field(min_length=1, max_length=160)
    date_of_birth: date | None = None
    sex: str | None = None
    preferred_language: str = "en"
    relationship_label: str | None = Field(default=None, max_length=60)


@router.post("/patients", status_code=201)
def create_patient(body: PatientIn, request: Request, s: Session = Depends(db, scope="function")):
    if body.preferred_language not in ("en", "hi", "mr"):
        raise problem(422, "validation-failed", "Language must be en, hi or mr")
    uid = request.state.user_id
    pid = new_patient(s, user_id=uid, full_name=body.full_name, date_of_birth=body.date_of_birth, sex=body.sex, language=body.preferred_language,
                         relationship_label=body.relationship_label, request_id=request.headers.get("x-request-id"))
    return {"id": str(pid), "full_name": body.full_name.strip()}


@router.get("/patients")
def list_patients(s: Session = Depends(db, scope="function")):
    rows = s.execute(text("""
        SELECT p.id, p.full_name, p.date_of_birth, p.preferred_language, p.is_synthetic
        FROM patients p WHERE p.deleted_at IS NULL ORDER BY p.created_at""")).mappings().all()
    return [{"id": str(r["id"]), "full_name": r["full_name"], "preferred_language": r["preferred_language"],
             "age": (date.today().year - r["date_of_birth"].year) if r["date_of_birth"] else None,
             "is_synthetic": r["is_synthetic"]} for r in rows]


@router.post("/patients/{patient_id}/documents", status_code=202)
async def upload_document(patient_id: UUID, request: Request, file: UploadFile = File(...),
                          doc_type: str = Form("other"), s: Session = Depends(db, scope="function")):
    require_member(s, patient_id)
    data = await file.read(get_settings().max_upload_bytes + 1)
    r = ingest_document(s, patient_id=patient_id, user_id=request.state.user_id, data=data, filename=file.filename or "", doc_type=doc_type)
    if r["new"]:
        doc_id = UUID(r["id"])
        run_after_commit(s, lambda: process_document(doc_id))      # only after this request's transaction commits
    return {"id": r["id"], "status": r["status"], "doc_type": r["doc_type"], "poll": f"/api/v1/documents/{r['id']}"}


@router.get("/patients/{patient_id}/documents")
def list_documents(patient_id: UUID, s: Session = Depends(db, scope="function")):
    require_member(s, patient_id)
    rows = s.execute(text("""SELECT id, doc_type, status, original_filename, page_count, created_at FROM documents
                             WHERE patient_id=:p AND deleted_at IS NULL ORDER BY created_at DESC"""), {"p": patient_id}).mappings().all()
    return [{**dict(r), "id": str(r["id"]), "created_at": r["created_at"].isoformat()} for r in rows]


@router.get("/documents/{doc_id}")
def get_document(doc_id: UUID, s: Session = Depends(db, scope="function")):
    r = s.execute(text("""SELECT id, patient_id, doc_type, status, original_filename, page_count, extracted_text
                          FROM documents WHERE id=:i"""), {"i": doc_id}).mappings().first()
    if not r:
        raise problem(404, "not-a-member", "Not found")
    return {"id": str(r["id"]), "patient_id": str(r["patient_id"]), "doc_type": r["doc_type"], "status": r["status"],
            "filename": r["original_filename"], "page_count": r["page_count"],
            "pages": [t.split("\n") for t in (r["extracted_text"] or "").split("\f")] if r["extracted_text"] else []}


_source = source_of


@router.get("/patients/{patient_id}/care-plan")
def care_plan(patient_id: UUID, s: Session = Depends(db, scope="function")):
    member = require_member(s, patient_id)
    pat = s.execute(text("SELECT id, full_name, date_of_birth, preferred_language FROM patients WHERE id=:p"), {"p": patient_id}).mappings().one()

    state = s.execute(text("SELECT state FROM v_allergy_effective WHERE patient_id=:p"), {"p": patient_id}).scalar_one()
    al_rows = s.execute(text("""
        SELECT a.allergy_key, a.substance, a.reaction, a.severity, sr.kind AS source_kind, sr.document_id, sr.page, sr.line_start, sr.quote,
               coalesce(d.original_filename, d.doc_type::text) AS doc_title
        FROM allergies a JOIN source_refs sr ON sr.id = a.source_ref_id LEFT JOIN documents d ON d.id = sr.document_id
        WHERE a.patient_id=:p AND a.is_current AND a.active"""), {"p": patient_id}).mappings().all()
    allergies = [{"allergy_key": str(r["allergy_key"]), "substance": r["substance"], "reaction": r["reaction"],
                  "severity": r["severity"], "source": _source(r)} for r in al_rows]

    item_rows = s.execute(text("""
        SELECT c.item_key, c.version, c.kind, c.title, c.details, c.alert_level, c.date_missing, c.confirmed_by, c.confirmed_at,
               u.display_name AS confirmer, sr.kind AS source_kind, sr.document_id, sr.page, sr.line_start, sr.quote,
               coalesce(d.original_filename, d.doc_type::text) AS doc_title
        FROM care_plan_items c JOIN source_refs sr ON sr.id = c.source_ref_id
        LEFT JOIN documents d ON d.id = sr.document_id LEFT JOIN users u ON u.id = c.confirmed_by
        WHERE c.patient_id=:p AND c.is_current AND c.status = 'active' ORDER BY c.kind, c.created_at"""), {"p": patient_id}).mappings().all()
    items = []
    for r in item_rows:
        det = r["details"] or {}
        detail = item_detail(det)
        items.append({"item_key": str(r["item_key"]), "version": r["version"], "kind": r["kind"], "title": r["title"],
                      "detail": detail, "schedule": det.get("schedule"), "alert_level": r["alert_level"],
                      "confirmed": r["confirmed_by"] is not None, "confirmed_by": r["confirmer"],
                      "date_missing": r["date_missing"], "source": _source(r)})

    conflicts = s.execute(text("""
        SELECT ac.id, ac.match, ci.title AS medicine, fo.body AS flag, qo.body AS question
        FROM allergy_conflicts ac JOIN care_plan_items ci ON ci.id = ac.care_plan_item_id
        LEFT JOIN generated_outputs fo ON fo.id = ac.flag_output_id AND fo.guard_status = 'pass'
        LEFT JOIN generated_outputs qo ON qo.id = ac.question_output_id AND qo.guard_status = 'pass'
        WHERE ac.patient_id=:p AND ac.status='open'"""), {"p": patient_id}).mappings().all()
    open_conflicts = [{"id": str(c["id"]), "match": c["match"], "medicine": c["medicine"],
                       "flag": c["flag"] or ("Could not check this ingredient against the reference list. Please ask the pharmacist."
                                             if c["match"] == "unresolved" else "Please ask the doctor or pharmacist about this."),
                       "doctor_question": c["question"] or "Please ask the doctor or pharmacist about this."} for c in conflicts]

    tl = s.execute(text("""SELECT id, occurred_at, summary, event_type, actor_type FROM timeline_events
                           WHERE patient_id=:p ORDER BY occurred_at DESC LIMIT 40"""), {"p": patient_id}).mappings().all()
    kind_map = {"document_uploaded": "document", "document_processed": "plan", "document_failed": "alert", "document_empty": "alert", "visit_started": "visit", "visit_processed": "visit", "visit_failed": "alert", "visit_consent_revoked": "alert", "follow_up_confirmed": "plan", "follow_up_done": "plan", "follow_up_dismissed": "plan", "document_injection": "alert", "omission_check": "plan",
                "item_confirmed": "approval", "change_confirmed": "approval", "change_rejected": "approval", "approval": "approval",
                "card_created": "card", "card_revoked": "card", "conflict_acknowledged": "alert", "omission_check": "plan",
                "omission_asked": "plan", "omission_resolved": "plan"}
    last = s.execute(text("SELECT max(created_at) FROM care_plan_items WHERE patient_id=:p"), {"p": patient_id}).scalar()
    return {
        "patient": {"id": str(pat["id"]), "name": pat["full_name"], "preferred_language": pat["preferred_language"],
                    "age": age_of(pat["date_of_birth"])},
        "reference_list_reviewed": False,
        "allergies": {"state": state, "items": allergies},
        "open_conflicts": open_conflicts, "items": items, "pending_changes": pending_changes(s, patient_id),
        "omissions": omission_list(s, patient_id),
        "approvals": awaiting_actions(s, patient_id) if member["can_approve"] else [],
        "can_approve": bool(member["can_approve"]),
        "duplicates": dup_groups(s, patient_id),
        "timeline": [{"id": str(t["id"]), "at": t["occurred_at"].isoformat(), "actor": t["actor_type"].title(),
                      "text": t["summary"], "kind": kind_map.get(t["event_type"], "plan")} for t in tl],
        "last_updated_at": (last or pat["date_of_birth"] or date.today()).isoformat() if last else None,
    }
