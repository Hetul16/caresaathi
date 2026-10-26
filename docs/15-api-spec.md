# API specification

The contract between the website, the WhatsApp channel and the backend. FastAPI will generate an OpenAPI document from the code; if that document and this file disagree, fix the code or this file in the same change.

Base path: `/api/v1`. All times are ISO 8601 in UTC. Request and response bodies are JSON unless stated.

## 1. Conventions

| Topic | Rule |
| --- | --- |
| Auth, family members | `Authorization: Bearer <access token>` (short-lived), refresh token in an HttpOnly cookie. Passwords hashed with Argon2id. |
| Auth, Elder device | `Authorization: Device <device token>`. The token is issued after a family member approves the pairing code, stored only as a hash. It can act only as the paired patient and only on the Elder endpoints marked below. |
| Auth, public Emergency Card | None. The random token in the URL is the credential. |
| Request context | After authentication the API opens a transaction and runs `SET LOCAL app.user_id = ...` (or `app.device_patient_id`, or `app.public_card_patient_id`). Row-level security does the rest. |
| Request id | Every response has `X-Request-Id`; the same id is written to `audit_log.request_id` and logs. |
| Idempotency | `POST` endpoints that create things accept `Idempotency-Key`. A repeat with the same key returns the first result. WhatsApp webhooks are deduplicated on `wa_message_id`. |
| Errors | RFC 9457 problem details: `{ "type", "title", "status", "detail", "request_id", "errors": [] }`. |
| Pagination | `?limit=50&cursor=...`; response `{ "items": [], "next_cursor": null }`. |
| Language | `Accept-Language: en \| hi \| mr` selects the language of generated text. Patients have a stored preference that wins for Elder mode. |
| Rate limits | Per user and per IP at the proxy. Stricter on `/auth/*` and the public card route. Limits to be tuned after load testing. |
| Uploads | Allowed types `image/jpeg`, `image/png`, `application/pdf`, audio `audio/webm`, `audio/ogg`, `audio/wav`, `audio/mp4`. Size limits to be set; content type is verified by file signature, not by the header. |
| Safety | Any response that contains generated text includes `output_id` and `sources[]`. A response without sources is a bug. |

## 2. Endpoints

Permission column: `A` automatic, `AF` ask first (the call creates an action awaiting approval instead of doing the thing), `AA` automatic alert. Role column: who may call it.

### Auth and members

| Method | Path | Role | Purpose |
| --- | --- | --- | --- |
| POST | `/auth/register` | public | Create a user (email or phone, password) |
| POST | `/auth/login` | public | Tokens |
| POST | `/auth/refresh` | cookie | New access token |
| POST | `/auth/logout` | user | Revoke the refresh token |
| POST | `/patients` | user | Create a patient and make the caller the first active member |
| GET | `/patients/{id}` | member, device | Patient summary |
| POST | `/patients/{id}/members` | member with `can_manage_members` | Invite a relative (creates an `invited` row) |
| PATCH | `/patients/{id}/members/{member_id}` | member with `can_manage_members` | Change role, language, approval right, or remove |
| POST | `/patients/{id}/devices/pair` | member | Create a pairing code for the patient's phone |
| POST | `/devices/claim` | public | The phone submits the pairing code and waits |
| POST | `/patients/{id}/devices/{device_id}/approve` | member with `can_approve` | Approve; the device receives its token |
| DELETE | `/patients/{id}/devices/{device_id}` | member | Revoke the device |

### Documents and care plan

| Method | Path | Role | Purpose |
| --- | --- | --- | --- |
| POST | `/patients/{id}/documents` | member, device | Upload a document (`multipart/form-data`). Returns `202` with the document id; extraction runs in the background |
| GET | `/patients/{id}/documents` | member | List documents and their status |
| GET | `/documents/{doc_id}` | member | Metadata and a short-lived signed URL for the file |
| GET | `/patients/{id}/care-plan` | member, device | Current care plan with sources and the effective allergy state |
| GET | `/care-plan-items/{item_key}/history` | member | All versions of one item |
| GET | `/patients/{id}/plan-changes?status=pending` | member | Changes waiting for a decision |
| POST | `/plan-changes/{id}/decision` | member with `can_approve` | `{ "decision": "confirm" \| "reject", "comment": "" }` |
| GET | `/patients/{id}/timeline` | member | Events, newest first |
| GET | `/patients/{id}/what-changed?since=...` | member | Diff report with explanations in the caller's language |

### Allergies

| Method | Path | Role | Purpose |
| --- | --- | --- | --- |
| GET | `/patients/{id}/allergies` | member, device | `{ "state": "listed \| no_known_allergies \| not_recorded", "items": [...] }` from `v_allergy_effective` |
| POST | `/patients/{id}/allergies` | member | Add a family-reported allergy. Requires `"confirmed": true` after the read-back. Triggers a re-check of current medicines |
| POST | `/allergies/{allergy_key}/versions` | member | Edit or deactivate (writes a new version, never overwrites) |
| GET | `/patients/{id}/allergy-conflicts?status=open` | member | Open conflicts with the flag text and the doctor question |
| POST | `/allergy-conflicts/{id}/acknowledge` | member | Mark seen. Only a person can do this |

### Visits

| Method | Path | Role | Purpose |
| --- | --- | --- | --- |
| POST | `/patients/{id}/visits` | member | Body holds both consents. Creates two `consents` rows and a `visits` row. Rejected without both |
| WS | `/patients/{id}/visits/{visit_id}/stream` | member | Audio in, live transcript out (section 4) |
| POST | `/visits/{visit_id}/finish` | member | Ends the recording and starts speaker mapping and extraction |
| GET | `/visits/{visit_id}` | member | Transcript with speakers, status, and extracted items |
| PUT | `/visits/{visit_id}/speakers` | member | Correct who is who |
| POST | `/visits/{visit_id}/consents/{consent_id}/revoke` | member | Revoke; triggers deletion rules |

### Agent, voice and chat

| Method | Path | Role | Purpose |
| --- | --- | --- | --- |
| POST | `/patients/{id}/agent/message` | member, device | `{ "text": "..." }` or multipart audio. Returns the reply, its `output_id`, `sources[]`, optional audio URL, and any `actions` that need approval |
| WS | `/patients/{id}/voice` | device, member | Push-to-talk or endpointed voice loop (section 5) |
| GET | `/patients/{id}/conversations/{conv_id}/messages` | member | Chat history |
| POST | `/outputs/{output_id}/speak` | member, device | "Repeat that" in the stored language; returns audio |
| GET | `/patients/{id}/warning-card` | member, device | Warning signs card with levels and emergency numbers |

### Approvals

| Method | Path | Role | Purpose |
| --- | --- | --- | --- |
| GET | `/patients/{id}/actions?status=awaiting_approval` | member with `can_approve` | The approvals screen |
| POST | `/actions/{id}/approve` | member with `can_approve` | Approve and run |
| POST | `/actions/{id}/refuse` | member with `can_approve` | Refuse |

### Reminders and schedule (stretch A)

| Method | Path | Role | Purpose |
| --- | --- | --- | --- |
| GET | `/patients/{id}/reminders` | member, device | Upcoming reminders |
| POST | `/reminders/{id}/respond` | member, device | `{ "response": "done" \| "not_yet" \| "snooze" }` |
| GET | `/patients/{id}/briefing/latest` | member | Weekly briefing |

### Emergency Card

| Method | Path | Role | Purpose |
| --- | --- | --- | --- |
| POST | `/patients/{id}/emergency-card` | member, device | Create a card and a new link. The full URL and QR are returned once. The token is stored only as a hash. `{ "expires_in_days": 30 }` optional |
| GET | `/patients/{id}/emergency-card` | member, device | Active cards (hint only), PDF and image URLs |
| POST | `/emergency-cards/{id}/revoke` | member | Turn a link off |
| GET | `/e/{token}` | public | Read-only live card. Neutral "link not available" page for expired, revoked or unknown tokens. Always writes an access log row |
| POST | `/emergency-cards/{id}/share` | member | `AF`: send the card to a named contact (approval required) |

### WhatsApp (if enabled)

| Method | Path | Role | Purpose |
| --- | --- | --- | --- |
| GET | `/whatsapp/webhook` | Meta | Verification challenge |
| POST | `/whatsapp/webhook` | Meta | Incoming messages and media. Signature verified (`X-Hub-Signature-256`), deduplicated on message id, mapped to a patient by the sender's phone number and `family_members` |

### Operations

| Method | Path | Role | Purpose |
| --- | --- | --- | --- |
| GET | `/healthz` | public | Process is up |
| GET | `/readyz` | public | Database and storage reachable |
| GET | `/patients/{id}/audit?limit=50` | member with `can_manage_members` | Who did what |

## 3. Key payloads

### 3.1 Upload response

```json
{
  "id": "5f0c...",
  "status": "uploaded",
  "doc_type": "prescription",
  "poll": "/api/v1/documents/5f0c..."
}
```

### 3.2 Care plan response (shape)

```json
{
  "patient": { "id": "...", "name": "Ramesh", "preferred_language": "mr" },
  "allergies": {
    "state": "listed",
    "items": [
      { "allergy_key": "...", "substance": "Penicillin", "reaction": "rash", "severity": "moderate",
        "source_type": "document", "source": { "document_id": "...", "page": 1, "quote": "Allergic to penicillin (rash)" } }
    ]
  },
  "open_conflicts": [
    { "id": "...", "match": "drug_family", "medicine": "Amoxicillin 500 mg",
      "flag": { "output_id": "...", "text": "..." },
      "doctor_question": { "output_id": "...", "text": "..." } }
  ],
  "items": [
    { "item_key": "...", "version": 2, "kind": "medicine", "status": "active", "title": "Amoxicillin 500 mg",
      "details": { "frequency_text": "1-0-1", "schedule": { "morning": 1, "noon": 0, "evening": 1, "night": null } },
      "confirmed": false,
      "source": { "kind": "document", "document_id": "...", "page": 1, "line_start": 3, "quote": "Tab Amoxicillin 500 mg 1-0-1 x 5 days" } }
  ],
  "pending_changes": 2,
  "last_updated_at": "2026-11-02T10:12:00Z"
}
```

`allergies.state` always comes from `v_allergy_effective`. The UI renders `not_recorded` as "Allergies not recorded", never as "none".

### 3.3 Agent reply

```json
{
  "output_id": "...",
  "language": "mr",
  "text": "...",
  "audio_url": "/api/v1/outputs/.../audio",
  "sources": [ { "source_ref_id": "...", "kind": "document", "quote": "..." } ],
  "actions": [ { "id": "...", "tool": "message_doctor_draft", "status": "awaiting_approval" } ],
  "guard": { "status": "pass" }
}
```

### 3.4 Problem response

```json
{
  "type": "https://caresaathi.example/problems/approval-required",
  "title": "Approval required",
  "status": 409,
  "detail": "This action needs approval from a family member with approval rights.",
  "request_id": "..."
}
```

Error types used by the website: `approval-required`, `consent-required`, `source-missing`, `guard-blocked`, `not-a-member`, `link-unavailable`, `validation-failed`, `model-unavailable`.

## 4. WebSocket: visit stream

Client sends binary audio frames (mono 16-bit PCM, 16 kHz) and JSON control messages. The server converts other formats first with ffmpeg.

| Direction | Message | Purpose |
| --- | --- | --- |
| client to server | `{"type":"start","language_hint":"hi","keywords":["amoxicillin","metformin"]}` | First message. Requires the visit to exist with both consents |
| client to server | binary audio | Continuous |
| client to server | `{"type":"stop"}` | End of recording |
| server to client | `{"type":"turn_start","turn_id":"t1"}` | Muse Voice Transcribe turn lifecycle |
| server to client | `{"type":"partial","turn_id":"t1","text":"..."}` | Cumulative partial text; replaces the previous partial |
| server to client | `{"type":"speaker","turn_id":"t1","label":"A"}` | Speaker label from diarization |
| server to client | `{"type":"final","turn_id":"t1","text":"...","start_ms":0,"end_ms":4200,"language":"hi"}` | Stored as a `transcript_segments` row |
| server to client | `{"type":"error","code":"asr_unavailable"}` | The client keeps recording locally and retries |

Events are correlated by `turn_id`, not by arrival order (Meta documents this). Diarization does not cover overlapping speech.

## 5. WebSocket: voice loop

| Direction | Message | Purpose |
| --- | --- | --- |
| client to server | `{"type":"start","mode":"push_to_talk \| endpointing","language_hint":"mr"}` | Opens a turn |
| client to server | binary audio | Speech |
| client to server | `{"type":"end_turn"}` | Push-to-talk release |
| server to client | `{"type":"transcript","text":"..."}` | What was heard, shown large, read back for medicine names |
| server to client | `{"type":"confirm","prompt":"Did you say metformin?","options":["yes","no"]}` | Read-back for risky words |
| server to client | `{"type":"reply","output_id":"...","text":"...","audio_url":"..."}` | Guarded reply with sources |
| server to client | `{"type":"approval_needed","action_id":"..."}` | The agent asked a family member |
| server to client | `{"type":"alert_sent","level":"emergency"}` | Family was alerted |

## 6. Agent tool registry

Permission is stored on the tool, not decided by the model. An unknown tool name is refused. The backend writes an `actions` row for every call.

| Tool | Permission | What it does |
| --- | --- | --- |
| `read_document`, `explain_item` | A | Read and explain a stored item with its source |
| `update_care_plan` | A | Apply document-derived changes (visit-derived ones wait for confirmation) |
| `compare_versions` | A | Run the diff engine |
| `set_reminder`, `schedule_checkin` | A | Create a reminder for a care plan item |
| `prepare_visit_summary`, `weekly_briefing` | A | Build a summary from stored data |
| `lookup_generic_prices` | A | Public price data only (stretch, may be cut) |
| `check_allergy_conflicts` | A | Run `find_allergy_conflicts`; on any match raise an urgent flag |
| `generate_emergency_card` | A | Create the card and link |
| `add_recovery_entry`, `compare_recovery_photos`, `describe_recovery_change` | A | Recovery Timeline (stretch B) |
| `alert_family_urgent` | AA | Notify family at once for a warning sign or a missed check-in |
| `record_allergy` | AF | Save only after a family member confirms the read-back |
| `send_recovery_bundle_to_doctor` | AF | Share photos and notes |
| `share_emergency_card`, `revoke_emergency_link` | AF | Send or switch off a link |
| `send_family_message`, `message_doctor_draft`, `assign_task`, `share_with_caregiver` | AF | Anything that involves other people |
| (none) | n/a | Changing medicines or doses, diagnosing, deciding on hospital. No tool exists |

## 7. Output guard

Every generated output passes the guard before it is shown, spoken or sent. A blocked output is stored with its reasons and replaced by a safe fallback ("Please ask the doctor or pharmacist about this.").

| Check | Rule |
| --- | --- |
| Source present | At least one `output_sources` row, unless the output is a plain chat reply marked exempt |
| Forbidden claims | Reject phrases such as "is safe", "safe to take", "no risk", "you can stop", "skip the", "increase the dose", "double the", "you have" followed by a diagnosis, "it is nothing", "nothing to worry about", "infected", "healing well", in English, Hindi and Marathi lists (lists kept in code and tested) |
| Medicine names | Every medicine name in the text must exist in the patient's care plan or the cited source |
| Numbers | Doses, frequencies and dates in the text must match the stored values |
| Language | Output language equals the requested language |
| Allergy wording | Flags may say "possible conflict, please confirm with the doctor or pharmacist". They may not say a medicine is or is not safe |
| Warning levels | The level shown equals the stored `alert_level` of the cited item |

The 30 adversarial prompts in `06-testing-demo.md` run against this guard and the agent as an automated suite.

## 8. Additions after kickoff (planned)

Built after Oct 26 (D-25). All endpoints follow the conventions in section 1 and pass the output guard in section 7.

| Method and path | Purpose | Who and approval |
| --- | --- | --- |
| GET `/patients/{id}/reconciliation` | Omission flags with both sources and the drafted question (S10) | Family members; read only |
| GET `/patients/{id}/follow-ups` | List follow-ups with computed dates and status | Family members |
| POST `/follow-ups/{id}/confirm` | Confirm or reject a derived follow-up | A named family member |
| GET `/patients/{id}/refills` | Run-out estimates with their inputs | Family members |
| POST `/patients/{id}/refills/start-date` | Confirm the start date used for an estimate | A named family member |
| GET `/care-plan-items/{id}/history` | Version history with quotes and sources (A3) | Family members |
| GET `/patients/{id}/fridge-sheet` | Printable A4 PDF in a chosen language (A4). Query parameter: `lang` | Family members |
| GET `/documents/{id}/second-read` | Both readings and the differing fields (A5) | Family members |
| POST `/second-reads/{id}/choose` | Choose a reading for a differing field | A named family member |
| GET `/patients/{id}/duplicates` | Same-ingredient flags (A8) | Family members |
| GET `/outputs/{id}/trace` | Model draft, guard report and final text (A2) | Family members |
| POST `/arena/prompt` | Judge's prompt, answered under the same guard, rate limited, synthetic data only | Public, rate limited |
| GET `/arena/scoreboard` | Adversarial suite results, failures included | Public |
| POST `/patients/{id}/claim-files` | Create a claim file for an admission | A named family member |
| GET `/claim-files/{id}` | Checklist state, tagged documents, mismatch flags | Family members |
| PUT `/claim-files/{id}/checklist` | Edit the checklist items | A named family member |
| POST `/claim-files/{id}/documents` | Link a document and its type | A named family member |
| PUT `/claim-files/{id}/policy` | Enter the policy deadlines by hand | A named family member |
| POST `/claim-files/{id}/build` | Build the indexed PDF. Returns a short-lived link | A named family member; audit row |

### 8.1 Claim file response (shape)

```json
{
  "id": "uuid",
  "label": "General guidance. Check your insurer's list.",
  "checklist": [
    {"item": "Itemized hospital bills", "state": "present", "documents": ["uuid"]},
    {"item": "Doctor's recommendation for admission", "state": "missing", "documents": []}
  ],
  "flags": [
    {"kind": "name_mismatch", "quotes": ["Ramesh Kulkarni", "Ramesh Kulkarny"], "documents": ["uuid", "uuid"]}
  ],
  "deadlines": [],
  "note": "No deadlines entered. This app does not know your insurer's deadlines."
}
```

No response from the claim file endpoints contains a statement about approval, eligibility or expected payout.

### 8.2 Output guard additions

| Check | Rule |
| --- | --- |
| Claim wording | Blocks phrases about approval, rejection chances, eligibility or "you will be paid" in English, Hindi and Marathi |
| Omission wording | Blocks "stopped on purpose", "safe to stop", "should continue", "should stop" |
| Refill wording | Blocks advice to take less, skip or stretch a supply |
| Arena | Same guard as normal use. A blocked answer is replaced by "Please ask the doctor or pharmacist about this." and counted on the scoreboard |
