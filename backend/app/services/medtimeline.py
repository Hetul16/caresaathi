"""The medicine timeline: every current medicine on one calendar, with same-ingredient overlaps and open allergy flags drawn on it.

Dates come from the documents' own printed dates and durations (safety/medtimeline.py). Overlaps use the duplicate-ingredient groups already
found by code; the question for each is the existing fixed template. Nothing here says a combination is fine or not fine."""
from __future__ import annotations

from datetime import date, timedelta
from typing import Any
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.orm import Session

from ..safety.duplicates import DupItem, duplicate_question, find_duplicates
from ..safety.medtimeline import how, overlap, span_of
from .readmodel import item_detail, source_of


def medicine_timeline(s: Session, patient_id: UUID, today: date | None = None) -> dict[str, Any]:
    today = today or date.today()
    rows = s.execute(text("""
        SELECT c.item_key, c.title, c.details, c.confirmed_by, c.id AS item_id,
               sr.kind AS source_kind, sr.document_id, sr.page, sr.line_start, sr.quote,
               coalesce(d.original_filename, d.doc_type::text) AS doc_title, d.doc_date, d.issuer,
               coalesce(array_agg(mi.ingredient_normalized) FILTER (WHERE mi.id IS NOT NULL), '{}') AS ings
        FROM care_plan_items c JOIN source_refs sr ON sr.id = c.source_ref_id
        LEFT JOIN documents d ON d.id = sr.document_id LEFT JOIN medicine_ingredients mi ON mi.item_id = c.id
        WHERE c.patient_id = :p AND c.is_current AND c.status = 'active' AND c.kind = 'medicine'
        GROUP BY c.item_key, c.title, c.details, c.confirmed_by, c.id, sr.kind, sr.document_id, sr.page, sr.line_start, sr.quote, d.original_filename, d.doc_type, d.doc_date, d.issuer
        ORDER BY d.doc_date NULLS LAST, c.title"""), {"p": patient_id}).mappings().all()
    flags = {str(r["item_key"]): r for r in s.execute(text("""
        SELECT c.item_key, ac.match, fo.body AS flag FROM allergy_conflicts ac JOIN care_plan_items c ON c.id = ac.care_plan_item_id
        LEFT JOIN generated_outputs fo ON fo.id = ac.flag_output_id AND fo.guard_status = 'pass'
        WHERE ac.patient_id = :p AND ac.status = 'open'"""), {"p": patient_id}).mappings().all()}

    out, spans = [], {}
    for r in rows:
        det = r["details"] or {}
        key = str(r["item_key"])
        sp = span_of(r["doc_date"], det.get("duration_days"))
        spans[key] = sp
        f = flags.get(key)
        out.append({
            "item_key": key, "title": r["title"], "detail": item_detail(det), "confirmed": r["confirmed_by"] is not None,
            "prescriber": r["issuer"] or r["doc_title"] or "Unknown source", "doc_date": r["doc_date"].isoformat() if r["doc_date"] else None,
            "start": sp.start.isoformat() if sp.start else None, "end": sp.end.isoformat() if sp.end else None,
            "open_end": sp.start is not None and sp.end is None, "how": how(r["doc_date"], det.get("duration_days")),
            "allergy": {"match": f["match"], "flag": f["flag"] or "Please ask the doctor or pharmacist about this."} if f else None,
            "source": source_of(r),
        })

    titles = {str(r["item_key"]): r["title"] for r in rows}
    dups = find_duplicates([DupItem(str(r["item_key"]), r["title"], frozenset(r["ings"])) for r in rows if r["ings"]])
    overlaps = []
    for g in dups:
        keys = [i.key for i in g.items]
        spots = []
        for i in range(len(keys)):
            for j in range(i + 1, len(keys)):
                o = overlap(spans[keys[i]], spans[keys[j]])
                if o:
                    spots.append({"a": keys[i], "b": keys[j], "start": o.start.isoformat(), "end": o.end.isoformat() if o.end else None})
        overlaps.append({"ingredient": g.ingredient, "medicines": [titles[k] for k in keys], "keys": keys, "spots": spots,
                         "dated": bool(spots), "question": duplicate_question(g)})

    drawn = [r for r in out if r["start"]]
    starts = [date.fromisoformat(r["start"]) for r in drawn]
    ends = [date.fromisoformat(r["end"]) for r in drawn if r["end"]]
    lo = min(starts + [today]) - timedelta(days=2) if starts else today - timedelta(days=2)
    hi = max(ends + starts + [today]) + timedelta(days=7) if starts else today + timedelta(days=14)
    return {"today": today.isoformat(), "window": {"start": lo.isoformat(), "end": hi.isoformat()}, "rows": out, "overlaps": overlaps,
            "note": "Dates are the ones printed on the documents, added up by code. A bar with no end has no number of days printed. "
                    "Where two bars with the same ingredient run together, ask the doctor or pharmacist whether that is intended. "
                    "This is not medical advice."}
