"""Diff engine (S5) and omission matching (S10). Pure functions over plain data: no model, no database."""
from __future__ import annotations

import re
from dataclasses import dataclass, field


@dataclass(frozen=True)
class MedItem:
    key: str                              # stable item identity
    title: str
    ingredients: frozenset[str]           # normalized ingredient names
    unresolved: bool = False              # True if any ingredient could not be resolved
    strength: str | None = None
    frequency: str | None = None
    duration: str | None = None
    source_id: str | None = None


@dataclass(frozen=True)
class Change:
    kind: str                             # new | changed
    item: MedItem
    before: MedItem | None = None
    fields: tuple[str, ...] = ()


def diff_plans(current: list[MedItem], incoming: list[MedItem]) -> list[Change]:
    """New and changed medicines, matched on the full ingredient set.

    Medicines present before and absent now are not reported here: that is the omission catch
    (`find_omissions`), which has its own completeness rules."""
    changes: list[Change] = []
    cur_by_ing = {i.ingredients: i for i in current if i.ingredients}
    for inc in incoming:
        before = cur_by_ing.get(inc.ingredients) if inc.ingredients else None
        if before is None:
            changes.append(Change("new", inc))
            continue
        diffs = tuple(f for f in ("strength", "frequency", "duration") if getattr(before, f) != getattr(inc, f))
        if diffs:
            changes.append(Change("changed", inc, before, diffs))
    return changes


@dataclass(frozen=True)
class OmissionResult:
    candidates: list[MedItem] = field(default_factory=list)          # present before, absent now
    could_not_compare: list[MedItem] = field(default_factory=list)   # unresolved ingredient involved
    skipped_reason: str | None = None                                # set when the document is incomplete


def find_omissions(previous: list[MedItem], current: list[MedItem], *, document_complete: bool | None) -> OmissionResult:
    """docs/14-data-mapping.md section 14.3.

    1. An incomplete document, or one whose completeness is unknown, raises no flags.
    2. A previous item is carried when any current item has the same full ingredient set.
    3. An item with an unresolved ingredient is `could_not_compare`, never a flag.
    4. Strength, frequency and brand differences are not omissions (see `diff_plans`).
    """
    if document_complete is not True:
        return OmissionResult(skipped_reason="document_incomplete_or_unknown")
    current_sets = {c.ingredients for c in current if c.ingredients}
    any_unresolved_now = any(c.unresolved for c in current)
    candidates: list[MedItem] = []
    uncomparable: list[MedItem] = []
    for prev in previous:
        # An unresolved line in the new document could be this medicine under another name.
        if prev.unresolved or not prev.ingredients or any_unresolved_now:
            if prev.ingredients not in current_sets:
                uncomparable.append(prev)
            continue
        if prev.ingredients not in current_sets:
            candidates.append(prev)
    return OmissionResult(candidates, uncomparable)


_PAGE_MARK = re.compile(r"page\s*(\d+)\s*(?:of|/)\s*(\d+)", re.IGNORECASE)


def doc_looks_incomplete(page_texts: list[str], expected_pages: int | None = None) -> bool:
    """Completeness heuristic: a 'page N of M' marker with fewer pages than M, or a page with no text."""
    if not page_texts or any(not t.strip() for t in page_texts):
        return True
    total = 0
    for t in page_texts:
        m = _PAGE_MARK.search(t)
        if m:
            total = max(total, int(m.group(2)))
    n = len(page_texts)
    return n < total or bool(expected_pages and n < expected_pages)


def document_completeness(page_texts: list[str]) -> str:
    """'complete', 'incomplete' or 'unknown'. Only an explicit "page N of M" marker with every page present
    counts as complete: without one we cannot know that nothing is missing, so the omission catch stays quiet."""
    if not page_texts or doc_looks_incomplete(page_texts):
        return "incomplete"
    total = 0
    for t in page_texts:
        m = _PAGE_MARK.search(t)
        if m:
            total = max(total, int(m.group(2)))
    return "complete" if total and len(page_texts) >= total else "unknown"
