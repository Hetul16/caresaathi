"""The Doctor Visit Listener against a real database. The mock visits replay the synthetic scripts' recorded answers (the
offline stand-in cannot hear audio), so these tests check consent, validation, pending changes and revocation, not a model."""
from __future__ import annotations

import io
import time
import wave
from datetime import date, datetime, timedelta, timezone

import pytest

pytestmark = pytest.mark.usefixtures("scratch_db")

IST = timezone(timedelta(hours=5, minutes=30))
CONSENT = {"patient_consent": {"agreed": True, "given_by_name": "Priya Kulkarni", "on_behalf_of_patient": True},
           "doctor_consent": {"agreed": True, "given_by_name": "Dr. Joshi"}, "consent_text_version": "visit-recording-v1"}


def start_mock(family, script="V1", **over):
    body = {**CONSENT, "script_id": script, **over}
    r = family.post(f"/patients/{family.pid}/visits/mock", body)
    assert r.status_code == 202, r.text
    vid = r.json()["id"]
    for _ in range(100):
        d = family.get(f"/visits/{vid}").json()
        if d["status"] not in ("processing", "recording"):
            return d
        time.sleep(0.1)
    raise AssertionError("visit was not processed in time")


def wav(seconds=1.0) -> bytes:
    buf = io.BytesIO()
    with wave.open(buf, "wb") as w:
        w.setnchannels(1); w.setsampwidth(2); w.setframerate(16000)
        w.writeframes(b"\x00\x00" * int(16000 * seconds))
    return buf.getvalue()


# ---- consent ------------------------------------------------------------------------------------------------------------------
@pytest.mark.parametrize("patient,doctor", [(False, True), (True, False)])
def test_nothing_starts_without_both_consents(family, patient, doctor):
    body = {**CONSENT, "patient_consent": {**CONSENT["patient_consent"], "agreed": patient}, "doctor_consent": {**CONSENT["doctor_consent"], "agreed": doctor}}
    r = family.post(f"/patients/{family.pid}/visits", body)
    assert r.status_code == 422 and "consent" in r.json()["type"]
    assert family.get(f"/patients/{family.pid}/visits").json() == []


def test_names_are_required_and_the_consent_text_version_must_match(family):
    no_name = {**CONSENT, "doctor_consent": {"agreed": True, "given_by_name": " "}}
    assert family.post(f"/patients/{family.pid}/visits", no_name).status_code == 422
    stale = {**CONSENT, "consent_text_version": "visit-recording-v0"}
    assert family.post(f"/patients/{family.pid}/visits", stale).status_code == 422


def test_consent_rows_are_stored_for_both_sides(family, admin):
    vid = family.post(f"/patients/{family.pid}/visits", CONSENT).json()["id"]
    rows = admin.execute("""SELECT c.subject_role::text, c.given_by_name, c.on_behalf_of_patient FROM visits v
                            JOIN consents c ON c.id IN (v.patient_consent_id, v.doctor_consent_id) WHERE v.id = %s ORDER BY 1""", (vid,)).fetchall()
    assert rows == [("doctor", "Dr. Joshi", False), ("patient", "Priya Kulkarni", True)]


def test_the_database_refuses_a_visit_with_one_consent_for_both_sides(family, admin):
    import psycopg
    cid = admin.execute("""INSERT INTO consents (patient_id, consent_type, subject_role, given_by_name, consent_text_version)
                           VALUES (%s, 'visit_recording', 'patient', 'X', 'v') RETURNING id""", (family.pid,)).fetchone()[0]
    with pytest.raises(psycopg.errors.CheckViolation):
        admin.execute("INSERT INTO visits (patient_id, started_by, patient_consent_id, doctor_consent_id) VALUES (%s, %s, %s, %s)",
                      (family.pid, family.user_id, cid, cid))


# ---- the replayed Hinglish visit ------------------------------------------------------------------------------------------------
def test_v1_creates_pending_changes_with_the_doctors_exact_words(family):
    family.upload("Tab Amlodipine 10 mg 1-0-0 x 30 days\n", name="before.txt", doc_type="prescription")
    d = start_mock(family, "V1")
    assert d["origin"] == "mock" and d["status"] == "completed" and d["failure_note"] is None
    plan = family.plan()
    assert [c["title"] for c in plan["pending_changes"] if c["change_type"] == "changed"] == ["Amlodipine 5 mg"]
    ch = next(c for c in plan["pending_changes"] if c["change_type"] == "changed")
    assert ch["before"] == "1-0-0" and "5 mg" in ch["after"] and ch["requires_confirmation"] is True
    assert ch["source"]["quote"].startswith("ab main amlodipine ka dose kam kar raha hoon")        # the doctor's own words
    # Nothing is in the plan yet: the old dose is still the current one.
    assert next(i for i in plan["items"] if i["title"].startswith("Amlodipine"))["title"] == "Amlodipine 10 mg"


def test_confirming_the_visit_change_adds_a_confirmed_version_sourced_to_the_words(family):
    family.upload("Tab Amlodipine 10 mg 1-0-0 x 30 days\n", name="before.txt", doc_type="prescription")
    start_mock(family, "V1")
    cid = next(c["id"] for c in family.plan()["pending_changes"] if c["change_type"] == "changed")
    assert family.post(f"/plan-changes/{cid}/decision", {"decision": "confirm"}).status_code == 200
    am = next(i for i in family.plan()["items"] if i["title"].startswith("Amlodipine"))
    assert am["title"] == "Amlodipine 5 mg" and am["version"] == 2 and am["confirmed"] and am["confirmed_by"] == "Priya Kulkarni"
    assert am["source"]["kind"] == "visit_segment" and "5 mg subah ek baar" in am["source"]["quote"]


def test_the_warning_sign_level_comes_from_the_doctors_wording(family):
    start_mock(family, "V1")
    sign = next(c for c in family.plan()["pending_changes"] if "emergency" in c["title"].lower())
    assert sign["source"]["quote"] == "Agar chest pain ho to immediately emergency mein aana."
    cid = sign["id"]
    family.post(f"/plan-changes/{cid}/decision", {"decision": "confirm"})
    item = next(i for i in family.plan()["items"] if i["kind"] == "warning_sign")
    assert item["alert_level"] == "emergency"


def test_the_follow_up_is_dated_by_code_from_the_visit_date(family):
    d = start_mock(family, "V1")
    visit_day = datetime.fromisoformat(d["started_at"]).astimezone(IST).date()
    fu = family.get(f"/patients/{family.pid}/follow-ups").json()
    assert len(fu) == 1 and fu[0]["due_date"] == (visit_day + timedelta(days=14)).isoformat() and fu[0]["anchor_kind"] == "visit"
    assert fu[0]["source"]["quote"] == "Do hafte baad review ke liye aaiye." and fu[0]["status"] == "pending"


def test_v2_a_new_medicine_and_a_three_month_follow_up(family):
    d = start_mock(family, "V2")
    assert d["status"] == "completed"
    assert [c["change_type"] for c in family.plan()["pending_changes"]] == ["new"]
    visit_day = datetime.fromisoformat(d["started_at"]).astimezone(IST).date()
    due = family.get(f"/patients/{family.pid}/follow-ups").json()[0]["due_date"]
    assert date.fromisoformat(due) > visit_day + timedelta(days=80)


def test_v3_unclear_speech_creates_no_change_and_goes_to_the_family(family):
    d = start_mock(family, "V3")
    assert d["status"] == "needs_review" and family.plan()["pending_changes"] == []
    assert d["unclear"] and "cannot be mapped" in d["unclear"][0]["note"]


# ---- speakers, access, withdrawal ---------------------------------------------------------------------------------------------------
def test_the_family_can_correct_who_is_who(family):
    d = start_mock(family, "V1")
    assert {s["label"]: s["role"] for s in d["speakers"]} == {"A": "doctor", "B": "patient", "C": "family"}
    assert all(s["mapped_by"] == "model" for s in d["speakers"])
    r = family.client.put(f"/api/v1/visits/{d['id']}/speakers", headers=family.h, json={"speakers": [{"label": "C", "role": "nurse", "name": "Sister Anita"}]})
    assert r.status_code == 200
    d2 = family.get(f"/visits/{d['id']}").json()
    c = next(s for s in d2["speakers"] if s["label"] == "C")
    assert (c["role"], c["name"], c["mapped_by"], c["confirmed"]) == ("nurse", "Sister Anita", "family", True)
    assert {x["role"] for x in d2["segments"] if x["speaker"] == "C"} == {"nurse"}


def test_another_family_cannot_see_a_visit(family, stranger):
    d = start_mock(family, "V1")
    assert stranger.get(f"/visits/{d['id']}").status_code == 404
    assert stranger.get(f"/patients/{family.pid}/visits").status_code == 404


def test_a_member_without_recording_access_sees_no_transcript(family, admin):
    d = start_mock(family, "V1")
    viewer = family.second_member(can_approve=True)           # can_view_recordings is false for added members
    r = family.client.get(f"/api/v1/visits/{d['id']}", headers=viewer).json()
    assert r["transcript_hidden"] is True and r["segments"] == [] and r["changes"]


def test_withdrawing_consent_removes_the_words_and_sets_changes_aside(family, admin):
    d = start_mock(family, "V1")
    cid = next(c["id"] for c in d["consents"] if c["role"] == "patient")
    assert family.post(f"/visits/{d['id']}/consents/{cid}/revoke").status_code == 200
    d2 = family.get(f"/visits/{d['id']}").json()
    assert d2["status"] == "cancelled" and all("removed" in s["text"] for s in d2["segments"])
    assert all(c["status"] == "superseded" for c in d2["changes"]) and family.plan()["pending_changes"] == []
    assert admin.execute("SELECT count(*) FROM source_refs WHERE segment_id IN (SELECT id FROM transcript_segments WHERE visit_id = %s) AND quote NOT LIKE '[removed%%'", (d["id"],)).fetchone()[0] == 0
    assert admin.execute("SELECT count(*) FROM audit_log WHERE action = 'visit.consent_revoked'").fetchone()[0] >= 1


# ---- real audio (offline mode cannot hear it) ----------------------------------------------------------------------------------------
def test_audio_is_checked_and_offline_mode_says_it_cannot_hear_it(family):
    vid = family.post(f"/patients/{family.pid}/visits", CONSENT).json()["id"]
    bad = family.client.post(f"/api/v1/visits/{vid}/audio", headers=family.h, files={"file": ("x.wav", b"not audio", "audio/wav")})
    assert bad.status_code == 422 and bad.json()["type"].endswith("audio-rejected")
    ok = family.client.post(f"/api/v1/visits/{vid}/audio", headers=family.h, files={"file": ("visit.wav", wav(1.0), "audio/wav")})
    assert ok.status_code == 202
    for _ in range(100):
        d = family.get(f"/visits/{vid}").json()
        if d["status"] != "processing":
            break
        time.sleep(0.1)
    assert d["status"] == "failed" and "mock visit" in d["failure_note"].lower() and d["changes"] == []
    assert family.plan()["pending_changes"] == []                                           # nothing was invented


def test_a_second_recording_cannot_be_added_to_a_visit(family):
    vid = family.post(f"/patients/{family.pid}/visits", CONSENT).json()["id"]
    family.client.post(f"/api/v1/visits/{vid}/audio", headers=family.h, files={"file": ("a.wav", wav(), "audio/wav")})
    again = family.client.post(f"/api/v1/visits/{vid}/audio", headers=family.h, files={"file": ("b.wav", wav(), "audio/wav")})
    assert again.status_code == 409


def test_scripts_are_listed_and_labeled_synthetic(family):
    scripts = family.get("/visit-scripts").json()
    assert [s["id"] for s in scripts] == ["V1", "V2", "V3"] and next(s for s in scripts if s["id"] == "V2")["experimental"] is True


def test_the_english_visit_turns_into_a_warning_sign_and_a_follow_up_but_no_medicine_change(family):
    """V4 is plain English. The doctor says both medicines continue, so nothing about them is proposed as a change."""
    d = start_mock(family, "V4", language_hint="en")
    assert d["status"] in ("completed", "needs_review") and d["language_hint"] == "en"
    plan = family.plan()
    titles = [c["title"].lower() for c in plan["pending_changes"]]
    assert any("chest pain" in t for t in titles) and not any("metformin" in t or "atorvastatin" in t for t in titles)
    chest = next(c for c in plan["pending_changes"] if "chest pain" in c["title"].lower())
    assert chest["source"]["kind"] == "visit_segment" and "fifteen minutes" in chest["source"]["quote"]
    fu = [f for f in family.get(f"/patients/{family.pid}/follow-ups").json() if "sugar" in f["what"].lower()]
    assert fu and fu[0]["due_text"] == "in two weeks" and fu[0]["status"] == "pending" and fu[0]["due_date"]
    assert any(s["id"] == "V4" and s["language"] == "en" for s in family.get("/visit-scripts").json())
