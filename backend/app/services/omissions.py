"""Omission catch at care transitions (S10, docs/14-data-mapping.md section 14.3).

Code compares ingredient sets between the earlier plan and a new discharge summary. The model only words the
question for the doctor, and the guard checks the words. An incomplete or unknown-completeness document raises
nothing, and an unresolved ingredient is "could not compare", never a flag (safety invariant 10)."""
from __future__ import annotations

from uuid import UUID

from sqlalchemy import text
from sqlalchemy.orm import Session

from ..clients.models import ModelClient
from ..safety.guard import GuardContext, guard_output
from ..safety.normalize import normalize_medicine_name
from ..safety.reconcile import MedItem, find_omissions
from .audit import timeline, write_audit
from .errors import ServiceError
from .plan import _store_output, ingredients_of, record_model_call
from .resolve import resolve_substance

TRANSITION_DOC_TYPES = {"discharge_summary"}


def _previous_items(s: Session, patient_id: UUID, document_id: UUID) -> list[tuple[MedItem, UUID]]:
    """Current medicines that did not come from this document, with the source of each."""
    rows = s.execute(text("""
        SELECT c.id, c.item_key, c.title, c.source_ref_id,
               coalesce(array_agg(mi.ingredient_normalized) FILTER (WHERE mi.id IS NOT NULL), '{}') AS ings,
               bool_or(mi.substance_id IS NULL) FILTER (WHERE mi.id IS NOT NULL) AS any_unresolved
        FROM care_plan_items c
        JOIN source_refs sr ON sr.id = c.source_ref_id
        LEFT JOIN medicine_ingredients mi ON mi.item_id = c.id
        WHERE c.patient_id = :p AND c.is_current AND c.status = 'active' AND c.kind = 'medicine'
          AND sr.document_id IS DISTINCT FROM :d
        GROUP BY c.id, c.item_key, c.title, c.source_ref_id"""), {"p": patient_id, "d": document_id}).mappings().all()
    return [(MedItem(key=str(r["id"]), title=r["title"], ingredients=frozenset(r["ings"]),
                     unresolved=bool(r["any_unresolved"]), source_id=str(r["source_ref_id"])), r["id"]) for r in rows]


def _incoming_items(s: Session, items) -> list[MedItem]:
    out: list[MedItem] = []
    for n, it in enumerate(items):
        if it.kind != "medicine":
            continue
        ings = [normalize_medicine_name(name) for name, _ in ingredients_of("medicine", it.title, dict(it.details or {}))]
        ings = [i for i in ings if i]
        out.append(MedItem(key=f"incoming-{n}", title=it.title, ingredients=frozenset(ings),
                           unresolved=any(resolve_substance(s, i) is None for i in ings) or not ings))
    return out


def raise_omission_flags(s: Session, *, patient_id: UUID, document_id: UUID, doc_type: str, items, client: ModelClient,
                         language: str = "en") -> list[UUID]:
    if doc_type not in TRANSITION_DOC_TYPES:
        return []
    completeness = s.execute(text("SELECT completeness FROM documents WHERE id = :d"), {"d": document_id}).scalar_one()
    previous = _previous_items(s, patient_id, document_id)
    if not previous:
        return []
    result = find_omissions([p for p, _ in previous], _incoming_items(s, items), document_complete=(completeness == "complete"))
    if result.skipped_reason:
        return []
    id_of = {p.key: pid for p, pid in previous}

    created: list[UUID] = []
    for cand in result.candidates:
        prev_id = id_of[cand.key]
        if s.execute(text("SELECT 1 FROM reconciliation_flags WHERE previous_item_id = :i AND new_document_id = :d"),
                     {"i": prev_id, "d": document_id}).first():
            continue
        text_out, usage = client.word("omission_question", {"medicine": cand.title}, language)
        ctx = GuardContext(language=language, source_ids=[cand.source_id], check_extra_wording=True)
        qid = _store_output(s, patient_id, "doctor_question", language, guard_output(text_out, ctx), [cand.source_id],
                            record_model_call(s, patient_id, usage))
        fid = s.execute(text("""
            INSERT INTO reconciliation_flags (patient_id, previous_item_id, previous_source_ref_id, new_document_id,
                                              medicine_title, question_output_id)
            VALUES (:p, :i, :src, :d, :t, :q) RETURNING id"""),
            {"p": patient_id, "i": prev_id, "src": cand.source_id, "d": document_id, "t": cand.title, "q": qid}).scalar_one()
        created.append(fid)
        write_audit(s, actor_type="system", actor_id=None, patient_id=patient_id, action="reconciliation.flag_opened",
                    entity_type="reconciliation_flag", entity_id=fid, after={"medicine": cand.title, "document_id": str(document_id)})
    if created or result.could_not_compare:
        parts = []
        if created:
            parts.append(f"{len(created)} medicine{'s' if len(created) != 1 else ''} on the earlier list are not on this document")
        if result.could_not_compare:
            parts.append(f"{len(result.could_not_compare)} could not be compared")
        timeline(s, patient_id=patient_id, event_type="omission_check", actor_type="system", actor_id=None,
                 summary="Compared with the earlier plan: " + ", ".join(parts) + ". We are only asking the doctor.",
                 entity_type="document", entity_id=document_id)
    return created


def set_flag_state(s: Session, *, flag_id: UUID, state: str, user_id: UUID) -> dict:
    row = s.execute(text("SELECT id, patient_id, medicine_title, state FROM reconciliation_flags WHERE id = :i FOR UPDATE"),
                    {"i": flag_id}).mappings().first()
    if row is None:
        raise ServiceError(404, "not-found", "Flag not found")
    s.execute(text("""UPDATE reconciliation_flags SET state = :st, state_changed_by = :u, state_changed_at = now() WHERE id = :i"""),
              {"st": state, "u": user_id, "i": flag_id})
    write_audit(s, actor_type="user", actor_id=user_id, patient_id=row["patient_id"], action=f"reconciliation.flag_{state}",
                entity_type="reconciliation_flag", entity_id=flag_id, before={"state": row["state"]}, after={"state": state})
    timeline(s, patient_id=row["patient_id"], event_type="omission_" + state, actor_type="user", actor_id=user_id,
             summary=("Question asked about " if state == "asked" else "Settled with the doctor: ") + row["medicine_title"],
             entity_type="reconciliation_flag", entity_id=flag_id)
    return {"id": str(flag_id), "state": state}
