"""Shared shaping of rows into the API's read models (matches frontend/src/lib/types.ts)."""
from __future__ import annotations

from datetime import date
from typing import Any


def source_of(r: Any) -> dict:
    """A source as the screens show it. Document sources carry page and line; others carry the exact words."""
    kind = r["source_kind"] if "source_kind" in r.keys() and r["source_kind"] else "document"
    if kind == "document":
        return {"kind": "document", "document_id": str(r["document_id"]), "document_title": r["doc_title"] or "Document",
                "page": r["page"], "line_start": r["line_start"], "quote": r["quote"]}
    return {"kind": kind, "quote": r["quote"]}


def item_detail(det: dict) -> str | None:
    parts = (det.get("frequency_text"), f"{det['duration_days']} days" if det.get("duration_days") else None,
             det.get("instructions_text"))
    return ", ".join(x for x in parts if x) or None


def age_of(dob: date | None) -> int | None:
    if not dob:
        return None
    today = date.today()
    return today.year - dob.year - ((today.month, today.day) < (dob.month, dob.day))
