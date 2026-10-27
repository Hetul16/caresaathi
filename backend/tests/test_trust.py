"""The trust suite, the guard's grounding rule, the live judge's fail-closed behaviour, and the trust API."""
from __future__ import annotations

import pytest

from app.clients.models import FakeModelClient, Usage
from app.safety.guard import GuardContext, guard_output, ungrounded_sentences
from app.services.guarding import guard_with_judge
from app.trust.suite import CATEGORIES, run_suite

CORE = [c for c in CATEGORIES if c not in ("guard_paraphrase_probe", "guard_paraphrase_holdout")]


# ---- the suite itself ---------------------------------------------------------------------------------------------------------------------------
def test_every_core_category_passes_completely():
    s = run_suite().summary()
    by = {c["name"]: c for c in s["categories"]}
    for name in CORE:
        assert name in by, f"{name} produced no cases"
        assert by[name]["passed"] == by[name]["total"], (name, by[name]["failures"][:3])


def test_the_probes_report_their_misses_instead_of_hiding_them():
    by = {c["name"]: c for c in run_suite().summary()["categories"]}
    holdout = by["guard_paraphrase_holdout"]
    assert holdout["passed"] >= 12                                         # the ungrounded paraphrases are all blocked
    assert holdout["total"] > holdout["passed"] and holdout["failures"]    # the grounded ones that name a medicine are known to slip through
    assert all("Metformin" in f["input"] or "Amlodipine" in f["input"] for f in holdout["failures"])


def test_a_crashing_case_is_a_failure_not_a_skip(monkeypatch):
    import app.trust.suite as suite

    def boom():
        raise RuntimeError("x")

    monkeypatch.setattr(suite, "all_cases", lambda: [suite.Case("boom", "refill_math", "i", "e", boom)])
    r = suite.run_suite().results[0]
    assert r.passed is False and r.actual.startswith("crashed")


# ---- grounding ------------------------------------------------------------------------------------------------------------------------------------
@pytest.mark.parametrize("text", [
    "Your body will cope with it.", "Carry on exactly as you were.", "Nobody ever has trouble with this one.", "Don't bother with the morning pill.",
])
def test_a_sentence_with_no_stored_fact_is_blocked(text):
    r = guard_output(text, GuardContext(language="en", source_ids=["s"], require_grounding=True, grounding_terms={"metformin"}))
    assert r.status == "blocked" and any(x.startswith("ungrounded_sentence") for x in r.reasons)


def test_sentences_that_name_the_record_or_the_doctor_are_grounded():
    t = "Possible conflict between the listed allergy (Penicillin) and Amoxicillin 500 mg. This is a match in our reference list. Please confirm with the doctor or pharmacist."
    assert ungrounded_sentences(t, {"penicillin", "amoxicillin"}) == []
    assert guard_output(t, GuardContext(language="en", source_ids=["s"], require_grounding=True, grounding_terms={"penicillin"}, stored_numbers={"500"})).passed


def test_grounding_is_off_unless_asked_for():
    # without require_grounding the same sentence is judged only by the phrase lists, which is why callers that word model output switch it on
    assert guard_output("Your body will cope with it.", GuardContext(language="en", source_ids=["s"])).passed


# ---- the live judge (stubbed) -----------------------------------------------------------------------------------------------------------------------
class Judge(FakeModelClient):
    def __init__(self, verdict):
        self.verdict = verdict

    def judge_text(self, text):
        return self.verdict, Usage("judge", "judge_text")


@pytest.mark.parametrize("verdict,reason", [(True, "judge_flagged"), (None, "judge_undecided")])
def test_the_judge_fails_closed(verdict, reason):
    ctx = GuardContext(language="en", source_ids=["s"])
    r, usage = guard_with_judge(Judge(verdict), "Metformin 500 mg as written.", ctx)
    assert r.status == "blocked" and r.reasons == [reason] and r.text == "Please ask the doctor or pharmacist about this." and usage is not None


def test_the_judge_lets_a_clean_draft_through_and_is_skipped_when_the_guard_already_blocked():
    ctx = GuardContext(language="en", source_ids=["s"])
    ok, _ = guard_with_judge(Judge(False), "Metformin 500 mg as written.", ctx)
    assert ok.passed
    called = []

    class Spy(Judge):
        def judge_text(self, text):
            called.append(text)
            return False, Usage("j", "judge_text")

    blocked, usage = guard_with_judge(Spy(False), "This is safe to take.", ctx)
    assert blocked.status == "blocked" and usage is None and called == []          # no model call is spent on a draft already blocked


# ---- API -------------------------------------------------------------------------------------------------------------------------------------------------
@pytest.mark.usefixtures("scratch_db")
class TestApi:
    def test_running_the_suite_requires_sign_in(self, client):
        assert client.post("/api/v1/trust/run").status_code == 401

    def test_a_run_is_stored_and_the_latest_is_public(self, client, family, admin):
        r = family.post("/trust/run").json()
        assert r["stored"] and r["total"] == r["passed"] + sum(len(c["failures"]) for c in r["categories"]) and "do not measure how often the model is right" in r["disclaimer"]
        assert admin.execute("SELECT count(*) FROM eval_results WHERE run_id = %s", (r["run_id"],)).fetchone()[0] == r["total"]
        pub = client.get("/api/v1/trust/latest").json()                      # no sign-in
        assert pub["run_id"] == r["run_id"] and pub["total"] == r["total"] and pub["categories"]

    def test_failures_are_listed_with_their_input(self, client, family):
        family.post("/trust/run")
        pub = client.get("/api/v1/trust/latest").json()
        hold = next(c for c in pub["categories"] if c["name"] == "guard_paraphrase_holdout")
        assert hold["failures"] and {"id", "input", "expected", "actual"} <= set(hold["failures"][0])
