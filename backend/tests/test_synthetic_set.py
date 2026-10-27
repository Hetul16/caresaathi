"""The fictional documents in data/synthetic, run through the real pipeline against a real database. Each test is one
planted case from docs/17-synthetic-data-plan.md. The offline reader is a rule-based stand-in, so this measures the
pipeline and the safety logic, not a model."""
from __future__ import annotations

import json
import re
from pathlib import Path

import psycopg
import pytest

pytestmark = pytest.mark.usefixtures("scratch_db")

DATA = Path(__file__).resolve().parents[2] / "data" / "synthetic"
KIND = {"R1": "prescription", "R2": "discharge_summary", "R3": "lab_report", "R4": "other", "R5": "prescription", "R6": "other",
        "R7": "prescription", "R8": "prescription", "R9": "discharge_summary", "R10": "prescription",
        "M2": "discharge_summary", "M3": "prescription", "H2": "discharge_summary", "H3": "prescription"}


def doc(family, doc_id: str) -> str:
    folder = {"R": "ramesh", "M": "margaret", "H": "hans"}[doc_id[0]]
    path = next((DATA / folder / "docs").glob(f"{doc_id}_*.txt"))
    return family.upload(path.read_text(encoding="utf-8"), name=path.name, doc_type=KIND[doc_id])


def meds(plan):
    return {i["title"]: i for i in plan["items"] if i["kind"] == "medicine"}


# ---- R1: the baseline ---------------------------------------------------------------------------------------------------
def test_r1_baseline_plan_follow_up_and_supply(family):
    doc(family, "R1")
    plan = family.plan()
    assert set(meds(plan)) == {"Amlodipine 10 mg", "Metformin 500 mg", "Atorvastatin 20 mg", "Paraclear 500"}
    assert plan["allergies"] == {"state": "not_recorded", "items": []}
    assert all(i["source"]["quote"] and i["source"]["page"] == 1 for i in plan["items"])

    fu = family.get(f"/patients/{family.pid}/follow-ups").json()
    assert [f["what"] for f in fu] == ["Review in 2 weeks"]
    assert fu[0]["due_date"] == "2026-09-28" and fu[0]["status"] == "pending"        # 14 Sep + 2 weeks, by code
    assert "14 Sep 2026" in fu[0]["how"] and "2 weeks" in fu[0]["how"]                  # the inputs are shown

    supply = {s["medicine"]: s for s in family.get(f"/patients/{family.pid}/supply").json()}
    assert supply["Amlodipine 10 mg"]["estimated_run_out"] == "2026-10-14"              # 30 tablets, 1 a day
    assert supply["Metformin 500 mg"]["estimated_run_out"] == "2026-10-14"              # 60 tablets, 2 a day
    assert supply["Metformin 500 mg"]["confirmed_by"] is None
    assert "÷" in supply["Metformin 500 mg"]["how"]


# ---- R2: omission, duplicate, follow-ups, warning levels -------------------------------------------------------------------
def test_r2_omission_duplicate_followups_and_levels(family):
    doc(family, "R1")
    doc(family, "R2")
    flags = family.get(f"/patients/{family.pid}/reconciliation").json()
    assert [f["medicine"] for f in flags] == ["Atorvastatin 20 mg"]
    q = flags[0]["question"]
    assert "?" in q and not re.search(r"stopped on purpose|safe to stop|should (?:continue|stop)", q, re.I)
    assert flags[0]["previous_source"]["quote"].startswith("Tab Atorvastatin 20 mg") and flags[0]["new_document"].startswith("R2_")

    plan = family.plan()
    dup = plan["duplicates"]
    assert len(dup) == 1 and dup[0]["ingredient"] == "paracetamol" and sorted(dup[0]["medicines"]) == ["Fevonil 500", "Paraclear 500"]
    assert dup[0]["question"].rstrip().endswith(".") and "?" in dup[0]["question"]

    levels = {i["title"]: i["alert_level"] for i in plan["items"] if i["kind"] == "warning_sign"}
    assert sorted(levels.values()) == ["call_doctor_today", "emergency"]                  # from the written words only

    due = {f["what"]: f["due_date"] for f in family.get(f"/patients/{family.pid}/follow-ups").json()}
    assert due["Repeat HbA1c after 3 months"] == "2027-01-20"                            # 20 Oct + 3 months


def test_r9_a_discharge_summary_with_page_two_missing_raises_no_omission(family):
    doc(family, "R1")
    doc(family, "R9")                      # also omits Atorvastatin, but says "Page 1 of 2" and has no page 2
    assert family.get(f"/patients/{family.pid}/reconciliation").json() == []


# ---- allergies -----------------------------------------------------------------------------------------------------------------
def test_r4_then_r5_raises_a_drug_family_conflict_without_any_safety_claim(family):
    doc(family, "R4")
    doc(family, "R5")
    plan = family.plan()
    assert plan["allergies"]["state"] == "listed" and plan["allergies"]["items"][0]["substance"] == "Penicillin"
    c = next(c for c in plan["open_conflicts"] if c["medicine"].startswith("Amoxicillin"))
    assert c["match"] == "drug_family" and c["doctor_question"].rstrip().endswith("?")
    assert not re.search(r"\bsafe\b|\bunsafe\b|\bfine\b|\bok\b", c["flag"], re.I)


def test_r10_a_document_without_an_allergy_section_is_not_recorded(family):
    doc(family, "R10")
    assert family.plan()["allergies"] == {"state": "not_recorded", "items": []}


def test_margaret_sulfa_allergy_then_a_sulfonamide(family):
    doc(family, "M2")
    doc(family, "M3")
    plan = family.plan()
    assert plan["allergies"]["items"][0]["substance"] == "Sulfa"
    assert any(c["medicine"].startswith("Sulfamethoxazole") and c["match"] == "drug_family" for c in plan["open_conflicts"])


def test_hans_unknown_brand_is_could_not_check_never_clear(family):
    doc(family, "H2")
    doc(family, "H3")
    plan = family.plan()
    z = next(c for c in plan["open_conflicts"] if c["medicine"].startswith("Zolvanex"))
    assert z["match"] == "unresolved" and "could not check" in z["flag"].lower()


# ---- hostile and unreadable documents -------------------------------------------------------------------------------------------
def test_r8_an_instruction_inside_a_document_changes_nothing(family, admin):
    doc(family, "R8")
    plan = family.plan()
    assert set(meds(plan)) == {"Metformin 500 mg"}                                        # only the real line became an item
    assert family.get(f"/patients/{family.pid}/actions").json() == []                    # nothing queued
    assert admin.execute("SELECT count(*) FROM emergency_cards WHERE patient_id = %s", (family.pid,)).fetchone()[0] == 0
    assert admin.execute("SELECT count(*) FROM actions WHERE patient_id = %s", (family.pid,)).fetchone()[0] == 0
    assert "safe" not in json.dumps(plan["items"]).lower()
    assert any("read like instructions" in e["text"] for e in plan["timeline"])          # and a person is told


def test_r6_an_unreadable_document_adds_nothing_and_asks_a_person(family, admin):
    d = doc(family, "R6")
    assert family.plan()["items"] == []
    assert admin.execute("SELECT status FROM documents WHERE id = %s", (d,)).fetchone()[0] == "needs_review"
    assert any("could not read anything" in t["text"] for t in family.plan()["timeline"])


def test_r3_a_lab_report_gives_a_follow_up_and_no_interpretation(family):
    doc(family, "R3")
    plan = family.plan()
    assert plan["items"] == []                                                             # values are not turned into advice
    assert [f["due_text"] for f in family.get(f"/patients/{family.pid}/follow-ups").json()] == ["Repeat HbA1c after 3 months"]


# ---- confirming trackers ---------------------------------------------------------------------------------------------------------
def test_confirming_a_follow_up_names_the_person_and_creates_a_reminder(family, admin):
    doc(family, "R1")
    fid = family.get(f"/patients/{family.pid}/follow-ups").json()[0]["id"]
    assert family.post(f"/follow-ups/{fid}/decision", {"action": "confirm"}).json()["status"] == "confirmed"
    row = admin.execute("SELECT status, confirmed_by::text FROM follow_ups WHERE id = %s", (fid,)).fetchone()
    assert row == ("confirmed", family.user_id)
    assert admin.execute("SELECT count(*) FROM reminders WHERE patient_id = %s AND kind = 'followup'", (family.pid,)).fetchone()[0] == 1
    assert family.post(f"/follow-ups/{fid}/decision", {"action": "confirm"}).status_code == 409
    assert family.post(f"/follow-ups/{fid}/decision", {"action": "done"}).json()["status"] == "done"


def test_only_an_approver_can_confirm_a_follow_up(family):
    doc(family, "R1")
    fid = family.get(f"/patients/{family.pid}/follow-ups").json()[0]["id"]
    viewer = family.second_member(can_approve=False)
    assert family.client.post(f"/api/v1/follow-ups/{fid}/decision", headers=viewer, json={"action": "confirm"}).status_code == 403
    assert family.client.post(f"/api/v1/follow-ups/{fid}/decision", headers=viewer, json={"action": "dismiss"}).status_code == 200


def test_the_database_refuses_an_unnamed_follow_up_decision(family, admin):
    doc(family, "R1")
    fid = family.get(f"/patients/{family.pid}/follow-ups").json()[0]["id"]
    with pytest.raises(psycopg.errors.CheckViolation):
        admin.execute("UPDATE follow_ups SET status = 'confirmed' WHERE id = %s", (fid,))


def test_confirming_supply_names_the_person(family):
    doc(family, "R1")
    sid = family.get(f"/patients/{family.pid}/supply").json()[0]["id"]
    assert family.post(f"/supply/{sid}/confirm").status_code == 200
    row = next(r for r in family.get(f"/patients/{family.pid}/supply").json() if r["id"] == sid)       # by id: two rows can share a date
    assert row["confirmed_by"] == "Priya Kulkarni"


# ---- history and the fridge sheet ----------------------------------------------------------------------------------------------
def test_medicine_history_keeps_every_version_with_its_source(family):
    doc(family, "R1")
    family.upload("Tab Amlodipine 5 mg 1-0-0 after breakfast\n", name="visit-note.txt", doc_type="prescription")
    h = {m["title"]: m for m in family.get(f"/patients/{family.pid}/medicine-history").json()}
    am = h["Amlodipine 5 mg"]
    assert [v["version"] for v in am["versions"]] == [1, 2]
    assert [v["title"] for v in am["versions"]] == ["Amlodipine 10 mg", "Amlodipine 5 mg"]
    assert am["versions"][0]["current"] is False and am["versions"][1]["current"] is True
    assert all(v["source"]["quote"] for v in am["versions"])


def test_fridge_sheet_has_only_confirmed_medicines_without_open_flags(family):
    doc(family, "R4")
    doc(family, "R5")                                        # amoxicillin raises an open conflict
    doc(family, "R10")                                       # metformin
    plan = family.plan()
    for key in [i["item_key"] for i in plan["items"] if i["kind"] == "medicine"]:
        family.post(f"/patients/{family.pid}/plan-items/{key}/confirm")
    sheet = family.get(f"/patients/{family.pid}/fridge-sheet").json()
    assert [m["title"] for m in sheet["medicines"]] == ["Metformin 500 mg"]              # amoxicillin is held back
    assert sheet["allergy_state"] == "listed" and sheet["allergies"][0]["substance"] == "Penicillin"
    assert all(m["source"] for m in sheet["medicines"]) and "not medical advice" in sheet["note"].lower()


def test_fridge_sheet_leaves_out_unconfirmed_medicines(family):
    doc(family, "R10")
    assert family.get(f"/patients/{family.pid}/fridge-sheet").json()["medicines"] == []
