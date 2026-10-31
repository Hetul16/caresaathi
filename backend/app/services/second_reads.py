"""Two-reader check (A5, D-54). When the first reading of a document says part of it was unclear, a second, independent reading is made
and the two are compared by code (`safety/second_read.py`). A medicine on which the readers disagree, in name, strength, schedule, duration or
quantity, is NOT applied to the plan. Both readings are shown beside the page line, and a named person chooses one or neither. The model never
merges or picks: the choice is a person's, and picking a reading goes through the same confirmation path as any other plan change."""
from __future__ import annotations

import json
from typing import Any
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.orm import Session

from ..clients.models import ModelClient, ModelError, PageText
from ..safety.normalize import brand_key, normalize_medicine_name
from ..safety.second_read import compare_readings, pair_readings
from ..safety.validate import ValidatedExtraction, validate_extraction
from .audit import timeline, write_audit
from .changes import decide_change
from .errors import ServiceError
from .plan import _item_key_match, ingredients_of, make_source_ref, record_model_call


def _reading(item: Any) -> dict[str, Any]:
    det = dict(item.details or {})
    ings = [i for i in (det.get("ingredients") or []) if isinstance(i, dict)]
    qty = det.get("quantity") if isinstance(det.get("quantity"), dict) else {}
    return {"title": item.title, "name": brand_key(item.title) or normalize_medicine_name(item.title),
            "strength": (ings[0].get("strength") if ings else None) or None, "frequency": det.get("frequency_text"),
            "duration": det.get("duration_days"), "quantity": qty.get("value"),
            "source": {"page": item.source.page, "line_start": item.source.line_start, "quote": item.source.quote}, "details": det}


def _medicines(validated: ValidatedExtraction) -> list[tuple[int | None, dict]]:
    if validated.data is None:
        return []
    return [(i, _reading(it)) for i, it in enumerate(validated.data.items) if it.kind == "medicine" and i not in validated.rejected_items]


def run_second_read(s: Session, *, patient_id: UUID, document_id: UUID, pages: list[PageText], validated: ValidatedExtraction,
                    client: ModelClient) -> int:
    """Called by the document pipeline before the first reading is applied. Returns how many medicines are held for a person.
    It runs only when the first reader reported unclear text: clear documents pay nothing and change nothing."""
    if validated.data is None or not validated.data.unreadable:
        return 0
    try:
        raw2, usage = client.second_read_document(pages)
    except ModelError:
        return 0                                   # no second opinion available: the first reading's own review flag still stands
    record_model_call(s, patient_id, usage)
    v2 = validate_extraction(raw2, {p.page: p.text for p in pages})
    if not v2.ok or v2.data is None:
        return 0
    a, b = _medicines(validated), _medicines(v2)
    index = {id(r): i for i, r in a}
    held = 0
    for ra, rb in pair_readings([r for _, r in a], [r for _, r in b]):
        diff = ["name"] if (ra is None or rb is None) else compare_readings(ra, rb)
        if not diff:
            continue
        first = ra or rb
        title = (first.get("name") or first["title"]).title()      # a neutral heading: the two readings may carry different strengths
        s.execute(text("""INSERT INTO second_reads (patient_id, document_id, item_title, reading_a, reading_b, differing_fields)
                          VALUES (:p, :d, :t, CAST(:a AS jsonb), CAST(:b AS jsonb), :f)"""),
                  {"p": patient_id, "d": document_id, "t": title, "a": json.dumps(ra or {}, default=str), "b": json.dumps(rb or {}, default=str), "f": diff})
        if ra is not None:
            validated.review_items[index[id(ra)]] = "two_reader_disagreement"
        held += 1
    if held:
        validated.needs_review = True
        timeline(s, patient_id=patient_id, event_type="second_read", actor_type="system", actor_id=None,
                 summary=f"Two readings of a document differ on {held} medicine{'s' if held != 1 else ''}. Please look at the original and choose.",
                 entity_type="document", entity_id=document_id)
    return held


def list_second_reads(s: Session, patient_id: UUID) -> list[dict[str, Any]]:
    rows = s.execute(text("""
        SELECT r.id, r.item_title, r.reading_a, r.reading_b, r.differing_fields, r.chosen_reading, r.chosen_at, u.display_name AS chooser,
               r.created_at, coalesce(d.original_filename, d.doc_type::text) AS doc_title
        FROM second_reads r JOIN documents d ON d.id = r.document_id LEFT JOIN users u ON u.id = r.chosen_by
        WHERE r.patient_id = :p ORDER BY (r.chosen_reading IS NOT NULL), r.created_at"""), {"p": patient_id}).mappings().all()

    def shown(x: dict) -> dict | None:
        if not x:
            return None
        return {"title": x.get("title"), "strength": x.get("strength"), "frequency": x.get("frequency"), "duration": x.get("duration"),
                "quantity": x.get("quantity"), "quote": (x.get("source") or {}).get("quote"), "page": (x.get("source") or {}).get("page"),
                "line": (x.get("source") or {}).get("line_start")}
    return [{"id": str(r["id"]), "medicine": r["item_title"], "document": r["doc_title"], "differs_in": list(r["differing_fields"]),
             "reading_a": shown(r["reading_a"]), "reading_b": shown(r["reading_b"]), "chosen": r["chosen_reading"], "chosen_by": r["chooser"],
             "chosen_at": r["chosen_at"].isoformat() if r["chosen_at"] else None} for r in rows]


def choose(s: Session, *, second_read_id: UUID, choice: str, user_id: UUID, client: ModelClient) -> dict[str, Any]:
    r = s.execute(text("SELECT * FROM second_reads WHERE id = :i FOR UPDATE"), {"i": second_read_id}).mappings().first()
    if r is None:
        raise ServiceError(404, "not-found", "Not found")
    if r["chosen_reading"] is not None:
        raise ServiceError(409, "already-chosen", "A reading has already been chosen for this medicine")
    pid = r["patient_id"]
    applied = None
    if choice in ("a", "b"):
        reading = r["reading_a"] if choice == "a" else r["reading_b"]
        if not reading:
            raise ServiceError(422, "not-found-by-that-reader", "That reader did not find this medicine, so there is nothing to add. Choose the other reading, or neither.")
        details = dict(reading.get("details") or {})
        ings = ingredients_of("medicine", reading["title"], details)
        ing_norm = frozenset(normalize_medicine_name(n) for n, _ in ings if normalize_medicine_name(n))
        match = _item_key_match(s, pid, "medicine", reading["title"], ing_norm, r["document_id"])
        src = reading.get("source") or {}
        ref = make_source_ref(s, patient_id=pid, document_id=r["document_id"], page=src.get("page") or 1, line_start=src.get("line_start"),
                              line_end=src.get("line_start"), quote=src.get("quote") or reading["title"])
        change_id = s.execute(text("""
            INSERT INTO plan_changes (patient_id, change_type, item_key, before_state, after_state, source_ref_id, requires_confirmation, status)
            VALUES (:p, CAST(:ct AS change_type), :k, CAST(:b AS jsonb), CAST(:a AS jsonb), :src, true, 'pending') RETURNING id"""),
            {"p": pid, "ct": "changed" if match else "new", "k": match["item_key"] if match else None,
             "b": json.dumps({"title": match["title"], "details": match["details"]}, default=str) if match else None,
             "a": json.dumps({"kind": "medicine", "title": reading["title"].strip(), "details": details}, default=str), "src": ref}).scalar_one()
        # Choosing a reading IS the person's decision, so it is applied now, through the same code and the same audit trail as a confirmation.
        decide_change(s, change_id=change_id, decision="confirm", comment="chosen from two readings", user_id=user_id, client=client)
        applied = str(change_id)
    elif choice != "neither":
        raise ServiceError(422, "bad-choice", "Choose reading a, reading b, or neither")
    s.execute(text("UPDATE second_reads SET chosen_reading = :c, chosen_by = :u, chosen_at = now() WHERE id = :i"), {"c": choice, "u": user_id, "i": second_read_id})
    write_audit(s, actor_type="user", actor_id=user_id, patient_id=pid, action="second_read.chosen", entity_type="second_read", entity_id=second_read_id,
                after={"choice": choice, "medicine": r["item_title"]})
    timeline(s, patient_id=pid, event_type="second_read_chosen", actor_type="user", actor_id=user_id,
             summary=("Neither reading was used for " if choice == "neither" else "A reading was chosen for ") + r["item_title"] + ". Ask the pharmacist if the page is unclear.",
             entity_type="second_read", entity_id=second_read_id)
    return {"id": str(second_read_id), "chosen": choice, "applied_change": applied}
