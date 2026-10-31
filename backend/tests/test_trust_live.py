"""The Trust page's live-model section is served from a committed report, never from a live call."""
import json

from app.api import trust


def test_a_missing_report_says_so(client, monkeypatch, tmp_path):
    monkeypatch.setattr(trust, "LIVE_RESULTS", tmp_path / "nope.json")
    assert client.get("/api/v1/trust/live").json() == {"available": False}


def test_a_broken_report_is_treated_as_missing(client, monkeypatch, tmp_path):
    f = tmp_path / "latest.json"
    f.write_text("{not json", encoding="utf-8")
    monkeypatch.setattr(trust, "LIVE_RESULTS", f)
    assert client.get("/api/v1/trust/live").json() == {"available": False}


def test_a_report_is_served_without_signing_in_and_keeps_its_failures(client, monkeypatch, tmp_path):
    f = tmp_path / "latest.json"
    f.write_text(json.dumps({"generated_at": "2026-10-31T10:00:00+00:00", "sections": {"documents": {"title": "Reading documents", "passed": 1, "total": 2,
                 "cases": [{"id": "a", "ok": True}, {"id": "b", "ok": False, "note": "declined"}]}}}), encoding="utf-8")
    monkeypatch.setattr(trust, "LIVE_RESULTS", f)
    r = client.get("/api/v1/trust/live")
    assert r.status_code == 200 and r.json()["available"] is True
    assert [c["ok"] for c in r.json()["sections"]["documents"]["cases"]] == [True, False]


def test_the_committed_report_is_synthetic_only_and_complete():
    from app.config import ROOT
    d = json.loads((ROOT / "data" / "live_results" / "latest.json").read_text(encoding="utf-8"))
    assert d["synthetic_data_only"] is True and d["mode"] == "live" and d["not_measured"]
    assert {"documents", "allergy_card", "judge_catches", "judge_plain", "labels", "visits"} <= set(d["sections"])
    for sec in d["sections"].values():
        assert sec["total"] == len(sec["cases"]) and sec["passed"] == sum(c["ok"] for c in sec["cases"])


def test_the_speech_result_if_present_reports_both_languages_with_and_without_the_hint():
    from app.config import ROOT
    d = json.loads((ROOT / "data" / "live_results" / "latest.json").read_text(encoding="utf-8"))
    sp = d.get("speech")
    assert sp is not None and "FLEURS" in sp["dataset"] and "not a doctor-visit" in sp["what"]
    assert {"hi_in", "mr_in", "en_us"} <= set(sp["languages"])
    for lang in sp["languages"].values():
        assert lang["clips"] >= 10 and lang["without_language_hint"]["wer"] is not None and lang["with_language_hint"]["wer"] is not None
    assert any("consultation" in x for x in d["not_measured"])         # the gap is stated, not hidden
