"""Follow-up dates are computed by code from the written words (safety invariant 9, D-31).
A vague phrase gives no date. The model never supplies a date."""
from datetime import date

import pytest

from app.safety.followups import compute_due, parse_interval


@pytest.mark.parametrize("text,anchor,expected", [
    ("Review in 2 weeks", date(2026, 9, 14), date(2026, 9, 28)),
    ("Repeat HbA1c after 3 months", date(2026, 10, 20), date(2027, 1, 20)),
    ("Come back in 10 days", date(2026, 10, 20), date(2026, 10, 30)),
    ("see me in two weeks", date(2026, 10, 20), date(2026, 11, 3)),
    ("review after a week", date(2026, 10, 20), date(2026, 10, 27)),
    ("in 1 year", date(2026, 10, 20), date(2027, 10, 20)),
])
def test_english_intervals(text, anchor, expected):
    assert compute_due(anchor, text) == expected


def test_month_end_is_clamped_not_rolled_over():
    assert compute_due(date(2026, 1, 31), "after 1 month") == date(2026, 2, 28)
    assert compute_due(date(2024, 1, 31), "after 1 month") == date(2024, 2, 29)   # leap year
    assert compute_due(date(2026, 11, 30), "in 3 months") == date(2027, 2, 28)


@pytest.mark.parametrize("text,days", [
    ("Do hafte baad review ke liye aaiye", 14),
    ("Tin mahinyani HbA1c punha karuya", None),        # months, checked below
    ("दो हफ्ते बाद दिखाएं", 14),
    ("दोन आठवडे नंतर या", 14),
    ("das din baad", 10),
])
def test_hindi_marathi_and_hinglish(text, days):
    got = parse_interval(text)
    assert got is not None
    if days is not None:
        assert got == (days // 7, "week") if days % 7 == 0 else got == (days, "day")


def test_marathi_and_hindi_months():
    assert parse_interval("Tin mahinyani HbA1c punha karuya") == (3, "month")
    assert parse_interval("तीन महीने बाद") == (3, "month")
    assert parse_interval("तीन महिन्यांनी") == (3, "month")


@pytest.mark.parametrize("text", [
    "Come back soon", "after some time", "later", "jaldi aaiye", "at the next visit", "review", "", "Take after food",
    "in 0 days", "in 500 years",
])
def test_vague_or_unusable_phrases_give_no_date(text):
    assert compute_due(date(2026, 10, 20), text) is None


def test_no_anchor_no_date():
    assert compute_due(None, "in 2 weeks") is None


def test_a_number_that_is_not_an_interval_is_ignored():
    # "Tab Metformin 500 mg" has a number but no interval unit.
    assert parse_interval("Tab Metformin 500 mg after food") is None
