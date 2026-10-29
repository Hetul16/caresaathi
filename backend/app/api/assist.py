"""Explanations and chat: things the family or the patient asks CareSaathi to read back."""
from __future__ import annotations

from typing import Literal
from uuid import UUID

from fastapi import APIRouter, Depends, File, Request, UploadFile
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from ..clients.models import ModelError, get_model_client
from ..safety.audio import AudioRejected, check_wav
from ..services import chat as chat_svc
from ..services import explain as explain_svc
from .deps import db, problem, require_member

router = APIRouter(tags=["assist"])


class ExplainIn(BaseModel):
    item_key: UUID
    language: Literal["en", "hi", "mr"] = "en"


@router.post("/patients/{patient_id}/explain")
def explain(patient_id: UUID, body: ExplainIn, request: Request, s: Session = Depends(db, scope="function")):
    require_member(s, patient_id)
    return explain_svc.explain_item(s, patient_id=patient_id, item_key=body.item_key, language=body.language,
                                    user_id=request.state.user_id, client=get_model_client())


class ChatIn(BaseModel):
    message: str = Field(min_length=1, max_length=1000)
    language: Literal["en", "hi", "mr"] = "en"


@router.post("/patients/{patient_id}/chat")
def chat(patient_id: UUID, body: ChatIn, request: Request, s: Session = Depends(db, scope="function")):
    require_member(s, patient_id)
    return chat_svc.answer(s, patient_id=patient_id, user_id=request.state.user_id, message=body.message.strip(), language=body.language)


@router.get("/patients/{patient_id}/chat")
def chat_history(patient_id: UUID, request: Request, s: Session = Depends(db, scope="function")):
    require_member(s, patient_id)
    return chat_svc.history(s, patient_id, request.state.user_id)


@router.post("/patients/{patient_id}/chat/voice")
async def chat_voice(patient_id: UUID, request: Request, language: Literal["en", "hi", "mr"] = "en", file: UploadFile = File(...), s: Session = Depends(db, scope="function")):
    """One spoken question (a short WAV). It is transcribed by Muse Voice Transcribe, then answered exactly like typed text."""
    require_member(s, patient_id)
    data = await file.read(8 * 1024 * 1024)
    try:
        check_wav(data)
    except AudioRejected as e:
        raise problem(422, "audio-rejected", str(e)) from e
    try:
        turns, _usage = get_model_client().transcribe_audio(data)
    except ModelError as e:
        raise problem(503, "voice-unavailable", "Voice questions need the live model", str(e)) from e
    spoken = " ".join(t.text for t in turns).strip()
    if not spoken:
        raise problem(422, "no-speech", "We did not hear anything. Please try again.")
    out = chat_svc.answer(s, patient_id=patient_id, user_id=request.state.user_id, message=spoken[:1000], language=language)
    return {**out, "heard": spoken}
