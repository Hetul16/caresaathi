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
from ..services.audit import timeline, write_audit
from .deps import db, problem, require_member

router = APIRouter(tags=["patients"])


class PatientIn(BaseModel):
    full_name: str = Field(min_length=1, max_length=160)
    date_of_birth: date | None = None
    sex: str | None = None
    preferred_language: str = "en"
    relationship_label: str | None = Field(default=None, max_length=60)


@router.post("/patients", status_code=201)
def create_patient(body: PatientIn, request: Request, s: Session = Depends(db)):
    if body.preferred_language not in ("en", "hi", "mr"):
        raise problem(422, "validation-failed", "Language must be en, hi or mr")
    pid, uid = uuid4(), request.state.user_id
    # Insert without RETURNING: the SELECT policy only passes once the member row exists.
    s.execute(text("""INSERT INTO patients (id, full_name, date_of_birth, sex, preferred_language, created_by)
                      VALUES (:i, :n, :d, :s, CAST(:l AS pref_lang), :u)"""),
              {"i": pid, "n": body.full_name.strip(), "d": body.date_of_birth, "s": body.sex,
               "l": body.preferred_language, "u": uid})
    s.execute(text("""INSERT INTO family_members (patient_id, user_id, member_role, relationship_label, status,
                                                  can_approve, can_manage_members, can_view_recordings, notify_urgent)
                      VALUES (:p, :u, 'child', :r, 'active', true, true, true, true)"""),
              {"p": pid, "u": uid, "r": body.relationship_label})
    s.execute(text("INSERT INTO allergy_status (patient_id) VALUES (:p)"), {"p": pid})
    write_audit(s, actor_type="user", actor_id=uid, patient_id=pid, action="patient.created", entity_type="patient",
                entity_id=pid, request_id=request.headers.get("x-request-id"))
    return {"id": str(pid), "full_name": body.full_name.strip()}


@router.get("/patients")
def list_patients(s: Session = Depends(db)):
    rows = s.execute(text("""
        SELECT p.id, p.full_name, p.date_of_birth, p.preferred_language, p.is_synthetic
        FROM patients p WHERE p.deleted_at IS NULL ORDER BY p.created_at""")).mappings().all()
    return [{"id": str(r["id"]), "full_name": r["full_name"], "preferred_language": r["preferred_language"],
             "age": (date.today().year - r["date_of_birth"].year) if r["date_of_birth"] else None,
             "is_synthetic": r["is_synthetic"]} for r in rows]


@router.post("/patients/{patient_id}/documents", status_code=202)
async def upload_document(patient_id: UUID, request: Request, file: UploadFile = File(...),
                          doc_type: str = Form("other"), s: Session = Depends(db)):
    require_member(s, patient_id)
    cfg = get_settings()
    data = await file.read(cfg.max_upload_bytes + 1)
    if not data:
        raise problem(422, "validation-failed", "The file is empty")
    if len(data) > cfg.max_upload_bytes:
        raise problem(413, "validation-failed", "The file is too large")
    mime = sniff_mime(data)
    if mime is None and cfg.model_mode == "fake" and file.filename and file.filename.lower().endswith(".txt"):
        mime = "text/plain"          # development only: the offline reader takes plain text
    if mime is None:
        raise problem(415, "validation-failed", "Please upload a photo (JPEG or PNG) or a PDF")
    if doc_type not in ("prescription", "lab_report", "discharge_summary", "specialist_letter", "imaging_report", "other"):
        doc_type = "other"

    digest = sha256(data)
    dup = s.execute(text("SELECT id FROM documents WHERE patient_id=:p AND sha256=:h"), {"p": patient_id, "h": digest}).first()
    if dup:
        return {"id": str(dup[0]), "status": "duplicate", "poll": f"/api/v1/documents/{dup[0]}"}

    doc_id = uuid4()
    key = new_key(str(patient_id), "documents", mime.split("/")[-1].replace("jpeg", "jpg"))
    get_storage().put(key, data, mime)
    s.execute(text("""INSERT INTO documents (id, patient_id, doc_type, original_filename, mime_type, byte_size, sha256, storage_key, uploaded_by)
                      VALUES (:i, :p, CAST(:t AS doc_type), :f, :m, :b, :h, :k, :u)"""),
              {"i": doc_id, "p": patient_id, "t": doc_type, "f": (file.filename or "")[:200], "m": mime, "b": len(data),
               "h": digest, "k": key, "u": request.state.user_id})
    write_audit(s, actor_type="user", actor_id=request.state.user_id, patient_id=patient_id, action="document.uploaded",
                entity_type="document", entity_id=doc_id, after={"mime": mime, "bytes": len(data)})
    timeline(s, patient_id=patient_id, event_type="document_uploaded", actor_type="user", actor_id=request.state.user_id,
             summary=f"Uploaded {file.filename or 'a document'}", entity_type="document", entity_id=doc_id)
    # Start the pipeline only after this request's transaction commits.
    run_after_commit(s, lambda: process_document(doc_id))
    return {"id": str(doc_id), "status": "uploaded", "doc_type": doc_type, "poll": f"/api/v1/documents/{doc_id}"}


@router.get("/patients/{patient_id}/documents")
def list_documents(patient_id: UUID, s: Session = Depends(db)):
    require_member(s, patient_id)
    rows = s.execute(text("""SELECT id, doc_type, status, original_filename, page_count, created_at FROM documents
                             WHERE patient_id=:p AND deleted_at IS NULL ORDER BY created_at DESC"""), {"p": patient_id}).mappings().all()
    return [{**dict(r), "id": str(r["id"]), "created_at": r["created_at"].isoformat()} for r in rows]


@router.get("/documents/{doc_id}")
def get_document(doc_id: UUID, s: Session = Depends(db)):
    r = s.execute(text("""SELECT id, patient_id, doc_type, status, original_filename, page_count, extracted_text
                          FROM documents WHERE id=:i"""), {"i": doc_id}).mappings().first()
    if not r:
        raise problem(404, "not-a-member", "Not found")
    return {"id": str(r["id"]), "patient_id": str(r["patient_id"]), "doc_type": r["doc_type"], "status": r["status"],
            "filename": r["original_filename"], "page_count": r["page_count"],
            "pages": [t.split("\n") for t in (r["extracted_text"] or "").split("\f")] if r["extracted_text"] else []}


def _source(r) -> dict:
    return {"kind": "document", "document_id": str(r["document_id"]), "document_title": r["doc_title"] or "Document",
            "page": r["page"], "line_start": r["line_start"], "quote": r["quote"]}


@router.get("/patients/{patient_id}/care-plan")
def care_plan(patient_id: UUID, s: Session = Depends(db)):
    require_member(s, patient_id)
    pat = s.execute(text("SELECT id, full_name, date_of_birth, preferred_language FROM patients WHERE id=:p"), {"p": patient_id}).mappings().one()

    state = s.execute(text("SELECT state FROM v_allergy_effective WHERE patient_id=:p"), {"p": patient_id}).scalar_one()
    al_rows = s.execute(text("""
        SELECT a.allergy_key, a.substance, a.reaction, a.severity, sr.document_id, sr.page, sr.line_start, sr.quote,
               coalesce(d.original_filename, d.doc_type::text) AS doc_title
        FROM allergies a JOIN source_refs sr ON sr.id = a.source_ref_id LEFT JOIN documents d ON d.id = sr.document_id
        WHERE a.patient_id=:p AND a.is_current AND a.active"""), {"p": patient_id}).mappings().all()
    allergies = [{"allergy_key": str(r["allergy_key"]), "substance": r["substance"], "reaction": r["reaction"],
                  "severity": r["severity"], "source": _source(r)} for r in al_rows]

    item_rows = s.execute(text("""
        SELECT c.item_key, c.version, c.kind, c.title, c.details, c.alert_level, c.date_missing, c.confirmed_by, c.confirmed_at,
               u.display_name AS confirmer, sr.document_id, sr.page, sr.line_start, sr.quote,
               coalesce(d.original_filename, d.doc_type::text) AS doc_title
        FROM care_plan_items c JOIN source_refs sr ON sr.id = c.source_ref_id
        LEFT JOIN documents d ON d.id = sr.document_id LEFT JOIN users u ON u.id = c.confirmed_by
        WHERE c.patient_id=:p AND c.is_current AND c.status = 'active' ORDER BY c.kind, c.created_at"""), {"p": patient_id}).mappings().all()
    items = []
    for r in item_rows:
        det = r["details"] or {}
        detail = ", ".join(x for x in (det.get("frequency_text"), f"{det['duration_days']} days" if det.get("duration_days") else None,
                                       det.get("instructions_text")) if x) or None
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
    kind_map = {"document_uploaded": "document", "document_processed": "plan", "document_failed": "alert"}
    last = s.execute(text("SELECT max(created_at) FROM care_plan_items WHERE patient_id=:p"), {"p": patient_id}).scalar()
    return {
        "patient": {"id": str(pat["id"]), "name": pat["full_name"], "preferred_language": pat["preferred_language"],
                    "age": (date.today().year - pat["date_of_birth"].year) if pat["date_of_birth"] else None},
        "reference_list_reviewed": False,
        "allergies": {"state": state, "items": allergies},
        "open_conflicts": open_conflicts, "items": items, "pending_changes": [], "omissions": [], "approvals": [],
        "timeline": [{"id": str(t["id"]), "at": t["occurred_at"].isoformat(), "actor": t["actor_type"].title(),
                      "text": t["summary"], "kind": kind_map.get(t["event_type"], "plan")} for t in tl],
        "last_updated_at": (last or pat["date_of_birth"] or date.today()).isoformat() if last else None,
    }
