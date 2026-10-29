"""The live reader's JSON is repaired (labels only) before validation. Found by running the website against the live model on Oct 29:
an allergy card came back as doc_type "allergy_card", the whole extraction failed validation, and the penicillin allergy was lost."""
import json
from types import SimpleNamespace

import pytest

from app.clients import models, repair
from app.models.contracts import ExtractV1, VisitV1
from app.safety.validate import validate_extraction

ALLERGY_CARD = {"schema_version": "extract.v1", "document": {"doc_type": "allergy_card", "language": "en"}, "items": [],
                "allergy_statement": "listed", "providers": [], "unreadable": [], "follow_ups": [],
                "allergies": [{"substance": "penicillin", "reaction": "rash", "severity": "unknown",
                               "source": {"page": 1, "line_start": 5, "line_end": 5, "quote": "Allergic to penicillin (rash)"}}]}
PAGE = {1: "SYNTHETIC\nALLERGY CARD\nPage 1 of 1\nName: Ramesh Kulkarni\nAllergic to penicillin (rash)"}


def test_the_exact_failure_from_the_live_run_no_longer_loses_the_allergy():
    with pytest.raises(Exception):
        ExtractV1.model_validate(ALLERGY_CARD)                    # the unrepaired answer is invalid
    fixed = repair.repair_extract(ALLERGY_CARD)
    assert fixed["document"]["doc_type"] == "other"
    v = validate_extraction(json.dumps(fixed), PAGE)
    assert v.ok and [a.substance for a in v.data.allergies] == ["penicillin"] and not v.rejected_allergies


def test_repairs_fix_labels_and_never_invent_facts():
    raw = {"document": {"doc_type": "Discharge Summary", "language": "Hindi"}, "extra_key": 1, "allergy_statement": "yes",
           "items": [{"kind": "medicine", "title": "Metformin", "source": {"page": 1, "quote": "Metformin"}},        # no confidence
                     {"kind": "mystery", "title": "x", "source": {"page": 1, "quote": "x"}},                          # unknown kind: dropped
                     {"kind": "medicine", "source": {"page": 1, "quote": "y"}}],                                      # no title: dropped
           "allergies": [{"substance": "sulfa", "severity": "catastrophic", "source": {"page": 1, "quote": "sulfa"}}]}
    fixed = repair.repair_extract(raw)
    assert fixed["document"]["doc_type"] == "discharge_summary" and fixed["document"]["language"] == "mixed"
    assert "extra_key" not in fixed and fixed["allergy_statement"] == "listed"
    assert [i["title"] for i in fixed["items"]] == ["Metformin"] and fixed["items"][0]["confidence"] == 0.5
    assert fixed["allergies"][0]["severity"] == "unknown"
    ExtractV1.model_validate(fixed)


def test_no_allergies_never_becomes_listed_and_a_listed_allergy_wins_over_a_wrong_statement():
    assert repair.repair_extract({"allergy_statement": "banana"})["allergy_statement"] == "not_mentioned"
    assert repair.repair_extract({"allergy_statement": "none_stated"})["allergy_statement"] == "none_stated"
    listed = {"allergy_statement": "none_stated", "allergies": [{"substance": "penicillin", "source": {"page": 1, "quote": "penicillin"}}]}
    assert repair.repair_extract(listed)["allergy_statement"] == "listed"     # a recorded allergy is never hidden behind "none"


def test_visit_repair_drops_what_it_cannot_fix_and_keeps_the_rest():
    raw = {"speaker_roles": [{"label": "A", "role": "physician"}],
           "items": [{"kind": "medicine", "change": "increase", "title": "Amlodipine", "source": {"segment_ids": ["s1"], "quote": "q"}},
                     {"kind": "medicine", "change": "changed", "title": "Amlodipine 5 mg", "source": {"segment_ids": ["s1"], "quote": "q"}, "confidence": "high"}],
           "allergies_mentioned": [{"substance": "x", "stated_by": "nurse", "source": {"segment_ids": ["s1"], "quote": "x"}}]}
    fixed = repair.repair_visit(raw)
    assert fixed["speaker_roles"][0]["role"] == "unknown"
    assert [i["title"] for i in fixed["items"]] == ["Amlodipine 5 mg"] and fixed["items"][0]["confidence"] == 0.5
    assert fixed["allergies_mentioned"] == []
    VisitV1.model_validate(fixed)


def _client(answers):
    it = iter(answers)
    c = models.LiveModelClient.__new__(models.LiveModelClient)
    c.s = SimpleNamespace(effort_read="low")
    c._chat = lambda *a, **k: (next(it), models.Usage("m", "extract_document"))
    return c


def test_the_live_reader_asks_again_when_the_first_answer_is_not_json():
    prompts = []
    c = _client(["Sorry, here is the result: not json", json.dumps(ALLERGY_CARD)])
    inner = c._chat
    c._chat = lambda purpose, content, *a, **k: (prompts.append(content[0]["text"]), inner(purpose, content))[1]
    text, _ = c.extract_document([models.PageText(1, ["Allergic to penicillin (rash)"])], None)
    assert len(prompts) == 2 and "not valid JSON" in prompts[1] and "not valid JSON" not in prompts[0]
    assert json.loads(text)["allergies"][0]["substance"] == "penicillin" and json.loads(text)["document"]["doc_type"] == "other"


def test_an_answer_that_is_never_valid_json_is_returned_for_downstream_failure():
    c = _client(["not json", "still not json", "nope"])
    text, _ = c.extract_document([models.PageText(1, ["x"])], None)
    assert text == "nope"
