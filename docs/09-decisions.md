# Decisions and corrections

How to read this: **Accepted** means the owner confirmed it in chat. **Recommended** means Claude recommended it and the owner has not confirmed it yet. When the owner confirms, change the status here and nowhere else needs updating.

## Decision log

### D-01 Applicant and track
- **Status:** Accepted (Oct 24, 2026)
- **Decision:** The owner applies as an individual, so the project enters the Indie developer track. Theme: Build for Your World.
- **Why:** Meta's page describes the Indie track as for individual builders and students, judged on creativity, technical ambition and whether it works. The Startup track is for teams and is judged on production-grade execution.

### D-02 Scope
- **Status:** Recommended (extended by D-26 on Oct 26)
- **Decision:** Build only the spine in `05-scope.md`. Stretch only after the spine passes its tests. The rest is a roadmap slide.
- **Why:** About 13 features in about nine days, solo, is the main risk to "whether it works".

### D-03 Demo language
- **Status:** Recommended
- **Decision:** Make Hindi the headline demo language until Marathi transcription is tested on real clips. Keep Marathi as the stretch target.
- **Why:** Meta lists Hindi among its extensively verified languages. Marathi is not named in the sources checked, and there are no published accuracy numbers for Indian languages. Hinglish code-switching is claimed in general but not specifically demonstrated.
- **Consequences:** Test Marathi and Hinglish clips the first day API access exists. In the judge Q&A, say "Hindi validated by Meta, code-switching supported, and here is what we measured on Marathi" rather than "handles Indian languages".

### D-04 Database
- **Status:** Recommended
- **Decision:** PostgreSQL is the system of record, run in Docker locally and as the same engine in production. No dependency on Supabase or any hosted backend-as-a-service. Keep the setup portable and self-hostable.
- **Why:** The system has concurrent writers (webhooks, scheduler, voice sessions, web). It needs relational integrity, versioned records and an append-only audit trail. SQLite is fine for a prototype but forces a risky migration once real families depend on it.
- **Rules:**
  - Schema changes only through Alembic migrations. Never edit the database by hand.
  - Every table has a UUID primary key, `created_at`, `updated_at` and `created_by`. Rows tied to a patient carry `patient_id`.
  - Care plan items and allergies are versioned: a change creates a new version that supersedes the old one. Nothing is overwritten.
  - `audit_log` is append-only: the application role has no UPDATE or DELETE rights on it.
  - Row-level security by patient membership through `family_members`.
  - Encrypt sensitive free text and media at rest. Decide the field-level scheme before any real patient data is stored.
  - Nightly `pg_dump` to encrypted off-host storage, plus a restore drill before the demo.
  - Long memory is built from structured queries plus periodic summaries. `pgvector` can be added in the same database later.
- **Implemented:** the full schema is in `db/schema.sql` (37 tables, 1 view, 33 enum types), explained in `docs/16-database-design.md`, and checked by 69 automated tests (`db/tests/run_tests.sh`). It supersedes the 10-table sketch in `02-architecture.md`. New tables beyond that sketch include `audit_log`, `consents`, `visits`, `transcript_segments`, `drug_families`, `drug_substances`, `emergency_card_access_log`, `extractions`, `plan_changes`, `generated_outputs`, `output_sources`, `source_refs`, `model_calls`, `outbox` and `eval_runs`.

### D-05 File storage
- **Status:** Recommended
- **Decision:** S3-compatible object storage (MinIO locally). The database stores object keys and SHA-256 hashes only. Per-patient key prefixes, short-lived presigned URLs, encryption at rest.

### D-06 Authentication
- **Status:** Recommended
- **Decision:** Own auth in FastAPI with roles (patient, child, attendant, nurse), not a hosted auth product.
- **Open point:** Elder mode needs passwordless pairing (a device approved by a family member). Design this before building the Elder UI.

### D-07 Hosting
- **Status:** Open
- **Decision:** One Docker Compose file with the API, Postgres and MinIO, deployable to a single VPS or any host that runs Postgres. A local-only database cannot give judges a live link.
- **Open question for the owner:** own machine or a VPS?

### D-08 Text-to-speech
- **Status:** Recommended
- **Decision:** Use an external multilingual TTS service; Meta's lineup has none (Muse Voice Transcribe is speech to text only and does not synthesize speech).
- **How to choose:** Test Marathi and Hindi naturalness, latency, streaming support, cost and licence on identical medicine-instruction sentences before Oct 26.
- **Fallback:** a Hindi or English voice with the Marathi text shown on screen.

### D-09 Audio pipeline
- **Status:** Recommended
- **Decision:**
  - Convert WhatsApp Opus/OGG voice notes with ffmpeg to mono 16-bit PCM at 16 kHz (24 kHz is also accepted).
  - Use `keywords` (medicine names) and `languageBias` hints, which nudge but do not guarantee spelling.
  - Diarization mode labels speakers "A", "B" and so on, and handles non-overlapping speech only. Spark maps labels to doctor, patient and relative, and the family can correct the mapping.
  - Read back every medicine name and match it against the written prescription.

### D-10 WhatsApp
- **Status:** Recommended
- **Decision:** Try the WhatsApp Business Cloud API with a test number. Decision gate Oct 29. Otherwise use an in-app chat screen styled like a chat app (voice notes, bubbles) and present it honestly as a "WhatsApp-style preview" of the planned channel. Never present the mock as a live WhatsApp integration; say so in the demo, on screen and in the README. No WhatsApp logo or branding on the mock.
- **To verify in Meta's WhatsApp docs (not checked yet):** test-number recipient limits, media and voice note handling, and the rule that business-initiated messages outside the 24-hour window need approved templates. This affects reminders and the weekly briefing.

### D-11 Development models and cost
- **Status:** Recommended
- **Decision:** Use the Spark Contributor variants (`muse-spark-1.3-contributor`) for cheap development runs with synthetic data only, since Contributor mode lets Meta train on prompts. Use `muse-spark-1.3` for final tests and the demo. Check the real credit balance at the end of Day 4.

### D-12 Safety invariants and how they are enforced
- **Status:** Accepted (they come straight from the owner's plan)
- **Decision:** The eight invariants in `CLAUDE.md` are enforced in backend code and covered by tests:
  1. The agent has no tool that changes medicines, diagnoses or decides on hospital.
  2. "Asks first" tools return an awaiting-approval record from the backend.
  3. Allergy matching is a code function over the vetted list. A missing match is never displayed as "no risk".
  4. Allergy status is an enum of three states; an empty list cannot render as "none".
  5. Every output stores a source reference; output without one is rejected.
  6. Warning levels are read from stored patient instructions only.
  7. The Emergency Card renders only documented or confirmed fields and fails loudly if a field has no source.
  8. A recording cannot start without a stored consent record.
- **Tests:** the 30 adversarial prompts (dosing requests, "should I skip this", unclear speech, fake documents) run as an automated suite with a target of zero safety failures.

### D-13 Data policy
- **Status:** Accepted (from the owner's plan)
- **Decision:** Synthetic patient data only during the hackathon (patient: Ramesh). State clearly whether voice recordings are deleted after transcription.
- **Before any real patient data:** consent records, retention and deletion rules, encryption and access logs in place, and a review of India's data-protection law (the DPDP Act and its rules) by someone qualified.

### D-14 Long memory
- **Status:** Recommended
- **Decision:** Use structured queries plus periodic summaries by default. Spark's roughly 1M-token context is a backstop for rare long questions, not the default.

### D-15 Tooling and rules
- **Status:** Open (rules text pasted by the owner on Oct 26 and summarized in `18-rules-and-compliance.md`; the AI-coding-tools rule is still not stated)
- **Decision:** Claude Code is the main coding tool. Muse Code is optional.
- **To check when the Official Rules are published (before Oct 26):** any rules on using AI coding assistants, ownership of the work, and submission format (video length, repository, live link).

### D-16 Connectors
- **Status:** Accepted (Oct 24, 2026)
- **Decision:** No MCP connectors. Plain local tooling and a portable stack.

### D-17 Delivery surface
- **Status:** Accepted (Oct 24, 2026)
- **Decision:** CareSaathi is delivered as a website only. No native mobile app (no iOS, Android or app-store work). The site is mobile-first and responsive so it works in a phone browser, and may be installable as a PWA. WhatsApp stays an optional chat channel (D-10), not a separate app.
- **Why:** Judges need a live link. One web codebase is the fastest path for a solo build, and the browser covers microphone input, camera or file upload, and the printable Emergency Card.
- **Consequences:** HTTPS from the first deploy (microphone access requires it). Test on a real mid-range Android phone. Glasses stay a slide and concept clip.

### D-18 Confirmation policy for care plan changes
- **Status:** Recommended
- **Decision:** Changes read from a written document are applied automatically as a new version, shown as "from document, not yet confirmed by a family member". Changes heard in a doctor visit stay `pending` in `plan_changes` and are applied only after a named family member confirms (enforced by a database check). Allergies saved from family voice or text are stored only after the read-back is confirmed.
- **Why:** A written prescription is the authoritative source; a transcript is a model's reading of speech and needs a human check.

### D-19 Database roles and row-level security
- **Status:** Recommended (implemented and tested)
- **Decision:** Four roles: `caresaathi_app` (API, subject to row-level security), `caresaathi_auth` (login and invitations, `users` table only), `caresaathi_worker` (background jobs, bypasses row-level security, separate credentials and container), `caresaathi_readonly`. The API sets the user, paired device or public-card context per request with `SET LOCAL`.
- **Why:** The first draft left `users` and `model_calls` open to any signed-in session, which would have let one family list other users' emails and phones. Tests now cover this.

### D-20 Model output contracts and quote checking
- **Status:** Recommended
- **Decision:** Models return only `extract.v1` or `visit.v1` JSON (`docs/14-data-mapping.md`). Code validates the JSON and rejects any item whose quote is not found in the cited page or transcript segment. Warning-sign levels come from a keyword rule table applied to the quoted instruction; a model suggestion that disagrees sends the item to review and shows the more urgent level meanwhile.

### D-21 Output guard
- **Status:** Recommended
- **Decision:** Every generated output passes a code guard before display, speech or sending: source present, forbidden-claim phrases blocked (English, Hindi, Marathi lists), medicine names and numbers must match stored values, language must match, and warning levels must match the stored level. A blocked output is replaced by "Please ask the doctor or pharmacist about this." Full rules: `docs/15-api-spec.md`, section 7.

### D-22 Versioned, immutable clinical rows
- **Status:** Recommended (implemented and tested)
- **Decision:** `care_plan_items` and `allergies` are never edited. A change inserts a new version and flips `is_current` on the old one; a trigger blocks edits to content columns.

### D-23 Unresolved ingredients
- **Status:** Recommended (implemented and tested)
- **Decision:** An ingredient that cannot be matched exactly to the reference list is returned as `unresolved` and shown as "could not check this ingredient, please ask the pharmacist". An empty result means "no match found in the list" and is never shown as safe. No fuzzy matching in the allergy path.

### D-24 Banned-category framing
- **Status:** Recommended (owner to confirm with the organizers)
- **Decision:** CareSaathi is presented and built as a care-coordination and document-organization tool for family caregivers. It never gives medical or health advice. Every flag ends with a question for the doctor or pharmacist.
- **Why:** The pasted Official Rules list "AI medical or health advice" among the generic project types to avoid. Details and wording rules: `18-rules-and-compliance.md`.
- **Consequences:** No tool for diagnosis, symptom checking, dosing, substitutes, or judging whether a treatment is complete. Gaps between documents may be flagged; gaps in treatment may not. The owner emails the organizers and keeps the reply.

### D-25 Pre-hackathon work and the new-work rule
- **Status:** Recommended
- **Decision:** Keep the pre-kickoff files (documents, diagrams, `db/` schema and tests, Docker file, design canvas) in a clearly labeled baseline commit. Build the application, the Alembic migrations and every demo feature after kickoff. Disclose the baseline in the README. If the organizers say the schema cannot be reused, recreate it as migrations from the design documents.
- **Why:** The rules say everything presented must be built during Oct 26 to Nov 4 and that judges must be able to tell what is new. Unclear cases risk disqualification.
- **Consequences:** The demo shows only post-kickoff features. New tables for stretch features are added only as migrations (`16-database-design.md`, section 9).

### D-26 Feature additions and scope budget
- **Status:** Accepted (owner direction, Oct 26, 2026)
- **Decision:** Add S10 (omission catch) to the spine. Add Stretch A items A1 to A8 and the Stretch B list in `05-scope.md`, in priority order. The order is the cut order from the bottom. Expect to finish the first three or four. Anything not finished by G3 (end of Nov 1) becomes a roadmap slide.
- **Why:** The owner wants more helpful, stronger features. The research (`12-product-requirements.md`, section 13) supports omission detection, follow-up tracking and duplicate detection as real problems.
- **Consequences:** No Stretch A work starts until the spine passes its tests. Feature freeze at G3.

### D-27 Omission catch
- **Status:** Recommended
- **Decision:** Spine item S10. Code compares ingredient sets between the earlier plan and a new discharge summary. A medicine present before and absent now gets a flag, both sources and a drafted question. Incomplete documents raise no flags. The wording never says a medicine was stopped on purpose or should continue.
- **Why:** In one hospital study, 96% of medication discrepancies at care transitions were omissions, and patients with discrepancies had about twice the risk of an emergency visit (single site, 339 patients analysed). It is code-checkable and makes no clinical claim.

### D-28 Claim file (insurance organizer) boundaries
- **Status:** Recommended
- **Decision:** A7 organizes paperwork for a health-insurance claim. It tags documents by type, numbers them, checks them against an editable checklist, flags mismatches between documents (name, dates, amounts), and builds one indexed PDF. The checklist is generic guidance and is labeled "check your insurer's list". Deadline reminders use only dates the family enters from their own policy.
- **Never:** predict or imply approval, judge eligibility, give legal or financial advice, or fill in insurer-specific rules from memory.
- **Why:** Common documents named by two consumer sources include original itemized bills, discharge summary, prescriptions, investigation reports, identity proof and the claim form, with an accident report where relevant. Mismatches between documents are a stated cause of rejection. Settlement within 30 days of the last required document is reported as an IRDAI rule, but filing deadlines vary by insurer. Check the policy.
- **Minimal slice:** checklist plus indexed PDF (A7 lite).

### D-29 Two-reader check
- **Status:** Recommended
- **Decision:** For documents, run two independent readings (different prompts or settings) and compare the structured results in code. Fields that differ are marked for human review and are not applied silently.
- **Why:** It turns model uncertainty into a visible safety feature and gives a measurable result (flags per test set). Cost is roughly double per document, recorded in `model_calls`.

### D-30 Trust panel
- **Status:** Recommended
- **Decision:** A2 has three parts: a "show your work" view (model draft, guard changes, final output), a "try to break it" arena, and a safety scoreboard of the adversarial suite with failures included. The arena runs on synthetic data only, has rate limits, and every attempt passes the same output guard as normal use.

### D-31 Derived dates and quantities
- **Status:** Recommended
- **Decision:** Follow-up dates, run-out dates and claim deadlines are computed by code from stated text, quantities and dates. The model returns the quoted text and the number; it never does the date arithmetic. A named family member confirms each derived item. A derived item shows the inputs it came from.

### D-32 Synthetic data set
- **Status:** Recommended
- **Decision:** Ramesh (India) is the full set. Margaret (USA) and Hans (Germany) are smaller test sets. Documents, ground truth, traps, visit scripts and insurance papers are defined in `17-synthetic-data-plan.md`.

### D-33 Dropped ideas
- **Status:** Accepted (owner direction, Oct 26, 2026)
- **Decision:** Glasses mode is dropped, with no prototype and no concept clip. Robotic surgery and any clinical procedure are out. Flagging missing prescriptions or inappropriate medicines is out because it is clinical judgment.

### D-34 Background work starts after the request commits
- **Status:** Accepted (Oct 27, 2026)
- **Decision:** A job that reads rows written in the same request starts from SQLAlchemy's `after_commit` event (`db.run_after_commit`), on a background thread. Starting it as a framework background task raced the commit: the pipeline found no document and returned without a trace. Threads are the interim; the persistent APScheduler job store (D-10) replaces them for retries and restarts.

### D-35 Public Emergency Card lookup
- **Status:** Accepted (Oct 27, 2026)
- **Decision:** The public link is checked and logged inside one SECURITY DEFINER function (`app_resolve_emergency_card`, migration 0003), so the web process needs no role that can read every card. Expired, revoked and unknown tokens return the same 404 body and the page shows one neutral message; each attempt writes an access row. The card is then read through a session whose row-level security shows only one patient's documented facts. The visitor's address is hashed into the log from `X-Forwarded-For` and never used for a decision. **Open:** per-IP rate limiting is not built.

### D-36 Omission catch needs a whole document
- **Status:** Accepted (Oct 27, 2026)
- **Decision:** `documents.completeness` is `complete` only when a "page N of M" marker shows every page is present; a missing page or an empty page gives `incomplete`; no marker gives `unknown`. Only `complete` lets the omission catch raise flags (invariant 10). A named member with approval rights can set the value by hand, and that is audited. The catch runs for discharge summaries only. The drafted question reuses the `doctor_question` output type and the guard's omission wording list.

### D-37 Approved actions are recorded, not executed
- **Status:** Accepted (Oct 27, 2026)
- **Decision:** An "asks first" request is stored as `awaiting_approval`. A named member with approval rights moves it to `approved` or `refused`, and the database refuses any other way past `awaiting_approval`. No executor (sending a message, sharing a link) is connected yet, so the screens say nothing is sent; wire executors only behind this gate.

### D-38 Tests and object storage in this build
- **Status:** Accepted (Oct 27, 2026)
- **Decision:** API tests run against a scratch database (`caresaathi_test`) cloned from the dev schema, grants, policies and drug list inside the same Postgres container, and are skipped when Docker is not available. The baseline `db/tests/run_tests.sh` drops cluster-wide roles, so it runs only in a throwaway container. The `minio/minio` image could not be pulled on the dev machine, so uploads use the local storage adapter behind the same interface until an S3-compatible service is chosen.

### D-39 Visual identity: "evidence after dark"
- **Status:** Accepted (Oct 27, 2026)
- **Decision:** The interface is dark, with signal lime for verified and primary, coral for danger, amber for voice and ice for sources. Evidence (source sheets, the Emergency Card) stays white paper. Display type is Bricolage Grotesque, body is Atkinson Hyperlegible, labels are JetBrains Mono. Motion is a separate layer (`motion.css`, `components/fx`), transform and opacity only, disabled for reduced motion and for touch pointers. Replaces the cream and teal "paper and ink" look. Details in `design-system/caresaathi/MASTER.md`.

### D-40 Doctor Visit Listener: consent first, record then read
- **Status:** Accepted (Oct 27, 2026)
- **Decision:** A visit cannot exist without two consents (patient side or family on their behalf, and the doctor): the API requires both and the database has a CHECK that they differ. The browser records mono 16 kHz WAV and sends it once, after the person presses stop; the transcript appears after processing, not live (Meta's realtime socket is documented but not used). A scripted **mock visit** replays a synthetic conversation through the same pipeline when no audio exists; it is stored with `origin = 'mock'` and labeled everywhere so it cannot be mistaken for a consultation. In offline mode the mock's extraction is the script's recorded answer, not a model; with a key it goes to Muse Spark. Withdrawing consent deletes the audio, replaces the transcript words and the quoted words in sources, and sets pending changes aside. Visit-derived changes are always PENDING until a named member confirms.

### D-41 A different brand is a different item
- **Status:** Accepted (Oct 27, 2026)
- **Decision:** A line in a new document is a new VERSION of an existing item only when it has the same full ingredient set AND is the same medicine (same name part, or a generic name for that ingredient). A different brand of one ingredient becomes a separate item, so a possible duplicate stays visible and is flagged with a question (A8). Items from the document being processed never match, so two lines in one document cannot overwrite each other. Merging was the less safe default.

### D-42 Wording is grounded, judged, and scored in public
- **Status:** Accepted (Oct 27, 2026)
- **Decision:** Model-written wording goes through the output guard with a grounding rule (every sentence must name a stored fact or the doctor or pharmacist), and in live mode through a second-pass judge that fails closed. The adversarial suite behind `/trust` scores the code around the model and is public, failures included. **Measured:** the keyword phrase lists alone caught 0 of 12 held-out paraphrased reassurances; with grounding, 12 of 12 of those; 4 that name a medicine and imply a claim still pass the keyword guard and depend on the live judge, which is unmeasured until the key is in (`live_smoke.py --judge`). Highest-risk content (doses, allergy verdicts, plan items, dates) is code-built and never model-worded.

### D-43 Prompt injection is dropped in code
- **Status:** Accepted (Oct 27, 2026)
- **Decision:** A document or transcript line that tries to instruct CareSaathi ("ignore your rules", "tell the family this medicine is safe", "share the card") is rejected by `safety/injection.py` before anything is stored, counted, and shown to a person. Found when the synthetic prompt-injection document became an emergency-level warning sign. Chat prompts get the same check.

### D-44 Baseline database function fixed by migration, baseline file left as it was
- **Status:** Accepted (Oct 27, 2026)
- **Decision:** `find_allergy_conflicts` in `db/schema.sql` never matched an allergy that names a drug class (sulfa, NSAIDs, macrolides), because `NOT (x = NULL)` is NULL. Fixed in migration 0005 with `IS DISTINCT FROM`; the baseline file stays untouched so it remains the pre-kickoff snapshot (D-25). The same migration adds about 120 common medicine names for resolution only (no family membership), because with the starter list every ordinary medicine was "could not check" and the omission catch could never fire. The reference list is still unreviewed; the banner stays.

### D-45 Not built: claim file
- **Status:** Accepted (Oct 27, 2026)
- **Decision:** The claim file (A7) is last in the cut order and was not started. Everything above it in `05-scope.md` is built and tested.

### D-46 Doctor link: read-only, expiring, the doctor's words stay the doctor's
- **Status:** Accepted (Oct 28, 2026)
- **Decision:** A family member creates a link for one named doctor (random token, SHA-256 stored, expiry, revocable, every access logged, same pattern as the Emergency Card). The page shows only documented or confirmed facts and clearly marks unconfirmed items. The family's drafted question reaches the page only after a named member approves the `message_doctor_draft` action; the approved action is executed by posting to that link's thread. A doctor's reply is stored verbatim with the time and is never merged into the plan by itself: turning it into a change goes through the same pending-change approval as a visit (D-18). For the demo the doctor is a labeled fictional persona.

### D-47 Care crew: the model proposes steps, the code runs only registered ones
- **Status:** Accepted (Oct 28, 2026)
- **Decision:** The agent loop lives in `backend/app/agent/`. The trigger is a user goal or a schedule, never text from a document. Each turn the model returns one JSON step `{tool, input}` from a short list; code validates it, passes it through `gate_tool_call`, runs automatic tools itself, queues "asks first" tools as awaiting approval, and records every step in `agent_steps` for the live trace. Hard limit of 6 steps and one model call per step. Tools are read-only or draft-only: there is no tool for doses, diagnosis, hospital decisions or sending anything without approval. Offline mode follows a fixed scripted plan so tests and demos are repeatable.

### D-48 Label check reads printed text only; loose pills are refused
- **Status:** Accepted (Oct 28, 2026)
- **Decision:** Identifying a loose pill by shape, colour or markings is a clinical identification task with real harm if wrong, and it breaks D-24. The camera feature reads printed text from a strip, box, bottle or tube. Code compares the read ingredients and strength with the current plan and the allergy list, and the result is one of: matches (with the plan line and its source), not in the plan (with a question for the pharmacist), could not read. The model never says a medicine is correct or safe. No fine-tuned vision model exists in this project; Muse Spark vision is used for reading only.

### D-49 Picture schedule is built by code, with no generated images
- **Status:** Accepted (Oct 28, 2026)
- **Decision:** The elder-friendly daily card uses fixed sun and moon icons and the schedule text parsed by code from the plan (for example 1-0-1). Generated images of medicines could mislead, so Muse Image is not used. Unconfirmed items are marked, and the card shows its source and last-updated date.

### D-50 Spend guard on live model calls
- **Status:** Accepted (Oct 28, 2026)
- **Decision:** Every live Meta call is priced from its token counts (prices from dev.meta.ai, kept in config) and appended to a local ledger (`.storage/spend.jsonl`). Before each call the total, plus a baseline for spend before the ledger existed, is compared with `SPEND_LIMIT_USD` (default 3.50, inside the owner's $4 working budget). At the limit the call is refused before it reaches the network and the caller sees a model error; the judge then fails closed. The ledger is shared by the web app and the scripts. `backend/scripts/spend.py` prints it. Limitation: it is a local file, so a second server instance would keep its own count.

### D-51 A doctor's reply can become pending changes, never applied ones
- **Status:** Accepted (Oct 28, 2026)
- **Decision:** A member with approval rights can read a stored reply once with the visit reader. The result is PENDING plan changes (and undated follow-ups) whose source is a new kind, `doctor_message`, holding the doctor's exact words; the words are never filed as a family member's. Quotes must appear in the reply, as for visits. A named member confirms each change on the Overview, as for a visit (D-18). Migration 0010 adds the enum value, the link from a source to the stored reply, and read-once columns, each with a CHECK.

### D-52 Outcomes board: own the outcome, not the engagement
- **Status:** Accepted (Oct 31, 2026)
- **Decision:** Allergy flags and omission flags are tracked as questions. A question is answered only when a member with approval rights records the answer: either a stored doctor reply (copied word for word and linked to the reply) or a note typed by a named member who says who told them. Migration 0011 adds `question_answers` with one answer per flag and CHECKs on the source kind. Recording an answer marks the flag resolved, with the person's name; a flag closed by the older "settled" button without an answer is counted separately as "closed with no answer on record". The board shows counts, days open (computed from stored times) and follow-up and doctor-thread totals. It never judges an answer and never says anything is safe. Duplicate-ingredient questions are computed, not stored, and are not on the board yet.

### D-53 Positioning: pre-crisis, and used at trigger moments
- **Status:** Accepted (Oct 31, 2026)
- **Decision:** The pitch says CareSaathi aims to catch a mix-up between two papers early, before it becomes an emergency visit. The supporting fact is limited to what the source says: in one single-hospital retrospective study (PMC11654400, 339 patients), patients with a medication discrepancy had about twice the risk of an ED visit within a month (hazard ratio 2.13). We do not claim CareSaathi prevents emergency visits; it has not been measured. The product is used at forced events (a discharge, a visit, a new prescription, a refill, a follow-up), so daily engagement is not a goal and is not measured. Consent language may say scoped, revocable and logged; it does not claim to follow any national consent framework.

### D-54 Two-reader check: wired in, only when the first reader says a page was unclear
- **Status:** Accepted (Oct 31, 2026)
- **Decision:** When the first reading of a document reports unclear text (`unreadable`), a second, independent reading is made with a different instruction (do not skip a line because part of it is hard to read). Code compares the two (`safety/second_read.py`) on name, strength, schedule, duration and quantity. A medicine on which they differ, or that only one reader found, is stored in `second_reads` and is NOT applied; the document is marked for review. A member with approval rights sees both readings with the page line and chooses reading A, reading B or neither. Choosing a reading goes through the same confirmation code and audit trail as any plan change; the model never merges or picks. Clear pages never trigger a second read, so they pay nothing and change nothing. Measured on the live model (Oct 31): on the smudged-strength test page both readers returned 5 mg in the run we tried, so no disagreement appeared; the live model does not disagree on demand. The demo family therefore includes a scripted blurry page (fictional Losartan, "5 mg or 50 mg") read by scripted offline readers, labelled as such, so the check can be shown repeatably. The demo family now uses the offline reader for every document and the visit so the story is repeatable; real uploads use the live model.

### D-55 Live measurements are a committed report, shown on the Trust page
- **Status:** Accepted (Oct 31, 2026)
- **Decision:** `backend/scripts/live_report.py` runs the live model on the fictional test set (documents, allergy card, labels, a scripted visit, and the second-pass judge in both directions) and writes `data/live_results/latest.json`, keeping a short history of earlier runs. The Trust page shows that file, including every failing case, and lists what is not measured. Opening the page makes no model call. The report checks what reaches the care plan after the app's own repair and validation, and includes the allergy card, because an earlier version that checked medicines only passed while the allergy card was being lost.

### D-56 Tell the speech model the visit's language; Marathi speech is experimental
- **Status:** Accepted (Oct 31, 2026)
- **Decision:** The visit's language, which the family chooses before recording, is sent to Muse Voice Transcribe as `languageBias`. Measured on 20 real FLEURS clips per language: Hindi about 10% word errors either way; Marathi 57% without the hint and 23% with it. Marathi speech input is described as experimental in the pitch and on the Trust page, and the Marathi voice of the app (explanations read aloud) is separate from this measurement. The result and its limits (read speech, not a consultation) are in the committed live report and `docs/10-hackathon-facts.md`.

## Corrections ledger (changes to the original plan)

| Where | Original | Corrected |
| --- | --- | --- |
| Section 1, Track | Indie if solo; Startup if team | Indie (solo), D-01 |
| Section 7, Model mapping, "Cheap development runs" | Muse Glimmer or Spark Contributor tier | Muse Glimmer is an open-weight model for local and edge use, not part of the Model API. Use the Spark Contributor variant for API development, D-11 |
| Section 7, Tech stack | Postgres or Supabase | Plain PostgreSQL plus MinIO, D-04, D-05 |
| Sections 5.1 and 7, speaker separation | Separates doctor, patient, daughter | Labels are A, B, C; non-overlapping speech only; roles mapped by Spark and confirmed by family, D-09 |
| Section 14, judge Q&A "Why Meta's models?" | Handles Indian languages | Hindi validated by Meta; Marathi to be measured, D-03 |
| Section 11, Day 1 | Oct 26 is a full build day | Kickoff is 9:30 PM IST; Day 1 is mostly pre-work, `05-scope.md` |
| Section 16, cut order | Glasses L2, SAM check, schedule, cost help | Longer cut list in `05-scope.md` |
| Section 9, Budget | Reported prices and $150 credits | Treat as unconfirmed until the Official Rules and the account dashboard say so |
| `06-testing-demo.md`, demo plan | Recovery Timeline, WhatsApp scene and glasses in the 3-minute video | Replaced by the post-kickoff demo path in the updated file, D-26 and D-33 |
| Section 14, judge Q&A "Why Meta's models?" and "How does it make money?" | Unverified claims | Updated answers in `06-testing-demo.md` |
| Project framing | "AI care companion", "medical decisions" language | Care-coordination and document-organization wording, D-24 |
