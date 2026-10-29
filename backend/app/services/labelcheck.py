"""Label check (C4, D-48). The caregiver photographs a strip, box, bottle or tube. A vision model READS the printed text; code does the rest.

What this is not: it never identifies a medicine from its shape, colour or markings, and it never says a medicine is right, safe or
unsafe. Every ingredient the model reports must appear in the text it transcribed, or it is dropped. The comparison with the care plan,
the allergy check and every sentence shown are built by code from stored facts."""
from __future__ import annotations

import re
from typing import Any
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.orm import Session

from ..clients.models import DocFile, ModelError, get_model_client
from ..safety.injection import looks_like_injection
from ..safety.normalize import normalize_medicine_name, same_medicine, split_combination
from ..safety.text import quote_in_text
from .audit import timeline, write_audit
from .errors import ServiceError
from .plan import record_model_call
from .readmodel import item_detail, source_of
from .resolve import resolve_substance

MAX_BYTES = 8_000_000
NOTE = "This reads the printed text on the label and compares it with your documents. It does not say whether a medicine is right or safe. Ask the pharmacist."
LOOSE = "I can only read printed text. I cannot tell what a loose pill or an unmarked tube is from how it looks. Please show the strip, box or bottle it came in, or ask the pharmacist."


def _norm_strength(s: str | None) -> str:
    return re.sub(r"\s+", "", (s or "").casefold())


def _plan_medicines(s: Session, pid: UUID) -> list[dict]:
    rows = s.execute(text("""
        SELECT c.id, c.title, c.details, sr.kind AS source_kind, sr.document_id, sr.page, sr.line_start, sr.quote,
               coalesce(d.original_filename, d.doc_type::text) AS doc_title
        FROM care_plan_items c JOIN source_refs sr ON sr.id = c.source_ref_id LEFT JOIN documents d ON d.id = sr.document_id
        WHERE c.patient_id = :p AND c.is_current AND c.status = 'active' AND c.kind = 'medicine' ORDER BY c.created_at"""), {"p": pid}).mappings().all()
    out = []
    for r in rows:
        ings = s.execute(text("SELECT ingredient_normalized, strength_text FROM medicine_ingredients WHERE item_id = :i"), {"i": r["id"]}).all()
        out.append({"title": r["title"], "ings": frozenset(i[0] for i in ings), "strengths": {i[0]: i[1] for i in ings},
                    "detail": item_detail(r["details"] or {}) or "", "source": source_of(r)})
    return out


def _allergy_flags(s: Session, pid: UUID, ingredients: list[dict]) -> list[dict]:
    """Direct and drug-family matches against the allergies on file, found in SQL against the vetted list. Unknown is not safe:
    an ingredient that cannot be resolved is reported as "could not check" whenever any allergy is on file."""
    allergies = s.execute(text("""
        SELECT a.substance, a.substance_id, a.family_id, sr.kind AS source_kind, sr.document_id, sr.page, sr.line_start, sr.quote,
               coalesce(d.original_filename, d.doc_type::text) AS doc_title
        FROM allergies a JOIN source_refs sr ON sr.id = a.source_ref_id LEFT JOIN documents d ON d.id = sr.document_id
        WHERE a.patient_id = :p AND a.is_current AND a.active"""), {"p": pid}).mappings().all()
    if not allergies:
        return []
    flags: list[dict] = []
    for ing in ingredients:
        sid = ing.get("substance_id")
        if sid is None:
            flags.append({"ingredient": ing["name"], "match": "unresolved", "text":
                          f"“{ing['name']}” on this label could not be checked against the allergy list. Question for the pharmacist: could you check it?"})
            continue
        for al in allergies:
            direct = al["substance_id"] is not None and al["substance_id"] == sid
            fam = False
            if not direct:
                fam = s.execute(text("""
                    SELECT 1 FROM drug_family_members fm WHERE fm.substance_id = :sid AND
                      (fm.family_id = :fid OR fm.family_id IN (SELECT m2.family_id FROM drug_family_members m2 WHERE m2.substance_id = :asid))
                    LIMIT 1"""), {"sid": sid, "fid": al["family_id"], "asid": al["substance_id"]}).first() is not None
            if direct or fam:
                flags.append({"ingredient": ing["name"], "match": "direct" if direct else "drug_family", "allergy": al["substance"], "source": source_of(al),
                              "text": f"“{ing['name']}” on this label {'is' if direct else 'belongs to the same family as'} the recorded allergy “{al['substance']}”. "
                                      "Question for the doctor or pharmacist: could you check this?"})
    return flags


def _verdict(product: dict, plan: list[dict]) -> tuple[str, dict | None, str, str | None]:
    names = frozenset(normalize_medicine_name(i["name"]) for i in product["ingredients"] if normalize_medicine_name(i["name"]))
    label_title = product.get("brand") or " + ".join(i["name"] for i in product["ingredients"])
    ing_text = " + ".join(i["name"] + (f" {i['strength']}" if i.get("strength") else "") for i in product["ingredients"])
    shown = f"{product['brand']} ({ing_text})" if product.get("brand") and ing_text else label_title
    if not names and not product.get("brand"):
        return "could_not_read", None, "No medicine name could be read from this label.", "Could you tell me what this medicine is?"
    for item in plan:
        if names and (names == item["ings"] or same_medicine(label_title, names, item["title"], item["ings"])):
            diffs = [(i["name"], i.get("strength"), item["strengths"].get(normalize_medicine_name(i["name"])))
                     for i in product["ingredients"]
                     if i.get("strength") and item["strengths"].get(normalize_medicine_name(i["name"]))
                     and _norm_strength(i["strength"]) != _norm_strength(item["strengths"].get(normalize_medicine_name(i["name"])))]
            if diffs:
                n, lab, plan_s = diffs[0]
                return ("different_strength", item,
                        f"The label says {n} {lab}. Your documents say {n} {plan_s} ({item['source']['quote'][:80]}).",
                        f"The label shows {n} {lab} but the plan says {plan_s}. Could you confirm which is right?")
            return "matches", item, f"The label reads as {item['title']}, which is in your documents.", None
        # a brand-only label that matches a plan item by its name
        if not names and product.get("brand") and normalize_medicine_name(product["brand"]) in {normalize_medicine_name(item["title"])} | item["ings"]:
            return "matches", item, f"The label name matches {item['title']} in your documents.", None
    return ("not_in_plan", None, f"“{shown}” is not in the care plan.",
            f"The label shows {shown}. It is not in the documents I have. Could you tell me whether it is meant to be taken?")


def check_label(s: Session, *, patient_id: UUID, user_id: UUID, data: bytes, mime: str, filename: str) -> dict[str, Any]:
    from ..config import get_settings
    if mime not in ("image/png", "image/jpeg", "image/webp", "text/plain") or (mime == "text/plain" and get_settings().model_mode == "live"):
        raise ServiceError(415, "unsupported-type", "Please send a photo (JPEG, PNG or WebP)")
    if len(data) > MAX_BYTES or not data:
        raise ServiceError(413, "bad-size", "The photo is empty or larger than 8 MB")
    client = get_model_client()
    try:
        raw, usage = client.read_label(DocFile(data, mime, filename))
    except ModelError as e:
        raise ServiceError(502, "reader-unavailable", f"The label could not be read right now ({e}). Please try again or ask the pharmacist.") from e
    record_model_call(s, patient_id, usage)

    lines = [str(x).strip()[:200] for x in (raw.get("lines") or []) if str(x).strip()][:60]
    kept = [ln for ln in lines if not looks_like_injection(ln)]
    printed = "\n".join(kept)
    products: list[dict] = []
    dropped = 0
    plan = _plan_medicines(s, patient_id)
    for p in (raw.get("products") or [])[:4]:
        ings = []
        for i in (p.get("ingredients") or [])[:6]:
            name = str(i.get("name") or "").strip()
            for part in split_combination(name):
                if part and quote_in_text(part, printed):
                    ings.append({"name": part, "strength": (str(i.get("strength")).strip() if i.get("strength") and quote_in_text(str(i["strength"]), printed) else None),
                                 "substance_id": resolve_substance(s, part)})
                elif part:
                    dropped += 1                 # the model named an ingredient that is not printed on the label
        brand = str(p.get("brand") or "").strip() or None
        if brand and not quote_in_text(brand, printed):
            brand, dropped = None, dropped + 1
        prod = {"brand": brand, "ingredients": ings, "form": p.get("form") if p.get("form") and quote_in_text(str(p["form"]), printed) else None,
                "expiry": str(p["expiry"]) if p.get("expiry") and quote_in_text(str(p["expiry"]), printed) else None,
                "batch": str(p["batch"]) if p.get("batch") and quote_in_text(str(p["batch"]), printed) else None}
        verdict, item, sentence, question = _verdict(prod, plan)
        allergy = _allergy_flags(s, patient_id, ings) if verdict != "could_not_read" else []
        products.append({**{k: v for k, v in prod.items()}, "ingredients": [{"name": i["name"], "strength": i["strength"]} for i in ings],
                         "verdict": verdict, "text": sentence, "question": question, "plan_item": item and {"title": item["title"], "detail": item["detail"], "source": item["source"]},
                         "allergy": allergy})
    if not products or not printed.strip() or raw.get("loose_pill_without_text"):
        products = [{"brand": None, "ingredients": [], "verdict": "could_not_read", "text": LOOSE if raw.get("loose_pill_without_text") or not printed.strip() else
                     "No medicine name could be read from this photo.", "question": "Could you tell me what this medicine is?", "plan_item": None, "allergy": []}]

    write_audit(s, actor_type="user", actor_id=user_id, patient_id=patient_id, action="label.checked", entity_type="label_check",
                after={"verdicts": [p["verdict"] for p in products], "dropped_unprinted": dropped})
    timeline(s, patient_id=patient_id, event_type="label_checked", actor_type="user", actor_id=user_id,
             summary="A medicine label was checked against the plan: " + ", ".join(sorted({p["verdict"].replace("_", " ") for p in products})))
    return {"products": products, "printed_lines": kept, "dropped_unprinted": dropped, "note": NOTE}
