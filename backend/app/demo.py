"""The demo family: Ramesh Kulkarni, a FICTIONAL patient, built by running the synthetic documents and a mock visit through the
real pipeline. Nothing here is pre-baked: every flag, source and pending change comes from the same code a real upload uses.

The story: an allergy card, a clinic prescription, a discharge summary that leaves a medicine out and repeats paracetamol under a
second brand, a specialist's amoxicillin for a penicillin-allergic patient, then a visit where the doctor halves a dose.
Nothing is confirmed: the family does that, so the demo shows who confirmed what."""
from __future__ import annotations

import logging
from pathlib import Path
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.orm import Session

from .config import get_settings
from .db import run_after_commit, worker_session
from .pipelines.documents import process_document
from .services import visits as visit_svc
from .services.audit import timeline
from .services.documents import ingest_document
from .services.patients import create_patient

log = logging.getLogger("caresaathi.demo")
DEMO_NAME = "Ramesh Kulkarni"
READY_TEXT = "Demo family ready"
# (document id, document type); the order is the story.
SEQUENCE = [("R4", "other"), ("R1", "prescription"), ("R2", "discharge_summary"), ("R5", "prescription")]


def start_demo(s: Session, *, user_id: UUID, display_name: str) -> dict:
    """Create the demo patient for this user (once) and load the story in the background."""
    # The marker is a timeline event written when the demo is requested, so a patient the family made by hand is never mistaken for it.
    existing = s.execute(text("""SELECT p.id FROM patients p JOIN timeline_events t ON t.patient_id = p.id AND t.event_type = 'demo_started'
                                 WHERE p.deleted_at IS NULL ORDER BY p.created_at LIMIT 1""")).scalar()
    if existing:
        return {"patient_id": str(existing), "status": "exists"}
    pid = create_patient(s, user_id=user_id, full_name=DEMO_NAME, language="hi", relationship_label="Daughter or son")
    timeline(s, patient_id=pid, event_type="demo_started", actor_type="system", actor_id=None,
             summary="Loading the demo family: a fictional patient with synthetic documents.")
    run_after_commit(s, lambda: _load_story(pid, user_id, display_name))
    return {"patient_id": str(pid), "status": "seeding"}


def _load_story(patient_id: UUID, user_id: UUID, display_name: str) -> None:
    root = Path(get_settings().synthetic_dir) / "ramesh"
    try:
        for doc_id, kind in SEQUENCE:
            path = next((root / "docs").glob(f"{doc_id}_*.txt"))
            with worker_session() as w:
                r = ingest_document(w, patient_id=patient_id, user_id=user_id, data=path.read_bytes(), filename=path.name, doc_type=kind)
            if r["new"]:
                process_document(UUID(r["id"]))
        script = visit_svc.load_script("V1")
        with worker_session() as w:
            vid = visit_svc.create_visit(
                w, patient_id=patient_id, user_id=user_id, origin="mock", doctor_name="Dr. Joshi (mock)", hospital=None, language_hint="hi",
                patient_consent={"agreed": True, "given_by_name": display_name, "on_behalf_of_patient": True},
                doctor_consent={"agreed": True, "given_by_name": "Dr. Joshi (mock)"})
            visit_svc.add_mock_segments(w, patient_id, vid, script)
        visit_svc.process_visit(vid)
    except Exception:                                    # a half-loaded demo must say so rather than look finished
        log.exception("demo load failed")
        with worker_session() as w:
            timeline(w, patient_id=patient_id, event_type="demo_failed", actor_type="system", actor_id=None,
                     summary="The demo family could not be fully loaded.")
        return
    with worker_session() as w:
        timeline(w, patient_id=patient_id, event_type="demo_ready", actor_type="system", actor_id=None,
                 summary=f"{READY_TEXT}: a fictional patient with synthetic documents and one mock visit.")
