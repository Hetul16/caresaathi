"""Small, deterministic repairs of the live model's JSON before it is validated.

Found by running the whole website against the live model (Oct 29): the reader answered `doc_type: "allergy_card"` for an allergy card, which
is not one of the six allowed types, so the WHOLE extraction failed validation and the penicillin allergy was never recorded. These repairs
only fix labels and shape. They never invent a fact: a value that cannot be mapped becomes the neutral one ("other", "unknown"), and an item
that cannot be fixed is dropped, never guessed. The strict validation and quote checks still run afterwards."""
from __future__ import annotations

from typing import Any

DOC_TYPES = {"prescription", "lab_report", "discharge_summary", "specialist_letter", "imaging_report", "other"}
_DOC_ALIASES = {"discharge": "discharge_summary", "discharge summary": "discharge_summary", "lab": "lab_report", "lab report": "lab_report",
                "laboratory_report": "lab_report", "letter": "specialist_letter", "referral": "specialist_letter", "imaging": "imaging_report",
                "radiology_report": "imaging_report", "rx": "prescription", "medical_prescription": "prescription"}
LANGS = {"en", "hi", "mr", "mixed"}
SEVERITY = {"mild", "moderate", "severe", "unknown"}
EXTRACT_KINDS = {"medicine", "condition", "test", "appointment", "warning_sign", "restriction", "instruction", "result"}
VISIT_KINDS = {"medicine", "test", "appointment", "warning_sign", "restriction", "instruction", "condition"}
VISIT_CHANGES = {"new", "changed", "stopped", "unchanged_mention"}
ROLES = {"doctor", "patient", "family", "nurse", "other", "unknown"}
EXTRACT_KEYS = {"schema_version", "document", "items", "allergy_statement", "allergies", "providers", "unreadable", "follow_ups"}
VISIT_KEYS = {"schema_version", "speaker_roles", "items", "allergies_mentioned", "unclear", "follow_ups"}


def _conf(v: Any) -> float:
    try:
        f = float(v)
    except (TypeError, ValueError):
        return 0.5
    return f if 0.0 <= f <= 1.0 else 0.5


def _list(v: Any) -> list:
    return v if isinstance(v, list) else []


def repair_extract(j: dict) -> dict:
    out = {k: v for k, v in j.items() if k in EXTRACT_KEYS}
    out["schema_version"] = "extract.v1"
    doc = out.get("document") if isinstance(out.get("document"), dict) else {}
    dt = str(doc.get("doc_type") or "other").strip().lower().replace("-", "_")
    dt = _DOC_ALIASES.get(dt, dt)
    lang = str(doc.get("language") or "en").strip().lower()
    out["document"] = {"doc_type": dt if dt in DOC_TYPES else "other", "language": lang if lang in LANGS else ("mixed" if lang else "en"),
                       "doc_date": doc.get("doc_date") if isinstance(doc.get("doc_date"), str) else None,
                       "issuer": doc.get("issuer") if isinstance(doc.get("issuer"), str) else None}
    items = []
    for it in _list(out.get("items")):
        if isinstance(it, dict) and str(it.get("kind", "")).lower() in EXTRACT_KINDS and it.get("title") and isinstance(it.get("source"), dict):
            it = {**it, "kind": str(it["kind"]).lower(), "confidence": _conf(it.get("confidence"))}
            it["details"] = it["details"] if isinstance(it.get("details"), dict) else {}
            items.append({k: it[k] for k in ("kind", "title", "details", "source", "confidence")})
    out["items"] = items
    allergies = []
    for al in _list(out.get("allergies")):
        if isinstance(al, dict) and al.get("substance") and isinstance(al.get("source"), dict):
            sev = str(al.get("severity") or "unknown").lower()
            allergies.append({"substance": al["substance"], "reaction": al.get("reaction") if isinstance(al.get("reaction"), str) else None,
                              "severity": sev if sev in SEVERITY else "unknown", "source": al["source"]})
    out["allergies"] = allergies
    stmt = out.get("allergy_statement")
    if stmt not in ("listed", "none_stated", "not_mentioned"):
        stmt = "listed" if allergies else "not_mentioned"
    if allergies and stmt != "listed":
        stmt = "listed"
    out["allergy_statement"] = stmt
    out["providers"] = [p for p in _list(out.get("providers")) if isinstance(p, dict)]
    out["unreadable"] = [u for u in _list(out.get("unreadable")) if isinstance(u, dict) and isinstance(u.get("page"), int) and isinstance(u.get("note"), str)]
    out["follow_ups"] = [f for f in _list(out.get("follow_ups")) if isinstance(f, dict) and f.get("what") and f.get("due_text") and isinstance(f.get("source"), dict)]
    return out


def repair_visit(j: dict) -> dict:
    out = {k: v for k, v in j.items() if k in VISIT_KEYS}
    out["schema_version"] = "visit.v1"
    roles = []
    for r in _list(out.get("speaker_roles")):
        if isinstance(r, dict) and r.get("label"):
            role = str(r.get("role") or "unknown").lower()
            roles.append({"label": str(r["label"])[:4], "role": role if role in ROLES else "unknown", "name": r.get("name") if isinstance(r.get("name"), str) else None})
    out["speaker_roles"] = roles
    items = []
    for it in _list(out.get("items")):
        if not (isinstance(it, dict) and str(it.get("kind", "")).lower() in VISIT_KINDS and str(it.get("change", "")).lower() in VISIT_CHANGES
                and it.get("title") and isinstance(it.get("source"), dict)):
            continue
        items.append({"kind": str(it["kind"]).lower(), "change": str(it["change"]).lower(), "title": it["title"],
                      "details": it["details"] if isinstance(it.get("details"), dict) else {}, "source": it["source"], "confidence": _conf(it.get("confidence"))})
    out["items"] = items
    out["allergies_mentioned"] = [a for a in _list(out.get("allergies_mentioned"))
                                  if isinstance(a, dict) and a.get("substance") and isinstance(a.get("source"), dict) and a.get("stated_by") in ("doctor", "patient", "family")]
    out["unclear"] = [{"segment_ids": [str(x) for x in _list(u.get("segment_ids"))], "note": str(u.get("note", ""))} for u in _list(out.get("unclear"))
                      if isinstance(u, dict) and str(u.get("note", "")).strip()]
    out["follow_ups"] = [f for f in _list(out.get("follow_ups")) if isinstance(f, dict) and f.get("what") and f.get("due_text") and isinstance(f.get("source"), dict)]
    return out
