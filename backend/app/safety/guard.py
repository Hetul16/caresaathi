"""Output guard (docs/15-api-spec.md, section 7). Every generated text passes here before it is shown, spoken or sent.

The guard is deliberately strict and string-based: it must not depend on a model obeying a prompt.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

from .text import normalize_text

FALLBACK = {
    "en": "Please ask the doctor or pharmacist about this.",
    "hi": "कृपया इसके बारे में डॉक्टर या फार्मासिस्ट से पूछें।",
    "mr": "कृपया याबद्दल डॉक्टर किंवा फार्मासिस्टला विचारा.",
}

# Forbidden claims. Lists are kept in code and tested (D-21). Matched on normalized text.
FORBIDDEN: dict[str, tuple[str, ...]] = {
    "en": (
        "is safe", "are safe", "safe to take", "safe to use", "safe for you", "no risk", "not dangerous",
        "you can stop", "you may stop", "stop taking", "stop the", "skip the", "skip a dose", "skip your",
        "increase the dose", "decrease the dose", "reduce the dose", "double the", "take less", "take more",
        "you have a", "you have an", "you are suffering", "it is nothing", "nothing to worry", "don't worry",
        "do not worry", "infected", "healing well", "you don't need", "no need to see", "switch to",
        "instead of", "substitute", "alternative medicine", "you should take", "i recommend",
        "no interaction", "won't interact", "will not interact", "no need for the hospital",
    ),
    "hi": (
        "सुरक्षित है", "सुरक्षित हैं", "कोई खतरा नहीं", "दवा बंद कर", "दवा छोड़", "खुराक बढ़ा", "खुराक कम",
        "चिंता की कोई बात नहीं", "चिंता मत", "आपको बीमारी है", "संक्रमण है", "कोई जोखिम नहीं",
        "की जगह ले", "इसके बजाय",
    ),
    "mr": (
        "सुरक्षित आहे", "सुरक्षित आहेत", "धोका नाही", "औषध बंद करा", "गोळी सोडा", "मात्रा वाढवा", "मात्रा कमी",
        "काळजी करू नका", "काळजीचे कारण नाही", "तुम्हाला आजार आहे", "संसर्ग झाला", "जोखीम नाही",
        "ऐवजी घ्या",
    ),
}
# Extra lists for the post-kickoff features (docs/15-api-spec.md, section 8.2).
CLAIM_FORBIDDEN = (
    "will be approved", "will be rejected", "claim will", "eligible", "not eligible", "you will be paid",
    "chances of approval", "will be reimbursed", "मंजूर होगा", "अस्वीकार होगा", "मंजूर होईल", "नाकारला जाईल",
)
OMISSION_FORBIDDEN = (
    "stopped on purpose", "stopped deliberately", "safe to stop", "should continue", "should stop",
    "जानबूझकर बंद", "हेतुपुरस्सर बंद",
)
REFILL_FORBIDDEN = (
    "stretch your", "make it last", "take half", "skip doses to", "ration", "कम खुराक लें", "कमी मात्रा घ्या",
)

_EXTRA_ALL = CLAIM_FORBIDDEN + OMISSION_FORBIDDEN + REFILL_FORBIDDEN

_DEVANAGARI = re.compile(r"[ऀ-ॿ]")
# Function words that separate Marathi from Hindi (both use Devanagari).
_MARATHI_HINTS = ("आहे", "आहेत", "आणि", "नाही", "करा", "तुम्ही", "माझ", "याबद्दल")
_HINDI_HINTS = ("है", "हैं", "और", "नहीं", "करें", "आप", "मेरा", "इसके")


@dataclass
class GuardResult:
    status: str                       # pass | blocked
    text: str                         # the text that may be shown (the fallback when blocked)
    reasons: list[str] = field(default_factory=list)

    @property
    def passed(self) -> bool:
        return self.status == "pass"


@dataclass
class GuardContext:
    language: str                                   # requested language: en | hi | mr
    source_ids: list[str]                           # source_ref ids attached to the output
    known_medicines: set[str] = field(default_factory=set)   # normalized names in the care plan or cited source
    medicine_mentions: list[str] = field(default_factory=list)  # names the output uses (found by the caller)
    stored_numbers: set[str] = field(default_factory=set)    # doses, frequencies and dates as stored text
    stored_alert_level: str | None = None           # level of the cited warning-sign item, if any
    shown_alert_level: str | None = None            # level the output claims
    source_exempt: bool = False                     # plain chat replies only
    check_extra_wording: bool = False               # claim, omission and refill lists


def detect_language(text: str) -> str:
    if _DEVANAGARI.search(text):
        mr = sum(text.count(h) for h in _MARATHI_HINTS)
        hi = sum(text.count(h) for h in _HINDI_HINTS)
        return "mr" if mr > hi else "hi"
    return "en"


def _find_forbidden(text: str, use_extra: bool) -> list[str]:
    n = normalize_text(text)
    pool: list[str] = [p for lst in FORBIDDEN.values() for p in lst]
    if use_extra:
        pool += list(_EXTRA_ALL)
    return sorted({p for p in pool if normalize_text(p) in n})


_NUMBER = re.compile(r"\d+(?:[.,]\d+)?")


def _numbers_in(text: str) -> set[str]:
    return {m.group(0) for m in _NUMBER.finditer(text)}


def guard_output(text: str, ctx: GuardContext) -> GuardResult:
    """Return the text if every check passes, otherwise the safe fallback with the reasons."""
    reasons: list[str] = []

    if not ctx.source_ids and not ctx.source_exempt:
        reasons.append("source_missing")

    hits = _find_forbidden(text, ctx.check_extra_wording)
    if hits:
        reasons.append("forbidden_claim:" + "|".join(hits))

    if detect_language(text) != ctx.language:
        reasons.append("language_mismatch")

    known = {normalize_text(m) for m in ctx.known_medicines}
    for name in ctx.medicine_mentions:
        if normalize_text(name) not in known:
            reasons.append(f"unknown_medicine:{name}")

    # Every number in the text must be a number that appears in the stored record.
    if ctx.stored_numbers:
        allowed: set[str] = set()
        for s in ctx.stored_numbers:
            allowed |= _numbers_in(s)
        for num in _numbers_in(text):
            if num not in allowed:
                reasons.append(f"number_not_in_record:{num}")

    if ctx.shown_alert_level is not None and ctx.shown_alert_level != ctx.stored_alert_level:
        reasons.append("alert_level_mismatch")

    if reasons:
        lang = ctx.language if ctx.language in FALLBACK else "en"
        return GuardResult("blocked", FALLBACK[lang], reasons)
    return GuardResult("pass", text, [])
