"""Why a drug-family match can be trusted: the WHO ATC classification behind it (D-63).

The decision is still made by code against our own list (CLAUDE.md invariant 3); this only states the basis in one sentence, built by code
from stored class codes. The model never writes it. A membership the ATC lookup did not confirm says so plainly rather than going quiet,
because an unexplained match is worth less than an honestly labelled one.
"""
from __future__ import annotations

from typing import Any
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.orm import Session

OWN_LIST = "Matched against CareSaathi's own reference list, which the WHO ATC classification did not confirm. It has not been reviewed by a pharmacist."


def reference_check(s: Session) -> dict[str, Any] | None:
    """What the reference list was checked against, and when. None before migration 0014 has run."""
    r = s.execute(text("SELECT source, caveat, checked_on, summary FROM reference_checks WHERE kind = 'drug_families'")).mappings().first()
    return {"source": r["source"], "caveat": r["caveat"], "checked_on": r["checked_on"].isoformat(), **(r["summary"] or {})} if r else None


def family_basis(s: Session, conflict_id: UUID) -> dict[str, Any] | None:
    """One line of provenance for a drug-family conflict: the ATC group both substances sit in, or an honest note that ours is unconfirmed."""
    r = s.execute(text("""
        SELECT f.name AS family, f.atc_prefix, f.atc_name, ci.title AS medicine, a.substance AS allergy,
               mi.ingredient_raw, ds.atc_codes, dm.atc_confirmed
        FROM allergy_conflicts ac
        JOIN drug_families f ON f.id = ac.family_id
        JOIN care_plan_items ci ON ci.id = ac.care_plan_item_id
        LEFT JOIN allergies a ON a.id = ac.allergy_id
        LEFT JOIN medicine_ingredients mi ON mi.id = ac.ingredient_id
        LEFT JOIN drug_substances ds ON ds.id = mi.substance_id
        LEFT JOIN drug_family_members dm ON dm.family_id = f.id AND dm.substance_id = mi.substance_id
        WHERE ac.id = :c AND ac.match = 'drug_family'"""), {"c": conflict_id}).mappings().first()
    if not r:
        return None
    chk = reference_check(s)
    ing = (r["ingredient_raw"] or r["medicine"]).strip()
    if r["atc_confirmed"] and r["atc_prefix"]:
        hit = next((c for c in (r["atc_codes"] or []) if c.startswith(r["atc_prefix"])), r["atc_prefix"])
        text_ = (f"{ing} is classed {hit} in the WHO ATC classification, inside {r['atc_prefix']} ({r['atc_name']}), which is the group this "
                 f"reference list calls {r['family']}. That is why it was matched against the recorded allergy to {r['allergy']}. "
                 "A classification, not a medical judgement.")
        return {"confirmed": True, "atc_code": hit, "atc_group": r["atc_prefix"], "atc_name": r["atc_name"], "family": r["family"],
                "text": text_, "source": chk["source"] if chk else None, "checked_on": chk["checked_on"] if chk else None}
    return {"confirmed": False, "atc_code": None, "atc_group": r["atc_prefix"], "atc_name": r["atc_name"], "family": r["family"],
            "text": f"{ing} is listed under {r['family']} in CareSaathi's own reference list. {OWN_LIST}",
            "source": chk["source"] if chk else None, "checked_on": chk["checked_on"] if chk else None}
