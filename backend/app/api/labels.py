"""Label check endpoint (C4, D-48): one photo of printed packaging in, a plan comparison out. The photo is not stored."""
from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, File, Request, UploadFile
from sqlalchemy.orm import Session

from ..clients.storage import sniff_mime
from ..services import labelcheck
from .deps import db, require_member

router = APIRouter(tags=["label-check"])


@router.post("/patients/{patient_id}/label-check")
async def label_check(patient_id: UUID, request: Request, file: UploadFile = File(...), s: Session = Depends(db)):
    require_member(s, patient_id)
    data = await file.read(labelcheck.MAX_BYTES + 1)
    mime = (sniff_mime(data) or ("text/plain" if (file.content_type or "").startswith("text/plain") else "")) if data else ""
    return labelcheck.check_label(s, patient_id=patient_id, user_id=request.state.user_id, data=data, mime=mime, filename=file.filename or "label")
