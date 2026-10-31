"""An allergy found after a medicine must still raise the conflict, whatever order the papers arrive or finish in.
Found on Oct 31 by uploading three photos at once through the live app: the allergy card and the Amoxicillin prescription were processed in
parallel, neither saw the other's uncommitted row, and no conflict was raised (a missed warning, not a wrong one)."""
import time
from pathlib import Path

DOCS = Path(__file__).resolve().parents[2] / "data" / "synthetic" / "ramesh" / "docs"


def _post(family, stem, doc_type="prescription"):
    f = next(DOCS.glob(f"{stem}_*.txt"))
    r = family.client.post(f"/api/v1/patients/{family.pid}/documents", headers=family.h, data={"doc_type": doc_type},
                           files={"file": (f.name, f.read_text(encoding="utf-8").encode(), "text/plain")})
    assert r.status_code == 202, r.text
    return r.json()["id"]


def _wait(family, ids):
    for _ in range(200):
        if all(family.client.get(f"/api/v1/documents/{i}", headers=family.h).json()["status"] in ("extracted", "needs_review", "failed") for i in ids):
            return
        time.sleep(0.1)
    raise AssertionError("documents were not processed in time")


def _amoxicillin_conflicts(family):
    return [c for c in family.plan()["open_conflicts"] if c["medicine"].startswith("Amoxicillin")]


def test_the_allergy_arriving_after_the_medicine_raises_the_conflict(family):
    family.upload((next(DOCS.glob("R5_*.txt"))).read_text(encoding="utf-8"), "R5.txt", doc_type="prescription")      # amoxicillin first
    assert _amoxicillin_conflicts(family) == []                                                                       # no allergy yet: nothing to flag
    family.upload((next(DOCS.glob("R4_*.txt"))).read_text(encoding="utf-8"), "R4.txt", doc_type="other")           # then the allergy card
    (c,) = _amoxicillin_conflicts(family)
    assert c["match"] == "drug_family" and c["doctor_question"].strip()


def test_papers_processed_at_the_same_time_still_raise_the_conflict(family, monkeypatch):
    """Both papers are read at once and each holds its transaction open for a while. Without the per-patient lock neither sees the other."""
    import app.pipelines.documents as pipe
    real = pipe.raise_omission_flags

    def slow(*a, **k):
        time.sleep(0.5)                      # keeps the processing transaction open, so the two overlap
        return real(*a, **k)
    monkeypatch.setattr(pipe, "raise_omission_flags", slow)
    ids = [_post(family, "R4", "other"), _post(family, "R5")]
    _wait(family, ids)
    assert len(_amoxicillin_conflicts(family)) == 1


def test_three_papers_at_once_in_either_order(family, monkeypatch):
    import app.pipelines.documents as pipe
    real = pipe.raise_omission_flags
    monkeypatch.setattr(pipe, "raise_omission_flags", lambda *a, **k: (time.sleep(0.3), real(*a, **k))[1])
    ids = [_post(family, "R5"), _post(family, "R1"), _post(family, "R4", "other")]
    _wait(family, ids)
    assert len(_amoxicillin_conflicts(family)) == 1 and family.plan()["allergies"]["state"] == "listed"
