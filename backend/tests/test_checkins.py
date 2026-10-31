"""Daily check-ins (C7, D-58): which doses appear, what "not marked" means, and that nothing is ever interpreted."""
from datetime import datetime, timedelta, timezone
from pathlib import Path
from uuid import UUID

import psycopg
import pytest

from app.db import worker_session
from app.services import checkins

DOCS = Path(__file__).resolve().parents[2] / "data" / "synthetic" / "sunita" / "docs"
IST = timezone(timedelta(hours=5, minutes=30))


def _upload(family, stem, kind):
    f = next(DOCS.glob(f"{stem}_*.txt"))
    family.upload(f.read_text(encoding="utf-8"), f.name, doc_type=kind)


def _documents(family):
    for stem, kind in (("S1", "other"), ("S2", "prescription"), ("S5", "prescription")):
        _upload(family, stem, kind)


def _confirmed_plan(family):
    _documents(family)
    for i in family.plan()["items"]:
        if i["kind"] == "medicine":
            family.post(f"/patients/{family.pid}/plan-items/{i['item_key']}/confirm")


def _at(hour, minute=0):
    d = datetime.now(IST)
    return datetime(d.year, d.month, d.day, hour, minute, tzinfo=IST)


def _today(family, at):
    with worker_session() as s:
        return checkins.today_view(s, UUID(family.pid), now=at)


def _rows(view, slot):
    return [r for sl in view["slots"] if sl["slot"] == slot for r in sl["items"]]


def test_only_confirmed_scheduled_medicines_not_held_by_an_allergy_flag_appear(family):
    _documents(family)
    assert _today(family, _at(9))["slots"] == []                                 # nothing is confirmed yet
    _confirmed_plan(family)
    v = _today(family, _at(9))
    everything = " ".join(r["title"] for sl in v["slots"] for r in sl["items"]).lower()
    assert "calpol" in everything and "pregabalin" in everything and "pantoprazole" in everything and "calcium" in everything
    assert "diclofenac" not in everything                                          # an open allergy flag holds it back, as on the fridge sheet
    assert "dolo" not in everything                                                # "if pain" is as-needed, so there is no time to mark
    assert any("Pregabalin" in r["title"] for r in _rows(v, "evening")) and not any("Pregabalin" in r["title"] for r in _rows(v, "morning"))


def test_status_depends_on_the_clock_and_on_what_a_person_marked(family):
    _confirmed_plan(family)
    assert {r["status"] for r in _rows(_today(family, _at(7)), "morning")} == {"later"}
    assert {r["status"] for r in _rows(_today(family, _at(8, 30)), "morning")} == {"due"}
    late = _today(family, _at(10, 30))
    assert {r["status"] for r in _rows(late, "morning")} == {"not_marked"}
    assert late["summary"]["not_marked"] >= 2 and "does not say what a missed dose means" in late["note"]
    first = _rows(late, "morning")[0]
    r = family.post(f"/patients/{family.pid}/doses", {"item_key": first["item_key"], "slot": "morning", "status": "taken"})
    assert r.status_code == 201
    api = family.get(f"/patients/{family.pid}/today").json()
    row = next(x for x in _rows(api, "morning") if x["item_key"] == first["item_key"])
    assert row["status"] == "taken" and row["marked_by"] == "Priya Kulkarni" and api["last_activity"]


def test_a_dose_that_is_not_on_todays_schedule_cannot_be_marked(family):
    _confirmed_plan(family)
    night_only = next(r for r in _rows(_today(family, _at(9)), "evening") if "Pregabalin" in r["title"])
    bad = family.post(f"/patients/{family.pid}/doses", {"item_key": night_only["item_key"], "slot": "morning", "status": "taken"})
    assert bad.status_code == 404
    unknown = family.post(f"/patients/{family.pid}/doses", {"item_key": "00000000-0000-0000-0000-000000000000", "slot": "morning", "status": "taken"})
    assert unknown.status_code == 404


def test_not_taken_is_recorded_with_a_neutral_notice_and_never_advice(family, admin):
    _confirmed_plan(family)
    item = _rows(_today(family, _at(9)), "morning")[0]
    assert family.post(f"/patients/{family.pid}/doses", {"item_key": item["item_key"], "slot": "morning", "status": "not_taken"}).status_code == 201
    ev = [t["text"] for t in family.plan()["timeline"] if "not taken" in t["text"]]
    assert ev and "Ask the doctor or pharmacist" in ev[0]
    assert not any(w in ev[0].lower() for w in ("take it now", "take it later", "double", "skip", "safe", "should"))
    assert admin.execute("SELECT count(*) FROM audit_log WHERE action = 'dose.not_taken' AND patient_id = %s", (family.pid,)).fetchone()[0] == 1
    # a correction on the same day replaces the mark instead of adding a second one
    assert family.post(f"/patients/{family.pid}/doses", {"item_key": item["item_key"], "slot": "morning", "status": "taken"}).status_code == 201
    assert admin.execute("SELECT count(*), max(status) FROM dose_logs WHERE patient_id = %s AND item_key = %s", (family.pid, item["item_key"])).fetchone() == (1, "taken")


def test_a_finished_course_is_no_longer_scheduled(family):
    _confirmed_plan(family)
    v = _today(family, _at(9) + timedelta(days=7))             # Calpol was written for 5 days; Pantoprazole for 14
    flat = " ".join(r["title"] for sl in v["slots"] for r in sl["items"]).lower()
    assert "calpol" not in flat and "pantoprazole" in flat


def test_wellbeing_is_stored_as_entered_and_never_labelled(family):
    assert family.post(f"/patients/{family.pid}/wellbeing", {"pain": 7, "note": "Woke up twice because of the back"}).status_code == 201
    assert family.post(f"/patients/{family.pid}/wellbeing", {"pain": 5}).status_code == 201          # a later entry the same day replaces it
    assert family.post(f"/patients/{family.pid}/wellbeing", {}).status_code == 422
    assert family.post(f"/patients/{family.pid}/wellbeing", {"pain": 11}).status_code == 422
    h = family.get(f"/patients/{family.pid}/wellbeing").json()
    assert h["days_with_entry"] == 1 and h["entries"][0]["pain"] == 5 and h["entries"][0]["note"] is None
    blob = (h["note"] + str(h)).lower()
    for word in ("improving", "worsening", "worse", "better", "severe", "normal", "high", "trend", "average"):
        assert word not in blob
    assert family.get(f"/patients/{family.pid}/today").json()["checkin"]["pain"] == 5


def test_only_members_can_see_or_record_and_the_database_keeps_its_limits(family, client, admin):
    from conftest import Family
    other = Family(client, admin, "Someone Else")
    assert other.get(f"/patients/{family.pid}/today").status_code == 404
    assert other.post(f"/patients/{family.pid}/wellbeing", {"pain": 3}).status_code == 404
    with pytest.raises(psycopg.errors.CheckViolation):
        admin.execute("INSERT INTO wellbeing_checkins (patient_id, for_date, pain, recorded_by) VALUES (%s, current_date, 11, %s)", (family.pid, family.user_id))
    with pytest.raises(psycopg.errors.CheckViolation):
        admin.execute("INSERT INTO wellbeing_checkins (patient_id, for_date, recorded_by) VALUES (%s, current_date, %s)", (family.pid, family.user_id))
    with pytest.raises(psycopg.errors.CheckViolation):
        admin.execute("INSERT INTO dose_logs (patient_id, item_key, slot, for_date, status, recorded_by) VALUES (%s, gen_random_uuid(), 'dawn', current_date, 'taken', %s)", (family.pid, family.user_id))
