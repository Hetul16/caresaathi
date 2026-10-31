"""A line the checks are unsure about must not vanish. Found on Oct 31 with the live model: a physiotherapy plan's emergency instruction was held
for low confidence and never reached the plan, with only "some lines need a check" on the document. It is now a pending change with its page line."""
import json
from pathlib import Path

from app.clients.models import FakeModelClient

S4 = next((Path(__file__).resolve().parents[2] / "data" / "synthetic" / "sunita" / "docs").glob("S4_*.txt"))


class Unsure(FakeModelClient):
    """The reader reports low confidence on every warning sign."""

    def extract_document(self, pages, hint, variant=False):
        raw = json.loads(FakeModelClient.extract_document(self, pages, None)[0])
        for it in raw["items"]:
            if it["kind"] == "warning_sign":
                it["confidence"] = 0.2
        return json.dumps(raw), self._usage("extract_document")


def test_a_held_warning_sign_becomes_a_pending_change_with_its_page_line(family, monkeypatch):
    monkeypatch.setattr("app.pipelines.documents.get_model_client", lambda: Unsure())
    family.upload(S4.read_text(encoding="utf-8"), S4.name, doc_type="specialist_letter")
    plan = family.plan()
    assert not any(i["kind"] == "warning_sign" for i in plan["items"])                 # not applied on the reader's say-so
    held = [c for c in plan["pending_changes"] if "emergency" in (c["title"] + str(c.get("after"))).lower() or "control urine" in c["title"].lower()]
    assert held and held[0]["source"]["kind"] == "document" and "emergency room" in held[0]["source"]["quote"].lower()
    # a named person decides; the level still comes from the page's own words
    assert family.post(f"/plan-changes/{held[0]['id']}/decision", {"decision": "confirm"}).status_code == 200
    signs = [i for i in family.plan()["items"] if i["kind"] == "warning_sign"]
    assert signs and any(s["alert_level"] == "emergency" for s in signs)


def test_a_rejected_line_whose_quote_is_not_on_the_page_is_never_offered(family, monkeypatch):
    class Invented(FakeModelClient):
        def extract_document(self, pages, hint, variant=False):
            raw = json.loads(FakeModelClient.extract_document(self, pages, None)[0])
            raw["items"].append({"kind": "warning_sign", "title": "Go to hospital at once", "confidence": 0.9, "details": {"level_basis_quote": "made up"},
                                 "source": {"page": 1, "line_start": 3, "line_end": 3, "quote": "This sentence is not on the page"}})
            return json.dumps(raw), self._usage("extract_document")
    monkeypatch.setattr("app.pipelines.documents.get_model_client", lambda: Invented())
    family.upload(S4.read_text(encoding="utf-8"), S4.name, doc_type="specialist_letter")
    assert not any("hospital at once" in c["title"].lower() for c in family.plan()["pending_changes"])
    assert not any("hospital at once" in i["title"].lower() for i in family.plan()["items"])
