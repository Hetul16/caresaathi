"""Spoken and written explanations of one plan item (S3).

The model (or, offline, a template) only WORDS what is stored. The guard then checks the words: a source is attached, no forbidden
claim, the right language, every number is a stored number, and the medicine named is in the plan. If the guard blocks a draft the
family sees the safe fallback, and the draft is kept beside it for the trust panel."""
from __future__ import annotations

import json
import re
from typing import Any
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.orm import Session

from ..clients.models import ModelClient
from ..safety.guard import GuardContext, guard_output
from ..safety.normalize import normalize_medicine_name
from .audit import write_audit
from .errors import ServiceError
from .readmodel import item_detail, source_of


def store_output(s: Session, *, patient_id: UUID, output_type: str, language: str, shown: str, draft: str, status: str, reasons: list[str],
                 source_ref_ids: list[UUID], source_exempt: bool = False, model_call_id: UUID | None = None) -> UUID:
    oid = s.execute(text("""
        INSERT INTO generated_outputs (patient_id, output_type, language, body, draft_text, model_call_id, guard_status, guard_reasons, guard_report, source_exempt)
        VALUES (:p, CAST(:t AS output_type), CAST(:l AS lang_code), :b, :d, :mc, CAST(:g AS guard_status), CAST(:r AS jsonb), CAST(:rep AS jsonb), :ex)
        RETURNING id"""), {"p": patient_id, "t": output_type, "l": language, "b": shown, "d": draft, "mc": model_call_id, "g": status,
                           "r": json.dumps(reasons), "rep": json.dumps({"status": status, "reasons": reasons}), "ex": source_exempt}).scalar_one()
    for sid in source_ref_ids:
        s.execute(text("INSERT INTO output_sources (output_id, source_ref_id, patient_id) VALUES (:o, :s, :p) ON CONFLICT DO NOTHING"),
                  {"o": oid, "s": sid, "p": patient_id})
    return oid


def explain_item(s: Session, *, patient_id: UUID, item_key: UUID, language: str, user_id: UUID, client: ModelClient) -> dict[str, Any]:
    row = s.execute(text("""
        SELECT c.id, c.title, c.kind, c.details, c.alert_level, c.confirmed_by, c.source_ref_id, sr.kind AS source_kind, sr.document_id, sr.page,
               sr.line_start, sr.quote, coalesce(d.original_filename, d.doc_type::text) AS doc_title
        FROM care_plan_items c JOIN source_refs sr ON sr.id = c.source_ref_id LEFT JOIN documents d ON d.id = sr.document_id
        WHERE c.patient_id = :p AND c.item_key = :k AND c.is_current AND c.status = 'active'"""), {"p": patient_id, "k": item_key}).mappings().first()
    if row is None:
        raise ServiceError(404, "not-found", "Plan item not found")

    det = row["details"] or {}
    detail = item_detail(det)
    facts = {"title": row["title"], "kind": row["kind"], "detail": detail, "quote": row["quote"]}
    draft, usage = client.word("explanation", facts, language)

    names = {normalize_medicine_name(row["title"])}
    names |= {normalize_medicine_name(i.get("name", "")) for i in det.get("ingredients", []) if isinstance(i, dict)}
    mentions = [n for n in names if n and n in draft.lower()]
    ctx = GuardContext(language=language, source_ids=[str(row["source_ref_id"])], known_medicines=names, medicine_mentions=mentions,
                       stored_numbers={row["title"], detail or "", row["quote"] or ""},
                       stored_alert_level=row["alert_level"], shown_alert_level=row["alert_level"] if row["alert_level"] else None)
    result = guard_output(draft, ctx)
    from .plan import record_model_call
    oid = store_output(s, patient_id=patient_id, output_type="explanation", language=language, shown=result.text, draft=draft,
                       status="pass" if result.passed else "blocked", reasons=result.reasons, source_ref_ids=[row["source_ref_id"]],
                       model_call_id=record_model_call(s, patient_id, usage))
    write_audit(s, actor_type="user", actor_id=user_id, patient_id=patient_id, action="output.explanation_generated", entity_type="generated_output",
                entity_id=oid, after={"item": row["title"], "guard": "pass" if result.passed else "blocked"})
    return {"id": str(oid), "text": result.text, "language": language, "passed": result.passed, "reasons": result.reasons,
            "confirmed": row["confirmed_by"] is not None, "source": source_of(row)}


_WORD = re.compile(r"\w+")


def digits_of(*texts: str | None) -> set[str]:
    return {m for t in texts if t for m in re.findall(r"\d+(?:[.,]\d+)?", t)}
