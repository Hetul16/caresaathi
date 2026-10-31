"""Daily check-ins for remote care (C7, D-58).

A child far away needs to know two things: did the medicines for today get marked as taken, and how does the parent say they feel.
This module shows exactly that, computed by code from what people marked, with the inputs visible. It never decides what a missed dose
means, never says to take a dose late or to skip one, and never calls a pain number high, low, better or worse.

Which doses appear: confirmed, current medicines with a plain schedule (1-0-1 is morning, noon and evening, as on every other screen), not held by an open allergy conflict, and, when the
document gave a number of days, only until that course would end (counted from the day the item was added)."""
from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from typing import Any
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.orm import Session

from ..safety.dosing import parse_schedule
from .audit import timeline, write_audit
from .errors import ServiceError

IST = timezone(timedelta(hours=5, minutes=30))
SLOTS = ("morning", "noon", "evening", "night")
SLOT_HOURS = {"morning": 8, "noon": 13, "evening": 19, "night": 22}       # standard clock times for the written schedule
GRACE = timedelta(hours=2)
LABEL = {"morning": "Morning", "noon": "Noon", "evening": "Evening", "night": "Night"}
NOTE = ("Times are the usual ones for a written schedule (8 in the morning, 1 at noon, 7 in the evening, 10 at night) and can be changed later. "
        "\"Not marked\" only means nobody marked it. CareSaathi does not say what a missed dose means: ask the doctor or pharmacist.")


def _now(now: datetime | None) -> datetime:
    return (now or datetime.now(timezone.utc)).astimezone(IST)


def _as_needed(title: str, det: dict) -> bool:
    words = " ".join(str(x or "") for x in (title, det.get("frequency_text"), det.get("instructions_text"), det.get("dose_text"))).casefold()
    return any(k in words for k in ("if pain", "if fever", "if needed", "when needed", "as needed", " sos", "prn", "if required"))


def scheduled_items(s: Session, patient_id: UUID, today: date) -> list[dict[str, Any]]:
    rows = s.execute(text("""
        SELECT c.item_key, c.title, c.details, c.created_at, u.display_name AS confirmer
        FROM care_plan_items c LEFT JOIN users u ON u.id = c.confirmed_by
        WHERE c.patient_id = :p AND c.is_current AND c.status = 'active' AND c.kind = 'medicine' AND c.confirmed_by IS NOT NULL
          AND NOT EXISTS (SELECT 1 FROM allergy_conflicts ac WHERE ac.care_plan_item_id = c.id AND ac.status = 'open')
        ORDER BY c.title"""), {"p": patient_id}).mappings().all()
    out = []
    for r in rows:
        det = r["details"] or {}
        sched = parse_schedule(det.get("frequency_text"))
        if not sched or _as_needed(r["title"], det):
            continue                                   # "if pain", "if fever" and anything else that is not a plain schedule is not tracked
        start = r["created_at"].astimezone(IST).date()
        days = det.get("duration_days")
        end = start + timedelta(days=int(days) - 1) if days else None
        if today < start or (end and today > end):
            continue
        out.append({"item_key": r["item_key"], "title": r["title"], "slots": {k: v for k, v in sched.items() if v}, "start": start, "end": end,
                    "confirmer": r["confirmer"]})
    return out


def today_view(s: Session, patient_id: UUID, now: datetime | None = None) -> dict[str, Any]:
    n = _now(now)
    today = n.date()
    items = scheduled_items(s, patient_id, today)
    logs = {(r["item_key"], r["slot"]): r for r in s.execute(text("""
        SELECT l.item_key, l.slot, l.status, l.recorded_at, u.display_name AS who FROM dose_logs l JOIN users u ON u.id = l.recorded_by
        WHERE l.patient_id = :p AND l.for_date = :d"""), {"p": patient_id, "d": today}).mappings().all()}
    slots = []
    counts = {"taken": 0, "not_taken": 0, "due": 0, "not_marked": 0, "later": 0}
    for slot in SLOTS:
        due_at = datetime(today.year, today.month, today.day, SLOT_HOURS[slot], 0, tzinfo=IST)
        rows = []
        for it in items:
            if slot not in it["slots"]:
                continue
            log = logs.get((it["item_key"], slot))
            if log:
                status = log["status"]
            elif n < due_at:
                status = "later"
            elif n <= due_at + GRACE:
                status = "due"
            else:
                status = "not_marked"
            counts[status] += 1
            rows.append({"item_key": str(it["item_key"]), "title": it["title"], "units": it["slots"][slot], "status": status,
                         "marked_by": log["who"] if log else None, "marked_at": log["recorded_at"].astimezone(IST).strftime("%H:%M") if log else None,
                         "how": f"From the plan, confirmed by {it['confirmer']}" + (f", until {it['end']:%d %b}" if it["end"] else "")})
        if rows:
            slots.append({"slot": slot, "label": LABEL[slot], "time": f"{SLOT_HOURS[slot]:02d}:00", "items": rows})
    today_pain = s.execute(text("SELECT pain, note, recorded_at FROM wellbeing_checkins WHERE patient_id = :p AND for_date = :d"),
                           {"p": patient_id, "d": today}).mappings().first()
    last = s.execute(text("""SELECT greatest((SELECT max(recorded_at) FROM dose_logs WHERE patient_id = :p),
                                            (SELECT max(recorded_at) FROM wellbeing_checkins WHERE patient_id = :p))"""), {"p": patient_id}).scalar()
    return {"date": today.isoformat(), "now": n.strftime("%H:%M"), "slots": slots, "summary": counts,
            "checkin": {"pain": today_pain["pain"], "note": today_pain["note"], "at": today_pain["recorded_at"].astimezone(IST).strftime("%H:%M")} if today_pain else None,
            "last_activity": last.astimezone(IST).strftime("%d %b, %H:%M") if last else None, "note": NOTE}


def log_dose(s: Session, *, patient_id: UUID, user_id: UUID, item_key: UUID, slot: str, status: str, now: datetime | None = None) -> dict[str, Any]:
    if slot not in SLOTS or status not in ("taken", "not_taken"):
        raise ServiceError(422, "bad-dose", "Choose a time of day and taken or not taken")
    today = _now(now).date()
    match = next((i for i in scheduled_items(s, patient_id, today) if i["item_key"] == item_key and slot in i["slots"]), None)
    if match is None:
        raise ServiceError(404, "not-scheduled", "That medicine is not on today's schedule at that time")
    s.execute(text("""INSERT INTO dose_logs (patient_id, item_key, slot, for_date, status, recorded_by) VALUES (:p, :k, :s, :d, :st, :u)
                      ON CONFLICT (patient_id, item_key, slot, for_date) DO UPDATE SET status = :st, recorded_by = :u, recorded_at = now()"""),
              {"p": patient_id, "k": item_key, "s": slot, "d": today, "st": status, "u": user_id})
    write_audit(s, actor_type="user", actor_id=user_id, patient_id=patient_id, action=f"dose.{status}", entity_type="care_plan_item",
                entity_id=item_key, after={"slot": slot, "date": today.isoformat()})
    if status == "not_taken":
        name = s.execute(text("SELECT full_name FROM patients WHERE id = :p"), {"p": patient_id}).scalar()
        timeline(s, patient_id=patient_id, event_type="dose_not_taken", actor_type="user", actor_id=user_id,
                 summary=f"{match['title']} ({LABEL[slot].lower()}) was marked as not taken for {name}. Ask the doctor or pharmacist what to do.",
                 entity_type="care_plan_item", entity_id=item_key)
    return {"item_key": str(item_key), "slot": slot, "status": status}


def save_wellbeing(s: Session, *, patient_id: UUID, user_id: UUID, pain: int | None, note: str | None, now: datetime | None = None) -> dict[str, Any]:
    note = (note or "").strip() or None
    if pain is None and not note:
        raise ServiceError(422, "empty-checkin", "Choose a number or write a short note")
    if pain is not None and not 0 <= pain <= 10:
        raise ServiceError(422, "bad-pain", "The number must be from 0 to 10")
    if note and len(note) > 300:
        raise ServiceError(422, "too-long", "Please keep the note under 300 characters")
    today = _now(now).date()
    s.execute(text("""INSERT INTO wellbeing_checkins (patient_id, for_date, pain, note, recorded_by) VALUES (:p, :d, :pa, :n, :u)
                      ON CONFLICT (patient_id, for_date) DO UPDATE SET pain = :pa, note = :n, recorded_by = :u, recorded_at = now()"""),
              {"p": patient_id, "d": today, "pa": pain, "n": note, "u": user_id})
    write_audit(s, actor_type="user", actor_id=user_id, patient_id=patient_id, action="wellbeing.checkin", entity_type="patient", entity_id=patient_id,
                after={"date": today.isoformat(), "has_pain": pain is not None, "has_note": bool(note)})
    return {"date": today.isoformat(), "pain": pain, "note": note}


def wellbeing_history(s: Session, patient_id: UUID, days: int = 14, now: datetime | None = None) -> dict[str, Any]:
    """The entries as written, newest first, and how many of the last N days have one. No averages, no direction, no labels."""
    today = _now(now).date()
    since = today - timedelta(days=days - 1)
    rows = s.execute(text("""SELECT c.for_date, c.pain, c.note, c.recorded_at, u.display_name AS who FROM wellbeing_checkins c JOIN users u ON u.id = c.recorded_by
                             WHERE c.patient_id = :p AND c.for_date BETWEEN :a AND :b ORDER BY c.for_date DESC"""), {"p": patient_id, "a": since, "b": today}).mappings().all()
    return {"days": days, "days_with_entry": len(rows), "entries": [{"date": r["for_date"].isoformat(), "pain": r["pain"], "note": r["note"], "by": r["who"]} for r in rows],
            "note": "These are the numbers and words that were entered, in order. CareSaathi does not say whether they are good or bad. Show them to the doctor."}
