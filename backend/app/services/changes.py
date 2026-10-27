"""Decisions by named people: confirming plan items, deciding pending changes, acknowledging allergy conflicts.

A change that needs confirmation is applied only after a named member with approval rights decides it
(safety invariant 4 and the CHECK on plan_changes). Nothing here is reachable by the model."""
from __future__ import annotations

from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import text
from sqlalchemy.orm import Session

from ..clients.models import ModelClient
from ..safety.dosing import parse_schedule
from ..safety.normalize import normalize_medicine_name
from .audit import timeline, write_audit
from .errors import ServiceError
from .plan import ingredients_of, insert_ingredients, insert_item_version, raise_conflicts_for_item
from .resolve import resolve_allergy

_KINDS = {"medicine", "condition", "test", "appointment", "warning_sign", "restriction", "instruction", "result"}


def confirm_item(s: Session, *, patient_id: UUID, item_key: UUID, user_id: UUID) -> dict[str, Any]:
    """A named person confirms the current version of a plan item. Elder mode reads out confirmed medicines only."""
    row = s.execute(text("""
        SELECT id, title, confirmed_by FROM care_plan_items
        WHERE patient_id = :p AND item_key = :k AND is_current AND status = 'active' FOR UPDATE"""),
        {"p": patient_id, "k": item_key}).mappings().first()
    if row is None:
        raise ServiceError(404, "not-found", "Plan item not found")
    if row["confirmed_by"] is None:
        s.execute(text("UPDATE care_plan_items SET confirmed_by = :u, confirmed_at = now() WHERE id = :i"),
                  {"u": user_id, "i": row["id"]})
        write_audit(s, actor_type="user", actor_id=user_id, patient_id=patient_id, action="plan.item_confirmed",
                    entity_type="care_plan_item", entity_id=row["id"], after={"title": row["title"]})
        timeline(s, patient_id=patient_id, event_type="item_confirmed", actor_type="user", actor_id=user_id,
                 summary=f"Confirmed: {row['title']}", entity_type="care_plan_item", entity_id=row["id"])
    return {"item_key": str(item_key), "confirmed": True}


def decide_change(s: Session, *, change_id: UUID, decision: str, comment: str | None, user_id: UUID,
                  client: ModelClient, language: str = "en") -> dict[str, Any]:
    ch = s.execute(text("SELECT * FROM plan_changes WHERE id = :i FOR UPDATE"), {"i": change_id}).mappings().first()
    if ch is None:
        raise ServiceError(404, "not-found", "Change not found")
    if ch["status"] != "pending":
        raise ServiceError(409, "already-decided", "This change has already been decided")
    patient_id: UUID = ch["patient_id"]

    if decision == "reject":
        s.execute(text("UPDATE plan_changes SET status = 'rejected', decided_by = :u, decided_at = now() WHERE id = :i"),
                  {"u": user_id, "i": change_id})
        write_audit(s, actor_type="user", actor_id=user_id, patient_id=patient_id, action="plan.change_rejected",
                    entity_type="plan_change", entity_id=change_id, after={"comment": comment})
        timeline(s, patient_id=patient_id, event_type="change_rejected", actor_type="user", actor_id=user_id,
                 summary="A change heard in the visit was not added to the plan", entity_type="plan_change", entity_id=change_id)
        return {"id": str(change_id), "status": "rejected"}

    after = ch["after_state"] or {}
    applied_item_id: UUID | None = None
    ctype = ch["change_type"]

    if ctype in ("new", "changed", "stopped"):
        applied_item_id = _apply_item_change(s, ch, after, user_id, client, language)
    elif ctype == "allergy_added":
        _apply_allergy_added(s, ch, after, user_id, client, language)
    else:
        raise ServiceError(422, "unsupported-change", "This kind of change cannot be applied from here yet")

    s.execute(text("""UPDATE plan_changes SET status = 'applied', decided_by = :u, decided_at = now(), applied_item_id = :a
                      WHERE id = :i"""), {"u": user_id, "a": applied_item_id, "i": change_id})
    write_audit(s, actor_type="user", actor_id=user_id, patient_id=patient_id, action="plan.change_confirmed",
                entity_type="plan_change", entity_id=change_id, after={"change_type": ctype, "comment": comment})
    timeline(s, patient_id=patient_id, event_type="change_confirmed", actor_type="user", actor_id=user_id,
             summary="A change heard in the visit was confirmed and added to the plan", entity_type="plan_change", entity_id=change_id)
    return {"id": str(change_id), "status": "applied"}


def _apply_item_change(s: Session, ch: dict, after: dict, user_id: UUID, client: ModelClient, language: str) -> UUID:
    patient_id: UUID = ch["patient_id"]
    current = None
    if ch["item_key"]:
        current = s.execute(text("""SELECT id, item_key, version, kind, title, details, alert_level, date_missing, due_at
                                    FROM care_plan_items WHERE patient_id = :p AND item_key = :k AND is_current FOR UPDATE"""),
                            {"p": patient_id, "k": ch["item_key"]}).mappings().first()
    if ch["change_type"] in ("changed", "stopped") and current is None:
        raise ServiceError(409, "item-missing", "The plan item this change refers to no longer exists")

    if ch["change_type"] == "stopped":
        new_id = insert_item_version(s, patient_id=patient_id, item_key=current["item_key"], version=current["version"] + 1,
                                     supersedes_id=current["id"], kind=current["kind"], title=current["title"],
                                     details=current["details"] or {}, alert_level=current["alert_level"], due_at=current["due_at"],
                                     date_missing=current["date_missing"], source_ref_id=ch["source_ref_id"],
                                     created_by_type="user", created_by=user_id, status="stopped")
    else:
        kind, title, details = after.get("kind"), (after.get("title") or "").strip(), dict(after.get("details") or {})
        if kind not in _KINDS or not title:
            raise ServiceError(422, "invalid-change", "The change does not say what to add")
        if kind == "medicine":
            sched = parse_schedule(details.get("frequency_text"))
            if sched:
                details["schedule"] = sched
        new_id = insert_item_version(s, patient_id=patient_id, item_key=current["item_key"] if current else (ch["item_key"] or uuid4()),
                                     version=(current["version"] + 1) if current else 1,
                                     supersedes_id=current["id"] if current else None, kind=kind, title=title, details=details,
                                     alert_level=after.get("alert_level") if kind == "warning_sign" else None, due_at=None,
                                     date_missing=kind in ("test", "appointment") and not (details.get("due_date") or details.get("when")),
                                     source_ref_id=ch["source_ref_id"], created_by_type="user", created_by=user_id)
        if kind == "medicine":
            insert_ingredients(s, patient_id, new_id, ingredients_of(kind, title, details))
            raise_conflicts_for_item(s, patient_id, new_id, client, language)
    s.execute(text("UPDATE care_plan_items SET confirmed_by = :u, confirmed_at = now() WHERE id = :i"), {"u": user_id, "i": new_id})
    return new_id


def _apply_allergy_added(s: Session, ch: dict, after: dict, user_id: UUID, client: ModelClient, language: str) -> None:
    substance = (after.get("substance") or "").strip()
    if not substance:
        raise ServiceError(422, "invalid-change", "The change does not say which substance")
    norm = normalize_medicine_name(substance)
    if s.execute(text("SELECT 1 FROM allergies WHERE patient_id=:p AND is_current AND active AND substance_normalized=:n"),
                 {"p": ch["patient_id"], "n": norm}).first():
        return
    sub_id, fam_id = resolve_allergy(s, substance)
    severity = after.get("severity") if after.get("severity") in ("mild", "moderate", "severe") else "unknown"
    s.execute(text("""
        INSERT INTO allergies (patient_id, allergy_key, version, substance, substance_normalized, substance_id, family_id,
                               reaction, severity, source_type, source_ref_id, confirmed_by, confirmed_at)
        VALUES (:p, :k, 1, :sub, :n, :sid, :fid, :r, CAST(:sev AS allergy_severity), 'visit', :src, :u, now())"""),
        {"p": ch["patient_id"], "k": uuid4(), "sub": substance, "n": norm, "sid": sub_id, "fid": fam_id,
         "r": after.get("reaction"), "sev": severity, "src": ch["source_ref_id"], "u": user_id})
    # An allergy that arrives after medicines were listed: check those medicines again.
    medicine_ids = s.execute(text("""SELECT id FROM care_plan_items
                                     WHERE patient_id = :p AND is_current AND status = 'active' AND kind = 'medicine'"""),
                             {"p": ch["patient_id"]}).scalars().all()
    for item_id in medicine_ids:
        raise_conflicts_for_item(s, ch["patient_id"], item_id, client, language)


def acknowledge_conflict(s: Session, *, conflict_id: UUID, user_id: UUID, note: str | None) -> dict[str, Any]:
    """A person has seen the flag. This does not say the medicine is fine: it only stops the banner repeating."""
    row = s.execute(text("SELECT id, patient_id, status FROM allergy_conflicts WHERE id = :i FOR UPDATE"), {"i": conflict_id}).mappings().first()
    if row is None:
        raise ServiceError(404, "not-found", "Conflict not found")
    if row["status"] == "open":
        s.execute(text("""UPDATE allergy_conflicts SET status = 'acknowledged', acknowledged_by = :u, acknowledged_at = now(),
                          resolution_note = :n WHERE id = :i"""), {"u": user_id, "n": (note or "").strip()[:500] or None, "i": conflict_id})
        write_audit(s, actor_type="user", actor_id=user_id, patient_id=row["patient_id"], action="allergy.conflict_acknowledged",
                    entity_type="allergy_conflict", entity_id=conflict_id, after={"note": note})
        timeline(s, patient_id=row["patient_id"], event_type="conflict_acknowledged", actor_type="user", actor_id=user_id,
                 summary="An allergy flag was seen by a family member. It is still a question for the doctor.",
                 entity_type="allergy_conflict", entity_id=conflict_id)
    return {"id": str(conflict_id), "status": "acknowledged"}
