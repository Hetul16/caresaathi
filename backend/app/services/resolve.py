"""Ingredient and allergy resolution against the vetted reference list (docs/14-data-mapping.md section 6).

Exact matches only: substance name, then synonyms, then brand names. No fuzzy matching anywhere in the allergy
path (D-23). No match returns None, which the conflict finder reports as `unresolved`.
"""
from __future__ import annotations

from uuid import UUID

from sqlalchemy import text
from sqlalchemy.orm import Session

from ..safety.normalize import normalize_medicine_name


# Salt words printed after the medicine name on Indian strips ("Diclofenac Sodium", "Metformin Hydrochloride"). They are removed only AFTER an exact
# match on the full name has failed, so names that really contain them ("sodium valproate") still match as themselves.
_SALT_WORDS = {"sodium", "potassium", "hydrochloride", "hcl", "besylate", "maleate", "tartrate", "succinate", "mesylate"}


def resolve_substance(s: Session, raw: str) -> UUID | None:
    n = normalize_medicine_name(raw)
    if not n:
        return None
    found = _lookup(s, n)
    if found is None:
        words = n.split()
        trimmed = [w for w in words if w not in _SALT_WORDS]
        if trimmed and len(trimmed) < len(words):
            found = _lookup(s, " ".join(trimmed))
    return found


def _lookup(s: Session, n: str) -> UUID | None:
    row = s.execute(text("""
        SELECT id FROM drug_substances
        WHERE substance_normalized = :n
           OR EXISTS (SELECT 1 FROM unnest(synonyms) x WHERE lower(x) = :n)
           OR EXISTS (SELECT 1 FROM unnest(brand_names) x WHERE lower(x) = :n)
        LIMIT 1"""), {"n": n}).first()
    return row[0] if row else None


def resolve_family(s: Session, raw: str) -> UUID | None:
    n = raw.strip().casefold()
    row = s.execute(text("""
        SELECT id FROM drug_families
        WHERE lower(code) = :n OR lower(name) = :n
           OR EXISTS (SELECT 1 FROM unnest(synonyms) x WHERE lower(x) = :n)
        LIMIT 1"""), {"n": n}).first()
    return row[0] if row else None


def resolve_allergy(s: Session, raw: str) -> tuple[UUID | None, UUID | None]:
    """An allergy names either a specific drug or a drug class. Returns (substance_id, family_id)."""
    sub = resolve_substance(s, raw)
    if sub:
        return sub, None
    return None, resolve_family(s, raw)
