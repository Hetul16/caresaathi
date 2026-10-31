"""Dates for the medicine timeline, computed by code (CLAUDE.md invariant 9). Nothing here is guessed.

A medicine starts on the date PRINTED on its document and runs for the number of days PRINTED on its line, counting the start day as day 1.
No printed date: no bar (it is listed as "start date not given"). No printed duration: the bar has no end ("no end date given"); it is never
shown as stopping, and never as continuing for ever. Two medicines overlap only where both bars are known to be running."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta


@dataclass(frozen=True)
class Span:
    start: date | None
    end: date | None          # None = no end date given (or no start date at all)


def days_of(value: object) -> int | None:
    """The printed number of days, if it is a plain positive whole number."""
    try:
        n = int(str(value).strip())
    except (TypeError, ValueError):
        return None
    return n if 0 < n <= 3650 else None


def span_of(doc_date: date | None, duration_days: object) -> Span:
    n = days_of(duration_days)
    if doc_date is None:
        return Span(None, None)
    return Span(doc_date, doc_date + timedelta(days=n - 1) if n else None)


def overlap(a: Span, b: Span) -> Span | None:
    """Where both are running. The end is None only when neither has a printed end."""
    if a.start is None or b.start is None:
        return None
    start = max(a.start, b.start)
    ends = [e for e in (a.end, b.end) if e is not None]
    end = min(ends) if ends else None
    if end is not None and end < start:
        return None
    return Span(start, end)


def how(doc_date: date | None, duration_days: object) -> str:
    """The inputs behind a bar, in words, so a person can check the sum."""
    n = days_of(duration_days)
    if doc_date is None:
        return "No date is printed on this document, so no bar is drawn."
    s = f"Document dated {doc_date:%d %b %Y}"
    if n:
        return f"{s}, plus {n} day{'s' if n != 1 else ''} as printed: last day {doc_date + timedelta(days=n - 1):%d %b %Y}."
    return f"{s}. No number of days is printed, so no end date is shown."
