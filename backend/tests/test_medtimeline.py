"""The medicine timeline: dates are the printed ones, added up by code; nothing is guessed; overlaps and allergy flags are drawn from code results."""
from datetime import date
from pathlib import Path

from app.safety.medtimeline import days_of, how, overlap, span_of

DOCS = Path(__file__).resolve().parents[2] / "data" / "synthetic" / "sunita" / "docs"
KINDS = {"S1": "other", "S2": "prescription", "S5": "prescription"}


def test_a_bar_runs_from_the_printed_date_for_the_printed_days_counting_day_one():
    sp = span_of(date(2026, 10, 20), 5)
    assert (sp.start, sp.end) == (date(2026, 10, 20), date(2026, 10, 24))
    assert span_of(date(2026, 9, 14), "30").end == date(2026, 10, 13)


def test_no_printed_duration_means_no_end_and_no_printed_date_means_no_bar():
    assert span_of(date(2026, 10, 23), None).end is None and span_of(date(2026, 10, 23), None).start == date(2026, 10, 23)
    assert span_of(None, 5).start is None and span_of(None, 5).end is None
    assert days_of("soon") is None and days_of(0) is None and days_of(-3) is None and days_of(99999) is None


def test_overlap_needs_both_bars_to_be_known_to_run():
    a, b = span_of(date(2026, 10, 20), 5), span_of(date(2026, 10, 23), None)
    o = overlap(a, b)
    assert (o.start, o.end) == (date(2026, 10, 23), date(2026, 10, 24))          # ends where the bar with a printed end ends
    assert overlap(a, span_of(date(2026, 10, 25), 3)) is None                     # one ends before the other starts
    assert overlap(a, span_of(None, 3)) is None                                   # unknown start: never an overlap
    both_open = overlap(span_of(date(2026, 10, 1), None), span_of(date(2026, 10, 5), None))
    assert both_open.start == date(2026, 10, 5) and both_open.end is None


def test_the_sum_is_shown_in_words():
    assert "last day 24 Oct 2026" in how(date(2026, 10, 20), 5)
    assert "No number of days is printed" in how(date(2026, 10, 23), None)
    assert "no bar is drawn" in how(None, 5)


def _upload(family, stem):
    f = next(DOCS.glob(f"{stem}_*.txt"))
    family.upload(f.read_text(encoding="utf-8"), f.name, doc_type=KINDS[stem])


def test_the_two_doctor_paracetamol_overlap_and_the_nsaid_flag_are_drawn(family):
    for stem in ("S1", "S2", "S5"):
        _upload(family, stem)
    r = family.get(f"/patients/{family.pid}/medicine-timeline")
    assert r.status_code == 200
    t = r.json()
    rows = {x["title"].lower().split()[0]: x for x in t["rows"]}
    assert rows["calpol"]["start"] == "2026-10-20" and rows["calpol"]["end"] == "2026-10-24" and "last day 24 Oct 2026" in rows["calpol"]["how"]
    assert rows["dolo"]["start"] == "2026-10-23" and rows["dolo"]["end"] is None and rows["dolo"]["open_end"] is True
    assert rows["diclofenac"]["end"] == "2026-10-27"
    assert rows["diclofenac"]["allergy"]["match"] == "drug_family" and rows["calpol"]["allergy"] is None
    para = [o for o in t["overlaps"] if o["ingredient"] == "paracetamol"]
    assert len(para) == 1 and para[0]["dated"] and "?" in para[0]["question"]
    assert para[0]["spots"][0]["start"] == "2026-10-23" and para[0]["spots"][0]["end"] == "2026-10-24"
    assert t["window"]["start"] < "2026-10-20" and all(x["source"]["quote"] for x in t["rows"])
    assert "not medical advice" in t["note"].lower()


def test_a_medicine_with_no_document_date_is_listed_but_not_drawn(family):
    family.upload("SYNTHETIC DOCUMENT - FICTIONAL PATIENT\nCLINIC\nPage 1 of 1\nPatient: Test, 60 y\nTab Pantoprazole 40 mg 1-0-0 x 14 days\n", "nodate.txt", doc_type="prescription")
    t = family.get(f"/patients/{family.pid}/medicine-timeline").json()
    row = next(x for x in t["rows"] if x["title"].lower().startswith("pantoprazole"))
    assert row["start"] is None and row["end"] is None and "no bar is drawn" in row["how"]


def test_another_family_cannot_read_the_timeline(family, stranger):
    assert stranger.get(f"/patients/{family.pid}/medicine-timeline").status_code in (403, 404)


def test_the_printed_date_is_read_day_first_and_an_ambiguous_one_stays_empty():
    from app.safety.normalize import printed_date
    assert printed_date("20/10/2026") == date(2026, 10, 20) and printed_date("2026-10-20") == date(2026, 10, 20) and printed_date("20.10.2026") == date(2026, 10, 20)
    assert printed_date("05/11/2026") is None          # could be 5 Nov or 11 May: left empty, never guessed
    assert printed_date(None) is None and printed_date("last Tuesday") is None
