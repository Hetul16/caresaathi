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

# Implied reassurance and "go ahead" permission, which exact phrases miss ("you'll be fine", "perfectly OK to take", "feel free to drop").
# Matched on normalized text. The families are deliberately broad: a false positive only replaces a draft with the safe fallback.
_A = "['’]?"
FORBIDDEN_PATTERNS: tuple[str, ...] = (
    rf"\byou{_A}(?:ll| will|re| are)? (?:be )?(?:fine|ok|okay|alright|good|safe)\b",
    r"\bperfectly (?:ok|okay|fine|safe|normal|harmless)\b",
    r"\bharmless\b",
    r"\bno (?:problem|issue|issues|harm|worries|trouble) (?:with|in|taking|at all)\b",
    r"\bnothing (?:wrong|to be concerned|to worry|to fear|to be afraid)\b",
    rf"\b(?:it{_A}s|it is|that is|that{_A}s|this is) (?:fine|ok|okay|alright|normal|good) to\b",
    r"\b(?:fine|ok|okay|alright) to (?:combine|take|mix|use|skip|drop|stop)\b",
    r"\bgo ahead and (?:take|use|combine|have|skip|drop|stop)\b",
    r"\bfeel free to (?:skip|drop|stop|take|combine|reduce|double|leave)\b",
    r"\b(?:leave out|drop|omit|cut out) (?:the|your|that|this) (?:\w+ ){0,2}(?:tablet|dose|pill|medicine|capsule)\b",
    r"\btolerate[sd]? (?:it|this|that)\b",
    r"\bwithout any (?:trouble|problem|risk|issue|side)\b",
    r"\blose sleep\b",
    r"\bjust try it\b",
    r"\bwhy not just\b",
    rf"\bwon{_A}t (?:hurt|harm)\b",
    # romanised Hindi
    r"\bbilkul theek\b", r"\btheek hai\b", r"\btension mat\b", r"\bsab theek\b", r"\bchinta mat\b", r"\bkoi dikkat nahi\b",
    r"\bkhatra nahi\b", r"\bsurakshit hai\b",
    # Devanagari
    r"बिल्कुल ठीक", r"कोई दिक्कत नहीं", r"चिंता न करें", r"बेफिक्र", r"काही हरकत नाही", r"अगदी ठीक आहे", r"बिनधास्त", r"काळजी नको",
)
_PATTERNS = tuple(re.compile(x) for x in FORBIDDEN_PATTERNS)

_DEVANAGARI = re.compile(r"[ऀ-ॿ]")
# Function words that separate Marathi from Hindi (both use Devanagari).
_MARATHI_HINTS = ("आहे", "आहेत", "आणि", "नाही", "करा", "तुम्ही", "माझ", "याबद्दल", "च्या", "कागदपत्र", "लिहिले", "तुमची", "तुमचे", "आणखी",
                  "पक्क", "ऍलर्जी", "औषध", "गोळी", "गोळ्या", "पुढ", "काळजी", "विचारा", "सांग", "डॉक्टरांना", "डॉक्टरांशी", "कुटुंबाने")
_HINDI_HINTS = ("है", "हैं", "और", "नहीं", "करें", "आप", "मेरा", "इसके", "दस्तावेज़", "आपके", "लिखा", "दवा", "पूछें", "में", "एलर्जी",
                "पक्की", "परिवार", "चेतावनी", "कृपया", "डॉक्टर से")


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
    require_grounding: bool = False                 # every sentence must mention a stored fact or the doctor/pharmacist
    grounding_terms: set[str] = field(default_factory=set)   # medicine, ingredient and allergy names from the stored record


# Words that tie a sentence to the record or to the right person to ask. A sentence with none of these, and none of the record's own
# names, is free-floating: it cannot be read back from anything stored, so it is not shown.
GENERIC_TERMS = ("doctor", "pharmacist", "document", "reference list", "records", "prescription", "earlier list", "new document", "allergy",
                 "डॉक्टर", "फार्मासिस्ट", "दस्तावेज़", "कागदपत्र", "एलर्जी", "ऍलर्जी")
_SENTENCES = re.compile(r"[^.!?।\n]+[.!?।]?")


def ungrounded_sentences(text: str, terms: set[str]) -> list[str]:
    pool = [normalize_text(t) for t in (*GENERIC_TERMS, *terms) if t and t.strip()]
    out = []
    for m in _SENTENCES.finditer(text):
        sent = m.group(0).strip()
        n = normalize_text(sent)
        if len(re.sub(r"[\W\d_]+", "", n)) < 3:
            continue                                   # punctuation, bullets, bare numbers
        if not any(t in n for t in pool):
            out.append(sent)
    return out


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
    hits = {p for p in pool if normalize_text(p) in n}
    hits |= {m.group(0) for pat in _PATTERNS if (m := pat.search(n))}
    return sorted(hits)


_NUMBER = re.compile(r"\d+(?:[.,]\d+)?")


def _numbers_in(text: str) -> set[str]:
    return {m.group(0) for m in _NUMBER.finditer(text)}


def guard_output(text: str, ctx: GuardContext) -> GuardResult:
    """Return the text if every check passes, otherwise the safe fallback with the reasons."""
    reasons: list[str] = []

    if not ctx.source_ids and not ctx.source_exempt:
        reasons.append("source_missing")

    if ctx.require_grounding:
        loose = ungrounded_sentences(text, ctx.grounding_terms)
        if loose:
            reasons.append("ungrounded_sentence:" + loose[0][:60])

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
