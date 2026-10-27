"""Follow-up dates (docs/14-data-mapping.md section 14.2, D-31).

The model returns the WORDS ("in two weeks"). Code computes the date from an anchor (the visit or document date) and
shows the inputs beside the result. A vague phrase ("soon", "after some time") gives no date, and a person confirms
every date before it becomes a reminder. Nothing here judges how soon a review is needed."""
from __future__ import annotations

import calendar
import re
from datetime import date, timedelta

from .text import normalize_text

_NUMBERS: dict[str, int] = {
    # English
    "a": 1, "an": 1, "one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6, "seven": 7, "eight": 8,
    "nine": 9, "ten": 10, "eleven": 11, "twelve": 12,
    # Hindi, Marathi and Hinglish (romanised)
    "ek": 1, "do": 2, "don": 2, "teen": 3, "tin": 3, "char": 4, "chaar": 4, "paanch": 5, "panch": 5, "chhe": 6, "saat": 7,
    "aath": 8, "nau": 9, "das": 10, "dah": 10,
    # Devanagari
    "एक": 1, "दो": 2, "दोन": 2, "तीन": 3, "चार": 4, "पांच": 5, "पाच": 5, "छह": 6, "सात": 7, "आठ": 8, "नौ": 9, "दस": 10, "दहा": 10,
}

_UNITS: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("year", ("year", "years", "saal", "varsh", "वर्ष", "साल")),
    ("month", ("month", "months", "mahine", "mahina", "mahinyani", "mahinyanni", "महीने", "महीना", "महिने", "महिन्यांनी", "महिन्यां", "महिना")),
    ("week", ("week", "weeks", "hafte", "hafta", "saptah", "aathvade", "aathvada", "हफ्ते", "हफ्ता", "सप्ताह", "आठवडे", "आठवडा")),
    ("day", ("day", "days", "din", "divas", "दिन", "दिवस")),
)
_UNIT_OF = {w: u for u, ws in _UNITS for w in ws}
_TOKEN = re.compile(r"[\wऀ-ॿ]+", re.UNICODE)
_MAX_YEARS = 5


def parse_interval(text: str) -> tuple[int, str] | None:
    """The first "<number> <unit>" in the words, as (count, unit). None when there is none."""
    tokens = _TOKEN.findall(normalize_text(text))
    for i, tok in enumerate(tokens[:-1]):
        count = int(tok) if tok.isdigit() else _NUMBERS.get(tok)
        unit = _UNIT_OF.get(tokens[i + 1])
        if count is not None and unit is not None:
            return count, unit
    return None


def _add_months(d: date, months: int) -> date:
    m = d.month - 1 + months
    y, m = d.year + m // 12, m % 12 + 1
    return date(y, m, min(d.day, calendar.monthrange(y, m)[1]))


def compute_due(anchor: date | None, due_text: str) -> date | None:
    """Anchor plus the stated interval. None for a missing anchor, a vague phrase, zero, or an absurd interval."""
    if anchor is None:
        return None
    got = parse_interval(due_text)
    if got is None:
        return None
    count, unit = got
    if count <= 0:
        return None
    if unit == "day":
        due = anchor + timedelta(days=count)
    elif unit == "week":
        due = anchor + timedelta(weeks=count)
    elif unit == "month":
        due = _add_months(anchor, count)
    else:
        due = _add_months(anchor, 12 * count)
    return due if (due - anchor).days <= 366 * _MAX_YEARS else None
