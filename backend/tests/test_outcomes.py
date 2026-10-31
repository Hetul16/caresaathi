"""Outcomes board (C6, D-52): every flag is a question until a named person records the answer and where it came from."""
from pathlib import Path

import psycopg
import pytest

DOCS = Path(__file__).resolve().parents[2] / "data" / "synthetic" / "ramesh" / "docs"


def _doc(family, stem, doc_type="prescription"):
    f = next(DOCS.glob(f"{stem}_*.txt"))
    family.upload(f.read_text(encoding="utf-8"), f.name, doc_type=doc_type)


def _with_conflict(family):
    for stem in ("R4", "R1", "R5"):                       # penicillin allergy, clinic prescription, amoxicillin from another doctor
        _doc(family, stem)
    board = family.get(f"/patients/{family.pid}/outcomes").json()
    return board, next(i for i in board["items"] if i["kind"] == "allergy_conflict")


def _reply_from_doctor(family, client, words):
    link = family.post(f"/patients/{family.pid}/doctor-links", {"doctor_name": "Dr. Joshi (fictional)", "expires_in_days": 7}).json()
    token = link["url"].rsplit("/d/", 1)[1]
    q = family.post(f"/doctor-links/{link['id']}/questions", {"body": "About the amoxicillin?"}).json()
    family.post(f"/actions/{q['id']}/approve", {})
    assert client.post(f"/api/v1/d/{token}/reply", json={"body": words}).status_code == 200
    return next(m for m in family.get(f"/patients/{family.pid}/doctor-links").json()["links"][0]["messages"] if m["direction"] == "from_doctor")


def test_a_new_flag_appears_on_the_board_as_an_open_question(family):
    board, c = _with_conflict(family)
    assert c["status"] == "open" and c["question"].strip() and c["answer"] is None
    s = board["summary"]
    assert s["raised"] >= 1 and s["answered"] == 0 and s["waiting"] >= 1 and s["average_days_to_answer"] is None
    assert "does not judge the answer" in board["note"]


def test_a_typed_answer_closes_the_flag_with_its_source_and_who_recorded_it(family):
    _, c = _with_conflict(family)
    r = family.post(f"/patients/{family.pid}/outcomes/answers", {"subject_kind": "allergy_conflict", "subject_id": c["id"],
                                                                 "answer_text": "Dr. Joshi said she knows about the allergy and will call us.",
                                                                 "answered_by": "Dr. Joshi"})
    assert r.status_code == 201
    board = family.get(f"/patients/{family.pid}/outcomes").json()
    item = next(i for i in board["items"] if i["id"] == c["id"])
    assert item["status"] == "answered" and item["answer"]["answered_by"] == "Dr. Joshi"
    assert item["answer"]["source_kind"] == "family_note" and item["answer"]["recorded_by"] == "Priya Kulkarni"
    assert board["summary"]["answered"] == 1 and board["summary"]["average_days_to_answer"] == 0
    assert all(x["id"] != c["id"] for x in family.plan()["open_conflicts"])          # no longer a banner
    assert family.post(f"/patients/{family.pid}/outcomes/answers", {"subject_kind": "allergy_conflict", "subject_id": c["id"],
                                                                    "answer_text": "again", "answered_by": "x"}).status_code == 409


def test_a_doctor_reply_can_be_the_answer_and_is_copied_word_for_word(family, client):
    _, c = _with_conflict(family)
    words = "  Please bring the allergy card on Thursday.  "
    msg = _reply_from_doctor(family, client, words)
    assert msg["id"] in [r["id"] for r in family.get(f"/patients/{family.pid}/outcomes").json()["usable_replies"]]
    r = family.post(f"/patients/{family.pid}/outcomes/answers", {"subject_kind": "allergy_conflict", "subject_id": c["id"],
                                                                 "doctor_message_id": msg["id"], "answer_text": "something else typed", "answered_by": "someone else"})
    assert r.status_code == 201
    item = next(i for i in family.get(f"/patients/{family.pid}/outcomes").json()["items"] if i["id"] == c["id"])
    assert item["answer"]["text"] == words.strip() and item["answer"]["answered_by"] == "Dr. Joshi (fictional)"      # the typed text is ignored
    assert item["answer"]["source_kind"] == "doctor_message"
    assert family.get(f"/patients/{family.pid}/outcomes").json()["usable_replies"] == []


def test_a_closed_flag_without_an_answer_is_counted_separately(family):
    _doc(family, "R1")
    _doc(family, "R2", "discharge_summary")                  # the discharge summary leaves Atorvastatin off the earlier list
    flag = next((i for i in family.get(f"/patients/{family.pid}/outcomes").json()["items"] if i["kind"] == "reconciliation_flag"), None)
    assert flag is not None and flag["title"].lower().startswith("atorvastatin")
    family.post(f"/reconciliation-flags/{flag['id']}/state", {"state": "resolved"})
    s = family.get(f"/patients/{family.pid}/outcomes").json()
    assert s["summary"]["closed_without_answer"] == 1 and s["summary"]["answered"] == 0


def test_only_a_member_with_approval_rights_can_record_an_answer(family, client):
    _, c = _with_conflict(family)
    viewer = family.second_member(can_approve=False)
    r = client.post(f"/api/v1/patients/{family.pid}/outcomes/answers", headers=viewer,
                    json={"subject_kind": "allergy_conflict", "subject_id": c["id"], "answer_text": "ok", "answered_by": "Dr"})
    assert r.status_code == 403
    assert client.get(f"/api/v1/patients/{family.pid}/outcomes", headers=viewer).status_code == 200      # but can read the board


def test_an_answer_needs_words_and_a_name_and_cannot_use_another_patients_reply(family, client, admin):
    from conftest import Family
    _, c = _with_conflict(family)
    assert family.post(f"/patients/{family.pid}/outcomes/answers", {"subject_kind": "allergy_conflict", "subject_id": c["id"],
                                                                    "answer_text": "  ", "answered_by": "Dr"}).status_code == 422
    other = Family(client, admin, "Someone Else")
    foreign = _reply_from_doctor(other, client, "Words about another patient.")
    r = family.post(f"/patients/{family.pid}/outcomes/answers", {"subject_kind": "allergy_conflict", "subject_id": c["id"], "doctor_message_id": foreign["id"]})
    assert r.status_code == 404
    assert other.get(f"/patients/{family.pid}/outcomes").status_code == 404


def test_the_database_ties_the_source_kind_to_the_stored_reply(family, admin):
    _, c = _with_conflict(family)
    with pytest.raises(psycopg.errors.CheckViolation):
        admin.execute("""INSERT INTO question_answers (patient_id, subject_kind, subject_id, answer_text, answered_by, source_kind, recorded_by)
                         VALUES (%s, 'allergy_conflict', %s, 'x', 'Dr', 'doctor_message', %s)""", (family.pid, c["id"], family.user_id))
    admin.execute("""INSERT INTO question_answers (patient_id, subject_kind, subject_id, answer_text, answered_by, source_kind, recorded_by)
                     VALUES (%s, 'allergy_conflict', %s, 'said so', 'Dr', 'family_note', %s)""", (family.pid, c["id"], family.user_id))
    with pytest.raises(psycopg.errors.UniqueViolation):
        admin.execute("""INSERT INTO question_answers (patient_id, subject_kind, subject_id, answer_text, answered_by, source_kind, recorded_by)
                         VALUES (%s, 'allergy_conflict', %s, 'twice', 'Dr', 'family_note', %s)""", (family.pid, c["id"], family.user_id))


def test_the_board_never_uses_safety_words(family):
    board, _ = _with_conflict(family)
    blob = " ".join([board["note"]] + [i["question"] + i["label"] for i in board["items"]]).lower()
    for bad in ("is safe", "safe to", "no risk", "cleared", "approved by"):
        assert bad not in blob
