"""End-to-end API behaviour against a real Postgres with row-level security (see conftest.py)."""
from __future__ import annotations

import json
import re

import psycopg
import pytest

pytestmark = pytest.mark.usefixtures("scratch_db")

DISCHARGE = """CITY HOSPITAL, PUNE - DISCHARGE SUMMARY
Page 1 of 1
Patient: Ramesh Kulkarni, 74 y
Allergic to penicillin (rash)
Tab Amoxicillin 500 mg 1-0-1 x 5 days
Tab Metformin 500 mg 1-0-1 after food
Go to the emergency immediately if chest pain
"""


def _source(admin, pid: str, doc_id: str, quote: str = "Tab Penicillin V 250 mg 1-0-1") -> str:
    return admin.execute("""INSERT INTO source_refs (patient_id, kind, document_id, page, line_start, quote)
                            VALUES (%s, 'document', %s, 1, 5, %s) RETURNING id""", (pid, doc_id, quote)).fetchone()[0]


def _pending(admin, pid, doc_id, *, ctype="new", item_key=None, after=None, before=None) -> str:
    src = _source(admin, pid, doc_id)
    return str(admin.execute("""INSERT INTO plan_changes (patient_id, change_type, item_key, before_state, after_state, source_ref_id)
                                VALUES (%s, %s, %s, %s, %s, %s) RETURNING id""",
                             (pid, ctype, item_key, json.dumps(before) if before else None, json.dumps(after) if after else None, src)).fetchone()[0])


# ---- sign in -----------------------------------------------------------------------------------------------------
def test_wrong_password_and_missing_token_are_401(client, family):
    r = client.post("/api/v1/auth/login", json={"identifier": family.email, "password": "not-the-password"})
    assert r.status_code == 401
    assert client.get(f"/api/v1/patients/{family.pid}/care-plan").status_code == 401


# ---- document to plan ----------------------------------------------------------------------------------------------
def test_document_becomes_a_sourced_plan_with_an_allergy_flag(family):
    family.upload(DISCHARGE)
    plan = family.plan()
    assert plan["allergies"]["state"] == "listed"
    assert plan["allergies"]["items"][0]["source"]["quote"] == "Allergic to penicillin (rash)"
    assert all(i["source"]["quote"] and i["source"]["page"] for i in plan["items"])
    amox = next(c for c in plan["open_conflicts"] if c["medicine"].startswith("Amoxicillin"))
    assert amox["match"] == "drug_family"
    assert amox["doctor_question"].rstrip().endswith("?")
    # Unknown is not safe: an ingredient the reference list cannot resolve is shown as such, never as clear.
    metformin = next(c for c in plan["open_conflicts"] if c["medicine"].startswith("Metformin"))
    assert metformin["match"] == "unresolved" and "could not check" in metformin["flag"].lower()
    # Nothing a document says is confirmed until a named person does so.
    assert not any(i["confirmed"] for i in plan["items"])


def test_empty_allergy_list_is_not_recorded_never_none(family):
    family.upload("Tab Metformin 500 mg 1-0-1 after food\n", name="rx.txt", doc_type="prescription")
    assert family.plan()["allergies"] == {"state": "not_recorded", "items": []}


def test_another_family_sees_nothing(family, stranger):
    doc = family.upload(DISCHARGE)
    for path in (f"/patients/{family.pid}/care-plan", f"/patients/{family.pid}/plan-changes", f"/patients/{family.pid}/actions",
                 f"/patients/{family.pid}/reconciliation", f"/documents/{doc}"):
        assert stranger.get(path).status_code == 404, path
    assert stranger.get("/patients").json() == [{**p} for p in stranger.get("/patients").json()]
    assert all(p["id"] != family.pid for p in stranger.get("/patients").json())


# ---- confirming ------------------------------------------------------------------------------------------------------
def test_confirming_needs_approval_rights_and_names_the_person(family):
    family.upload(DISCHARGE)
    key = next(i for i in family.plan()["items"] if i["kind"] == "medicine")["item_key"]
    viewer = family.second_member(can_approve=False)
    r = family.client.post(f"/api/v1/patients/{family.pid}/plan-items/{key}/confirm", headers=viewer)
    assert r.status_code == 403
    assert family.post(f"/patients/{family.pid}/plan-items/{key}/confirm").status_code == 200
    item = next(i for i in family.plan()["items"] if i["item_key"] == key)
    assert item["confirmed"] and item["confirmed_by"] == "Priya Kulkarni"


# ---- pending changes ---------------------------------------------------------------------------------------------------
def test_confirming_a_pending_change_adds_a_confirmed_version_and_rechecks_allergies(family, admin):
    doc = family.upload(DISCHARGE)
    cid = _pending(admin, family.pid, doc, after={"kind": "medicine", "title": "Penicillin V 250 mg",
                                                  "details": {"frequency_text": "1-0-1", "dose_text": "250 mg"}})
    pending = family.get(f"/patients/{family.pid}/plan-changes").json()
    assert [p["id"] for p in pending] == [cid] and pending[0]["source"]["quote"]
    assert family.post(f"/plan-changes/{cid}/decision", {"decision": "confirm"}).status_code == 200
    plan = family.plan()
    added = next(i for i in plan["items"] if i["title"] == "Penicillin V 250 mg")
    assert added["confirmed"] and added["confirmed_by"] == "Priya Kulkarni"
    assert any(c["medicine"] == "Penicillin V 250 mg" and c["match"] in ("direct", "drug_family") for c in plan["open_conflicts"])
    assert plan["pending_changes"] == []
    assert family.post(f"/plan-changes/{cid}/decision", {"decision": "confirm"}).status_code == 409


def test_changed_item_supersedes_the_old_version(family, admin):
    doc = family.upload(DISCHARGE)
    old = next(i for i in family.plan()["items"] if i["title"].startswith("Metformin"))
    cid = _pending(admin, family.pid, doc, ctype="changed", item_key=old["item_key"],
                   after={"kind": "medicine", "title": "Metformin 500 mg", "details": {"frequency_text": "1-0-0"}})
    assert family.post(f"/plan-changes/{cid}/decision", {"decision": "confirm"}).status_code == 200
    new = next(i for i in family.plan()["items"] if i["item_key"] == old["item_key"])
    assert new["version"] == old["version"] + 1 and new["detail"] == "1-0-0"
    current = admin.execute("SELECT count(*) FROM care_plan_items WHERE item_key = %s AND is_current", (old["item_key"],)).fetchone()[0]
    assert current == 1


def test_rejecting_a_change_changes_nothing(family, admin):
    doc = family.upload(DISCHARGE)
    before = family.plan()["items"]
    cid = _pending(admin, family.pid, doc, after={"kind": "medicine", "title": "Ibuprofen 400 mg", "details": {}})
    assert family.post(f"/plan-changes/{cid}/decision", {"decision": "reject"}).json()["status"] == "rejected"
    assert family.plan()["items"] == before


def test_a_member_without_approval_rights_cannot_decide(family, admin):
    doc = family.upload(DISCHARGE)
    cid = _pending(admin, family.pid, doc, after={"kind": "medicine", "title": "Ibuprofen 400 mg", "details": {}})
    viewer = family.second_member(can_approve=False)
    r = family.client.post(f"/api/v1/plan-changes/{cid}/decision", headers=viewer, json={"decision": "confirm"})
    assert r.status_code == 403
    assert admin.execute("SELECT status FROM plan_changes WHERE id = %s", (cid,)).fetchone()[0] == "pending"


def test_the_database_refuses_an_unconfirmed_apply(family, admin):
    doc = family.upload(DISCHARGE)
    cid = _pending(admin, family.pid, doc, after={"kind": "medicine", "title": "Ibuprofen 400 mg", "details": {}})
    with pytest.raises(psycopg.errors.CheckViolation):
        admin.execute("UPDATE plan_changes SET status = 'applied' WHERE id = %s", (cid,))


# ---- allergy flags -------------------------------------------------------------------------------------------------------
def test_acknowledging_a_flag_is_audited_and_does_not_call_the_medicine_fine(family, admin):
    family.upload(DISCHARGE)
    plan = family.plan()
    cid = next(c for c in plan["open_conflicts"] if c["match"] == "drug_family")["id"]
    r = family.post(f"/allergy-conflicts/{cid}/acknowledge", {"note": "Asked Dr Joshi"})
    assert r.json()["status"] == "acknowledged"
    assert cid not in [c["id"] for c in family.plan()["open_conflicts"]]
    row = admin.execute("SELECT actor_id::text FROM audit_log WHERE action = 'allergy.conflict_acknowledged' AND entity_id = %s", (cid,)).fetchone()
    assert row and row[0] == family.user_id


# ---- approvals -------------------------------------------------------------------------------------------------------------
def test_sharing_a_card_waits_for_a_named_approver(family, admin):
    card = family.post(f"/patients/{family.pid}/emergency-card", {}).json()
    r = family.post(f"/emergency-cards/{card['id']}/share", {"contact_name": "Dr Joshi"})
    assert r.status_code == 202 and r.json()["status"] == "awaiting_approval"
    waiting = family.plan()["approvals"]
    assert len(waiting) == 1 and "Dr Joshi" in waiting[0]["summary"]
    aid = waiting[0]["id"]
    viewer = family.second_member(can_approve=False)
    assert family.client.post(f"/api/v1/actions/{aid}/approve", headers=viewer, json={}).status_code == 403
    assert family.post(f"/actions/{aid}/approve", {}).json()["status"] == "approved"
    row = admin.execute("SELECT status, approved_by::text FROM actions WHERE id = %s", (aid,)).fetchone()
    assert row == ("approved", family.user_id)
    assert family.post(f"/actions/{aid}/approve", {}).status_code == 409


def test_the_database_refuses_an_unapproved_ask_first_action(family, admin):
    card = family.post(f"/patients/{family.pid}/emergency-card", {}).json()
    aid = family.post(f"/emergency-cards/{card['id']}/share", {"contact_name": "X"}).json()["id"]
    with pytest.raises(psycopg.errors.CheckViolation):
        admin.execute("UPDATE actions SET status = 'done' WHERE id = %s", (aid,))


def test_refusing_an_action_records_it(family):
    card = family.post(f"/patients/{family.pid}/emergency-card", {}).json()
    aid = family.post(f"/emergency-cards/{card['id']}/share", {"contact_name": "X"}).json()["id"]
    assert family.post(f"/actions/{aid}/refuse", {"comment": "Not now"}).json()["status"] == "refused"
    assert family.plan()["approvals"] == []


# ---- Emergency Card ----------------------------------------------------------------------------------------------------------
def test_emergency_card_lifecycle(family, client, admin):
    family.upload(DISCHARGE)
    card = family.post(f"/patients/{family.pid}/emergency-card", {"expires_in_days": 30}).json()
    token = card["url"].rsplit("/e/", 1)[1]
    assert len(token) >= 30 and card["hint"] == token[-4:]
    # Only a hash is stored, never the token.
    assert admin.execute("SELECT count(*) FROM emergency_cards WHERE token_hint = %s AND token_hash <> %s::bytea", (token[-4:], token.encode())).fetchone()[0] == 1
    assert token not in json.dumps(admin.execute("SELECT to_jsonb(c) FROM emergency_cards c WHERE id = %s", (card["id"],)).fetchone()[0])

    r = client.get(f"/api/v1/e/{token}")           # no sign-in
    assert r.status_code == 200 and r.headers["cache-control"] == "no-store"
    body = r.json()
    assert body["allergies"]["state"] == "listed" and body["allergies"]["items"][0]["substance"] == "Penicillin"
    assert body["allergies"]["items"][0]["source"]["quote"]
    assert body["last_updated_at"]
    assert all(m["source"]["quote"] for m in body["medicines"])
    assert "contacts" in body and "email" not in json.dumps(body).lower()

    assert family.post(f"/emergency-cards/{card['id']}/revoke").json()["status"] == "revoked"
    gone, unknown = client.get(f"/api/v1/e/{token}"), client.get("/api/v1/e/" + "x" * 32)
    assert gone.status_code == unknown.status_code == 404 and gone.json() == unknown.json() == {"available": False}

    outcomes = [r[0] for r in admin.execute("SELECT outcome::text FROM emergency_card_access_log WHERE card_id = %s ORDER BY id", (card["id"],)).fetchall()]
    assert outcomes == ["ok", "revoked"]
    assert admin.execute("SELECT count(*) FROM emergency_card_access_log WHERE outcome = 'not_found'").fetchone()[0] >= 1


def test_an_expired_card_looks_like_an_unknown_one(family, client, admin):
    card = family.post(f"/patients/{family.pid}/emergency-card", {"expires_in_days": 1}).json()
    token = card["url"].rsplit("/e/", 1)[1]
    admin.execute("UPDATE emergency_cards SET expires_at = now() - interval '1 minute' WHERE id = %s", (card["id"],))
    assert client.get(f"/api/v1/e/{token}").status_code == 404
    assert admin.execute("SELECT outcome::text FROM emergency_card_access_log WHERE card_id = %s", (card["id"],)).fetchone()[0] == "expired"


def test_card_without_documents_says_not_recorded(family, client):
    token = family.post(f"/patients/{family.pid}/emergency-card", {}).json()["url"].rsplit("/e/", 1)[1]
    body = client.get(f"/api/v1/e/{token}").json()
    assert body["allergies"] == {"state": "not_recorded", "items": []}
    assert body["medicines"] == [] and body["last_updated_at"] is None


def test_only_managers_can_create_cards(family):
    viewer = family.second_member(can_approve=True)
    r = family.client.post(f"/api/v1/patients/{family.pid}/emergency-card", headers=viewer, json={})
    assert r.status_code == 403


# ---- omission catch (S10) ----------------------------------------------------------------------------------------------------
BEFORE = """CITY HOSPITAL - DISCHARGE SUMMARY
Page 1 of 1
Tab Ibuprofen 400 mg 1-0-1 after food
Tab Azithromycin 500 mg 1-0-0 x 3 days
Tab Naproxen 250 mg 1-0-1
"""
AFTER_COMPLETE = """RECOVERY CLINIC - DISCHARGE SUMMARY
Page 1 of 1
Tab Ibuprofen 400 mg 1-0-1 after food
Tab Azithromycin 500 mg 1-0-0 x 3 days
"""


def test_a_missing_medicine_is_flagged_with_both_sources_and_a_question(family):
    family.upload(BEFORE, name="first.txt")
    family.upload(AFTER_COMPLETE, name="second.txt")
    flags = family.get(f"/patients/{family.pid}/reconciliation").json()
    assert [f["medicine"] for f in flags] == ["Naproxen 250 mg"]
    f = flags[0]
    assert f["previous_source"]["quote"] == "Tab Naproxen 250 mg 1-0-1" and f["new_document"] == "second.txt"
    assert f["question"].rstrip().endswith(".") or f["question"].rstrip().endswith("?")
    assert not re.search(r"stopped on purpose|safe to stop|should (?:continue|stop)", f["question"], re.I)
    assert family.plan()["omissions"][0]["id"] == f["id"]


def test_an_incomplete_or_unmarked_document_raises_no_flag(family):
    family.upload(BEFORE, name="first.txt")
    family.upload("RECOVERY CLINIC - DISCHARGE SUMMARY\nTab Ibuprofen 400 mg 1-0-1 after food\n", name="no-marker.txt")   # unknown
    family.upload("RECOVERY CLINIC\nPage 1 of 3\nTab Azithromycin 500 mg 1-0-0 x 3 days\n", name="partial.txt")             # incomplete
    assert family.get(f"/patients/{family.pid}/reconciliation").json() == []


def test_a_person_can_vouch_for_a_document_after_the_fact(family, admin):
    family.upload(BEFORE, name="first.txt")
    doc = family.upload("RECOVERY CLINIC\nTab Ibuprofen 400 mg 1-0-1 after food\n", name="no-marker.txt")
    assert admin.execute("SELECT completeness FROM documents WHERE id = %s", (doc,)).fetchone()[0] == "unknown"
    assert family.post(f"/documents/{doc}/completeness", {"completeness": "complete"}).status_code == 200
    assert admin.execute("SELECT count(*) FROM audit_log WHERE action = 'document.completeness_set' AND entity_id = %s", (doc,)).fetchone()[0] == 1


def test_an_unresolved_ingredient_is_not_flagged_as_missing(family):
    family.upload("EARLIER HOSPITAL - DISCHARGE SUMMARY\nPage 1 of 1\nTab Zzyxomab 10 mg 1-0-0\n", name="first.txt")
    family.upload(AFTER_COMPLETE, name="second.txt")
    assert family.get(f"/patients/{family.pid}/reconciliation").json() == []


def test_prescriptions_do_not_trigger_the_omission_catch(family):
    family.upload(BEFORE, name="first.txt")
    family.upload(AFTER_COMPLETE, name="rx.txt", doc_type="prescription")
    assert family.get(f"/patients/{family.pid}/reconciliation").json() == []


def test_flag_state_moves_only_by_a_named_person(family, admin):
    family.upload(BEFORE, name="first.txt")
    family.upload(AFTER_COMPLETE, name="second.txt")
    fid = family.get(f"/patients/{family.pid}/reconciliation").json()[0]["id"]
    assert family.post(f"/reconciliation-flags/{fid}/state", {"state": "asked"}).json()["state"] == "asked"
    with pytest.raises(psycopg.errors.CheckViolation):
        admin.execute("UPDATE reconciliation_flags SET state = 'resolved', state_changed_by = NULL WHERE id = %s", (fid,))
    assert family.post(f"/reconciliation-flags/{fid}/state", {"state": "resolved"}).status_code == 200
    assert family.get(f"/patients/{family.pid}/reconciliation").json() == []


# ---- versions from documents ---------------------------------------------------------------------------------------------------
def test_a_second_document_that_changes_a_medicine_adds_a_new_version(family, admin):
    family.upload("Tab Metformin 500 mg 1-0-1 after food\n", name="a.txt", doc_type="prescription")
    first = next(i for i in family.plan()["items"] if i["title"].startswith("Metformin"))
    family.upload("Tab Metformin 500 mg 1-0-0 after food\n", name="b.txt", doc_type="prescription")
    second = next(i for i in family.plan()["items"] if i["item_key"] == first["item_key"])
    assert (first["version"], second["version"]) == (1, 2)
    assert admin.execute("SELECT count(*) FROM care_plan_items WHERE item_key = %s", (first["item_key"],)).fetchone()[0] == 2
    assert admin.execute("SELECT count(*) FROM care_plan_items WHERE item_key = %s AND is_current", (first["item_key"],)).fetchone()[0] == 1


def test_the_database_only_accepts_known_completeness_values(family, admin):
    doc = family.upload("Tab Metformin 500 mg 1-0-1\n", name="c.txt", doc_type="prescription")
    with pytest.raises(psycopg.errors.CheckViolation):
        admin.execute("UPDATE documents SET completeness = 'probably' WHERE id = %s", (doc,))
