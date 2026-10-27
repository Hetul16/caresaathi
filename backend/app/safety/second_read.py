"""Two-reader comparison (docs/14-data-mapping.md section 14.4). Two independent readings of the same document are
compared field by field. A difference in name, strength, frequency, duration or quantity blocks the item: both
readings are shown and nothing is applied until a person chooses. Quote text, case, spacing and page never count."""
from __future__ import annotations

from .text import normalize_text

BLOCKING = ("name", "strength", "frequency", "duration", "quantity")


def _norm(v: object) -> str:
    return normalize_text(str(v)).replace(" ", "") if v not in (None, "") else ""


def compare_readings(a: dict, b: dict) -> list[str]:
    """The blocking fields whose values differ, in a fixed order."""
    return [f for f in BLOCKING if _norm(a.get(f)) != _norm(b.get(f))]


def pair_readings(a: list[dict], b: list[dict]) -> list[tuple[dict | None, dict | None]]:
    """Pair two readings by medicine name. An item only one reader found is paired with None."""
    remaining = list(b)
    out: list[tuple[dict | None, dict | None]] = []
    for ra in a:
        match = next((rb for rb in remaining if _norm(rb.get("name")) == _norm(ra.get("name"))), None)
        if match is not None:
            remaining.remove(match)
        out.append((ra, match))
    out.extend((None, rb) for rb in remaining)
    return out
