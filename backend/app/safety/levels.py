"""Warning-sign levels come from the patient's own written words, never from a model guess (D-20)."""
from __future__ import annotations

from dataclasses import dataclass

from .text import normalize_text

LEVELS = ("watch", "call_doctor_today", "emergency")
_RANK = {lvl: i for i, lvl in enumerate(LEVELS)}

# Checked from most urgent to least urgent; the first group that matches wins.
_RULES: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("emergency", (
        "emergency", "call an ambulance", "ambulance", "immediately", "come to casualty", "casualty",
        "go to hospital at once", "right away",
        "आपातकाल", "तुरंत", "एम्बुलेंस", "ambulance बुलाएं",
        "आपत्कालीन", "ताबडतोब", "रुग्णवाहिका",
    )),
    ("call_doctor_today", (
        "call the clinic", "call the doctor", "contact your doctor", "contact the doctor", "inform the doctor",
        "report to opd", "see the doctor", "tell the doctor",
        "डॉक्टर को बताएं", "डॉक्टर से संपर्क", "क्लिनिक में फोन",
        "डॉक्टरांना सांगा", "डॉक्टरांशी संपर्क",
    )),
    ("watch", (
        "keep an eye on", "monitor", "note if", "watch for", "look out for",
        "ध्यान रखें", "नज़र रखें", "लक्ष रखा", "निरीक्षण",
    )),
)


def level_from_quote(quote: str) -> str | None:
    """Return the level the written instruction supports, or None when it names no level."""
    q = normalize_text(quote)
    for level, keywords in _RULES:
        if any(normalize_text(k) in q for k in keywords):
            return level
    return None


@dataclass(frozen=True)
class LevelDecision:
    level: str | None       # level to show now
    needs_review: bool      # True when the model disagreed with the rule table or no rule matched


def decide_level(quote: str, model_suggestion: str | None) -> LevelDecision:
    """Rule table wins. If the model disagrees, show the more urgent level and send the item to review."""
    rule = level_from_quote(quote)
    if rule is None:
        # No level-bearing wording: cannot be saved as a warning sign without a person.
        return LevelDecision(level=None, needs_review=True)
    if model_suggestion is None or model_suggestion == rule:
        return LevelDecision(level=rule, needs_review=False)
    if model_suggestion not in _RANK:
        return LevelDecision(level=rule, needs_review=True)
    more_urgent = max(rule, model_suggestion, key=_RANK.__getitem__)
    return LevelDecision(level=more_urgent, needs_review=True)
