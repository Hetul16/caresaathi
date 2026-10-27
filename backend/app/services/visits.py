"""The Doctor Visit Listener (S2).

Flow: consent on screen (both the patient side and the doctor), a recording or a labeled mock visit, transcription with
speaker labels, role mapping, extraction, validation, then PENDING changes for a named member to confirm.

Rules enforced here and in the database:
  - a visit cannot exist without two consents (visits.patient_consent_id and doctor_consent_id, and the API requires both);
  - every change cites the doctor's exact words, and a quote that is not in the cited segments is dropped (D-20);
  - a visit-derived change is only ever written as a PENDING plan_change; nothing enters the plan until a person confirms;
  - warning-sign levels come from the doctor's wording by rule, never from a model guess;
  - unclear speech goes to the family and is never guessed;
  - audio is deleted after transcription, and withdrawing consent removes the words too."""
from __future__ import annotations

import json
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import text
from sqlalchemy.orm import Session

from ..clients.models import AudioTurn, ModelClient, ModelError
from ..clients.storage import get_storage
from ..config import get_settings
from ..db import worker_session
from ..safety.followups import compute_due
from ..safety.validate import validate_visit
from .audit import timeline, write_audit
from .errors import ServiceError
from .plan import _j, ingredients_of, record_model_call, _item_key_match
from ..safety.normalize import normalize_medicine_name
from .readmodel import source_of

CONSENT_TEXT_VERSION = "visit-recording-v1"
_IST = timezone(timedelta(hours=5, minutes=30))


def today_ist() -> date:
    return datetime.now(_IST).date()


# ---- creating a visit (consent first) --------------------------------------------------------------------------------------
def create_visit(s: Session, *, patient_id: UUID, user_id: UUID, patient_consent: dict, doctor_consent: dict, doctor_name: str | None,
                 hospital: str | None, language_hint: str, origin: str) -> UUID:
    if patient_consent.get("agreed") is not True or doctor_consent.get("agreed") is not True:
        raise ServiceError(422, "consent-required", "Both the patient (or the family on their behalf) and the doctor must agree before anything is recorded")
    pname, dname = (patient_consent.get("given_by_name") or "").strip(), (doctor_consent.get("given_by_name") or "").strip()
    if not pname or not dname:
        raise ServiceError(422, "consent-required", "Please enter the names of the people who agreed")

    def consent(role: str, name: str, behalf: bool) -> UUID:
        return s.execute(text("""
            INSERT INTO consents (patient_id, consent_type, subject_role, given_by_user_id, given_by_name, on_behalf_of_patient,
                                  consent_text_version, evidence)
            VALUES (:p, 'visit_recording', CAST(:r AS speaker_role), :u, :n, :b, :v, CAST(:e AS jsonb)) RETURNING id"""),
            {"p": patient_id, "r": role, "u": user_id, "n": name, "b": behalf, "v": CONSENT_TEXT_VERSION,
             "e": json.dumps({"shown_on_screen": True, "origin": origin})}).scalar_one()

    pc = consent("patient", pname, bool(patient_consent.get("on_behalf_of_patient")))
    dc = consent("doctor", dname, False)
    vid = s.execute(text("""
        INSERT INTO visits (patient_id, started_by, patient_consent_id, doctor_consent_id, doctor_name, hospital, language_hint, origin)
        VALUES (:p, :u, :pc, :dc, :dn, :h, CAST(:l AS lang_code), :o) RETURNING id"""),
        {"p": patient_id, "u": user_id, "pc": pc, "dc": dc, "dn": (doctor_name or dname)[:120], "h": (hospital or None),
         "l": language_hint if language_hint in ("en", "hi", "mr") else "unknown", "o": origin}).scalar_one()
    write_audit(s, actor_type="user", actor_id=user_id, patient_id=patient_id, action="visit.consent_given", entity_type="visit", entity_id=vid,
                after={"origin": origin, "patient_side": pname, "doctor_side": dname, "version": CONSENT_TEXT_VERSION})
    timeline(s, patient_id=patient_id, event_type="visit_started", actor_type="user", actor_id=user_id,
             summary=("Mock visit started (a scripted conversation)" if origin == "mock" else "Visit recording started, with consent"),
             entity_type="visit", entity_id=vid)
    return vid


def load_script(script_id: str) -> dict:
    if not script_id.isalnum():
        raise ServiceError(404, "not-found", "No such script")
    f = Path(get_settings().synthetic_dir) / "ramesh" / "visits" / f"{script_id}.json"
    if not f.is_file():
        raise ServiceError(404, "not-found", "No such script")
    return json.loads(f.read_text(encoding="utf-8"))


def insert_segments(s: Session, patient_id: UUID, visit_id: UUID, turns: list[AudioTurn], language: str = "unknown") -> list[tuple[str, str, str]]:
    """Store the transcript and one visit_speakers row per label. Returns (segment id, speaker label, text) in order."""
    out: list[tuple[str, str, str]] = []
    for seq, t in enumerate(turns, 1):
        sid = s.execute(text("""
            INSERT INTO transcript_segments (patient_id, visit_id, turn_id, seq, speaker_label, start_ms, end_ms, body, language)
            VALUES (:p, :v, :t, :q, :l, :a, :b, :body, CAST(:lang AS lang_code)) RETURNING id"""),
            {"p": patient_id, "v": visit_id, "t": str(t.turn_id), "q": seq, "l": t.speaker, "a": t.start_ms, "b": max(t.end_ms, t.start_ms),
             "body": t.text.strip(), "lang": language if language in ("en", "hi", "mr") else "unknown"}).scalar_one()
        out.append((str(sid), t.speaker, t.text.strip()))
    for label in sorted({t.speaker for t in turns}):
        s.execute(text("INSERT INTO visit_speakers (patient_id, visit_id, speaker_label) VALUES (:p, :v, :l) ON CONFLICT DO NOTHING"),
                  {"p": patient_id, "v": visit_id, "l": label})
    return out


def add_mock_segments(s: Session, patient_id: UUID, visit_id: UUID, script: dict) -> None:
    turns = [AudioTurn(i, g["speaker"], g["start_ms"], g["end_ms"], g["text"]) for i, g in enumerate(script["segments"], 1)]
    insert_segments(s, patient_id, visit_id, turns, script.get("language", "unknown"))
    s.execute(text("UPDATE visits SET duration_ms = :d WHERE id = :v"), {"d": script["segments"][-1]["end_ms"], "v": visit_id})


# ---- processing --------------------------------------------------------------------------------------------------------------
def process_visit(visit_id: UUID, client: ModelClient | None = None) -> None:
    """Runs in the background after the upload or mock request commits."""
    from ..clients.models import get_model_client
    client = client or get_model_client()
    with worker_session() as s:
        v = s.execute(text("SELECT * FROM visits WHERE id = :v"), {"v": visit_id}).mappings().first()
        if v is None or v["status"] not in ("recording", "processing", "failed"):
            return
        s.execute(text("UPDATE visits SET status = 'processing', failure_note = NULL WHERE id = :v"), {"v": visit_id})
        patient_id: UUID = v["patient_id"]
        have_segments = s.execute(text("SELECT count(*) FROM transcript_segments WHERE visit_id = :v"), {"v": visit_id}).scalar_one() > 0

    try:
        if not have_segments:
            if not v["audio_storage_key"]:
                raise ModelError("There is no recording to transcribe.")
            turns, u0 = client.transcribe_audio(get_storage().get(v["audio_storage_key"]))
            if not turns:
                raise ModelError("No speech was found in the recording.")
            with worker_session() as s:
                record_model_call(s, patient_id, u0)
                insert_segments(s, patient_id, visit_id, turns, v["language_hint"])
        with worker_session() as s:
            rows = s.execute(text("SELECT id, speaker_label, body FROM transcript_segments WHERE visit_id = :v ORDER BY seq"), {"v": visit_id}).all()
        segments = [(str(r[0]), r[1], r[2]) for r in rows]
        raw, u1 = client.extract_visit(segments)
    except ModelError as e:
        with worker_session() as s:
            s.execute(text("UPDATE visits SET status = 'failed', failure_note = :n WHERE id = :v"), {"n": str(e)[:300], "v": visit_id})
            timeline(s, patient_id=patient_id, event_type="visit_failed", actor_type="system", actor_id=None,
                     summary="We could not process this visit. " + str(e)[:200], entity_type="visit", entity_id=visit_id)
        return

    validated = validate_visit(raw, {sid: body for sid, _l, body in segments})
    with worker_session() as s:
        mc = record_model_call(s, patient_id, u1)
        _apply_visit(s, v, validated, raw, mc, segments)
        if v["audio_storage_key"] and v["delete_audio_after_transcription"]:
            try:
                get_storage().delete(v["audio_storage_key"])
            except Exception:                           # a missing object is not a reason to fail the visit
                pass
            s.execute(text("UPDATE visits SET audio_deleted_at = now() WHERE id = :v"), {"v": visit_id})


def _visit_source(s: Session, patient_id: UUID, segment_id: str, quote: str) -> UUID:
    return s.execute(text("""INSERT INTO source_refs (patient_id, kind, segment_id, quote) VALUES (:p, 'visit_segment', :s, :q) RETURNING id"""),
                     {"p": patient_id, "s": segment_id, "q": quote.strip()}).scalar_one()


def _apply_visit(s: Session, v: dict, validated, raw: str, model_call_id: UUID, segments: list[tuple[str, str, str]]) -> None:
    patient_id, visit_id = v["patient_id"], v["id"]
    ext_status = "failed" if not validated.ok else ("needs_review" if (validated.review_items or validated.rejected_items) else "applied")
    ext_id = s.execute(text("""
        INSERT INTO extractions (patient_id, origin, visit_id, model_call_id, schema_version, raw_output, validated, validation_errors, status, applied_at)
        VALUES (:p, 'visit', :v, :mc, 'visit.v1', CAST(:r AS jsonb), :ok, CAST(:e AS jsonb), CAST(:st AS extraction_status),
                CASE WHEN :st = 'applied' THEN now() END) RETURNING id"""),
        {"p": patient_id, "v": visit_id, "mc": model_call_id, "r": raw if raw.strip().startswith("{") else '{"unparseable": true}', "ok": validated.ok,
         "e": _j(validated.errors + [{"type": "review", "item": i, "reason": r} for i, r in validated.review_items.items()]),
         "st": ext_status}).scalar_one()
    if not validated.ok:
        s.execute(text("UPDATE visits SET status = 'needs_review', ended_at = coalesce(ended_at, now()) WHERE id = :v"), {"v": visit_id})
        timeline(s, patient_id=patient_id, event_type="visit_failed", actor_type="system", actor_id=None,
                 summary="We could not read this visit into the plan. A person should listen to it.", entity_type="visit", entity_id=visit_id)
        return

    data = validated.data
    by_label = {r.label: r for r in data.speaker_roles}
    for label, r in by_label.items():
        s.execute(text("""UPDATE visit_speakers SET role = CAST(:r AS speaker_role), display_name = :n, mapped_by = 'model'
                          WHERE visit_id = :v AND speaker_label = :l AND confirmed_by IS NULL"""), {"r": r.role, "n": r.name, "v": visit_id, "l": label})
        s.execute(text("UPDATE transcript_segments SET mapped_role = CAST(:r AS speaker_role), mapped_by = 'model' WHERE visit_id = :v AND speaker_label = :l"),
                  {"r": r.role, "v": visit_id, "l": label})

    created = 0
    for i, item in enumerate(data.items):
        if i in validated.rejected_items or i in validated.review_items or item.change == "unchanged_mention":
            continue
        details = dict(item.details or {})
        ings = ingredients_of(item.kind, item.title, details) if item.kind == "medicine" else []
        ing_norm = frozenset(normalize_medicine_name(n) for n, _ in ings if normalize_medicine_name(n))
        match = _item_key_match(s, patient_id, item.kind, item.title, ing_norm, None)  # type: ignore[arg-type]
        ctype = item.change
        if ctype in ("changed", "stopped") and match is None:
            ctype = "new" if ctype == "changed" else "other"          # nothing to change or stop: show it as a note, never guess
        if ctype == "other":
            continue
        src = _visit_source(s, patient_id, item.source.segment_ids[0], item.source.quote)
        after = {"kind": item.kind, "title": item.title.strip(), "details": details}
        if item.kind == "warning_sign":
            after["alert_level"] = validated.alert_levels.get(i)
        s.execute(text("""
            INSERT INTO plan_changes (patient_id, extraction_id, change_type, item_key, before_state, after_state, source_ref_id,
                                      requires_confirmation, status)
            VALUES (:p, :e, CAST(:ct AS change_type), :k, CAST(:b AS jsonb), CAST(:a AS jsonb), :src, true, 'pending')"""),
            {"p": patient_id, "e": ext_id, "ct": ctype, "k": match["item_key"] if match else None,
             "b": _j({"title": match["title"], "details": match["details"]}) if match else None, "a": _j(after), "src": src})
        created += 1

    for i, al in enumerate(data.allergies_mentioned):
        if i in validated.rejected_allergies:
            continue
        src = _visit_source(s, patient_id, al.source.segment_ids[0], al.source.quote)
        s.execute(text("""
            INSERT INTO plan_changes (patient_id, extraction_id, change_type, after_state, source_ref_id, requires_confirmation, status)
            VALUES (:p, :e, 'allergy_added', CAST(:a AS jsonb), :src, true, 'pending')"""),
            {"p": patient_id, "e": ext_id, "a": _j({"substance": al.substance, "reaction": al.reaction, "stated_by": al.stated_by}), "src": src})
        created += 1

    anchor = v["started_at"].astimezone(_IST).date()
    follow = 0
    for i, fu in enumerate(data.follow_ups):
        if i in validated.rejected_follow_ups:
            continue
        src = _visit_source(s, patient_id, fu.source.segment_ids[0], fu.source.quote)
        s.execute(text("""
            INSERT INTO follow_ups (patient_id, source_ref_id, what, due_text, anchor_date, anchor_kind, due_date)
            VALUES (:p, :src, :w, :t, :ad, 'visit', :dd) ON CONFLICT DO NOTHING"""),
            {"p": patient_id, "src": src, "w": fu.what.strip(), "t": fu.due_text.strip(), "ad": anchor, "dd": compute_due(anchor, fu.due_text)})
        follow += 1

    needs = bool(data.unclear or validated.rejected_items or validated.review_items or validated.injection_lines)
    s.execute(text("UPDATE visits SET status = :st, ended_at = coalesce(ended_at, now()) WHERE id = :v"),
              {"st": "needs_review" if needs else "completed", "v": visit_id})
    parts = [f"{created} change{'s' if created != 1 else ''} waiting for you"]
    if follow:
        parts.append(f"{follow} follow-up{'s' if follow != 1 else ''}")
    if data.unclear:
        parts.append(f"{len(data.unclear)} unclear part{'s' if len(data.unclear) != 1 else ''} to check")
    if validated.injection_lines:
        parts.append(f"{validated.injection_lines} line{'s' if validated.injection_lines != 1 else ''} ignored")
    timeline(s, patient_id=patient_id, event_type="visit_processed", actor_type="system", actor_id=None,
             summary="Visit read: " + ", ".join(parts) + ".", entity_type="visit", entity_id=visit_id)
    write_audit(s, actor_type="system", actor_id=None, patient_id=patient_id, action="visit.processed", entity_type="visit", entity_id=visit_id,
                after={"changes": created, "follow_ups": follow, "unclear": len(data.unclear), "rejected": len(validated.rejected_items)})


# ---- reading a visit ---------------------------------------------------------------------------------------------------------
def visit_detail(s: Session, visit_id: UUID, *, can_view_recordings: bool) -> dict[str, Any]:
    v = s.execute(text("SELECT * FROM visits WHERE id = :v"), {"v": visit_id}).mappings().first()
    if v is None:
        raise ServiceError(404, "not-found", "Not found")
    speakers = s.execute(text("SELECT speaker_label, role, display_name, mapped_by, confirmed_at FROM visit_speakers WHERE visit_id = :v ORDER BY speaker_label"),
                         {"v": visit_id}).mappings().all()
    segs = []
    if can_view_recordings:
        segs = [{"id": str(r["id"]), "seq": r["seq"], "speaker": r["speaker_label"], "role": r["mapped_role"], "start_ms": r["start_ms"], "end_ms": r["end_ms"], "text": r["body"]}
                for r in s.execute(text("SELECT id, seq, speaker_label, mapped_role, start_ms, end_ms, body FROM transcript_segments WHERE visit_id = :v ORDER BY seq"),
                                   {"v": visit_id}).mappings().all()]
    ext = s.execute(text("SELECT id, raw_output FROM extractions WHERE visit_id = :v ORDER BY created_at DESC LIMIT 1"), {"v": visit_id}).mappings().first()
    unclear, changes = [], []
    if ext:
        raw = ext["raw_output"] or {}
        unclear = [{"note": u.get("note", ""), "segment_ids": u.get("segment_ids", [])} for u in raw.get("unclear", [])] if isinstance(raw, dict) else []
        for r in s.execute(text("""
            SELECT pc.id, pc.change_type, pc.status, pc.before_state, pc.after_state, sr.kind AS source_kind, sr.quote
            FROM plan_changes pc JOIN source_refs sr ON sr.id = pc.source_ref_id WHERE pc.extraction_id = :e ORDER BY pc.created_at"""), {"e": ext["id"]}).mappings():
            a, b = r["after_state"] or {}, r["before_state"] or {}
            changes.append({"id": str(r["id"]), "change_type": r["change_type"], "status": r["status"], "title": a.get("title") or a.get("substance") or b.get("title"),
                            "quote": r["quote"]})
    consents = [{"id": str(c["id"]), "role": c["subject_role"], "given_by": c["given_by_name"], "granted_at": c["granted_at"].isoformat(),
                 "revoked_at": c["revoked_at"].isoformat() if c["revoked_at"] else None}
                for c in s.execute(text("SELECT id, subject_role, given_by_name, granted_at, revoked_at FROM consents WHERE id IN (:a, :b)"),
                                   {"a": v["patient_consent_id"], "b": v["doctor_consent_id"]}).mappings()]
    follow = [dict(f) for f in s.execute(text("""
        SELECT f.what, f.due_text, f.due_date::text AS due_date, f.status FROM follow_ups f JOIN source_refs sr ON sr.id = f.source_ref_id
        JOIN transcript_segments ts ON ts.id = sr.segment_id WHERE ts.visit_id = :v"""), {"v": visit_id}).mappings()]
    return {"id": str(v["id"]), "status": v["status"], "origin": v["origin"], "doctor_name": v["doctor_name"], "hospital": v["hospital"],
            "language_hint": v["language_hint"], "started_at": v["started_at"].isoformat(), "duration_ms": v["duration_ms"],
            "audio_deleted": v["audio_deleted_at"] is not None, "failure_note": v["failure_note"],
            "speakers": [{"label": r["speaker_label"], "role": r["role"], "name": r["display_name"], "mapped_by": r["mapped_by"],
                          "confirmed": r["confirmed_at"] is not None} for r in speakers],
            "segments": segs, "transcript_hidden": not can_view_recordings, "unclear": unclear, "changes": changes, "follow_ups": follow, "consents": consents}


def set_speakers(s: Session, *, visit_id: UUID, user_id: UUID, speakers: list[dict]) -> None:
    v = s.execute(text("SELECT patient_id FROM visits WHERE id = :v"), {"v": visit_id}).mappings().first()
    if v is None:
        raise ServiceError(404, "not-found", "Not found")
    for sp in speakers:
        s.execute(text("""UPDATE visit_speakers SET role = CAST(:r AS speaker_role), display_name = :n, mapped_by = 'family',
                                                      confirmed_by = :u, confirmed_at = now()
                          WHERE visit_id = :v AND speaker_label = :l"""), {"r": sp["role"], "n": sp.get("name"), "u": user_id, "v": visit_id, "l": sp["label"]})
        s.execute(text("UPDATE transcript_segments SET mapped_role = CAST(:r AS speaker_role), mapped_by = 'family' WHERE visit_id = :v AND speaker_label = :l"),
                  {"r": sp["role"], "v": visit_id, "l": sp["label"]})
    write_audit(s, actor_type="user", actor_id=user_id, patient_id=v["patient_id"], action="visit.speakers_corrected", entity_type="visit", entity_id=visit_id,
                after={"speakers": [{"label": x["label"], "role": x["role"]} for x in speakers]})


def revoke_consent(s: Session, *, visit_id: UUID, consent_id: UUID, user_id: UUID) -> None:
    """Withdrawing consent removes what the recording produced: the audio, the transcript words, and the quoted words in
    every source that cited them. Pending changes from this visit are set aside; confirmed plan items keep a placeholder."""
    v = s.execute(text("SELECT * FROM visits WHERE id = :v"), {"v": visit_id}).mappings().first()
    if v is None or consent_id not in (v["patient_consent_id"], v["doctor_consent_id"]):
        raise ServiceError(404, "not-found", "Not found")
    s.execute(text("UPDATE consents SET revoked_at = coalesce(revoked_at, now()), revoked_by = :u WHERE id = :c"), {"u": user_id, "c": consent_id})
    if v["audio_storage_key"] and v["audio_deleted_at"] is None:
        try:
            get_storage().delete(v["audio_storage_key"])
        except Exception:
            pass
    s.execute(text("UPDATE visits SET status = 'cancelled', audio_deleted_at = coalesce(audio_deleted_at, now()) WHERE id = :v"), {"v": visit_id})
    s.execute(text("""UPDATE source_refs SET quote = '[removed: consent was withdrawn]'
                      WHERE segment_id IN (SELECT id FROM transcript_segments WHERE visit_id = :v)"""), {"v": visit_id})
    s.execute(text("UPDATE transcript_segments SET body = '[removed: consent was withdrawn]' WHERE visit_id = :v"), {"v": visit_id})
    s.execute(text("""UPDATE plan_changes SET status = 'superseded'
                      WHERE status = 'pending' AND extraction_id IN (SELECT id FROM extractions WHERE visit_id = :v)"""), {"v": visit_id})
    write_audit(s, actor_type="user", actor_id=user_id, patient_id=v["patient_id"], action="visit.consent_revoked", entity_type="visit", entity_id=visit_id,
                after={"consent_id": str(consent_id)})
    timeline(s, patient_id=v["patient_id"], event_type="visit_consent_revoked", actor_type="user", actor_id=user_id,
             summary="Consent for a visit recording was withdrawn. The recording and its words were removed.", entity_type="visit", entity_id=visit_id)


def list_visits(s: Session, patient_id: UUID) -> list[dict]:
    rows = s.execute(text("""SELECT id, status, origin, doctor_name, started_at, duration_ms FROM visits WHERE patient_id = :p ORDER BY started_at DESC"""),
                     {"p": patient_id}).mappings().all()
    return [{"id": str(r["id"]), "status": r["status"], "origin": r["origin"], "doctor_name": r["doctor_name"],
             "started_at": r["started_at"].isoformat(), "duration_ms": r["duration_ms"]} for r in rows]
