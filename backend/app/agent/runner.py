"""The care crew's loop (C2, D-47).

One goal, at most six steps. Each step: the model names a tool, the CODE decides what happens (registry, permission gate, repeat check),
runs automatic tools itself, queues "asks first" tools for a named person, and writes the step to the database before the next one
starts, so the screen can follow along. The model's one-sentence "why" is shown only after the output guard passes it.

Triggers are a person's goal (or later a schedule), never text found in a document: documents are not inputs to this loop."""
from __future__ import annotations

import json
import logging
from uuid import UUID

from sqlalchemy import text

from ..clients.models import ModelError, default_next_step, get_model_client
from ..db import request_session, run_after_commit, worker_session
from ..safety.guard import GuardContext, guard_output
from ..safety.permissions import gate_tool_call
from ..services.audit import timeline, write_audit
from ..services.chat import classify
from ..services.errors import ServiceError
from ..services.plan import record_model_call
from .tools import TOOL_HELP, TOOLS

log = logging.getLogger("caresaathi.agent")
MAX_STEPS = 6


def start_run(s, *, patient_id: UUID, user_id: UUID, goal: str) -> dict:
    """Create the run row inside the caller's transaction and start the loop once it commits."""
    goal = goal.strip()
    if not goal or len(goal) > 300:
        raise ServiceError(422, "bad-goal", "Write a goal of up to 300 characters")
    kind = classify(goal)
    if kind in ("advice", "hostile"):
        # A goal that asks for medical advice or tries to instruct the assistant never starts. The refusal is recorded and shown.
        run_id = s.execute(text("""INSERT INTO agent_runs (patient_id, trigger, goal, requested_by, status, error, finished_at)
                                   VALUES (:p, 'message', :g, :u, 'failed', :e, now()) RETURNING id"""),
                           {"p": patient_id, "g": goal, "u": user_id,
                            "e": "This request was refused. The care crew coordinates documents and questions; it cannot give medical advice. Ask the doctor or pharmacist."}).scalar_one()
        write_audit(s, actor_type="user", actor_id=user_id, patient_id=patient_id, action="agent.run_refused", entity_type="agent_run", entity_id=run_id)
        return {"id": str(run_id), "status": "failed"}
    run_id = s.execute(text("""INSERT INTO agent_runs (patient_id, trigger, goal, requested_by) VALUES (:p, 'message', :g, :u) RETURNING id"""),
                       {"p": patient_id, "g": goal, "u": user_id}).scalar_one()
    write_audit(s, actor_type="user", actor_id=user_id, patient_id=patient_id, action="agent.run_started", entity_type="agent_run", entity_id=run_id,
                after={"goal": goal})
    run_after_commit(s, lambda: execute_run(run_id, patient_id, user_id, goal))
    return {"id": str(run_id), "status": "running"}


def _why(raw: str | None) -> str | None:
    if not raw:
        return None
    r = guard_output(raw, GuardContext(language="en", source_ids=[], source_exempt=True))
    return r.text if r.passed else None


def _record(s, *, run_id: UUID, pid: UUID, seq: int, tool: str, perm: str | None, status: str, why: str | None,
            output: dict | None = None, reason: str | None = None, action_id: str | None = None) -> None:
    s.execute(text("""INSERT INTO agent_steps (run_id, patient_id, seq, tool, permission, status, why, output, reason, action_id)
                      VALUES (:r, :p, :q, :t, CAST(:perm AS permission_level), :st, :w, CAST(:o AS jsonb), :re, :a)"""),
              {"r": run_id, "p": pid, "q": seq, "t": tool[:80], "perm": perm, "st": status, "w": why,
               "o": json.dumps(output, default=str) if output is not None else None, "re": reason, "a": action_id})
    s.execute(text("UPDATE agent_runs SET step_count = :n WHERE id = :r"), {"n": seq, "r": run_id})


def execute_run(run_id: UUID, patient_id: UUID, user_id: UUID, goal: str) -> None:
    ctx: dict = {}
    done: list[str] = []
    try:
        client = get_model_client()
        for seq in range(1, MAX_STEPS + 1):
            with worker_session() as s:
                has_link = s.execute(text("SELECT 1 FROM doctor_links WHERE patient_id = :p AND revoked_at IS NULL AND expires_at > now()"),
                                     {"p": patient_id}).first() is not None
            try:
                choice, usage = client.next_step(goal, TOOL_HELP, done, has_link)
                with worker_session() as s:
                    record_model_call(s, patient_id, usage)
            except ModelError:
                choice = default_next_step(done, has_link)
            tool = (choice.get("tool") or "").strip()
            if not tool:                       # an unusable answer from the model: fall back to the fixed plan, not to guessing
                choice = default_next_step(done, has_link)
                tool = choice["tool"]
            if tool == "finish":
                break
            why = _why(choice.get("why"))
            with worker_session() as s:
                gate = gate_tool_call(tool, trusted_trigger=True)
                if tool in done:
                    _record(s, run_id=run_id, pid=patient_id, seq=seq, tool=tool, perm=gate.permission.value if gate.permission else None,
                            status="refused", why=why, reason="This tool was already used in this run.")
                elif gate.status == "refused" or tool not in TOOLS:
                    _record(s, run_id=run_id, pid=patient_id, seq=seq, tool=tool, perm=None, status="refused", why=why,
                            reason="There is no such tool. The crew can only use its registered tools." if gate.reason == "unknown_tool" else f"Refused ({gate.reason}).")
                else:
                    try:
                        with s.begin_nested():
                            out = TOOLS[tool](s, patient_id, ctx)
                        ctx[tool] = out
                        waiting = gate.status == "awaiting_approval"
                        _record(s, run_id=run_id, pid=patient_id, seq=seq, tool=tool, perm=gate.permission.value,
                                status="awaiting_approval" if waiting else "ran", why=why, output=out,
                                action_id=out.get("action_id") if waiting else None)
                    except ServiceError as e:
                        _record(s, run_id=run_id, pid=patient_id, seq=seq, tool=tool, perm=gate.permission.value if gate.permission else None,
                                status="failed", why=why, reason=e.message)
                    except Exception:  # noqa: BLE001 - one broken tool must not end the whole run; the step shows as failed
                        log.exception("agent tool %s failed", tool)
                        _record(s, run_id=run_id, pid=patient_id, seq=seq, tool=tool, perm=gate.permission.value if gate.permission else None,
                                status="failed", why=why, reason="This step could not be completed.")
            done.append(tool)
        with worker_session() as s:
            s.execute(text("UPDATE agent_runs SET status = 'done', finished_at = now(), result = CAST(:r AS jsonb) WHERE id = :i"),
                      {"r": json.dumps(ctx.get("prepare_visit_summary"), default=str) if ctx.get("prepare_visit_summary") else None, "i": run_id})
            timeline(s, patient_id=patient_id, event_type="agent_run", actor_type="agent", actor_id=None,
                     summary="The care crew finished a run", entity_type="agent_run", entity_id=run_id)
    except Exception as e:  # noqa: BLE001 - a crashed run must end as failed, never stay "running"
        log.exception("agent run %s failed", run_id)
        with worker_session() as s:
            s.execute(text("UPDATE agent_runs SET status = 'failed', finished_at = now(), error = :e WHERE id = :i"),
                      {"e": f"The run stopped: {type(e).__name__}", "i": run_id})


def list_runs(s, patient_id: UUID, limit: int = 10) -> list[dict]:
    runs = s.execute(text("""SELECT r.id, r.goal, r.status, r.error, r.started_at, r.finished_at, r.result, u.display_name AS who
                             FROM agent_runs r LEFT JOIN users u ON u.id = r.requested_by
                             WHERE r.patient_id = :p AND r.goal IS NOT NULL ORDER BY r.started_at DESC LIMIT :n"""),
                    {"p": patient_id, "n": limit}).mappings().all()
    out = []
    for r in runs:
        steps = s.execute(text("""SELECT st.seq, st.tool, st.permission::text AS permission, st.status, st.why, st.output, st.reason, st.action_id,
                                         a.status::text AS action_status, ap.display_name AS approver, a.approved_at
                                  FROM agent_steps st LEFT JOIN actions a ON a.id = st.action_id LEFT JOIN users ap ON ap.id = a.approved_by
                                  WHERE st.run_id = :r ORDER BY st.seq"""), {"r": r["id"]}).mappings().all()
        out.append({"id": str(r["id"]), "goal": r["goal"], "status": r["status"], "error": r["error"], "requested_by": r["who"],
                    "started_at": r["started_at"].isoformat(), "finished_at": r["finished_at"].isoformat() if r["finished_at"] else None,
                    "brief": r["result"],
                    "steps": [{"seq": x["seq"], "tool": x["tool"], "permission": x["permission"], "status": x["status"], "why": x["why"],
                               "summary": _summarise(x["tool"], x["output"]), "reason": x["reason"], "action_id": str(x["action_id"]) if x["action_id"] else None,
                               "action_status": x["action_status"], "approved_by": x["approver"],
                               "approved_at": x["approved_at"].isoformat() if x["approved_at"] else None} for x in steps]})
    return out


def _summarise(tool: str, out: dict | None) -> str | None:
    if not out:
        return None
    if tool == "read_care_plan":
        return f"{len(out.get('medicines', []))} medicines, {len(out.get('warning_signs', []))} warning signs; allergies: {out.get('allergy_state', '').replace('_', ' ')}"
    if tool == "list_open_flags":
        return f"{len(out.get('allergy_conflicts', []))} allergy flags, {len(out.get('omissions', []))} omission questions, {len(out.get('duplicates', []))} duplicate questions"
    if tool == "list_pending":
        return f"{len(out.get('pending_changes', []))} changes and {len(out.get('follow_ups', []))} follow-ups waiting"
    if tool == "check_supply":
        return f"{len([x for x in out.get('supply', []) if x.get('estimated_run_out')])} refill dates computed"
    if tool == "prepare_visit_summary":
        return f"Brief ready with {len(out.get('questions', []))} questions"
    if tool == "message_doctor_draft":
        return f"Drafted {out.get('question_count', 0)} questions for {out.get('doctor', 'the doctor')}; waiting for approval"
    return None
