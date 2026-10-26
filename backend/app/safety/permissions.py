"""Tool registry and permission gate (docs/15-api-spec.md, section 6). The model cannot bypass this."""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class Permission(str, Enum):
    AUTOMATIC = "automatic"
    ASK_FIRST = "ask_first"
    AUTOMATIC_ALERT = "automatic_alert"


A, AF, AA = Permission.AUTOMATIC, Permission.ASK_FIRST, Permission.AUTOMATIC_ALERT

# Permission lives on the tool, not in the model's decision. There is deliberately no tool that
# changes a medicine or dose, diagnoses, or decides on hospital (safety invariant 1).
TOOL_REGISTRY: dict[str, Permission] = {
    "read_document": A, "explain_item": A, "update_care_plan": A, "compare_versions": A,
    "set_reminder": A, "schedule_checkin": A, "prepare_visit_summary": A, "weekly_briefing": A,
    "lookup_generic_prices": A, "check_allergy_conflicts": A, "generate_emergency_card": A,
    "add_recovery_entry": A, "compare_recovery_photos": A, "describe_recovery_change": A,
    "alert_family_urgent": AA,
    "record_allergy": AF, "send_recovery_bundle_to_doctor": AF, "share_emergency_card": AF,
    "revoke_emergency_link": AF, "send_family_message": AF, "message_doctor_draft": AF,
    "assign_task": AF, "share_with_caregiver": AF,
}


@dataclass(frozen=True)
class GateDecision:
    status: str          # run | awaiting_approval | refused
    permission: Permission | None
    reason: str = ""


def gate_tool_call(tool: str, *, trusted_trigger: bool = True) -> GateDecision:
    """Decide what the backend does with a tool call proposed by the model.

    - unknown tool                         -> refused
    - trigger is not a user message, schedule or system event (for example text inside a
      document)                            -> refused, so a document cannot trigger tools
    - ask_first                            -> awaiting_approval (a named person must approve)
    - automatic / automatic_alert          -> run
    """
    perm = TOOL_REGISTRY.get(tool)
    if perm is None:
        return GateDecision("refused", None, "unknown_tool")
    if not trusted_trigger:
        return GateDecision("refused", perm, "untrusted_trigger")
    if perm is Permission.ASK_FIRST:
        return GateDecision("awaiting_approval", perm)
    return GateDecision("run", perm)
