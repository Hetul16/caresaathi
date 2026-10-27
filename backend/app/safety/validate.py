"""Validation of model output: schema, then quote verification against the page text or transcript (D-20)."""
from __future__ import annotations

import json
from dataclasses import dataclass, field

from pydantic import ValidationError

from ..models.contracts import ExtractV1, VisitV1
from .injection import looks_like_injection
from .levels import decide_level
from .text import quote_in_text

LOW_CONFIDENCE = 0.6


def _parse(raw: str | dict):
    return json.loads(raw) if isinstance(raw, str) else raw


@dataclass
class ValidatedExtraction:
    data: ExtractV1 | None
    errors: list[dict] = field(default_factory=list)
    rejected_items: list[int] = field(default_factory=list)       # quote not found on the cited page
    rejected_allergies: list[int] = field(default_factory=list)
    rejected_follow_ups: list[int] = field(default_factory=list)
    review_items: dict[int, str] = field(default_factory=dict)    # index -> reason
    alert_levels: dict[int, str | None] = field(default_factory=dict)
    needs_review: bool = False
    injection_lines: int = 0                                         # lines that tried to instruct the assistant

    @property
    def ok(self) -> bool:
        return self.data is not None


def validate_extraction(raw: str | dict, page_texts: dict[int, str]) -> ValidatedExtraction:
    """page_texts maps page number -> page text. Items whose quote is not on the cited page are rejected."""
    try:
        data = ExtractV1.model_validate(_parse(raw))
    except (ValidationError, json.JSONDecodeError, ValueError) as e:
        return ValidatedExtraction(None, [{"type": "schema", "detail": str(e)[:2000]}], needs_review=True)

    out = ValidatedExtraction(data)
    for i, item in enumerate(data.items):
        if looks_like_injection(f"{item.title} {item.source.quote}"):
            out.rejected_items.append(i)
            out.injection_lines += 1
            out.errors.append({"type": "injection_suspected", "item": i, "page": item.source.page})
            continue
        if not quote_in_text(item.source.quote, page_texts.get(item.source.page, "")):
            out.rejected_items.append(i)
            out.errors.append({"type": "quote_not_found", "item": i, "page": item.source.page})
            continue
        if item.confidence < LOW_CONFIDENCE:
            out.review_items[i] = "low_confidence"
        if item.kind == "warning_sign":
            basis = str(item.details.get("level_basis_quote") or item.source.quote)
            decision = decide_level(basis, item.details.get("alert_level_suggestion"))
            out.alert_levels[i] = decision.level
            if decision.level is None:
                out.review_items[i] = "no_level_wording"
            elif decision.needs_review:
                out.review_items[i] = "level_disagreement"
    for i, al in enumerate(data.allergies):
        if looks_like_injection(f"{al.substance} {al.source.quote}"):
            out.rejected_allergies.append(i)
            out.injection_lines += 1
            out.errors.append({"type": "injection_suspected", "allergy": i, "page": al.source.page})
            continue
        if not quote_in_text(al.source.quote, page_texts.get(al.source.page, "")):
            out.rejected_allergies.append(i)
            out.errors.append({"type": "allergy_quote_not_found", "allergy": i, "page": al.source.page})
    for i, fu in enumerate(data.follow_ups):
        if looks_like_injection(f"{fu.what} {fu.source.quote}"):
            out.rejected_follow_ups.append(i)
            out.injection_lines += 1
            out.errors.append({"type": "injection_suspected", "follow_up": i, "page": fu.source.page})
            continue
        if not quote_in_text(fu.source.quote, page_texts.get(fu.source.page, "")):
            out.rejected_follow_ups.append(i)
            out.errors.append({"type": "follow_up_quote_not_found", "follow_up": i, "page": fu.source.page})
    out.needs_review = bool(data.unreadable or out.review_items or out.rejected_items or out.rejected_allergies or out.injection_lines)
    return out


@dataclass
class ValidatedVisit:
    data: VisitV1 | None
    errors: list[dict] = field(default_factory=list)
    rejected_items: list[int] = field(default_factory=list)
    rejected_allergies: list[int] = field(default_factory=list)
    rejected_follow_ups: list[int] = field(default_factory=list)
    review_items: dict[int, str] = field(default_factory=dict)
    alert_levels: dict[int, str | None] = field(default_factory=dict)
    injection_lines: int = 0

    @property
    def ok(self) -> bool:
        return self.data is not None


def validate_visit(raw: str | dict, segments: dict[str, str]) -> ValidatedVisit:
    """segments maps segment id -> segment text. A quote must appear in the segments it cites."""
    try:
        data = VisitV1.model_validate(_parse(raw))
    except (ValidationError, json.JSONDecodeError, ValueError) as e:
        return ValidatedVisit(None, [{"type": "schema", "detail": str(e)[:2000]}])

    out = ValidatedVisit(data)

    def cited_text(ids: list[str]) -> str | None:
        if any(s not in segments for s in ids):
            return None
        return " ".join(segments[s] for s in ids)

    for i, item in enumerate(data.items):
        if looks_like_injection(f"{item.title} {item.source.quote}"):
            out.rejected_items.append(i)
            out.injection_lines += 1
            out.errors.append({"type": "injection_suspected", "item": i})
            continue
        text = cited_text(item.source.segment_ids)
        if text is None or not quote_in_text(item.source.quote, text):
            out.rejected_items.append(i)
            out.errors.append({"type": "quote_not_found", "item": i})
            continue
        if item.confidence < LOW_CONFIDENCE:
            out.review_items[i] = "low_confidence"
        if item.kind == "warning_sign":
            decision = decide_level(item.source.quote, item.details.get("alert_level_suggestion"))
            out.alert_levels[i] = decision.level
            if decision.level is None:
                out.review_items[i] = "no_level_wording"
            elif decision.needs_review:
                out.review_items[i] = "level_disagreement"
    for i, al in enumerate(data.allergies_mentioned):
        text = cited_text(al.source.segment_ids)
        if text is None or not quote_in_text(al.source.quote, text):
            out.rejected_allergies.append(i)
            out.errors.append({"type": "allergy_quote_not_found", "allergy": i})
    for i, fu in enumerate(data.follow_ups):
        text = cited_text(fu.source.segment_ids)
        if text is None or not quote_in_text(fu.source.quote, text):
            out.rejected_follow_ups.append(i)
            out.errors.append({"type": "follow_up_quote_not_found", "follow_up": i})
    return out
