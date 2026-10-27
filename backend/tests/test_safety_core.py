import json

import pytest

from app.safety.dosing import daily_units, parse_schedule
from app.safety.guard import FALLBACK, GuardContext, detect_language, guard_output
from app.safety.levels import decide_level, level_from_quote
from app.safety.normalize import AmbiguousDate, normalize_medicine_name, parse_document_date, split_combination
from app.safety.permissions import TOOL_REGISTRY, Permission, gate_tool_call
from app.safety.reconcile import MedItem, diff_plans, doc_looks_incomplete, find_omissions
from app.safety.text import normalize_text, quote_in_text
from app.safety.validate import validate_extraction, validate_visit


# ---------- quotes ----------
def test_quote_survives_whitespace_and_case():
    assert quote_in_text("tab  AMOXICILLIN 500 mg", "x\nTab Amoxicillin\n500 mg 1-0-1")


def test_empty_quote_never_matches():
    assert not quote_in_text("   ", "anything")


def test_quote_not_in_text():
    assert not quote_in_text("metformin 500", "Tab Amoxicillin 500 mg")


# ---------- warning levels ----------
@pytest.mark.parametrize("quote,level", [
    ("Go to the emergency if chest pain", "emergency"),
    ("Call an ambulance if he faints", "emergency"),
    ("Contact your doctor if fever persists", "call_doctor_today"),
    ("Report to OPD if swelling increases", "call_doctor_today"),
    ("Keep an eye on the swelling", "watch"),
    ("Monitor sugar daily", "watch"),
])
def test_level_rules(quote, level):
    assert level_from_quote(quote) == level


def test_no_level_wording_returns_none():
    assert level_from_quote("Take rest") is None
    assert decide_level("Take rest", "emergency").level is None


def test_model_disagreement_shows_more_urgent_and_flags_review():
    d = decide_level("Contact your doctor if fever persists", "emergency")
    assert d.level == "emergency" and d.needs_review
    d = decide_level("Go to the emergency now", "watch")
    assert d.level == "emergency" and d.needs_review


def test_model_agreement_is_clean():
    d = decide_level("Keep an eye on the swelling", "watch")
    assert d.level == "watch" and not d.needs_review


# ---------- dosing ----------
def test_dosing_patterns():
    assert parse_schedule("1-0-1") == {"morning": 1.0, "noon": 0.0, "evening": 1.0, "night": None}
    assert parse_schedule("0-0-1")["night"] is None and parse_schedule("0-0-1")["evening"] == 1.0
    assert parse_schedule("1-1-1-1")["night"] == 1.0
    assert parse_schedule("SOS") is None and parse_schedule("PRN") is None
    assert parse_schedule("twice a day") is None
    assert parse_schedule(None) is None


def test_daily_units():
    assert daily_units("1-0-1") == 2.0
    assert daily_units("SOS") is None


# ---------- normalization ----------
def test_medicine_name_normalization():
    assert normalize_medicine_name("Tab. Amoxicillin 500 mg") == "amoxicillin"
    assert normalize_medicine_name("  Syp  Crocin ") == "crocin"


def test_combination_split():
    assert split_combination("amoxicillin + clavulanic acid") == ["amoxicillin", "clavulanic acid"]


def test_dates_day_first():
    assert str(parse_document_date("25/10/2026")) == "2026-10-25"
    assert str(parse_document_date("2026-10-25")) == "2026-10-25"
    assert str(parse_document_date("11/12/2026", other_cue="dmy")) == "2026-12-11"


def test_ambiguous_date_is_not_guessed():
    with pytest.raises(AmbiguousDate):
        parse_document_date("03/04/2026")


# ---------- permission gate ----------
def test_unknown_tool_refused():
    assert gate_tool_call("change_dose").status == "refused"
    assert gate_tool_call("stop_medicine").status == "refused"


def test_no_tool_changes_medicines_or_diagnoses():
    banned = ("dose", "stop_med", "diagnos", "triage", "hospital", "prescribe", "substitut")
    assert not [t for t in TOOL_REGISTRY if any(b in t for b in banned)]


def test_ask_first_waits_for_approval():
    for tool, perm in TOOL_REGISTRY.items():
        d = gate_tool_call(tool)
        if perm is Permission.ASK_FIRST:
            assert d.status == "awaiting_approval", tool
        else:
            assert d.status == "run", tool


def test_untrusted_trigger_refused_even_for_automatic_tools():
    assert gate_tool_call("update_care_plan", trusted_trigger=False).status == "refused"


# ---------- output guard ----------
def ctx(**kw):
    base = dict(language="en", source_ids=["s1"])
    base.update(kw)
    return GuardContext(**base)


@pytest.mark.parametrize("text", [
    "This medicine is safe to take with your other tablets.",
    "You can stop the tablet tomorrow.",
    "Skip the evening dose if you feel dizzy.",
    "Nothing to worry about, it is nothing.",
    "You could take paracetamol instead of this.",
    "You should take an extra tablet.",
])
def test_forbidden_english_claims_blocked(text):
    r = guard_output(text, ctx())
    assert r.status == "blocked" and r.text == FALLBACK["en"]
    assert any(x.startswith("forbidden_claim") for x in r.reasons)


def test_forbidden_hindi_and_marathi_blocked():
    r = guard_output("यह दवा सुरक्षित है, आप इसे लें।", ctx(language="hi"))
    assert r.status == "blocked" and r.text == FALLBACK["hi"]
    r = guard_output("हे औषध सुरक्षित आहे, तुम्ही घ्या.", ctx(language="mr"))
    assert r.status == "blocked" and r.text == FALLBACK["mr"]


def test_missing_source_blocked_unless_exempt():
    assert guard_output("Your next visit is on the 5th.", ctx(source_ids=[])).status == "blocked"
    assert guard_output("Please say that again.", ctx(source_ids=[], source_exempt=True)).status == "pass"


def test_clean_text_passes():
    r = guard_output("Your doctor wrote Tab Amoxicillin 500 mg 1-0-1. Please ask the doctor if unsure.",
                     ctx(known_medicines={"amoxicillin"}, medicine_mentions=["Amoxicillin"],
                         stored_numbers={"500 mg", "1-0-1"}))
    assert r.status == "pass", r.reasons


def test_unknown_medicine_blocked():
    r = guard_output("Tab Warfarin 5 mg is on your list.", ctx(known_medicines={"amoxicillin"},
                                                              medicine_mentions=["Warfarin"]))
    assert r.status == "blocked" and "unknown_medicine:Warfarin" in r.reasons


def test_number_not_in_record_blocked():
    r = guard_output("Take Amoxicillin 1000 mg.", ctx(stored_numbers={"500 mg"}))
    assert r.status == "blocked"


def test_language_mismatch_blocked():
    r = guard_output("Please take your tablet.", ctx(language="hi"))
    assert "language_mismatch" in r.reasons


def test_detect_language():
    assert detect_language("hello") == "en"
    assert detect_language("आपकी दवा नहीं है और आप") == "hi"
    assert detect_language("तुमची गोळी आहे आणि नाही") == "mr"


def test_alert_level_must_match_stored():
    assert guard_output("Call the clinic if fever.", ctx(stored_alert_level="call_doctor_today",
                                                         shown_alert_level="emergency")).status == "blocked"
    assert guard_output("Call the clinic if fever.", ctx(stored_alert_level="call_doctor_today",
                                                         shown_alert_level="call_doctor_today")).status == "pass"


def test_extra_wording_lists():
    assert guard_output("Your claim will be approved.", ctx(check_extra_wording=True)).status == "blocked"
    assert guard_output("It was stopped on purpose.", ctx(check_extra_wording=True)).status == "blocked"
    assert guard_output("Make it last by taking half.", ctx(check_extra_wording=True)).status == "blocked"


def test_allergy_flag_wording_ok():
    r = guard_output("Possible conflict between the listed allergy and this medicine. Please confirm with the doctor or pharmacist.",
                     ctx())
    assert r.status == "pass", r.reasons


# ---------- diff and omissions ----------
def med(key, ings, **kw):
    return MedItem(key=key, title=key, ingredients=frozenset(ings), **kw)


def test_diff_new_changed():
    cur = [med("a", {"metformin"}, strength="500 mg", frequency="1-0-1")]
    inc = [med("a2", {"metformin"}, strength="500 mg", frequency="1-1-1"), med("b", {"amlodipine"})]
    kinds = {c.item.key: c for c in diff_plans(cur, inc)}
    assert kinds["a2"].kind == "changed" and kinds["a2"].fields == ("frequency",)
    assert kinds["b"].kind == "new"


def test_omission_flagged_when_complete():
    prev = [med("m", {"metformin"}), med("a", {"amlodipine"})]
    cur = [med("a", {"amlodipine"})]
    r = find_omissions(prev, cur, document_complete=True)
    assert [c.key for c in r.candidates] == ["m"]


def test_no_omissions_when_incomplete_or_unknown():
    prev = [med("m", {"metformin"})]
    assert find_omissions(prev, [], document_complete=False).candidates == []
    assert find_omissions(prev, [], document_complete=None).candidates == []


def test_brand_or_strength_difference_is_not_omission():
    prev = [med("m", {"metformin"}, strength="500 mg")]
    cur = [med("m2", {"metformin"}, strength="850 mg")]
    assert find_omissions(prev, cur, document_complete=True).candidates == []


def test_unresolved_is_could_not_compare_not_flag():
    prev = [med("x", {"zzz"}, unresolved=True)]
    r = find_omissions(prev, [], document_complete=True)
    assert r.candidates == [] and [i.key for i in r.could_not_compare] == ["x"]


def test_unresolved_line_in_new_document_blocks_flags():
    prev = [med("m", {"metformin"})]
    cur = [med("q", {"unknown brand"}, unresolved=True)]
    r = find_omissions(prev, cur, document_complete=True)
    assert r.candidates == [] and len(r.could_not_compare) == 1


def test_combination_product_must_match_full_set():
    prev = [med("c", {"amoxicillin", "clavulanic acid"})]
    cur = [med("a", {"amoxicillin"})]
    assert [c.key for c in find_omissions(prev, cur, document_complete=True).candidates] == ["c"]


def test_incomplete_document_detection():
    assert doc_looks_incomplete(["Page 1 of 2 ... meds"])
    assert doc_looks_incomplete(["text", "  "])
    assert not doc_looks_incomplete(["Page 1 of 2 a", "Page 2 of 2 b"])


# ---------- contracts and quote verification ----------
def good_extract():
    return {
        "schema_version": "extract.v1",
        "document": {"doc_type": "prescription", "doc_date": "2026-10-20", "issuer": "Dr A", "language": "en"},
        "items": [
            {"kind": "medicine", "title": "Amoxicillin 500 mg",
             "details": {"ingredients": [{"name": "amoxicillin", "strength": "500 mg"}], "frequency_text": "1-0-1"},
             "source": {"page": 1, "line_start": 3, "line_end": 3, "quote": "Tab Amoxicillin 500 mg 1-0-1"},
             "confidence": 0.95},
            {"kind": "warning_sign", "title": "Fever",
             "details": {"alert_level_suggestion": "emergency"},
             "source": {"page": 1, "quote": "Contact your doctor if fever persists"}, "confidence": 0.9},
        ],
        "allergy_statement": "listed",
        "allergies": [{"substance": "Penicillin", "reaction": "rash", "severity": "moderate",
                       "source": {"page": 1, "quote": "Allergic to penicillin (rash)"}}],
    }


PAGE = {1: "Dr A clinic\nTab Amoxicillin\n500 mg 1-0-1\nContact your doctor if fever persists\nAllergic to penicillin (rash)"}


def test_valid_extraction_accepted_with_level_disagreement_flagged():
    v = validate_extraction(json.dumps(good_extract()), PAGE)
    assert v.ok and not v.rejected_items
    assert v.alert_levels[1] == "emergency"                   # more urgent level shown
    assert v.review_items[1] == "level_disagreement" and v.needs_review


def test_invented_quote_rejected():
    d = good_extract()
    d["items"][0]["source"]["quote"] = "Tab Warfarin 5 mg daily"
    v = validate_extraction(d, PAGE)
    assert v.rejected_items == [0] and v.needs_review


def test_extra_fields_and_bad_schema_rejected():
    d = good_extract()
    d["items"][0]["dose_advice"] = "double it"
    assert not validate_extraction(d, PAGE).ok
    assert not validate_extraction("not json", PAGE).ok
    d = good_extract()
    d["schema_version"] = "extract.v2"
    assert not validate_extraction(d, PAGE).ok


def test_empty_quote_rejected_by_schema():
    d = good_extract()
    d["items"][0]["source"]["quote"] = "  "
    assert not validate_extraction(d, PAGE).ok


def test_low_confidence_goes_to_review():
    d = good_extract()
    d["items"][0]["confidence"] = 0.4
    v = validate_extraction(d, PAGE)
    assert v.review_items[0] == "low_confidence" and v.needs_review


def test_unreadable_sets_review():
    d = good_extract()
    d["unreadable"] = [{"page": 1, "note": "blurry"}]
    assert validate_extraction(d, PAGE).needs_review


def test_allergy_quote_checked():
    d = good_extract()
    d["allergies"][0]["source"]["quote"] = "Allergic to sulfa"
    assert validate_extraction(d, PAGE).rejected_allergies == [0]


def test_visit_quote_must_be_in_cited_segments():
    segs = {"s1": "Start Tab Metformin 500 twice a day", "s2": "Come back in two weeks"}
    good = {"schema_version": "visit.v1",
            "items": [{"kind": "medicine", "change": "new", "title": "Metformin",
                       "source": {"segment_ids": ["s1"], "quote": "Start Tab Metformin 500 twice a day"},
                       "confidence": 0.9}]}
    assert validate_visit(good, segs).rejected_items == []
    bad = json.loads(json.dumps(good))
    bad["items"][0]["source"]["quote"] = "Start Tab Warfarin"
    assert validate_visit(bad, segs).rejected_items == [0]
    unknown = json.loads(json.dumps(good))
    unknown["items"][0]["source"]["segment_ids"] = ["nope"]
    assert validate_visit(unknown, segs).rejected_items == [0]


def test_normalize_text_nfkc():
    assert normalize_text("ＡＢＣ  d") == "abc d"


@pytest.mark.parametrize("text,lang", [
    ("तुमच्या कागदपत्रांत लिहिलेली ऍलर्जी:\n• Penicillin (rash)", "mr"),
    ("तुमच्या कुटुंबाने ही औषधे पक्की केली आहेत.", "mr"),
    ("अजून काहीही बदलले नाही.", "mr"),
    ("आपके दस्तावेज़ों में लिखी एलर्जी:\n• Penicillin (rash)", "hi"),
    ("आपके परिवार ने ये दवाइयाँ पक्की की हैं।", "hi"),
    ("Your documents say there are no known allergies.", "en"),
])
def test_detect_language_on_short_replies(text, lang):
    assert detect_language(text) == lang
