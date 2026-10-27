"""Document pipeline (docs/14-data-mapping.md section 2): store, read, validate, apply.

Runs in the background after the upload returns 202. Every step stores its output so a failure can resume
without calling the model again. A model failure is recorded and shown plainly; nothing is invented."""
from __future__ import annotations

import logging
from uuid import UUID

from sqlalchemy import text

from ..clients.models import DocFile, ModelError, get_model_client
from ..clients.storage import get_storage
from ..db import worker_session
from ..safety.reconcile import document_completeness
from ..safety.validate import validate_extraction
from ..services.audit import timeline, write_audit
from ..services.omissions import raise_omission_flags
from ..services.plan import apply_document_extraction, record_model_call

log = logging.getLogger("caresaathi.pipeline")


def process_document(document_id: UUID) -> None:
    client = get_model_client()
    storage = get_storage()

    with worker_session() as s:
        doc = s.execute(text("SELECT * FROM documents WHERE id=:i"), {"i": document_id}).mappings().first()
        if not doc:
            return
        s.execute(text("UPDATE documents SET status='processing' WHERE id=:i"), {"i": document_id})
        patient_id = doc["patient_id"]

    try:
        data = storage.get(doc["storage_key"])
        pages, u1 = client.transcribe_pages(DocFile(data, doc["mime_type"], doc["original_filename"] or "document"))
        page_lines = {p.page: p.lines for p in pages}
        page_texts = {p.page: p.text for p in pages}

        raw, u2 = client.extract_document(pages, doc["doc_type"] if doc["doc_type"] != "other" else None)
        validated = validate_extraction(raw, page_texts)
    except ModelError as e:
        log.warning("document %s failed: %s", document_id, e)
        with worker_session() as s:
            s.execute(text("UPDATE documents SET status='failed' WHERE id=:i"), {"i": document_id})
            timeline(s, patient_id=patient_id, event_type="document_failed", actor_type="system", actor_id=None,
                     summary="We could not read this document. Please try again or upload a clearer copy.",
                     entity_type="document", entity_id=document_id)
        return

    with worker_session() as s:
        mc1 = record_model_call(s, patient_id, u1)
        mc2 = record_model_call(s, patient_id, u2)
        ordered = [page_texts[k] for k in sorted(page_texts)]
        s.execute(text("UPDATE documents SET extracted_text=:t, page_count=:n, completeness=:c WHERE id=:i"),
                  {"t": "\f".join(ordered), "n": len(pages), "c": document_completeness(ordered), "i": document_id})
        if not validated.ok:
            s.execute(text("""INSERT INTO extractions (patient_id, origin, document_id, model_call_id, schema_version, raw_output,
                                                      validated, validation_errors, status)
                              VALUES (:p, 'document', :d, :mc, 'extract.v1', CAST(:r AS jsonb), false, CAST(:e AS jsonb), 'failed')"""),
                      {"p": patient_id, "d": document_id, "mc": mc2,
                       "r": raw if raw.strip().startswith("{") else '{"unparseable": true}',
                       "e": __import__("json").dumps(validated.errors)})
            s.execute(text("UPDATE documents SET status='needs_review' WHERE id=:i"), {"i": document_id})
            return

        meta = validated.data.document
        s.execute(text("""UPDATE documents SET doc_type = CAST(:t AS doc_type), language = CAST(:l AS lang_code),
                                               issuer = :iss WHERE id = :i"""),
                  {"t": meta.doc_type if doc["doc_type"] == "other" else doc["doc_type"], "l": meta.language,
                   "iss": meta.issuer, "i": document_id})
        res = apply_document_extraction(
            s, patient_id=patient_id, document_id=document_id, validated=validated, raw_output=raw, page_lines=page_lines,
            user_id=doc["uploaded_by"], client=client, model_call_id=mc2)
        if validated.injection_lines:
            n = validated.injection_lines
            timeline(s, patient_id=patient_id, event_type="document_injection", actor_type="system", actor_id=None,
                     summary=f"{n} line{'s' if n != 1 else ''} in this document read like instructions to CareSaathi, so {'they were' if n != 1 else 'it was'} ignored. "
                             "Please look at the document.", entity_type="document", entity_id=document_id)
            write_audit(s, actor_type="system", actor_id=None, patient_id=patient_id, action="document.injection_ignored",
                        entity_type="document", entity_id=document_id, after={"lines": n})
        final_type = meta.doc_type if doc["doc_type"] == "other" else doc["doc_type"]
        flags = raise_omission_flags(s, patient_id=patient_id, document_id=document_id, doc_type=final_type,
                                     items=validated.data.items, client=client)
        d = validated.data
        found_nothing = not (d.items or d.allergies or d.follow_ups or d.allergy_statement == "none_stated")
        if found_nothing:
            timeline(s, patient_id=patient_id, event_type="document_empty", actor_type="system", actor_id=None,
                     summary="We could not read anything we could use from this document. Please look at it, or upload a clearer copy.",
                     entity_type="document", entity_id=document_id)
        s.execute(text("UPDATE documents SET status = CAST(:st AS doc_status) WHERE id=:i"),
                  {"st": "needs_review" if (validated.needs_review or found_nothing) else "extracted", "i": document_id})
        write_audit(s, actor_type="system", actor_id=None, patient_id=patient_id, action="document.processed",
                    entity_type="document", entity_id=document_id,
                    after={"new": res.new_items, "changed": res.changed_items, "review": res.skipped_for_review,
                           "conflicts": len(res.conflicts), "omission_flags": len(flags)})
