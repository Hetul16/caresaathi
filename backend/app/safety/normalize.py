"""Medicine-name and date normalization (docs/14-data-mapping.md, section 6). No fuzzy matching here."""
from __future__ import annotations

import re
from datetime import date

_FORM_WORDS = {"tab", "tabs", "tablet", "tablets", "cap", "caps", "capsule", "capsules", "syp", "syrup",
               "inj", "injection", "drops", "oint", "ointment", "cream", "gel", "susp", "suspension"}
_PUNCT = re.compile(r"[^\w\s]+", re.UNICODE)
_STRENGTH = re.compile(r"\b\d+(?:\.\d+)?\s*(?:mg|mcg|g|ml|iu|%)\b", re.IGNORECASE)
_WS = re.compile(r"\s+")


def normalize_medicine_name(raw: str) -> str:
    """Lowercase, strip form words, strengths and punctuation, collapse spaces."""
    s = _STRENGTH.sub(" ", raw.casefold())
    s = _PUNCT.sub(" ", s)
    words = [w for w in s.split() if w not in _FORM_WORDS]
    return _WS.sub(" ", " ".join(words)).strip()


def split_combination(name: str) -> list[str]:
    """`amoxicillin + clavulanic acid` -> two ingredients."""
    parts = re.split(r"\s*(?:\+|/|\bwith\b|\band\b)\s*", name, flags=re.IGNORECASE)
    return [p for p in (x.strip() for x in parts) if p]


_DMY = re.compile(r"^\s*(\d{1,2})[/-](\d{1,2})[/-](\d{4})\s*$")
_ISO = re.compile(r"^\s*(\d{4})-(\d{2})-(\d{2})\s*$")


class AmbiguousDate(ValueError):
    """Day and month are both 12 or less with no other cue: the caller sends the item to review."""


def parse_document_date(text: str, *, other_cue: str | None = None) -> date:
    """Indian documents are day-first. ISO passes through. `other_cue` ('dmy' or 'mdy') comes from the document."""
    m = _ISO.match(text)
    if m:
        return date(int(m[1]), int(m[2]), int(m[3]))
    m = _DMY.match(text)
    if not m:
        raise ValueError(f"unrecognised date: {text!r}")
    a, b, y = int(m[1]), int(m[2]), int(m[3])
    if a > 12:
        return date(y, b, a)
    if b > 12:
        return date(y, a, b)
    if a == b:
        return date(y, a, b)
    if other_cue == "dmy":
        return date(y, b, a)
    if other_cue == "mdy":
        return date(y, a, b)
    raise AmbiguousDate(text)
