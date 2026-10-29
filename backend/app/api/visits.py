"""Doctor Visit Listener endpoints (docs/15-api-spec.md, Visits). Consent first; the transcript is read-only evidence."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Literal
from uuid import UUID

from fastapi import APIRouter, Depends, File, Request, UploadFile
from pydantic import BaseModel, Field
from sqlalchemy import text
from sqlalchemy.orm import Session

from ..clients.storage import get_storage, new_key, sha256
from ..config import get_settings
from ..db import run_after_commit
from ..safety.audio import AudioRejected, check_wav
from ..services import visits as svc
from ..services.audit import write_audit
from .deps import db, problem, require_member
from .plan import _patient_of

router = APIRouter(tags=["visits"])


class Consent(BaseModel):
    agreed: bool
    given_by_name: str = Field(default="", max_length=120)
    on_behalf_of_patient: bool = False


class VisitIn(BaseModel):
    patient_consent: Consent
    doctor_consent: Consent
    doctor_name: str | None = Field(default=None, max_length=120)
    hospital: str | None = Field(default=None, max_length=160)
    language_hint: Literal["en", "hi", "mr", "unknown"] = "unknown"
    consent_text_version: str


class MockVisitIn(VisitIn):
    script_id: str = Field(min_length=1, max_length=12)


def _check_version(v: str) -> None:
    if v != svc.CONSENT_TEXT_VERSION:
        raise problem(422, "consent-required", "Please read and agree to the current consent text", f"expected {svc.CONSENT_TEXT_VERSION}")


@router.get("/visit-scripts")
def visit_scripts(s: Session = Depends(db, scope="function")):
    """The scripted mock visits available for demos and tests. Synthetic only."""
    folder = Path(get_settings().synthetic_dir) / "ramesh" / "visits"
    out = []
    for f in sorted(folder.glob("*.json")) if folder.is_dir() else []:
        d = json.loads(f.read_text(encoding="utf-8"))
        out.append({"id": d["id"], "title": d["title"], "language": d["language"], "experimental": bool(d.get("experimental"))})
    return out


@router.post("/patients/{patient_id}/visits", status_code=201)
def start_visit(patient_id: UUID, body: VisitIn, request: Request, s: Session = Depends(db, scope="function")):
    require_member(s, patient_id)
    _check_version(body.consent_text_version)
    vid = svc.create_visit(s, patient_id=patient_id, user_id=request.state.user_id, patient_consent=body.patient_consent.model_dump(),
                           doctor_consent=body.doctor_consent.model_dump(), doctor_name=body.doctor_name, hospital=body.hospital,
                           language_hint=body.language_hint, origin="recording")
    return {"id": str(vid), "status": "recording"}


@router.post("/patients/{patient_id}/visits/mock", status_code=202)
def start_mock_visit(patient_id: UUID, body: MockVisitIn, request: Request, s: Session = Depends(db, scope="function")):
    """Replays a scripted synthetic conversation through the same pipeline. Consent is still asked: it is the same flow."""
    require_member(s, patient_id)
    _check_version(body.consent_text_version)
    script = svc.load_script(body.script_id)
    vid = svc.create_visit(s, patient_id=patient_id, user_id=request.state.user_id, patient_consent=body.patient_consent.model_dump(),
                           doctor_consent=body.doctor_consent.model_dump(), doctor_name=body.doctor_name or "Dr. Joshi (mock)", hospital=body.hospital,
                           language_hint=body.language_hint if body.language_hint != "unknown" else script.get("language", "unknown"), origin="mock")
    svc.add_mock_segments(s, patient_id, vid, script)
    run_after_commit(s, lambda: svc.process_visit(vid))
    return {"id": str(vid), "status": "processing"}


@router.post("/visits/{visit_id}/audio", status_code=202)
async def upload_audio(visit_id: UUID, request: Request, file: UploadFile = File(...), s: Session = Depends(db, scope="function")):
    pid = _patient_of(s, "visits", visit_id)
    require_member(s, pid)
    row = s.execute(text("SELECT status, origin, audio_storage_key FROM visits WHERE id = :v"), {"v": visit_id}).mappings().one()
    if row["origin"] != "recording" or row["status"] != "recording" or row["audio_storage_key"]:
        raise problem(409, "visit-not-recording", "This visit is not waiting for a recording")
    data = await file.read(40 * 1024 * 1024)
    try:
        info = check_wav(data)
    except AudioRejected as e:
        raise problem(422, "audio-rejected", str(e)) from e
    key = new_key(str(pid), "visits", "wav")
    get_storage().put(key, data, "audio/wav")
    s.execute(text("UPDATE visits SET audio_storage_key = :k, audio_sha256 = :h, duration_ms = :d, status = 'processing', ended_at = now() WHERE id = :v"),
              {"k": key, "h": sha256(data), "d": info.duration_ms, "v": visit_id})
    write_audit(s, actor_type="user", actor_id=request.state.user_id, patient_id=pid, action="visit.audio_uploaded", entity_type="visit",
                entity_id=visit_id, after={"bytes": len(data), "duration_ms": info.duration_ms})
    run_after_commit(s, lambda: svc.process_visit(visit_id))
    return {"id": str(visit_id), "status": "processing"}


@router.post("/visits/{visit_id}/retry", status_code=202)
def retry_visit(visit_id: UUID, s: Session = Depends(db, scope="function")):
    require_member(s, _patient_of(s, "visits", visit_id))
    status = s.execute(text("SELECT status FROM visits WHERE id = :v"), {"v": visit_id}).scalar_one()
    if status != "failed":
        raise problem(409, "visit-not-failed", "Only a visit that failed can be tried again")
    run_after_commit(s, lambda: svc.process_visit(visit_id))
    return {"id": str(visit_id), "status": "processing"}


@router.get("/patients/{patient_id}/visits")
def list_visits(patient_id: UUID, s: Session = Depends(db, scope="function")):
    require_member(s, patient_id)
    return svc.list_visits(s, patient_id)


@router.get("/visits/{visit_id}")
def get_visit(visit_id: UUID, s: Session = Depends(db, scope="function")):
    m = require_member(s, _patient_of(s, "visits", visit_id))
    return svc.visit_detail(s, visit_id, can_view_recordings=bool(m["can_view_recordings"]))


class SpeakerIn(BaseModel):
    label: str = Field(min_length=1, max_length=4)
    role: Literal["doctor", "patient", "family", "nurse", "other", "unknown"]
    name: str | None = Field(default=None, max_length=80)


class SpeakersIn(BaseModel):
    speakers: list[SpeakerIn] = Field(min_length=1, max_length=8)


@router.put("/visits/{visit_id}/speakers")
def put_speakers(visit_id: UUID, body: SpeakersIn, request: Request, s: Session = Depends(db, scope="function")):
    require_member(s, _patient_of(s, "visits", visit_id))
    svc.set_speakers(s, visit_id=visit_id, user_id=request.state.user_id, speakers=[x.model_dump() for x in body.speakers])
    return {"ok": True}


@router.post("/visits/{visit_id}/consents/{consent_id}/revoke")
def revoke_visit_consent(visit_id: UUID, consent_id: UUID, request: Request, s: Session = Depends(db, scope="function")):
    require_member(s, _patient_of(s, "visits", visit_id), can_manage=True)
    svc.revoke_consent(s, visit_id=visit_id, consent_id=consent_id, user_id=request.state.user_id)
    return {"ok": True}
