"""Two-reader check (A5, D-54): a disagreement is held for a person, never applied, and a person's choice goes through the normal path."""
import json

import psycopg
import pytest

from app.clients.models import FakeModelClient

PAGE = ("CLINIC PRESCRIPTION\nPage 1 of 1\nDate: 24/10/2026\nPatient: Ramesh Kulkarni\nTab Amlodipine 5 mg 1-0-0\nStrength smudged: could read 0.5 mg or 5 mg\n")


class Readers(FakeModelClient):
    """First reading: strength 0.5 mg and a note that part of the page was unclear. Second reading: 5 mg (or whatever a test sets)."""

    def __init__(self, first_strength="0.5 mg", second_strength="5 mg", unclear=True, second_missing=False, first_missing=False):
        self.first_strength, self.second_strength, self.unclear, self.second_missing, self.first_missing = first_strength, second_strength, unclear, second_missing, first_missing
        self.second_calls = 0

    def _variant(self, pages, strength, unclear, missing):
        raw = json.loads(FakeModelClient.extract_document(self, pages, None)[0])
        raw["items"] = [] if missing else [{**it, "details": {**it["details"], "ingredients": [{"name": "Amlodipine", "strength": strength}]}} for it in raw["items"]]
        raw["unreadable"] = [{"page": 1, "note": "the strength is smudged"}] if unclear else []
        return json.dumps(raw)

    def extract_document(self, pages, hint, variant=False):
        return self._variant(pages, self.first_strength, self.unclear, self.first_missing), self._usage("extract_document")

    def second_read_document(self, pages):
        self.second_calls += 1
        return self._variant(pages, self.second_strength, False, self.second_missing), self._usage("extract_document")


def _upload(family, monkeypatch, client):
    monkeypatch.setattr("app.pipelines.documents.get_model_client", lambda: client)
    family.upload(PAGE, "R7_blurry.txt", doc_type="prescription")


def _reads(family):
    return family.get(f"/patients/{family.pid}/second-reads").json()["reads"]


def test_a_disagreement_is_held_and_not_applied(family, monkeypatch):
    c = Readers()
    _upload(family, monkeypatch, c)
    assert c.second_calls == 1
    assert not any("Amlodipine" in i["title"] for i in family.plan()["items"])           # nothing applied
    (r,) = _reads(family)
    assert r["differs_in"] == ["strength"] and r["reading_a"]["strength"] == "0.5 mg" and r["reading_b"]["strength"] == "5 mg"
    assert r["reading_a"]["quote"] and r["chosen"] is None
    doc = family.get(f"/patients/{family.pid}/documents").json()
    assert any(d["status"] == "needs_review" for d in (doc if isinstance(doc, list) else doc.get("documents", [])))


def test_choosing_a_reading_applies_it_with_the_page_line_and_only_once(family, monkeypatch, admin):
    _upload(family, monkeypatch, Readers())
    (r,) = _reads(family)
    out = family.post(f"/second-reads/{r['id']}/choose", {"choice": "b"})
    assert out.status_code == 200 and out.json()["applied_change"]
    item = next(i for i in family.plan()["items"] if "Amlodipine" in i["title"])
    assert item["source"]["kind"] == "document" and "Amlodipine" in item["source"]["quote"] and item["confirmed"]
    assert family.post(f"/second-reads/{r['id']}/choose", {"choice": "a"}).status_code == 409
    assert _reads(family)[0]["chosen"] == "b" and _reads(family)[0]["chosen_by"] == "Priya Kulkarni"
    assert admin.execute("SELECT count(*) FROM audit_log WHERE action = 'second_read.chosen' AND patient_id = %s", (family.pid,)).fetchone()[0] == 1


def test_choosing_neither_adds_nothing(family, monkeypatch):
    _upload(family, monkeypatch, Readers())
    (r,) = _reads(family)
    out = family.post(f"/second-reads/{r['id']}/choose", {"choice": "neither"}).json()
    assert out["chosen"] == "neither" and out["applied_change"] is None
    assert not any("Amlodipine" in i["title"] for i in family.plan()["items"])


def test_a_clear_page_never_triggers_a_second_read(family, monkeypatch):
    c = Readers(unclear=False)
    _upload(family, monkeypatch, c)
    assert c.second_calls == 0 and _reads(family) == []


def test_two_readers_that_agree_hold_nothing(family, monkeypatch):
    c = Readers(first_strength="5 mg", second_strength="5 mg")
    _upload(family, monkeypatch, c)
    assert c.second_calls == 1 and _reads(family) == []
    assert any("Amlodipine" in i["title"] for i in family.plan()["items"])


def test_a_medicine_only_the_second_reader_found_cannot_be_chosen_from_the_empty_reading(family, monkeypatch):
    _upload(family, monkeypatch, Readers(first_missing=True))
    (r,) = _reads(family)
    assert r["reading_a"] is None and r["reading_b"]["strength"] == "5 mg" and r["differs_in"] == ["name"]
    assert family.post(f"/second-reads/{r['id']}/choose", {"choice": "a"}).status_code == 422
    assert family.post(f"/second-reads/{r['id']}/choose", {"choice": "b"}).status_code == 200


def test_only_a_member_with_approval_rights_can_choose_and_others_cannot_see_it(family, client, admin, monkeypatch):
    from conftest import Family
    _upload(family, monkeypatch, Readers())
    (r,) = _reads(family)
    viewer = family.second_member(can_approve=False)
    assert client.post(f"/api/v1/second-reads/{r['id']}/choose", headers=viewer, json={"choice": "b"}).status_code == 403
    other = Family(client, admin, "Someone Else")
    assert other.get(f"/patients/{family.pid}/second-reads").status_code == 404
    assert other.post(f"/second-reads/{r['id']}/choose", {"choice": "b"}).status_code in (403, 404)


def test_the_database_requires_a_difference_and_a_chooser(family, admin, monkeypatch):
    _upload(family, monkeypatch, Readers())
    (r,) = _reads(family)
    with pytest.raises(psycopg.errors.CheckViolation):
        admin.execute("UPDATE second_reads SET chosen_reading = 'a' WHERE id = %s", (r["id"],))          # no named chooser
    with pytest.raises(psycopg.errors.CheckViolation):
        admin.execute("UPDATE second_reads SET differing_fields = '{}' WHERE id = %s", (r["id"],))
