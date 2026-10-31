"""The fictional leg-and-back set (data/synthetic/sunita): an NSAID class allergy, a second doctor's Diclofenac, and a second paracetamol brand."""
from pathlib import Path

DOCS = Path(__file__).resolve().parents[2] / "data" / "synthetic" / "sunita" / "docs"
KINDS = {"S1": "other", "S2": "prescription", "S3": "imaging_report", "S4": "specialist_letter", "S5": "prescription", "S6": "lab_report"}


def _upload(family, stem):
    f = next(DOCS.glob(f"{stem}_*.txt"))
    family.upload(f.read_text(encoding="utf-8"), f.name, doc_type=KINDS[stem])


def test_every_document_is_marked_fictional():
    for f in DOCS.glob("*.txt"):
        assert f.read_text(encoding="utf-8").startswith("SYNTHETIC DOCUMENT - FICTIONAL PATIENT"), f.name


def test_class_allergy_then_a_second_doctors_nsaid_and_a_second_paracetamol(family):
    for stem in ("S1", "S2", "S3", "S4", "S6", "S5"):
        _upload(family, stem)
    plan = family.plan()
    assert plan["allergies"]["state"] == "listed" and "nsaid" in plan["allergies"]["items"][0]["substance"].lower()
    conflicts = [c for c in plan["open_conflicts"] if c["medicine"].lower().startswith("diclofenac")]
    assert len(conflicts) == 1 and conflicts[0]["match"] == "drug_family" and conflicts[0]["doctor_question"].strip().endswith("?")
    assert not any(c["medicine"].lower().startswith(("calpol", "pregabalin", "pantoprazole", "calcium")) for c in plan["open_conflicts"])
    assert [d["ingredient"] for d in plan["duplicates"]] == ["paracetamol"]
    medicines = {i["title"].lower().split()[0] for i in plan["items"] if i["kind"] == "medicine"}
    assert {"calpol", "pregabalin", "pantoprazole", "diclofenac"} <= medicines
    assert all(i["source"]["quote"] for i in plan["items"])


def test_the_written_warning_signs_take_their_level_from_the_documents_own_words(family):
    _upload(family, "S4")
    signs = [i for i in family.plan()["items"] if i["kind"] == "warning_sign"]
    assert any("emergency" in (s["alert_level"] or "") for s in signs) or any("emergency" in s["title"].lower() for s in signs)


def test_a_lab_result_is_shown_as_printed_with_its_reference_and_never_a_verdict():
    from app.services.readmodel import item_detail
    assert item_detail({"value": "14", "unit": "ng/mL", "reference_range": "30 to 100"}) == "14 ng/mL (reference 30 to 100)"
    assert item_detail({"value": "28", "unit": "mm/hr"}) == "28 mm/hr"
    assert item_detail({"frequency_text": "1-0-1", "duration_days": 5}) == "1-0-1, 5 days"
