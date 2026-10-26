"""Append-only audit log writer. Every approval, allergy change, consent, share and card access goes here."""
from __future__ import annotations

import json
from typing import Any
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.orm import Session


def write_audit(s: Session, *, actor_type: str, actor_id: UUID | None, patient_id: UUID | None, action: str,
                entity_type: str | None = None, entity_id: Any = None, before: dict | None = None,
                after: dict | None = None, request_id: str | None = None) -> None:
    s.execute(
        text("""INSERT INTO audit_log (actor_type, actor_id, patient_id, action, entity_type, entity_id,
                                       before_state, after_state, request_id)
                VALUES (CAST(:at AS actor_type), :aid, :pid, :act, :et, :eid,
                        CAST(:b AS jsonb), CAST(:a AS jsonb), :rid)"""),
        {"at": actor_type, "aid": actor_id, "pid": patient_id, "act": action, "et": entity_type,
         "eid": str(entity_id) if entity_id is not None else None,
         "b": json.dumps(before, default=str) if before is not None else None,
         "a": json.dumps(after, default=str) if after is not None else None, "rid": request_id},
    )


def timeline(s: Session, *, patient_id: UUID, event_type: str, actor_type: str, actor_id: UUID | None, summary: str,
             entity_type: str | None = None, entity_id: UUID | None = None, data: dict | None = None) -> None:
    s.execute(
        text("""INSERT INTO timeline_events (patient_id, event_type, actor_type, actor_id, entity_type, entity_id, summary, data)
                VALUES (:p, :et, CAST(:at AS actor_type), :aid, :ent, :eid, :sum, CAST(:d AS jsonb))"""),
        {"p": patient_id, "et": event_type, "at": actor_type, "aid": actor_id, "ent": entity_type, "eid": entity_id,
         "sum": summary, "d": json.dumps(data or {}, default=str)},
    )
