# Technical architecture (original plan section 7)

> **Note (Oct 24, 2026):** Original text. The database, storage, auth, hosting, TTS and audio decisions in `09-decisions.md` (D-04 to D-11) override the Tech stack table. The Muse Glimmer row in Model mapping is corrected in the corrections ledger there.

## 7. Technical architecture

### Model mapping

| Feature | Model | How it is used |
| --- | --- | --- |
| Reading prescriptions, reports, discharge papers | Muse Spark 1.3 | Image or PDF in; structured care plan JSON out, with source references |
| Explaining in Marathi, Hindi, English | Muse Spark 1.3 | Plain-language rewrite from care plan fields |
| What changed since last time | Code + Muse Spark 1.3 | Code compares old and new JSON; Spark explains the difference |
| Agent brain and tool choice | Muse Spark 1.3 | Function calling with permission levels enforced in the backend |
| Long memory questions | Muse Spark 1.3 | Large context (about 1M tokens) holds a year of history when needed |
| Patient and caregiver voice input | Muse Voice Transcribe | Real-time streaming speech-to-text with code-switching |
| Doctor Visit Listener | Muse Voice Transcribe + Muse Spark 1.3 | Speaker separation, then instruction extraction |
| Voice replies | Separate TTS service | Meta’s current lineup has no text-to-speech model; choose a multilingual TTS that handles Marathi and Hindi |
| Allergy capture | Muse Spark 1.3 + Muse Voice Transcribe | Extract allergies from documents and visits; voice entries read back and confirmed |
| Allergy conflict check | Code + vetted drug-family list + Muse Spark 1.3 | Code finds matches; Spark only writes the plain-language flag and the question for the doctor |
| Emergency Card | Code + Muse Spark 1.3 | Code fills the card from care plan fields; Spark writes the short recent-changes summary; PDF and QR generated in code |
| Recovery Timeline photo comparison | SAM 3.1 + Muse Spark 1.3 | Isolate the wound/swelling area and describe visible change day to day |
| Recovery Timeline voice updates | Muse Voice Transcribe | Daily spoken updates, tagged by day |
| Recovery Timeline exercise videos | Muse Spark 1.3 (video input) | Compare a rehab video against the written exercise instructions |
| Medicine photo check (optional) | SAM 3.1 + Muse Spark 1.3 | Segment strips or bottles, read labels, match to plan |
| Cheap development runs | Muse Glimmer or Spark Contributor tier | Lower cost while building; Contributor tier allows Meta to train on prompts, so synthetic data only |
| Writing code faster | Muse Code | Agentic coding assistant for the whole build |

### Tech stack

| Layer | Choice | Why |
| --- | --- | --- |
| Frontend | React or Next.js, mobile-first web app (installable on phones) | Works on any phone, fast to build, easy live link for judges |
| Backend | Python with FastAPI | Simple, async, good for WebSockets and model calls |
| Database | PostgreSQL (or Supabase) | Structured care plan, history and users; Supabase adds auth and storage |
| File storage | Object storage (Supabase Storage or S3-compatible) | Document photos, PDFs, audio |
| Voice streaming | WebSocket from browser to backend to Muse Voice Transcribe | Live transcription with low delay |
| Scheduler | APScheduler or a cron worker | Reminders, check-ins, weekly briefings, follow-ups |
| Messaging | WhatsApp Business Cloud API webhook | Agent inside the family’s WhatsApp |
| Hosting | Any simple cloud host (for example Render, Railway, Vercel + a backend host) | Public live link for the demo |

### Data model (main tables)

| Table | Key fields |
| --- | --- |
| patients | id, name, age, preferred language, conditions, emergency contacts |
| family_members | id, patient_id, name, role (patient, child, attendant, nurse), language, phone, permissions |
| documents | id, patient_id, type, file link, uploaded by, date, extracted text |
| care_plan_items | id, patient_id, kind (medicine, test, appointment, warning sign, restriction), details, status, source document, source quote, version |
| allergies | id, patient_id, substance, reaction, severity, source type (document, visit, family-reported), source reference, confirmed by, date, active |
| allergy_status | patient_id, status (listed, no known allergies, not recorded), source, last checked |
| recovery_entries | id, patient_id, day_number, photo_url, photo_region (from SAM 3.1), voice_note_url, transcript, video_url, exercise_match, described_change, alert_level, source_instruction_id |
| emergency_cards | id, patient_id, link token, created at, expires at, revoked, PDF file link |
| events | id, patient_id, type (check-in, handoff, visit recording, reminder, alert), content, time, author |
| actions | id, patient_id, tool, input, permission level, status (done, awaiting approval, refused), approved by |
| schedules | id, patient_id, task, assigned to, due time, done |

### Agent tools

| Tool | Permission level |
| --- | --- |
| read_document, explain_item, update_care_plan, compare_versions | Automatic |
| set_reminder, schedule_checkin, prepare_visit_summary, weekly_briefing | Automatic |
| lookup_generic_prices (public data only) | Automatic |
| check_allergy_conflicts (runs on every new medicine) | Automatic, and raises an urgent family flag on a match |
| generate_emergency_card | Automatic |
| add_recovery_entry, compare_recovery_photos, describe_recovery_change | Automatic |
| send_recovery_bundle_to_doctor | Asks first |
| record_allergy (from family voice or text) | Asks first: a family member confirms before it is saved |
| share_emergency_card, revoke_emergency_link | Asks first |
| send_family_message, message_doctor_draft, assign_task, share_with_caregiver | Asks first |
| alert_family_urgent (warning sign or no response) | Automatic alert, because waiting could cause harm |
| Changing medicines or doses, diagnosing, deciding on hospital | Not a tool. The agent cannot do these. |

Important: permission levels are enforced in backend code, not only in the prompt. If the model calls a “asks first” tool, the backend stores it as awaiting approval and sends an approval request instead of acting.

### Main API endpoints

| Endpoint | Purpose |
| --- | --- |
| POST /documents | Upload a photo or PDF; triggers extraction and care plan update |
| WS /voice | Stream audio for live transcription and agent reply |
| POST /visits | Upload or stream a doctor visit recording |
| POST /agent/message | Text message to the agent from any family member |
| GET /care-plan/{patient} | Current care plan with sources |
| GET /timeline/{patient} | History of events and changes |
| GET /allergies/{patient}, POST /allergies | View allergies and status; add or confirm an allergy |
| POST /recovery/{patient}/entries | Add a day’s photo, voice note and optional video |
| GET /recovery/{patient}/timeline | Visual timeline with photos, transcripts and described change |
| POST /emergency-card/{patient} | Create the card as PDF and image, with a new QR link |
| GET /e/{token} | Public read-only card for hospital staff; no login, no patient details in the address |
| POST /actions/{id}/approve | Approve an “asks first” action |
| POST /whatsapp/webhook | Incoming WhatsApp messages and media |
