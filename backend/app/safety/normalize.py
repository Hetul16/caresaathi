"""Medicine-name and date normalization (docs/14-data-mapping.md, section 6). No fuzzy matching here."""
from __future__ import annotations

import re
from datetime import date

_FORM_WORDS = {"tab", "tabs", "tablet", "tablets", "cap", "caps", "capsule", "capsules", "syp", "syrup",
               "inj", "injection", "drops", "oint", "ointment", "cream", "gel", "susp", "suspension"}
# Salt words printed AFTER the name on many strips ("Diclofenac Sodium", "Metformin Hydrochloride"). Dropped only when they are the last word of a
# name with at least two words, so "sodium valproate", "ferrous sulfate" and "calcium carbonate" keep their names.
_SALT_WORDS = {"sodium", "potassium", "hydrochloride", "hcl", "besylate", "maleate", "tartrate", "succinate", "mesylate"}
_PUNCT = re.compile(r"[^\w\s]+", re.UNICODE)
_STRENGTH = re.compile(r"\b\d+(?:\.\d+)?\s*(?:mg|mcg|g|ml|iu|%)\b", re.IGNORECASE)
_WS = re.compile(r"\s+")


def normalize_medicine_name(raw: str) -> str:
    """Lowercase, strip form words, strengths and punctuation, collapse spaces."""
    s = _STRENGTH.sub(" ", raw.casefold())
    s = _PUNCT.sub(" ", s)
    words = [w for w in s.split() if w not in _FORM_WORDS]
    while len(words) >= 2 and words[-1] in _SALT_WORDS:
        words.pop()
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


_LEADING_FORM = re.compile(r"^(?:tab|tablet|cap|capsule|syp|syrup|inj)\b\.?\s*", re.IGNORECASE)


def brand_key(title: str) -> str:
    """The name part of a medicine title: everything before the first digit, lowercased. "Amlodipine 10 mg" -> "amlodipine"."""
    t = _LEADING_FORM.sub("", title.strip())
    m = re.search(r"\d", t)
    return re.sub(r"\s+", " ", (t[:m.start()] if m else t)).strip().lower()


def same_medicine(title_a: str, ings_a: frozenset[str], title_b: str, ings_b: frozenset[str]) -> bool:
    """True when a line is a new VERSION of an existing item (a dose or schedule change), false when it is a different item.

    Same full ingredient set is required. A different brand of the same ingredient is a different item, so a possible
    duplicate stays visible instead of being merged away. A generic name matches a brand of that ingredient."""
    if not ings_a or ings_a != ings_b:
        return False
    a, b = brand_key(title_a), brand_key(title_b)
    if not a or not b:
        return False
    return a == b or a in ings_a or b in ings_a or a.startswith(b) or b.startswith(a)
