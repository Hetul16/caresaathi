"""Family task board (C8, D-59): who is doing what. Coordination only; a task never says what to give or when."""
from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from typing import Any
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.orm import Session

from .audit import timeline, write_audit
from .errors import ServiceError

_IST = timezone(timedelta(hours=5, minutes=30))


def list_tasks(s: Session, patient_id: UUID) -> list[dict[str, Any]]:
    today = datetime.now(_IST).date()
    rows = s.execute(text("""
        SELECT t.id, t.title, t.due_date, t.status, t.created_at, t.done_at, a.display_name AS assignee, c.display_name AS creator, d.display_name AS finisher
        FROM care_tasks t JOIN users c ON c.id = t.created_by LEFT JOIN users a ON a.id = t.assigned_to LEFT JOIN users d ON d.id = t.done_by
        WHERE t.patient_id = :p ORDER BY (t.status = 'done'), t.due_date NULLS LAST, t.created_at"""), {"p": patient_id}).mappings().all()
    return [{"id": str(r["id"]), "title": r["title"], "due_date": r["due_date"].isoformat() if r["due_date"] else None, "status": r["status"],
             "assigned_to": r["assignee"], "created_by": r["creator"], "done_by": r["finisher"], "overdue": bool(r["status"] == "open" and r["due_date"] and r["due_date"] < today),
             "done_at": r["done_at"].astimezone(_IST).strftime("%d %b, %H:%M") if r["done_at"] else None} for r in rows]


def create_task(s: Session, *, patient_id: UUID, user_id: UUID, title: str, assigned_to: UUID | None, due_date: date | None) -> dict[str, Any]:
    title = title.strip()
    if not title or len(title) > 200:
        raise ServiceError(422, "bad-title", "Write what needs doing, up to 200 characters")
    if assigned_to is not None and not s.execute(text("SELECT 1 FROM family_members WHERE patient_id = :p AND user_id = :u AND status = 'active'"),
                                                 {"p": patient_id, "u": assigned_to}).first():
        raise ServiceError(422, "not-a-member", "Choose someone who is part of this family")
    tid = s.execute(text("""INSERT INTO care_tasks (patient_id, title, assigned_to, due_date, created_by) VALUES (:p, :t, :a, :d, :u) RETURNING id"""),
                    {"p": patient_id, "t": title, "a": assigned_to, "d": due_date, "u": user_id}).scalar_one()
    write_audit(s, actor_type="user", actor_id=user_id, patient_id=patient_id, action="task.created", entity_type="care_task", entity_id=tid, after={"title": title})
    timeline(s, patient_id=patient_id, event_type="task_created", actor_type="user", actor_id=user_id, summary=f"New task: {title}", entity_type="care_task", entity_id=tid)
    return {"id": str(tid)}


def complete_task(s: Session, *, task_id: UUID, user_id: UUID) -> dict[str, Any]:
    t = s.execute(text("SELECT id, patient_id, title, status FROM care_tasks WHERE id = :i FOR UPDATE"), {"i": task_id}).mappings().first()
    if t is None:
        raise ServiceError(404, "not-found", "Not found")
    if t["status"] == "done":
        raise ServiceError(409, "already-done", "This task is already done")
    s.execute(text("UPDATE care_tasks SET status = 'done', done_by = :u, done_at = now() WHERE id = :i"), {"u": user_id, "i": task_id})
    write_audit(s, actor_type="user", actor_id=user_id, patient_id=t["patient_id"], action="task.done", entity_type="care_task", entity_id=task_id)
    timeline(s, patient_id=t["patient_id"], event_type="task_done", actor_type="user", actor_id=user_id, summary=f"Done: {t['title']}", entity_type="care_task", entity_id=task_id)
    return {"id": str(task_id), "status": "done"}
