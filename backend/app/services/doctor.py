"""Doctor link (C1, D-46).

A family member makes a link for one named doctor. The page shows the same documented facts as the Emergency Card. A question
reaches the doctor only after a named member approves the `message_doctor_draft` action; the doctor's reply is stored word for word
and never changes the plan by itself."""
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

MAX_QUESTION = 1500


def create_link(s: Session, *, patient_id: UUID, user_id: UUID, doctor_name: str, expires_in_days: int) -> dict[str, Any]:
    name = doctor_name.strip()
    if not name:
        raise ServiceError(422, "name-required", "Enter the doctor's name")
    token = new_token(24)
    expires = datetime.now(timezone.utc) + timedelta(days=expires_in_days)
    link_id = s.execute(text("""
        INSERT INTO doctor_links (patient_id, token_hash, token_hint, doctor_name, created_by, expires_at)
        VALUES (:p, :h, :hint, :n, :u, :e) RETURNING id"""),
        {"p": patient_id, "h": hash_token(token), "hint": token[-4:], "n": name, "u": user_id, "e": expires}).scalar_one()
    write_audit(s, actor_type="user", actor_id=user_id, patient_id=patient_id, action="doctor_link.created",
                entity_type="doctor_link", entity_id=link_id, after={"doctor": name, "expires_at": expires})
    timeline(s, patient_id=patient_id, event_type="doctor_link_created", actor_type="user", actor_id=user_id,
             summary=f"A link for {name} was created", entity_type="doctor_link", entity_id=link_id)
    base = get_settings().public_base_url.rstrip("/")
    return {"id": str(link_id), "url": f"{base}/d/{token}", "hint": token[-4:], "doctor_name": name, "expires_at": expires.isoformat()}


def _status(r: Any, now: datetime) -> str:
    return "revoked" if r["revoked_at"] else ("expired" if r["expires_at"] <= now else "active")


def list_links(s: Session, patient_id: UUID) -> list[dict[str, Any]]:
    now = datetime.now(timezone.utc)
    links = s.execute(text("""
        SELECT id, token_hint, doctor_name, expires_at, revoked_at, created_at,
               (SELECT count(*) FROM doctor_link_access_log a WHERE a.link_id = doctor_links.id AND a.outcome = 'ok') AS opened
        FROM doctor_links WHERE patient_id = :p ORDER BY created_at DESC"""), {"p": patient_id}).mappings().all()
    out = []
    for l in links:
        msgs = s.execute(text("""SELECT id, direction, body, created_at FROM doctor_messages WHERE link_id = :l ORDER BY created_at"""),
                         {"l": l["id"]}).mappings().all()
        out.append({"id": str(l["id"]), "hint": l["token_hint"], "doctor_name": l["doctor_name"], "status": _status(l, now),
                    "expires_at": l["expires_at"].isoformat(), "created_at": l["created_at"].isoformat(), "opened": l["opened"],
                    "messages": [{"id": str(m["id"]), "direction": m["direction"], "body": m["body"],
                                  "at": m["created_at"].isoformat()} for m in msgs]})
    return out


def revoke_link(s: Session, *, link_id: UUID, user_id: UUID) -> dict[str, Any]:
    row = s.execute(text("SELECT id, patient_id, doctor_name, revoked_at FROM doctor_links WHERE id = :i FOR UPDATE"), {"i": link_id}).mappings().first()
    if row is None:
        raise ServiceError(404, "not-found", "Not found")
    if row["revoked_at"] is None:
        s.execute(text("UPDATE doctor_links SET revoked_at = now(), revoked_by = :u WHERE id = :i"), {"u": user_id, "i": link_id})
        write_audit(s, actor_type="user", actor_id=user_id, patient_id=row["patient_id"], action="doctor_link.revoked",
                    entity_type="doctor_link", entity_id=link_id)
        timeline(s, patient_id=row["patient_id"], event_type="doctor_link_revoked", actor_type="user", actor_id=user_id,
                 summary=f"The link for {row['doctor_name']} was switched off", entity_type="doctor_link", entity_id=link_id)
    return {"id": str(link_id), "status": "revoked"}


def link_patient(s: Session, link_id: UUID) -> tuple[UUID, str, str]:
    row = s.execute(text("SELECT patient_id, doctor_name, CASE WHEN revoked_at IS NOT NULL THEN 'revoked' WHEN expires_at <= now() THEN 'expired' ELSE 'active' END "
                         "FROM doctor_links WHERE id = :i"), {"i": link_id}).first()
    if row is None:
        raise ServiceError(404, "not-found", "Not found")
    return row[0], row[1], row[2]


def propose_question(s: Session, *, link_id: UUID, user_id: UUID, body: str, requested_by: str = "user") -> dict[str, Any]:
    """Queue a question for the doctor. Nothing is visible to the doctor until a member with approval rights approves it."""
    from . import actions as action_svc
    body = body.strip()
    if not body or len(body) > MAX_QUESTION:
        raise ServiceError(422, "bad-question", f"Write between 1 and {MAX_QUESTION} characters")
    pid, name, status = link_patient(s, link_id)
    if status != "active":
        raise ServiceError(409, "link-not-active", "This link is switched off or has expired")
    return action_svc.propose_action(s, patient_id=pid, tool="message_doctor_draft", actor_id=user_id, requested_by=requested_by,
                                     input={"link_id": str(link_id), "contact_name": name, "body": body})


def deliver_approved_question(s: Session, *, action_id: UUID, patient_id: UUID, inp: dict[str, Any]) -> bool:
    """The executor for an approved `message_doctor_draft`: post it to the link's thread. Returns whether it was delivered."""
    link_id, body = inp.get("link_id"), inp.get("body")
    if not link_id or not body:
        return False
    row = s.execute(text("SELECT 1 FROM doctor_links WHERE id = :l AND patient_id = :p AND revoked_at IS NULL AND expires_at > now()"),
                    {"l": link_id, "p": patient_id}).first()
    if row is None:
        s.execute(text("UPDATE actions SET status = 'failed', result = CAST(:r AS jsonb) WHERE id = :i"),
                  {"r": json.dumps({"error": "link switched off or expired"}), "i": action_id})
        return False
    s.execute(text("""INSERT INTO doctor_messages (patient_id, link_id, direction, body, action_id)
                      VALUES (:p, :l, 'to_doctor', :b, :a)"""), {"p": patient_id, "l": link_id, "b": body, "a": action_id})
    s.execute(text("UPDATE actions SET status = 'done', result = CAST(:r AS jsonb) WHERE id = :i"),
              {"r": json.dumps({"delivered": "doctor_link"}), "i": action_id})
    return True


def doctor_view(s: Session, *, token: str, ip_hash: bytes, ua: str) -> tuple[str, dict[str, Any] | None]:
    """Resolve a public token. Returns (outcome, page data). Every outcome other than 'ok' carries no data."""
    from . import card as card_svc
    h = hash_token(token[:200])
    row = s.execute(text("SELECT r_patient_id, r_doctor_name, r_expires_at, r_outcome FROM app_resolve_doctor_link(:h, :ip, :ua)"),
                    {"h": h, "ip": ip_hash, "ua": ua}).first()
    if row is None or row[3] != "ok" or row[0] is None:
        return (row[3] if row else "not_found"), None
    return "ok", {"patient_id": row[0], "doctor_name": row[1], "expires_at": row[2].isoformat(), "hash": h,
                  "build_card": card_svc.build_card}


def doctor_thread(s: Session, token_hash: bytes) -> list[dict[str, Any]]:
    rows = s.execute(text("SELECT r_id, r_direction, r_body, r_at FROM app_doctor_thread(:h)"), {"h": token_hash}).all()
    return [{"id": str(r[0]), "direction": r[1], "body": r[2], "at": r[3].isoformat()} for r in rows]


def doctor_reply(s: Session, *, token: str, body: str, ip_hash: bytes, ua: str) -> str:
    return s.execute(text("SELECT app_doctor_reply(:h, :b, :ip, :ua)"),
                     {"h": hash_token(token[:200]), "b": body, "ip": ip_hash, "ua": ua}).scalar_one()
