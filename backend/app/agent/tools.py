"""The care crew's tools (C2, D-47). Each tool is read-only or draft-only and runs in code; the model never executes anything.

A tool returns a plain dict. Every fact in it carries its source, copied from the stored record. There is deliberately no tool that
changes a medicine or a dose, diagnoses, decides on hospital, or sends anything without a named person's approval."""
from __future__ import annotations

from typing import Any, Callable
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.orm import Session

from ..services import doctor as doctor_svc
from ..services import tracking
from ..services.errors import ServiceError
from ..services.readmodel import item_detail, source_of

# What the model is told about each tool. The permission level is NOT here: it comes from TOOL_REGISTRY, never from the model.
TOOL_HELP: dict[str, str] = {
    "read_care_plan": "Read the allergy state, medicines and warning signs on file, each with its source.",
    "list_open_flags": "List open allergy conflicts, omission questions and duplicate-ingredient questions, with the drafted questions.",
    "list_pending": "List plan changes and follow-ups that are waiting for a family member to confirm.",
    "check_supply": "List computed refill dates with the numbers they came from.",
    "prepare_visit_summary": "Build the one-page visit brief (what is on file, what is unconfirmed, questions for the doctor) from the steps so far.",
    "message_doctor_draft": "Draft the brief's questions as a message to the doctor's link. A family member must approve before the doctor sees it.",
}


def _items(s: Session, pid: UUID, kinds: tuple[str, ...]) -> list[dict]:
    rows = s.execute(text("""
        SELECT c.title, c.details, c.kind, c.alert_level, c.confirmed_by IS NOT NULL AS confirmed,
               sr.kind AS source_kind, sr.document_id, sr.page, sr.line_start, sr.quote, coalesce(d.original_filename, d.doc_type::text) AS doc_title
        FROM care_plan_items c JOIN source_refs sr ON sr.id = c.source_ref_id LEFT JOIN documents d ON d.id = sr.document_id
        WHERE c.patient_id = :p AND c.is_current AND c.status = 'active' AND c.kind = ANY(:k) ORDER BY c.kind, c.created_at"""),
        {"p": pid, "k": list(kinds)}).mappings().all()
    return [{"title": r["title"], "detail": item_detail(r["details"] or {}) or "", "confirmed": r["confirmed"],
             "alert_level": r["alert_level"], "source": source_of(r)} for r in rows]


def read_care_plan(s: Session, pid: UUID, ctx: dict) -> dict[str, Any]:
    state = s.execute(text("SELECT state FROM v_allergy_effective WHERE patient_id = :p"), {"p": pid}).scalar_one()
    al = s.execute(text("""
        SELECT a.substance, a.reaction, sr.kind AS source_kind, sr.document_id, sr.page, sr.line_start, sr.quote,
               coalesce(d.original_filename, d.doc_type::text) AS doc_title
        FROM allergies a JOIN source_refs sr ON sr.id = a.source_ref_id LEFT JOIN documents d ON d.id = sr.document_id
        WHERE a.patient_id = :p AND a.is_current AND a.active ORDER BY a.created_at"""), {"p": pid}).mappings().all()
    return {"allergy_state": state,
            "allergies": [{"substance": a["substance"], "reaction": a["reaction"], "source": source_of(a)} for a in al],
            "medicines": _items(s, pid, ("medicine",)), "warning_signs": _items(s, pid, ("warning_sign",))}


def list_open_flags(s: Session, pid: UUID, ctx: dict) -> dict[str, Any]:
    from ..api.plan import omission_list
    conflicts = s.execute(text("""
        SELECT ac.match, ci.title AS medicine, fo.body AS flag, qo.body AS question
        FROM allergy_conflicts ac JOIN care_plan_items ci ON ci.id = ac.care_plan_item_id
        LEFT JOIN generated_outputs fo ON fo.id = ac.flag_output_id AND fo.guard_status = 'pass'
        LEFT JOIN generated_outputs qo ON qo.id = ac.question_output_id AND qo.guard_status = 'pass'
        WHERE ac.patient_id = :p AND ac.status = 'open' ORDER BY ci.created_at"""), {"p": pid}).mappings().all()
    fallback = "Please ask the doctor or pharmacist about this."
    return {"allergy_conflicts": [{"medicine": c["medicine"], "match": c["match"],
                                   "flag": c["flag"] or fallback, "question": c["question"] or fallback} for c in conflicts],
            "omissions": [{"medicine": o["medicine"], "question": o["question"], "source": o["previous_source"]} for o in omission_list(s, pid)],
            "duplicates": [{"medicines": d["medicines"], "question": d["question"]} for d in tracking.duplicates(s, pid)]}


def list_pending(s: Session, pid: UUID, ctx: dict) -> dict[str, Any]:
    from ..api.plan import pending_changes
    return {"pending_changes": [{"title": c["title"], "before": c["before"], "after": c["after"], "source": c["source"]}
                                for c in pending_changes(s, pid)],
            "follow_ups": [{"what": f["what"], "due_text": f["due_text"], "how": f["how"], "source": f["source"]}
                           for f in tracking.list_follow_ups(s, pid) if f["status"] == "pending"]}


def check_supply(s: Session, pid: UUID, ctx: dict) -> dict[str, Any]:
    return {"supply": [{"medicine": x["medicine"], "estimated_run_out": x["estimated_run_out"], "how": x["how"],
                        "confirmed": bool(x["confirmed_by"]), "source": x["source"]} for x in tracking.list_supply(s, pid)]}


def prepare_visit_summary(s: Session, pid: UUID, ctx: dict) -> dict[str, Any]:
    """The brief is assembled by code from stored facts. Questions are the drafted questions already in the record, plus plain
    confirmation questions. Nothing here is worded by a model, so there is nothing to judge."""
    plan = ctx.get("read_care_plan") or read_care_plan(s, pid, ctx)
    flags = ctx.get("list_open_flags") or list_open_flags(s, pid, ctx)
    pend = ctx.get("list_pending") or list_pending(s, pid, ctx)
    supply = ctx.get("check_supply") or check_supply(s, pid, ctx)
    name = s.execute(text("SELECT full_name FROM patients WHERE id = :p"), {"p": pid}).scalar_one()

    allergy_line = {"listed": "Allergies on file: " + ", ".join(a["substance"] + (f" ({a['reaction']})" if a["reaction"] else "") for a in plan["allergies"]),
                    "none_stated": "A document or the doctor states there are no known allergies.",
                    "not_recorded": "Allergies are not recorded."}.get(plan["allergy_state"], "Allergies are not recorded.")
    sections: list[dict[str, Any]] = [
        {"heading": "Allergies", "lines": [{"text": allergy_line, "source": (plan["allergies"][0]["source"] if plan["allergies"] else None)}]},
        {"heading": "Medicines on file", "lines": [
            {"text": f"{m['title']}" + (f", {m['detail']}" if m["detail"] else "") + ("" if m["confirmed"] else " (not yet confirmed by a family member)"),
             "source": m["source"]} for m in plan["medicines"]] or [{"text": "No medicines on file yet.", "source": None}]},
    ]
    waiting = ([{"text": f"Change waiting: {c['title']}" + (f" ({c['before']} to {c['after']})" if c["before"] or c["after"] else ""), "source": c["source"]}
                for c in pend["pending_changes"]] +
               [{"text": f"Follow-up to confirm: {f['what']}. {f['how']}", "source": f["source"]} for f in pend["follow_ups"]])
    if waiting:
        sections.append({"heading": "Waiting for a family member to confirm", "lines": waiting})
    runs = [x for x in supply["supply"] if x["estimated_run_out"]]
    if runs:
        sections.append({"heading": "Estimated refill dates (computed, please confirm)", "lines": [
            {"text": f"{x['medicine']}: about {x['estimated_run_out']} ({x['how']})", "source": x["source"]} for x in runs]})

    questions: list[str] = []
    if plan["allergy_state"] == "not_recorded":
        questions.append(f"Could you record whether {name} has any known allergies?")
    questions += [c["question"] for c in flags["allergy_conflicts"]]
    questions += [o["question"] for o in flags["omissions"]]
    questions += [d["question"] for d in flags["duplicates"]]
    questions += [f"Could you confirm this change: {c['title']}?" for c in pend["pending_changes"]]
    questions += [f"When exactly should we do this: {f['what']}? The document says “{f['due_text']}”." for f in pend["follow_ups"]]
    seen, uniq = set(), []
    for q in questions:
        if q not in seen:
            seen.add(q)
            uniq.append(q)
    return {"title": f"Visit brief for {name}", "sections": sections, "questions": uniq,
            "note": "This brief lists what the documents say. It is not medical advice."}


def message_doctor_draft(s: Session, pid: UUID, ctx: dict) -> dict[str, Any]:
    brief = ctx.get("prepare_visit_summary")
    if not brief or not brief["questions"]:
        raise ServiceError(409, "nothing-to-ask", "There are no questions to send yet")
    link = s.execute(text("""SELECT id, doctor_name FROM doctor_links WHERE patient_id = :p AND revoked_at IS NULL AND expires_at > now()
                             ORDER BY created_at DESC LIMIT 1"""), {"p": pid}).first()
    if link is None:
        raise ServiceError(409, "no-doctor-link", "There is no active doctor link to send to")
    lines, used = [], 0
    for i, q in enumerate(brief["questions"], 1):
        line = f"{i}. {q}"
        if used + len(line) > doctor_svc.MAX_QUESTION - 80:
            break
        lines.append(line)
        used += len(line) + 1
    body = "Questions from the family ahead of the visit:\n" + "\n".join(lines)
    out = doctor_svc.propose_question(s, link_id=link[0], user_id=None, body=body, requested_by="agent")
    return {"action_id": out["id"], "doctor": link[1], "status": out["status"], "question_count": len(lines)}


TOOLS: dict[str, Callable[[Session, UUID, dict], dict[str, Any]]] = {
    "read_care_plan": read_care_plan, "list_open_flags": list_open_flags, "list_pending": list_pending,
    "check_supply": check_supply, "prepare_visit_summary": prepare_visit_summary, "message_doctor_draft": message_doctor_draft,
}
DEFAULT_ORDER = ["read_care_plan", "list_open_flags", "list_pending", "check_supply", "prepare_visit_summary", "message_doctor_draft"]
