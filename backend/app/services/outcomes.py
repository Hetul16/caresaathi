"""Outcomes board (C6, D-52): own the outcome, not the engagement.

Every flag CareSaathi raises is a question. It stays on this board until a named person records the answer, with who gave it and where it
came from. The board counts questions and answers; it never says a medicine is safe, and "answered" means only that a person wrote down
what the doctor or pharmacist said. All numbers are computed by code from stored rows."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.orm import Session

from .audit import timeline, write_audit
from .errors import ServiceError
from .tracking import list_follow_ups

_FALLBACK = "Please ask the doctor or pharmacist about this."


def _days(since: datetime, until: datetime | None = None) -> int:
    return max(0, ((until or datetime.now(timezone.utc)) - since).days)


def _answer_row(a: Any) -> dict | None:
    if a["answer_id"] is None:
        return None
    return {"text": a["answer_text"], "answered_by": a["answered_by"], "source_kind": a["source_kind"], "recorded_by": a["recorder"],
            "recorded_at": a["answered_at"].isoformat()}


def board(s: Session, patient_id: UUID) -> dict[str, Any]:
    conflicts = s.execute(text("""
        SELECT ac.id, ci.title AS medicine, ac.match, ac.status::text AS status, ac.raised_at, qo.body AS question, fo.body AS flag,
               qa.id AS answer_id, qa.answer_text, qa.answered_by, qa.source_kind, qa.created_at AS answered_at, u.display_name AS recorder
        FROM allergy_conflicts ac JOIN care_plan_items ci ON ci.id = ac.care_plan_item_id
        LEFT JOIN generated_outputs qo ON qo.id = ac.question_output_id AND qo.guard_status = 'pass'
        LEFT JOIN generated_outputs fo ON fo.id = ac.flag_output_id AND fo.guard_status = 'pass'
        LEFT JOIN question_answers qa ON qa.subject_kind = 'allergy_conflict' AND qa.subject_id = ac.id
        LEFT JOIN users u ON u.id = qa.recorded_by
        WHERE ac.patient_id = :p ORDER BY ac.raised_at"""), {"p": patient_id}).mappings().all()
    flags = s.execute(text("""
        SELECT f.id, f.medicine_title AS medicine, f.state, f.created_at AS raised_at, f.state_changed_at, qo.body AS question,
               qa.id AS answer_id, qa.answer_text, qa.answered_by, qa.source_kind, qa.created_at AS answered_at, u.display_name AS recorder
        FROM reconciliation_flags f
        LEFT JOIN generated_outputs qo ON qo.id = f.question_output_id AND qo.guard_status = 'pass'
        LEFT JOIN question_answers qa ON qa.subject_kind = 'reconciliation_flag' AND qa.subject_id = f.id
        LEFT JOIN users u ON u.id = qa.recorded_by
        WHERE f.patient_id = :p ORDER BY f.created_at"""), {"p": patient_id}).mappings().all()

    items: list[dict[str, Any]] = []
    for c in conflicts:
        answered = c["answer_id"] is not None
        status = "answered" if answered else ("closed_without_answer" if c["status"] in ("resolved", "dismissed_by_doctor") else
                                               "seen" if c["status"] == "acknowledged" else "open")
        items.append({"kind": "allergy_conflict", "id": str(c["id"]), "title": c["medicine"],
                      "label": "Possible allergy conflict" if c["match"] != "unresolved" else "Could not check against the allergy list",
                      "question": c["question"] or _FALLBACK, "status": status, "raised_at": c["raised_at"].isoformat(),
                      "days_open": _days(c["raised_at"], c["answered_at"] if answered else None), "answer": _answer_row(c)})
    for f in flags:
        answered = f["answer_id"] is not None
        status = "answered" if answered else ("closed_without_answer" if f["state"] == "resolved" else "asked" if f["state"] == "asked" else "open")
        items.append({"kind": "reconciliation_flag", "id": str(f["id"]), "title": f["medicine"], "label": "On the earlier list, not on the new one",
                      "question": f["question"] or "Could you confirm whether this medicine is meant to continue, or was left off on purpose or by mistake? We are only asking.",
                      "status": status, "raised_at": f["raised_at"].isoformat(), "days_open": _days(f["raised_at"], f["answered_at"] if answered else None),
                      "answer": _answer_row(f)})
    items.sort(key=lambda i: (i["status"] == "answered", i["raised_at"]))

    answered_days = [i["days_open"] for i in items if i["status"] == "answered"]
    summary = {"raised": len(items), "answered": len(answered_days),
               "waiting": sum(i["status"] in ("open", "seen", "asked") for i in items),
               "closed_without_answer": sum(i["status"] == "closed_without_answer" for i in items),
               "oldest_waiting_days": max([i["days_open"] for i in items if i["status"] in ("open", "seen", "asked")], default=None),
               "average_days_to_answer": round(sum(answered_days) / len(answered_days), 1) if answered_days else None}

    follow = [f for f in list_follow_ups(s, patient_id)]
    follow_ups = {"total": len(follow), "waiting_for_confirmation": sum(f["status"] == "pending" for f in follow),
                  "confirmed": sum(f["status"] == "confirmed" for f in follow), "done": sum(f["status"] == "done" for f in follow)}

    msgs = s.execute(text("""
        SELECT m.id, m.direction, m.body, m.created_at, l.doctor_name,
               EXISTS (SELECT 1 FROM question_answers qa WHERE qa.doctor_message_id = m.id) AS used
        FROM doctor_messages m JOIN doctor_links l ON l.id = m.link_id WHERE m.patient_id = :p ORDER BY m.created_at"""), {"p": patient_id}).mappings().all()
    asked = [m for m in msgs if m["direction"] == "to_doctor"]
    replies = [m for m in msgs if m["direction"] == "from_doctor"]
    doctor_thread = {"questions_sent": len(asked), "replies_received": len(replies), "replies_not_yet_used": sum(not r["used"] for r in replies)}
    usable = [{"id": str(r["id"]), "doctor_name": r["doctor_name"], "body": r["body"][:300], "at": r["created_at"].isoformat()} for r in replies if not r["used"]]
    return {"summary": summary, "items": items, "follow_ups": follow_ups, "doctor_thread": doctor_thread, "usable_replies": usable,
            "note": "A question counts as answered when a named person records what the doctor or pharmacist said. CareSaathi does not judge the answer."}


def record_answer(s: Session, *, patient_id: UUID, user_id: UUID, subject_kind: str, subject_id: UUID, answer_text: str | None,
                  answered_by: str | None, doctor_message_id: UUID | None) -> dict[str, Any]:
    if subject_kind == "allergy_conflict":
        row = s.execute(text("SELECT id, status::text AS st FROM allergy_conflicts WHERE id = :i AND patient_id = :p FOR UPDATE"),
                        {"i": subject_id, "p": patient_id}).mappings().first()
        label = s.execute(text("SELECT ci.title FROM allergy_conflicts ac JOIN care_plan_items ci ON ci.id = ac.care_plan_item_id WHERE ac.id = :i"), {"i": subject_id}).scalar()
    elif subject_kind == "reconciliation_flag":
        row = s.execute(text("SELECT id, state AS st FROM reconciliation_flags WHERE id = :i AND patient_id = :p FOR UPDATE"),
                        {"i": subject_id, "p": patient_id}).mappings().first()
        label = s.execute(text("SELECT medicine_title FROM reconciliation_flags WHERE id = :i"), {"i": subject_id}).scalar()
    else:
        raise ServiceError(422, "bad-subject", "Unknown kind of question")
    if row is None:
        raise ServiceError(404, "not-found", "Not found")
    if s.execute(text("SELECT 1 FROM question_answers WHERE subject_kind = :k AND subject_id = :i"), {"k": subject_kind, "i": subject_id}).first():
        raise ServiceError(409, "already-answered", "An answer is already recorded for this question")

    if doctor_message_id is not None:
        m = s.execute(text("""SELECT m.body, l.doctor_name FROM doctor_messages m JOIN doctor_links l ON l.id = m.link_id
                              WHERE m.id = :m AND m.patient_id = :p AND m.direction = 'from_doctor'"""), {"m": doctor_message_id, "p": patient_id}).mappings().first()
        if m is None:
            raise ServiceError(404, "not-found", "That reply was not found")
        text_, by, kind = m["body"], m["doctor_name"], "doctor_message"
    else:
        text_, by, kind = (answer_text or "").strip(), (answered_by or "").strip(), "family_note"
        if not text_ or not by:
            raise ServiceError(422, "answer-required", "Write what the doctor or pharmacist said, and who said it")
        if len(text_) > 1500 or len(by) > 80:
            raise ServiceError(422, "too-long", "That is too long")

    aid = s.execute(text("""INSERT INTO question_answers (patient_id, subject_kind, subject_id, answer_text, answered_by, source_kind, doctor_message_id, recorded_by)
                            VALUES (:p, :k, :i, :t, :b, :sk, :dm, :u) RETURNING id"""),
                    {"p": patient_id, "k": subject_kind, "i": subject_id, "t": text_, "b": by, "sk": kind, "dm": doctor_message_id, "u": user_id}).scalar_one()
    # Close the underlying flag. It is the person's act, recorded with their name; the flag stays visible on the board with its answer.
    if subject_kind == "allergy_conflict":
        s.execute(text("""UPDATE allergy_conflicts SET status = 'resolved', acknowledged_by = coalesce(acknowledged_by, :u),
                          acknowledged_at = coalesce(acknowledged_at, now()), resolution_note = 'Answer recorded' WHERE id = :i"""), {"u": user_id, "i": subject_id})
    else:
        s.execute(text("UPDATE reconciliation_flags SET state = 'resolved', state_changed_by = :u, state_changed_at = now() WHERE id = :i"), {"u": user_id, "i": subject_id})
    write_audit(s, actor_type="user", actor_id=user_id, patient_id=patient_id, action="question.answer_recorded", entity_type=subject_kind,
                entity_id=subject_id, after={"answered_by": by, "source": kind})
    timeline(s, patient_id=patient_id, event_type="answer_recorded", actor_type="user", actor_id=user_id,
             summary=f"An answer from {by} was recorded for the question about {label}", entity_type=subject_kind, entity_id=subject_id)
    return {"id": str(aid), "status": "answered"}
