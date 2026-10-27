"""Emergency Card content and links (safety invariant 7).

The card copies only facts that have a source (a document line or the doctor's words), shows when it was last
updated, and is reached by a random token that is stored only as a hash and can be revoked.

build_card runs under either the family's session or the public-link session. It touches only tables the public
policy exposes (patients, care_plan_items, allergies, allergy_status, care_providers, source_refs)."""
from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from typing import Any
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.orm import Session

from ..config import get_settings
from ..security import hash_token, new_token
from .audit import timeline, write_audit
from .errors import ServiceError
from .readmodel import age_of, item_detail

_NOTE = "This card lists what the family's documents say. It is not medical advice."


def _src(r: Any) -> dict:
    # The public link cannot read the documents table, so the card names the page and line, not the file.
    return {"kind": r["kind"], "document_id": str(r["document_id"]) if r["document_id"] else "", "document_title": "Document",
            "page": r["page"], "line_start": r["line_start"], "quote": r["quote"]}


def build_card(s: Session, patient_id: UUID) -> dict[str, Any]:
    pat = s.execute(text("SELECT full_name, date_of_birth, blood_group, preferred_language FROM patients WHERE id = :p"),
                    {"p": patient_id}).mappings().first()
    if pat is None:
        raise ServiceError(404, "not-found", "Not found")
    state = s.execute(text("SELECT state FROM v_allergy_effective WHERE patient_id = :p"), {"p": patient_id}).scalar_one()
    allergies = s.execute(text("""
        SELECT a.allergy_key, a.substance, a.reaction, a.severity, sr.kind, sr.document_id, sr.page, sr.line_start, sr.quote
        FROM allergies a JOIN source_refs sr ON sr.id = a.source_ref_id
        WHERE a.patient_id = :p AND a.is_current AND a.active ORDER BY a.created_at"""), {"p": patient_id}).mappings().all()
    items = s.execute(text("""
        SELECT c.kind, c.title, c.details, c.alert_level, c.created_at, sr.kind AS skind, sr.document_id, sr.page, sr.line_start, sr.quote
        FROM care_plan_items c JOIN source_refs sr ON sr.id = c.source_ref_id
        WHERE c.patient_id = :p AND c.is_current AND c.status = 'active' AND c.kind IN ('condition', 'medicine', 'warning_sign')
        ORDER BY c.kind, c.created_at"""), {"p": patient_id}).mappings().all()
    providers = s.execute(text("SELECT name, hospital, phone FROM care_providers WHERE patient_id = :p ORDER BY is_primary DESC, name"),
                          {"p": patient_id}).mappings().all()
    stamps = [r["created_at"] for r in items] + list(
        s.execute(text("SELECT created_at FROM allergies WHERE patient_id = :p"), {"p": patient_id}).scalars())

    def with_kind(r: Any) -> dict:
        d = dict(r)
        d["kind"] = d.get("skind", d.get("kind"))
        return d

    medicines = [r for r in items if r["kind"] == "medicine"]
    last_med = max((r["created_at"] for r in medicines), default=None)
    return {
        "patient": {"name": pat["full_name"], "age": age_of(pat["date_of_birth"]), "blood_group": pat["blood_group"],
                    "language": pat["preferred_language"]},
        "allergies": {"state": state, "items": [
            {"allergy_key": str(a["allergy_key"]), "substance": a["substance"], "reaction": a["reaction"],
             "severity": a["severity"], "source": _src(a)} for a in allergies]},
        "conditions": [{"title": r["title"], "source": _src(with_kind(r))} for r in items if r["kind"] == "condition"],
        "medicines": [{"title": r["title"], "detail": item_detail(r["details"] or {}) or "", "source": _src(with_kind(r))}
                      for r in medicines],
        "recent_changes": f"Medicine list last updated {last_med.astimezone(timezone.utc):%d %b %Y}." if last_med else "",
        "providers": [{"name": p["name"], "hospital": p["hospital"] or "", "phone": p["phone"] or ""} for p in providers],
        "contacts": [],
        "last_updated_at": max(stamps).isoformat() if stamps else None,
        "note": _NOTE,
    }


def create_card(s: Session, *, patient_id: UUID, user_id: UUID, expires_in_days: int | None) -> dict[str, Any]:
    """A new link. The token is returned once and only its hash is stored."""
    token = new_token(24)
    expires = datetime.now(timezone.utc) + timedelta(days=expires_in_days) if expires_in_days else None
    card_id = s.execute(text("""
        INSERT INTO emergency_cards (patient_id, token_hash, token_hint, created_by, expires_at, snapshot, snapshot_generated_at)
        VALUES (:p, :h, :hint, :u, :e, CAST(:snap AS jsonb), now()) RETURNING id"""),
        {"p": patient_id, "h": hash_token(token), "hint": token[-4:], "u": user_id, "e": expires,
         "snap": json.dumps(build_card(s, patient_id), default=str)}).scalar_one()
    write_audit(s, actor_type="user", actor_id=user_id, patient_id=patient_id, action="card.created",
                entity_type="emergency_card", entity_id=card_id, after={"hint": token[-4:], "expires_at": expires})
    timeline(s, patient_id=patient_id, event_type="card_created", actor_type="user", actor_id=user_id,
             summary="A new Emergency Card link was created", entity_type="emergency_card", entity_id=card_id)
    base = get_settings().public_base_url.rstrip("/")
    return {"id": str(card_id), "url": f"{base}/e/{token}", "hint": token[-4:], "expires_at": expires.isoformat() if expires else None}


def list_cards(s: Session, patient_id: UUID) -> list[dict[str, Any]]:
    rows = s.execute(text("""SELECT id, token_hint, expires_at, revoked_at, created_at FROM emergency_cards
                             WHERE patient_id = :p ORDER BY created_at DESC"""), {"p": patient_id}).mappings().all()
    now = datetime.now(timezone.utc)
    out = []
    for r in rows:
        status = "revoked" if r["revoked_at"] else ("expired" if r["expires_at"] and r["expires_at"] <= now else "active")
        out.append({"id": str(r["id"]), "hint": r["token_hint"], "status": status, "created_at": r["created_at"].isoformat(),
                    "expires_at": r["expires_at"].isoformat() if r["expires_at"] else None})
    return out


def revoke_card(s: Session, *, card_id: UUID, user_id: UUID) -> dict[str, Any]:
    row = s.execute(text("SELECT id, patient_id, revoked_at FROM emergency_cards WHERE id = :i FOR UPDATE"), {"i": card_id}).mappings().first()
    if row is None:
        raise ServiceError(404, "not-found", "Not found")
    if row["revoked_at"] is None:
        s.execute(text("UPDATE emergency_cards SET revoked_at = now(), revoked_by = :u WHERE id = :i"), {"u": user_id, "i": card_id})
        write_audit(s, actor_type="user", actor_id=user_id, patient_id=row["patient_id"], action="card.revoked",
                    entity_type="emergency_card", entity_id=card_id)
        timeline(s, patient_id=row["patient_id"], event_type="card_revoked", actor_type="user", actor_id=user_id,
                 summary="An Emergency Card link was switched off", entity_type="emergency_card", entity_id=card_id)
    return {"id": str(card_id), "status": "revoked"}
