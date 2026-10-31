"""Applying a validated extraction to the care plan (docs/14-data-mapping.md section 2, steps 4 to 10).

Rules enforced here and in the database:
  - every item and allergy gets a source_ref with the quote that was verified against the page text;
  - items that need review (low confidence, level disagreement) are NOT applied;
  - changes read from a written document are applied as a new version, marked "not yet confirmed" (D-18);
  - allergy conflicts are found by `find_allergy_conflicts` (SQL, vetted list); the model only words the flag.
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from datetime import date
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import text
from sqlalchemy.orm import Session

from ..clients.models import ModelClient, Usage
from ..safety.dosing import daily_units, parse_schedule
from ..safety.followups import compute_due
from ..safety.refill import estimate_run_out
from ..safety.guard import GuardContext, guard_output
from ..safety.normalize import normalize_medicine_name, same_medicine, split_combination
from ..safety.text import normalize_text
from ..safety.validate import ValidatedExtraction
from .audit import timeline, write_audit
from .guarding import guard_with_judge
from .resolve import resolve_allergy, resolve_substance

_NO_ALLERGY_LINE = re.compile(r"no known (?:drug )?allergies|nkda|no allergies", re.I)


@dataclass
class ApplyResult:
    new_items: int = 0
    changed_items: int = 0
    unchanged_items: int = 0
    skipped_for_review: int = 0
    allergies_added: int = 0
    conflicts: list[UUID] = field(default_factory=list)
    changes: list[UUID] = field(default_factory=list)
    medicine_item_ids: list[UUID] = field(default_factory=list)
    follow_ups: int = 0
    supply_records: int = 0


def _j(v: Any) -> str:
    return json.dumps(v, default=str, ensure_ascii=False)


def record_model_call(s: Session, patient_id: UUID | None, u: Usage) -> UUID:
    row = s.execute(text("""
        INSERT INTO model_calls (patient_id, provider, model, purpose, status, input_tokens, output_tokens,
                                 latency_ms, contributor_mode, error)
        VALUES (:p, 'meta', :m, :pu, :st, :i, :o, :l, :c, :e) RETURNING id"""),
        {"p": patient_id, "m": u.model, "pu": u.purpose, "st": u.status, "i": u.input_tokens, "o": u.output_tokens,
         "l": u.latency_ms, "c": u.contributor_mode, "e": u.error}).first()
    return row[0]


def make_source_ref(s: Session, *, patient_id: UUID, document_id: UUID, page: int, line_start: int | None,
                    line_end: int | None, quote: str) -> UUID:
    return s.execute(text("""
        INSERT INTO source_refs (patient_id, kind, document_id, page, line_start, line_end, quote)
        VALUES (:p, 'document', :d, :pg, :ls, :le, :q) RETURNING id"""),
        {"p": patient_id, "d": document_id, "pg": page, "ls": line_start, "le": line_end, "q": quote}).scalar_one()


def insert_item_version(s: Session, *, patient_id: UUID, item_key: UUID, version: int, supersedes_id: UUID | None,
                        kind: str, title: str, details: dict, alert_level: str | None, due_at: Any, date_missing: bool,
                        source_ref_id: UUID, created_by_type: str, created_by: UUID | None, status: str = "active") -> UUID:
    """Write one immutable version of a plan item and retire the one it replaces. The only writer of care_plan_items."""
    new_id = uuid4()
    if supersedes_id:        # retire the old version first: only one version of an item may be current
        s.execute(text("UPDATE care_plan_items SET is_current = false WHERE id = :id"), {"id": supersedes_id})
    s.execute(text("""
        INSERT INTO care_plan_items (id, patient_id, item_key, version, supersedes_id, kind, status, title, details, alert_level,
                                     due_at, date_missing, source_ref_id, created_by_type, created_by)
        VALUES (:id, :p, :k, :v, :sup, CAST(:kind AS plan_item_kind), CAST(:st AS plan_item_status), :t, CAST(:d AS jsonb),
                CAST(:al AS alert_level), :due, :dm, :src, CAST(:cbt AS actor_type), :cb)"""),
        {"id": new_id, "p": patient_id, "k": item_key, "v": version, "sup": supersedes_id, "kind": kind, "st": status,
         "t": title.strip(), "d": _j(details), "al": alert_level, "due": due_at, "dm": date_missing, "src": source_ref_id,
         "cbt": created_by_type, "cb": created_by})
    return new_id


def insert_ingredients(s: Session, patient_id: UUID, item_id: UUID, ings: list[tuple[str, str | None]]) -> None:
    for raw_name, strength in ings:
        norm = normalize_medicine_name(raw_name)
        if not norm:
            continue
        s.execute(text("""
            INSERT INTO medicine_ingredients (patient_id, item_id, ingredient_raw, ingredient_normalized, substance_id, strength_text)
            VALUES (:p, :i, :raw, :n, :sid, :st)"""),
            {"p": patient_id, "i": item_id, "raw": raw_name, "n": norm, "sid": resolve_substance(s, norm), "st": strength})


def ingredients_of(kind: str, title: str, details: dict) -> list[tuple[str, str | None]]:
    """(raw name, strength) pairs for a medicine item."""
    out: list[tuple[str, str | None]] = []
    for ing in details.get("ingredients") or []:
        if isinstance(ing, dict) and ing.get("name"):
            for part in split_combination(str(ing["name"])):
                out.append((part, ing.get("strength")))
    if not out:
        for part in split_combination(normalize_medicine_name(title)):
            out.append((part, None))
    return out


def _item_key_match(s: Session, patient_id: UUID, kind: str, title: str, ing_norm: frozenset[str], document_id: UUID) -> dict | None:
    """Find the current item this line is a new version of. Medicines match on the full ingredient set AND the same
    medicine (a different brand of one ingredient stays a separate item, so a possible duplicate remains visible).
    Items that came from THIS document never match, so two lines in one document cannot overwrite each other."""
    if kind == "medicine" and ing_norm:
        rows = s.execute(text("""
            SELECT c.id, c.item_key, c.version, c.title, c.details,
                   array_agg(mi.ingredient_normalized ORDER BY mi.ingredient_normalized) AS ings
            FROM care_plan_items c JOIN medicine_ingredients mi ON mi.item_id = c.id
            JOIN source_refs sr ON sr.id = c.source_ref_id
            WHERE c.patient_id = :p AND c.is_current AND c.kind = 'medicine' AND sr.document_id IS DISTINCT FROM CAST(:d AS uuid)
            GROUP BY c.id"""), {"p": patient_id, "d": document_id}).mappings().all()
        for r in rows:
            if same_medicine(title, ing_norm, r["title"], frozenset(r["ings"])):
                return dict(r)
        return None
    rows = s.execute(text("""
        SELECT c.id, c.item_key, c.version, c.title, c.details FROM care_plan_items c JOIN source_refs sr ON sr.id = c.source_ref_id
        WHERE c.patient_id = :p AND c.is_current AND c.kind = CAST(:k AS plan_item_kind) AND sr.document_id IS DISTINCT FROM CAST(:d AS uuid)"""),
        {"p": patient_id, "k": kind, "d": document_id}).mappings().all()
    for r in rows:
        if normalize_text(r["title"]) == normalize_text(title):
            return dict(r)
    return None


def _comparable(details: dict) -> dict:
    keep = ("dose_text", "frequency_text", "duration_days", "instructions_text", "form", "with_food", "route",
            "description", "text", "test_name", "due_date", "when", "purpose")
    out = {k: details.get(k) for k in keep if details.get(k) is not None}
    out["ingredients"] = sorted((i.get("name", "").casefold(), (i.get("strength") or "").casefold())
                                for i in details.get("ingredients") or [] if isinstance(i, dict))
    return out


def apply_document_extraction(s: Session, *, patient_id: UUID, document_id: UUID, validated: ValidatedExtraction,
                              raw_output: str, page_lines: dict[int, list[str]], user_id: UUID | None,
                              client: ModelClient, language: str = "en", model_call_id: UUID | None = None) -> ApplyResult:
    assert validated.data is not None
    lock_patient(s, patient_id)
    data = validated.data
    res = ApplyResult()
    try:
        doc_date: date | None = date.fromisoformat(data.document.doc_date) if data.document.doc_date else None
    except ValueError:
        doc_date = None

    ext_status = "needs_review" if validated.needs_review else "applied"
    ext_id = s.execute(text("""
        INSERT INTO extractions (patient_id, origin, document_id, model_call_id, schema_version, raw_output, validated,
                                 validation_errors, status, applied_at)
        VALUES (:p, 'document', :d, :mc, 'extract.v1', CAST(:r AS jsonb), true, CAST(:e AS jsonb),
                CAST(:st AS extraction_status), CASE WHEN :st = 'applied' THEN now() END) RETURNING id"""),
        {"p": patient_id, "d": document_id, "mc": model_call_id, "r": raw_output,
         "e": _j(validated.errors + [{"type": "review", "item": i, "reason": r} for i, r in validated.review_items.items()]),
         "st": ext_status}).scalar_one()

    # ---- allergies from the document --------------------------------------------------------------
    for i, al in enumerate(data.allergies):
        if i in validated.rejected_allergies:
            continue
        sub_id, fam_id = resolve_allergy(s, al.substance)
        norm = normalize_medicine_name(al.substance)
        exists = s.execute(text("SELECT 1 FROM allergies WHERE patient_id=:p AND is_current AND active AND substance_normalized=:n"),
                           {"p": patient_id, "n": norm}).first()
        if exists:
            continue
        src = make_source_ref(s, patient_id=patient_id, document_id=document_id, page=al.source.page,
                              line_start=al.source.line_start, line_end=al.source.line_end, quote=al.source.quote)
        key = uuid4()
        s.execute(text("""
            INSERT INTO allergies (patient_id, allergy_key, version, substance, substance_normalized, substance_id, family_id,
                                   reaction, severity, source_type, source_ref_id)
            VALUES (:p, :k, 1, :sub, :n, :sid, :fid, :r, CAST(:sev AS allergy_severity), 'document', :src)"""),
            {"p": patient_id, "k": key, "sub": al.substance, "n": norm, "sid": sub_id, "fid": fam_id,
             "r": al.reaction, "sev": al.severity, "src": src})
        res.allergies_added += 1
        write_audit(s, actor_type="system", actor_id=None, patient_id=patient_id, action="allergy.added_from_document",
                    entity_type="allergy", entity_id=key, after={"substance": al.substance, "document_id": str(document_id)})

    if res.allergies_added:
        recheck_medicines_for_new_allergy(s, patient_id, client, language)

    # "No known allergies" is recorded only when the page literally says so. Code finds the line, not the model.
    if data.allergy_statement == "none_stated" and not data.allergies:
        for pg, lines in page_lines.items():
            hit = next(((n, ln) for n, ln in enumerate(lines, 1) if _NO_ALLERGY_LINE.search(ln)), None)
            if hit:
                src = make_source_ref(s, patient_id=patient_id, document_id=document_id, page=pg,
                                      line_start=hit[0], line_end=hit[0], quote=hit[1].strip())
                s.execute(text("""
                    INSERT INTO allergy_status (patient_id, state, source_ref_id, last_checked_at)
                    VALUES (:p, 'no_known_allergies', :src, now())
                    ON CONFLICT (patient_id) DO UPDATE SET state = 'no_known_allergies', source_ref_id = :src,
                                                           last_checked_at = now(), updated_at = now()"""),
                    {"p": patient_id, "src": src})
                break

    # ---- plan items ------------------------------------------------------------------------------------
    for i, item in enumerate(data.items):
        if i in validated.rejected_items or i in validated.review_items:
            res.skipped_for_review += 1
            continue
        details = dict(item.details or {})
        if item.kind == "medicine":
            sched = parse_schedule(details.get("frequency_text"))
            if sched:
                details["schedule"] = sched
        ings = ingredients_of(item.kind, item.title, details) if item.kind == "medicine" else []
        ing_norm = frozenset(normalize_medicine_name(n) for n, _ in ings if normalize_medicine_name(n))
        match = _item_key_match(s, patient_id, item.kind, item.title, ing_norm, document_id)

        if match and _comparable(match["details"] or {}) == _comparable(details):
            res.unchanged_items += 1
            continue

        src = make_source_ref(s, patient_id=patient_id, document_id=document_id, page=item.source.page,
                              line_start=item.source.line_start, line_end=item.source.line_end, quote=item.source.quote)
        alert = validated.alert_levels.get(i) if item.kind == "warning_sign" else None
        due_at = None
        date_missing = item.kind in ("test", "appointment") and not (details.get("due_date") or details.get("when"))

        item_key = match["item_key"] if match else uuid4()
        version = (match["version"] + 1) if match else 1
        new_id = insert_item_version(s, patient_id=patient_id, item_key=item_key, version=version,
                                     supersedes_id=match["id"] if match else None, kind=item.kind, title=item.title,
                                     details=details, alert_level=alert, due_at=due_at, date_missing=date_missing,
                                     source_ref_id=src, created_by_type="agent", created_by=None)
        insert_ingredients(s, patient_id, new_id, ings)
        if item.kind == "medicine":
            res.medicine_item_ids.append(new_id)
            res.supply_records += _record_supply(s, patient_id, item_key, new_id, details, doc_date, src)

        change_id = s.execute(text("""
            INSERT INTO plan_changes (patient_id, extraction_id, change_type, item_key, before_state, after_state, source_ref_id,
                                      requires_confirmation, status, applied_item_id)
            VALUES (:p, :e, CAST(:ct AS change_type), :k, CAST(:b AS jsonb), CAST(:a AS jsonb), :src, false, 'applied', :ai)
            RETURNING id"""),
            {"p": patient_id, "e": ext_id, "ct": "changed" if match else "new", "k": item_key,
             "b": _j({"title": match["title"], "details": match["details"]}) if match else None,
             "a": _j({"title": item.title, "details": details}), "src": src, "ai": new_id}).scalar_one()
        res.changes.append(change_id)
        if match:
            res.changed_items += 1
        else:
            res.new_items += 1
        write_audit(s, actor_type="system", actor_id=None, patient_id=patient_id,
                    action="plan.version_added_from_document", entity_type="care_plan_item", entity_id=new_id,
                    after={"title": item.title, "version": version, "document_id": str(document_id)})

    # ---- follow-ups: the model gave the words, code computes the date, a person confirms ---------------------
    for i, fu in enumerate(data.follow_ups):
        if i in validated.rejected_follow_ups:
            continue
        src = make_source_ref(s, patient_id=patient_id, document_id=document_id, page=fu.source.page,
                              line_start=fu.source.line_start, line_end=fu.source.line_end, quote=fu.source.quote)
        s.execute(text("""
            INSERT INTO follow_ups (patient_id, source_ref_id, what, due_text, anchor_date, anchor_kind, due_date)
            VALUES (:p, :src, :w, :t, :ad, :ak, :dd) ON CONFLICT DO NOTHING"""),
            {"p": patient_id, "src": src, "w": fu.what.strip(), "t": fu.due_text.strip(), "ad": doc_date,
             "ak": "document" if doc_date else None, "dd": compute_due(doc_date, fu.due_text)})
        res.follow_ups += 1

    # ---- allergy conflicts for every new or changed medicine ---------------------------------------------
    for item_id in res.medicine_item_ids:
        res.conflicts += raise_conflicts_for_item(s, patient_id, item_id, client, language)

    timeline(s, patient_id=patient_id, event_type="document_processed", actor_type="system", actor_id=None,
             summary=f"Document read: {res.new_items} new, {res.changed_items} changed, {res.skipped_for_review} need a person to check.",
             entity_type="document", entity_id=document_id)
    return res


def _record_supply(s: Session, patient_id: UUID, item_key: UUID, item_id: UUID, details: dict, start: date | None, source_ref_id: UUID) -> int:
    """Quantity as written plus the daily units from the written frequency. The estimate is computed by code from those
    inputs, needs a start date, and stays unconfirmed until a named person confirms it."""
    q = details.get("quantity")
    if not isinstance(q, dict) or start is None:
        return 0
    try:
        qty = float(q.get("value"))
    except (TypeError, ValueError):
        return 0
    if qty <= 0:
        return 0
    daily = daily_units(details.get("frequency_text"))
    daily = daily if daily and daily > 0 else None
    s.execute(text("""
        INSERT INTO supply_records (patient_id, item_key, care_plan_item_id, quantity, quantity_unit, daily_units, start_date,
                                    estimated_run_out, source_ref_id)
        VALUES (:p, :k, :i, :q, :u, :d, :sd, :eta, :src) ON CONFLICT (care_plan_item_id) DO NOTHING"""),
        {"p": patient_id, "k": item_key, "i": item_id, "q": qty, "u": str(q.get("unit") or "tablets"), "d": daily, "sd": start,
         "eta": estimate_run_out(start, qty, daily), "src": source_ref_id})
    return 1


def lock_patient(s: Session, patient_id: UUID) -> None:
    """Serialize the writes that decide allergy conflicts for one patient until this transaction ends.

    Found by uploading three photos at once through the live app (Oct 31): the second prescription (Amoxicillin) and the allergy card were
    processed in parallel, each transaction could not see the other's uncommitted row, and the conflict was never raised. Model calls stay
    parallel; only the short database write that follows waits its turn."""
    s.execute(text("SELECT pg_advisory_xact_lock(hashtextextended(:k, 0))"), {"k": f"patient-plan:{patient_id}"})


def recheck_medicines_for_new_allergy(s: Session, patient_id: UUID, client: ModelClient, language: str = "en") -> int:
    """An allergy that arrives after medicines were listed: check those medicines again. Already-open conflicts are not duplicated."""
    ids = s.execute(text("""SELECT id FROM care_plan_items WHERE patient_id = :p AND is_current AND status = 'active' AND kind = 'medicine'"""),
                    {"p": patient_id}).scalars().all()
    return sum(len(raise_conflicts_for_item(s, patient_id, i, client, language)) for i in ids)


def raise_conflicts_for_item(s: Session, patient_id: UUID, item_id: UUID, client: ModelClient, language: str = "en") -> list[UUID]:
    """Run the SQL conflict finder for one medicine and open a conflict row for each finding. The model only
    words the flag and the question; the guard checks the words (D-12 rule 3, D-21)."""
    rows = s.execute(text("SELECT allergy_id, match, ingredient_id, family_id FROM find_allergy_conflicts(:i)"), {"i": item_id}).mappings().all()
    created: list[UUID] = []
    if not rows:
        return created
    item = s.execute(text("SELECT title, source_ref_id FROM care_plan_items WHERE id=:i"), {"i": item_id}).mappings().one()
    for r in rows:
        existing = s.execute(text("""
            SELECT id FROM allergy_conflicts WHERE care_plan_item_id=:i AND allergy_id IS NOT DISTINCT FROM :a
              AND ingredient_id IS NOT DISTINCT FROM :g"""), {"i": item_id, "a": r["allergy_id"], "g": r["ingredient_id"]}).first()
        if existing:
            continue
        allergy = None
        if r["allergy_id"]:
            allergy = s.execute(text("SELECT substance, source_ref_id FROM allergies WHERE id=:a"), {"a": r["allergy_id"]}).mappings().one()
        flag_out = question_out = None
        source_ids = [str(item["source_ref_id"])] + ([str(allergy["source_ref_id"])] if allergy else [])
        if allergy:
            facts = {"allergy": allergy["substance"], "medicine": item["title"], "match": r["match"]}
            flag_text, u1 = client.word("allergy_flag", facts, language)
            q_text, u2 = client.word("doctor_question", facts, language)
            ctx = GuardContext(language=language, source_ids=source_ids, require_grounding=True,
                               grounding_terms={allergy["substance"], item["title"], item["title"].split()[0]})
            flag_res, _ = guard_with_judge(client, flag_text, ctx)
            q_res, _ = guard_with_judge(client, q_text, ctx)
            flag_out = _store_output(s, patient_id, "allergy_flag", language, flag_res, source_ids, record_model_call(s, patient_id, u1))
            question_out = _store_output(s, patient_id, "doctor_question", language, q_res, source_ids, record_model_call(s, patient_id, u2))
        cid = s.execute(text("""
            INSERT INTO allergy_conflicts (patient_id, allergy_id, care_plan_item_id, ingredient_id, match, family_id,
                                           flag_output_id, question_output_id)
            VALUES (:p, :a, :i, :g, CAST(:m AS match_type), :f, :fo, :qo) RETURNING id"""),
            {"p": patient_id, "a": r["allergy_id"], "i": item_id, "g": r["ingredient_id"], "m": r["match"],
             "f": r["family_id"], "fo": flag_out, "qo": question_out}).scalar_one()
        created.append(cid)
        s.execute(text("""
            INSERT INTO outbox (patient_id, channel, template, payload, dedupe_key)
            VALUES (:p, 'in_app', 'allergy_conflict_urgent', CAST(:pl AS jsonb), :dk) ON CONFLICT (dedupe_key) DO NOTHING"""),
            {"p": patient_id, "pl": _j({"conflict_id": str(cid), "medicine": item["title"], "match": r["match"]}),
             "dk": f"conflict:{cid}"})
        write_audit(s, actor_type="system", actor_id=None, patient_id=patient_id, action="allergy.conflict_opened",
                    entity_type="allergy_conflict", entity_id=cid, after={"match": r["match"], "medicine": item["title"]})
    return created


def _store_output(s: Session, patient_id: UUID, otype: str, language: str, result, source_ids: list[str], model_call_id: UUID) -> UUID:
    oid = s.execute(text("""
        INSERT INTO generated_outputs (patient_id, output_type, language, body, model_call_id, guard_status, guard_reasons)
        VALUES (:p, CAST(:t AS output_type), :l, :b, :mc, CAST(:g AS guard_status), CAST(:r AS jsonb)) RETURNING id"""),
        {"p": patient_id, "t": otype, "l": language, "b": result.text, "mc": model_call_id,
         "g": "pass" if result.passed else "blocked", "r": _j(result.reasons)}).scalar_one()
    # A blocked output keeps its sources too (so the trust panel can show it), but it is never shown as a pass.
    for sid in source_ids:
        s.execute(text("INSERT INTO output_sources (output_id, source_ref_id, patient_id) VALUES (:o, :s, :p) ON CONFLICT DO NOTHING"),
                  {"o": oid, "s": sid, "p": patient_id})
    return oid
