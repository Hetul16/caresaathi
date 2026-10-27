"""The permission gate in action. Proposed tool calls become rows; "asks first" tools wait for a named approver.

Nothing here executes a tool. An approved action is recorded as approved; the executors (sending a message,
sharing a card) are separate and are not connected in this build."""
from __future__ import annotations

import json
from typing import Any
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.orm import Session

from ..safety.permissions import gate_tool_call
from .audit import timeline, write_audit
from .errors import ServiceError


def propose_action(s: Session, *, patient_id: UUID, tool: str, input: dict[str, Any], requested_by: str = "user",
                   actor_id: UUID | None = None, trusted_trigger: bool = True) -> dict[str, Any]:
    """Queue an "asks first" tool call. The backend, not the caller, decides the status."""
    gate = gate_tool_call(tool, trusted_trigger=trusted_trigger)
    if gate.status == "refused":
        raise ServiceError(403, "tool-refused", f"This request was refused ({gate.reason})")
    if gate.status != "awaiting_approval":
        raise ServiceError(422, "not-an-approval-tool", "This tool does not need approval")
    aid = s.execute(text("""
        INSERT INTO actions (patient_id, tool, input, permission, status, requested_by)
        VALUES (:p, :t, CAST(:i AS jsonb), CAST(:perm AS permission_level), 'awaiting_approval', CAST(:rb AS actor_type))
        RETURNING id"""), {"p": patient_id, "t": tool, "i": json.dumps(input, default=str), "perm": gate.permission.value,
                           "rb": requested_by}).scalar_one()
    write_audit(s, actor_type=requested_by, actor_id=actor_id, patient_id=patient_id, action="action.proposed",
                entity_type="action", entity_id=aid, after={"tool": tool})
    return {"id": str(aid), "status": "awaiting_approval"}


def decide_action(s: Session, *, action_id: UUID, approve: bool, user_id: UUID, comment: str | None) -> dict[str, Any]:
    row = s.execute(text("SELECT id, patient_id, tool, input, status FROM actions WHERE id = :i FOR UPDATE"),
                    {"i": action_id}).mappings().first()
    if row is None:
        raise ServiceError(404, "not-found", "Action not found")
    if row["status"] != "awaiting_approval":
        raise ServiceError(409, "already-decided", "This request has already been decided")
    if approve:
        s.execute(text("""UPDATE actions SET status = 'approved', approved_by = :u, approved_at = now(), approver_comment = :c
                          WHERE id = :i"""), {"u": user_id, "c": comment, "i": action_id})
    else:
        s.execute(text("UPDATE actions SET status = 'refused', approver_comment = :c WHERE id = :i"), {"c": comment, "i": action_id})
    write_audit(s, actor_type="user", actor_id=user_id, patient_id=row["patient_id"],
                action="action.approved" if approve else "action.refused", entity_type="action", entity_id=action_id,
                after={"tool": row["tool"], "comment": comment})
    timeline(s, patient_id=row["patient_id"], event_type="approval", actor_type="user", actor_id=user_id,
             summary=("Approved: " if approve else "Refused: ") + describe_action(row["tool"], row["input"] or {}),
             entity_type="action", entity_id=action_id)
    return {"id": str(action_id), "status": "approved" if approve else "refused"}


def describe_action(tool: str, inp: dict[str, Any]) -> str:
    to = inp.get("contact_name")
    return {
        "share_emergency_card": f"Share the Emergency Card link{' with ' + to if to else ''}",
        "revoke_emergency_link": "Switch off an Emergency Card link",
        "send_family_message": "Send a message to the family",
        "message_doctor_draft": "Send a drafted question to the doctor",
        "record_allergy": "Record an allergy",
    }.get(tool, tool.replace("_", " ").capitalize())
