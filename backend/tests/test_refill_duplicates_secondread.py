"""Refill estimate (A6), duplicate ingredients (A8) and the two-reader comparison (A5). Pure code, no model."""
from datetime import date

import pytest

from app.safety.duplicates import DupItem, duplicate_question, find_duplicates
from app.safety.refill import estimate_run_out
from app.safety.second_read import compare_readings, pair_readings


# ---- refill ------------------------------------------------------------------------------------------------------------
def test_thirty_tablets_twice_a_day_runs_out_after_fifteen_days():
    assert estimate_run_out(date(2026, 9, 14), 30, 2.0) == date(2026, 9, 29)


def test_hand_calculation_matches_for_the_planted_case():
    # 60 tablets, 1-0-1 = 2 a day: 30 days. 30 tablets once a day: 30 days.
    assert estimate_run_out(date(2026, 9, 14), 60, 2.0) == date(2026, 10, 14)
    assert estimate_run_out(date(2026, 9, 14), 30, 1.0) == date(2026, 10, 14)


def test_a_part_day_is_not_rounded_up():
    assert estimate_run_out(date(2026, 9, 14), 31, 2.0) == date(2026, 9, 29)       # 15.5 days -> 15


@pytest.mark.parametrize("qty,daily", [(30, None), (30, 0), (0, 2.0), (-5, 2.0)])
def test_no_estimate_without_usable_inputs(qty, daily):
    assert estimate_run_out(date(2026, 9, 14), qty, daily) is None


def test_no_estimate_without_a_start_date():
    assert estimate_run_out(None, 30, 2.0) is None


# ---- duplicates --------------------------------------------------------------------------------------------------------
def D(key, title, *ings):
    return DupItem(key, title, frozenset(ings))


def test_two_brands_with_one_ingredient_are_flagged():
    groups = find_duplicates([D("1", "Paraclear 500", "paracetamol"), D("2", "Fevonil 500", "paracetamol"), D("3", "Metformin 500 mg", "metformin")])
    assert len(groups) == 1 and groups[0].ingredient == "paracetamol" and [i.key for i in groups[0].items] == ["1", "2"]


def test_different_ingredients_are_not_flagged():
    assert find_duplicates([D("1", "A", "x"), D("2", "B", "y")]) == []


def test_a_combination_that_contains_a_listed_ingredient_is_flagged():
    groups = find_duplicates([D("1", "Pain Plus", "paracetamol", "caffeine"), D("2", "Fevonil 500", "paracetamol")])
    assert [g.ingredient for g in groups] == ["paracetamol"]


def test_the_same_item_is_not_its_own_duplicate():
    assert find_duplicates([D("1", "Paraclear 500", "paracetamol"), D("1", "Paraclear 500", "paracetamol")]) == []


def test_items_without_ingredients_are_ignored():
    assert find_duplicates([D("1", "Unknown", ), D("2", "Other")]) == []


def test_the_question_only_asks():
    g = find_duplicates([D("1", "Paraclear 500", "paracetamol"), D("2", "Fevonil 500", "paracetamol")])[0]
    q = duplicate_question(g)
    assert "Paraclear 500" in q and "Fevonil 500" in q and "paracetamol" in q and q.rstrip().endswith(".")
    assert "?" in q
    for banned in ("safe", "dangerous", "overdose", "stop", "skip"):
        assert banned not in q.lower()


# ---- two readers -------------------------------------------------------------------------------------------------------
A = {"name": "Amlodipine", "strength": "5 mg", "frequency": "1-0-0", "duration": None, "quantity": None}


def test_identical_readings_do_not_differ():
    assert compare_readings(A, dict(A)) == []


def test_a_blurry_strength_is_a_blocking_difference():
    assert compare_readings(A, {**A, "strength": "0.5 mg"}) == ["strength"]


def test_spacing_and_case_do_not_count():
    assert compare_readings({**A, "strength": "5 mg"}, {**A, "name": "AMLODIPINE", "strength": "5mg"}) == []


def test_frequency_duration_and_quantity_are_blocking():
    b = {**A, "frequency": "1-0-1", "duration": "5", "quantity": "30"}
    assert compare_readings(A, b) == ["frequency", "duration", "quantity"]


def test_quote_and_page_are_not_compared():
    assert compare_readings({**A, "quote": "Tab Amlodipine 5 mg", "page": 1}, {**A, "quote": "tab amlodipine 5 MG", "page": 2}) == []


def test_pairing_finds_missing_items():
    a = [{"name": "Amlodipine", "strength": "5 mg"}, {"name": "Metformin", "strength": "500 mg"}]
    b = [{"name": "amlodipine", "strength": "5 mg"}]
    pairs = pair_readings(a, b)
    assert pairs[0][0]["name"] == "Amlodipine" and pairs[0][1]["name"] == "amlodipine"
    assert pairs[1][0]["name"] == "Metformin" and pairs[1][1] is None
