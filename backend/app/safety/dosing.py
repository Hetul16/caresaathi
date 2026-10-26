"""Indian dosing notation (docs/14-data-mapping.md, section 6). Unparseable text stays as written."""
import re

_SLOTS4 = ("morning", "noon", "evening", "night")
_PATTERN = re.compile(r"^\s*(\d+(?:\.\d+)?|½|¼)(?:\s*[-–]\s*(\d+(?:\.\d+)?|½|¼)){2,3}\s*$")
_FRACTIONS = {"½": 0.5, "¼": 0.25}


def _num(tok: str) -> float:
    return _FRACTIONS.get(tok, float(tok))


def parse_schedule(frequency_text: str | None) -> dict[str, float | None] | None:
    """`1-0-1` -> morning 1, noon 0, evening 1, night None. `1-1-1-1` fills all four.
    SOS/PRN and anything else return None; the caller keeps the original text."""
    if not frequency_text:
        return None
    t = frequency_text.strip()
    if t.casefold() in {"sos", "prn"} or not _PATTERN.match(t):
        return None
    parts = [p for p in re.split(r"\s*[-–]\s*", t)]
    values = [_num(p) for p in parts]
    if len(values) == 3:
        values.append(None)  # type: ignore[arg-type]
    return dict(zip(_SLOTS4, values))


def daily_units(frequency_text: str | None) -> float | None:
    """Units per day for the refill tracker. None when the frequency is not a plain schedule."""
    sched = parse_schedule(frequency_text)
    if sched is None:
        return None
    return float(sum(v for v in sched.values() if v is not None))
