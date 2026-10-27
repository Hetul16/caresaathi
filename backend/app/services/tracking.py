"""Trackers built on the care plan: follow-ups (A1), medicine history (A3), the fridge sheet (A4), refill estimates (A6)
and duplicate ingredients (A8).

Dates and quantities are computed by code from the written words and shown with their inputs. A named person confirms
each one. Nothing here decides when a review or a refill is needed."""
from __future__ import annotations

from datetime import datetime, time, timedelta, timezone
from typing import Any
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.orm import Session

from ..safety.duplicates import DupItem, duplicate_question, find_duplicates
from .audit import timeline, write_audit
from .errors import ServiceError
from .readmodel import item_detail, source_of

_IST = timezone(timedelta(hours=5, minutes=30))


# ---- follow-ups ---------------------------------------------------------------------------------------------------------
def list_follow_ups(s: Session, patient_id: UUID) -> list[dict[str, Any]]:
    rows = s.execute(text("""
        SELECT f.id, f.what, f.due_text, f.anchor_date, f.anchor_kind, f.due_date, f.status, u.display_name AS actor,
               sr.kind AS source_kind, sr.document_id, sr.page, sr.line_start, sr.quote,
               coalesce(d.original_filename, d.doc_type::text) AS doc_title
        FROM follow_ups f JOIN source_refs sr ON sr.id = f.source_ref_id
        LEFT JOIN documents d ON d.id = sr.document_id LEFT JOIN users u ON u.id = f.confirmed_by
        WHERE f.patient_id = :p AND f.status <> 'dismissed'
        ORDER BY (f.status = 'done'), f.due_date NULLS LAST, f.created_at"""), {"p": patient_id}).mappings().all()
    return [{"id": str(r["id"]), "what": r["what"], "due_text": r["due_text"], "anchor_date": r["anchor_date"].isoformat() if r["anchor_date"] else None,
             "anchor_kind": r["anchor_kind"], "due_date": r["due_date"].isoformat() if r["due_date"] else None, "status": r["status"],
             "acted_by": r["actor"], "source": source_of(r),
             # The inputs of the computed date, always shown beside it.
             "how": (f"{r['anchor_date']:%d %b %Y} ({r['anchor_kind']} date) + “{r['due_text']}”" if r["due_date"] else
                     "No date could be worked out from the words. Please ask the doctor when.")} for r in rows]


def decide_follow_up(s: Session, *, follow_up_id: UUID, action: str, user_id: UUID) -> dict[str, Any]:
    row = s.execute(text("SELECT id, patient_id, what, due_date, status FROM follow_ups WHERE id = :i FOR UPDATE"), {"i": follow_up_id}).mappings().first()
    if row is None:
        raise ServiceError(404, "not-found", "Follow-up not found")
    new = {"confirm": "confirmed", "done": "done", "dismiss": "dismissed"}[action]
    if row["status"] in ("done", "dismissed"):
        raise ServiceError(409, "already-decided", "This follow-up is already closed")
    if action == "confirm" and row["status"] != "pending":
        raise ServiceError(409, "already-decided", "This follow-up is already confirmed")
    s.execute(text("UPDATE follow_ups SET status = :st, confirmed_by = :u, confirmed_at = now() WHERE id = :i"),
              {"st": new, "u": user_id, "i": follow_up_id})
    if action == "confirm" and row["due_date"]:
        due = datetime.combine(row["due_date"], time(9, 0), tzinfo=_IST)       # a plain morning reminder, in IST
        s.execute(text("""INSERT INTO reminders (patient_id, kind, title, due_at, created_by_type, created_by)
                          VALUES (:p, 'followup', :t, :d, 'user', :u)"""), {"p": row["patient_id"], "t": row["what"], "d": due, "u": user_id})
    write_audit(s, actor_type="user", actor_id=user_id, patient_id=row["patient_id"], action=f"follow_up.{new}",
                entity_type="follow_up", entity_id=follow_up_id, after={"what": row["what"], "due_date": row["due_date"]})
    timeline(s, patient_id=row["patient_id"], event_type="follow_up_" + new, actor_type="user", actor_id=user_id,
             summary={"confirmed": "Confirmed a follow-up: ", "done": "Marked done: ", "dismissed": "Set aside: "}[new] + row["what"],
             entity_type="follow_up", entity_id=follow_up_id)
    return {"id": str(follow_up_id), "status": new}


# ---- refill estimates ---------------------------------------------------------------------------------------------------
def list_supply(s: Session, patient_id: UUID) -> list[dict[str, Any]]:
    rows = s.execute(text("""
        SELECT sp.id, c.title, sp.quantity, sp.quantity_unit, sp.daily_units, sp.start_date, sp.estimated_run_out, u.display_name AS confirmer,
               sr.kind AS source_kind, sr.document_id, sr.page, sr.line_start, sr.quote, coalesce(d.original_filename, d.doc_type::text) AS doc_title
        FROM supply_records sp JOIN care_plan_items c ON c.id = sp.care_plan_item_id
        LEFT JOIN source_refs sr ON sr.id = sp.source_ref_id LEFT JOIN documents d ON d.id = sr.document_id
        LEFT JOIN users u ON u.id = sp.confirmed_by
        WHERE sp.patient_id = :p AND c.is_current AND c.status = 'active' ORDER BY sp.estimated_run_out NULLS LAST"""), {"p": patient_id}).mappings().all()
    out = []
    for r in rows:
        q = float(r["quantity"])
        d = float(r["daily_units"]) if r["daily_units"] is not None else None
        out.append({"id": str(r["id"]), "medicine": r["title"], "quantity": q, "unit": r["quantity_unit"], "daily_units": d,
                    "start_date": r["start_date"].isoformat(), "estimated_run_out": r["estimated_run_out"].isoformat() if r["estimated_run_out"] else None,
                    "confirmed_by": r["confirmer"], "source": source_of(r) if r["quote"] else None,
                    "how": (f"{q:g} {r['quantity_unit']} ÷ {d:g} a day, counted from {r['start_date']:%d %b %Y}" if d else
                            "No estimate: the written frequency is not a plain daily schedule.")})
    return out


def confirm_supply(s: Session, *, supply_id: UUID, user_id: UUID) -> dict[str, Any]:
    row = s.execute(text("SELECT id, patient_id FROM supply_records WHERE id = :i FOR UPDATE"), {"i": supply_id}).mappings().first()
    if row is None:
        raise ServiceError(404, "not-found", "Not found")
    s.execute(text("UPDATE supply_records SET confirmed_by = :u, confirmed_at = now() WHERE id = :i AND confirmed_by IS NULL"), {"u": user_id, "i": supply_id})
    write_audit(s, actor_type="user", actor_id=user_id, patient_id=row["patient_id"], action="supply.confirmed", entity_type="supply_record", entity_id=supply_id)
    return {"id": str(supply_id), "confirmed": True}


# ---- medicine history ---------------------------------------------------------------------------------------------------
def medicine_history(s: Session, patient_id: UUID) -> list[dict[str, Any]]:
    rows = s.execute(text("""
        SELECT c.item_key, c.version, c.title, c.details, c.status, c.is_current, c.created_at, c.created_by_type, u.display_name AS confirmer,
               sr.kind AS source_kind, sr.document_id, sr.page, sr.line_start, sr.quote, coalesce(d.original_filename, d.doc_type::text) AS doc_title
        FROM care_plan_items c JOIN source_refs sr ON sr.id = c.source_ref_id
        LEFT JOIN documents d ON d.id = sr.document_id LEFT JOIN users u ON u.id = c.confirmed_by
        WHERE c.patient_id = :p AND c.kind = 'medicine' ORDER BY c.item_key, c.version"""), {"p": patient_id}).mappings().all()
    by_key: dict[str, dict[str, Any]] = {}
    for r in rows:
        k = str(r["item_key"])
        g = by_key.setdefault(k, {"item_key": k, "title": r["title"], "versions": []})
        g["title"] = r["title"]
        g["versions"].append({"version": r["version"], "title": r["title"], "detail": item_detail(r["details"] or {}), "status": r["status"],
                              "current": r["is_current"], "at": r["created_at"].isoformat(), "confirmed_by": r["confirmer"], "source": source_of(r)})
    return sorted(by_key.values(), key=lambda g: g["title"].lower())


# ---- duplicate ingredients ----------------------------------------------------------------------------------------------
def duplicates(s: Session, patient_id: UUID) -> list[dict[str, Any]]:
    rows = s.execute(text("""
        SELECT c.item_key, c.title, c.source_ref_id, array_agg(mi.ingredient_normalized) AS ings
        FROM care_plan_items c JOIN medicine_ingredients mi ON mi.item_id = c.id
        WHERE c.patient_id = :p AND c.is_current AND c.status = 'active' AND c.kind = 'medicine'
        GROUP BY c.item_key, c.title, c.source_ref_id"""), {"p": patient_id}).mappings().all()
    items = [DupItem(str(r["item_key"]), r["title"], frozenset(r["ings"])) for r in rows]
    src = {str(r["item_key"]): r["source_ref_id"] for r in rows}
    out = []
    for g in find_duplicates(items):
        refs = s.execute(text("""SELECT sr.kind AS source_kind, sr.document_id, sr.page, sr.line_start, sr.quote,
                                        coalesce(d.original_filename, d.doc_type::text) AS doc_title
                                 FROM source_refs sr LEFT JOIN documents d ON d.id = sr.document_id WHERE sr.id = ANY(:ids)"""),
                         {"ids": [src[i.key] for i in g.items]}).mappings().all()
        out.append({"ingredient": g.ingredient, "medicines": [i.title for i in g.items], "sources": [source_of(r) for r in refs],
                    "question": duplicate_question(g)})
    return out


# ---- fridge sheet -------------------------------------------------------------------------------------------------------
def fridge_sheet(s: Session, patient_id: UUID) -> dict[str, Any]:
    """A printable one-pager. Only CONFIRMED medicines, nothing under an open allergy conflict, and each with its source."""
    pat = s.execute(text("SELECT full_name, preferred_language FROM patients WHERE id = :p"), {"p": patient_id}).mappings().one()
    meds = s.execute(text("""
        SELECT c.item_key, c.title, c.details, sr.page, sr.line_start, sr.quote, coalesce(d.original_filename, d.doc_type::text) AS doc_title,
               EXISTS (SELECT 1 FROM allergy_conflicts ac WHERE ac.care_plan_item_id = c.id AND ac.status = 'open') AS held
        FROM care_plan_items c JOIN source_refs sr ON sr.id = c.source_ref_id LEFT JOIN documents d ON d.id = sr.document_id
        WHERE c.patient_id = :p AND c.is_current AND c.status = 'active' AND c.kind = 'medicine' AND c.confirmed_by IS NOT NULL
        ORDER BY c.title"""), {"p": patient_id}).mappings().all()
    state = s.execute(text("SELECT state FROM v_allergy_effective WHERE patient_id = :p"), {"p": patient_id}).scalar_one()
    allergies = s.execute(text("SELECT substance, reaction FROM allergies WHERE patient_id = :p AND is_current AND active"), {"p": patient_id}).mappings().all()
    signs = s.execute(text("""SELECT c.title, c.alert_level FROM care_plan_items c WHERE c.patient_id = :p AND c.is_current AND c.status = 'active'
                              AND c.kind = 'warning_sign' ORDER BY c.alert_level DESC"""), {"p": patient_id}).mappings().all()
    docs = s.execute(text("SELECT name, hospital, phone FROM care_providers WHERE patient_id = :p ORDER BY is_primary DESC LIMIT 3"), {"p": patient_id}).mappings().all()
    slots = ("morning", "noon", "evening", "night")
    rows = []
    for m in meds:
        if m["held"]:
            continue
        det = m["details"] or {}
        sched = det.get("schedule") or {}
        rows.append({"title": m["title"], "detail": item_detail(det), "when": {k: sched.get(k) or 0 for k in slots},
                     "source": f"{m['doc_title']}, p.{m['page']}" + (f" line {m['line_start']}" if m["line_start"] else "")})
    return {"patient": pat["full_name"], "language": pat["preferred_language"], "allergy_state": state,
            "allergies": [{"substance": a["substance"], "reaction": a["reaction"]} for a in allergies], "medicines": rows,
            "warning_signs": [{"title": w["title"], "level": w["alert_level"]} for w in signs],
            "doctors": [{"name": d["name"], "hospital": d["hospital"] or "", "phone": d["phone"] or ""} for d in docs],
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "note": "Copied from the family's confirmed documents. Not medical advice. Ask the doctor or pharmacist if anything is unclear."}
