"""Storing an uploaded document. One path for the API and the demo seed, so both get the same checks."""
from __future__ import annotations

from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import text
from sqlalchemy.orm import Session

from ..clients.storage import get_storage, new_key, sha256, sniff_mime
from ..config import get_settings
from .audit import timeline, write_audit
from .errors import ServiceError

DOC_TYPES = ("prescription", "lab_report", "discharge_summary", "specialist_letter", "imaging_report", "other")


def ingest_document(s: Session, *, patient_id: UUID, user_id: UUID, data: bytes, filename: str, doc_type: str, allow_text: bool = False) -> dict[str, Any]:
    """Validate, store and record a document. Returns {"id", "status", "doc_type", "new"}; `new` is False for a duplicate."""
    cfg = get_settings()
    if not data:
        raise ServiceError(422, "validation-failed", "The file is empty")
    if len(data) > cfg.max_upload_bytes:
        raise ServiceError(413, "validation-failed", "The file is too large")
    mime = sniff_mime(data)
    if mime is None and (cfg.model_mode == "fake" or allow_text) and filename.lower().endswith(".txt"):
        mime = "text/plain"          # offline mode, or the demo family (allow_text): the offline reader takes plain text; the live reader does not
    if mime is None:
        raise ServiceError(415, "validation-failed", "Please upload a photo (JPEG or PNG) or a PDF")
    if doc_type not in DOC_TYPES:
        doc_type = "other"

    digest = sha256(data)
    dup = s.execute(text("SELECT id FROM documents WHERE patient_id=:p AND sha256=:h"), {"p": patient_id, "h": digest}).first()
    if dup:
        return {"id": str(dup[0]), "status": "duplicate", "doc_type": doc_type, "new": False}

    doc_id = uuid4()
    key = new_key(str(patient_id), "documents", mime.split("/")[-1].replace("jpeg", "jpg"))
    get_storage().put(key, data, mime)
    s.execute(text("""INSERT INTO documents (id, patient_id, doc_type, original_filename, mime_type, byte_size, sha256, storage_key, uploaded_by)
                      VALUES (:i, :p, CAST(:t AS doc_type), :f, :m, :b, :h, :k, :u)"""),
              {"i": doc_id, "p": patient_id, "t": doc_type, "f": filename[:200], "m": mime, "b": len(data), "h": digest, "k": key, "u": user_id})
    write_audit(s, actor_type="user", actor_id=user_id, patient_id=patient_id, action="document.uploaded",
                entity_type="document", entity_id=doc_id, after={"mime": mime, "bytes": len(data)})
    timeline(s, patient_id=patient_id, event_type="document_uploaded", actor_type="user", actor_id=user_id,
             summary=f"Uploaded {filename or 'a document'}", entity_type="document", entity_id=doc_id)
    return {"id": str(doc_id), "status": "uploaded", "doc_type": doc_type, "new": True}
