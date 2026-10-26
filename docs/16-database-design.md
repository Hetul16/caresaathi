# Database design

PostgreSQL 16 is the system of record (D-04). The executable definition is `db/schema.sql`; this file explains the design and the reasons. Diagrams: `diagrams/10-er-identity-sources.png`, `11-er-clinical.png`, `12-er-agent-ops.png`.

**Status:** the schema loads on a real PostgreSQL 16 and passes 69 automated checks (39 schema and logic tests, 30 row-level-security and privilege tests). Run them with `db/tests/run_tests.sh`.

## 1. Design rules

1. **Nothing is overwritten.** Care plan items and allergies are versioned. A change inserts a new version and flips the old one to `is_current = false`. A trigger blocks edits to the content columns of stored rows.
2. **Every fact has a source.** `care_plan_items.source_ref_id` and `allergies.source_ref_id` are `NOT NULL`. `source_refs` rows are checked by kind: a document source needs a document and a non-empty quote, a visit source needs a transcript segment and a quote.
3. **Safety rules live in the database as well as in the code.** If the application has a bug, the database still refuses the dangerous write.
4. **One patient, one boundary.** Every table with patient data has `patient_id`, and row-level security limits each session to the patients its user belongs to.
5. **Unknown is a value.** `allergy_status.not_recorded`, `date_missing`, and `medicine_ingredients.substance_id IS NULL` (unresolved) each carry the meaning "we do not know".
6. **The audit log is append-only.** No update, delete or truncate, enforced by both privileges and a trigger.
7. **Models are not trusted with the database.** The model returns JSON; deterministic code validates it and writes the rows.

## 2. Inventory (37 tables, 1 view, 33 enum types)

### Identity and access

| Table | Purpose | Key constraints |
| --- | --- | --- |
| `users` | People who log in (family, attendants, nurses) | Email or phone required, E.164 phone check. Row-level security: you see yourself and people who share a patient with you |
| `patients` | The cared-for person | `is_synthetic` defaults to true (D-13). Soft delete with `deleted_at` |
| `family_members` | Who may see which patient, and what they may do | `UNIQUE (patient_id, user_id)`. Flags `can_approve`, `can_manage_members`, `can_view_recordings`, `notify_urgent` |
| `devices` | A phone paired to one patient for Elder mode | A device token cannot exist without an approving family member |
| `care_providers` | Doctors and hospitals | Feeds the Emergency Card |

### Sources and recordings

| Table | Purpose | Key constraints |
| --- | --- | --- |
| `documents` | Uploaded prescriptions, reports and letters | `UNIQUE (patient_id, sha256)` blocks duplicate uploads. Object key, not the file, is stored here |
| `consents` | Who agreed to what, and when | Per subject (doctor, patient, family). Only revocation changes a row; deletes are not allowed |
| `visits` | A recorded doctor visit | `patient_consent_id` and `doctor_consent_id` are `NOT NULL` and must differ, so a visit cannot exist without both consents |
| `transcript_segments` | Diarized turns | Speaker label (`A`, `B`), mapped role, times, text. `UNIQUE (visit_id, turn_id)` |
| `visit_speakers` | Who each speaker label is | Model suggestion, corrected by the family |
| `messages`, `conversations` | Chat in the app or WhatsApp | `wa_message_id` unique for webhook deduplication |
| `source_refs` | Where a fact came from | Kind-specific checks. Doctor's exact words or document line is in `quote` |

### Clinical core

| Table | Purpose | Key constraints |
| --- | --- | --- |
| `extractions` | Raw and validated model output, before anything is applied | Keeps `raw_output` for audit and evaluation |
| `care_plan_items` | The living care plan | `item_key` + `version`. Unique current version per item. `warning_sign` requires an `alert_level`, and only warning signs may have one. Content immutable |
| `medicine_ingredients` | One row per active ingredient | `substance_id IS NULL` means "not in the reference list" |
| `plan_changes` | New, changed and stopped items, with before and after | If confirmation is required, `applied` needs `decided_by` and `decided_at` |
| `allergies` | Versioned allergies | Family-reported ones need `confirmed_by` and `confirmed_at`. Content immutable |
| `allergy_status` | The recorded state | `no_known_allergies` needs a source. The UI never reads this table directly |
| `v_allergy_effective` | The only allergy state the UI may read | Returns `listed` if any active allergy exists, `no_known_allergies` only with a source, otherwise `not_recorded` |
| `allergy_conflicts` | Flags for a new medicine | `unresolved` rows have no allergy; all others must name one |
| `drug_families`, `drug_substances`, `drug_family_members` | The vetted reference list | `reviewed` needs a reviewer and a date. Application roles cannot write to them |
| `generated_outputs`, `output_sources` | Every explanation, flag and reply, with its sources | A deferred trigger rejects a passed output with no source, except exempt plain chat replies |
| `recovery_entries` (stretch B) | Daily wound photo, voice note, alert | An alert level needs a source instruction |

### Agent, operations and trust

| Table | Purpose | Key constraints |
| --- | --- | --- |
| `agent_runs`, `actions` | Every tool call the agent makes | An `ask_first` action past `awaiting_approval` needs a named approver and a time |
| `reminders`, `timeline_events` | Schedule and history | Reminders carry an RRULE and a time zone |
| `outbox` | Messages to send, written in the same transaction as the change | `dedupe_key` unique, retry fields |
| `emergency_cards`, `emergency_card_access_log` | Links and who opened them | Only the SHA-256 hash of the token is stored. Access log is append-only |
| `audit_log` | Who did what | Append-only, optional hash chain (`prev_hash`, `row_hash`) |
| `model_calls` | Every model request: tokens, cost, latency | Row-level security follows the patient |
| `eval_runs`, `eval_results` | Evaluation results for the published accuracy numbers | |

The APScheduler job store creates its own table (`apscheduler_jobs`) on first start.

## 3. Safety invariants and where each is enforced

| # | Invariant | Database | Application | Test |
| --- | --- | --- | --- | --- |
| 1 | No tool changes medicines, diagnoses or decides on hospital | none (there is no such table or tool) | Tool registry has no such tool | Adversarial suite |
| 2 | Allergy state has three values; empty is never "none" | `allergy_state` enum, `v_allergy_effective`, check on `no_known_allergies` | UI reads the view only | `allergy:*` tests |
| 3 | Conflicts found in code from a vetted list | `find_allergy_conflicts()`, reference tables not writable by the app | Model only words the flag | `conflict:*` tests |
| 4 | "Ask first" tools wait for a named person | check constraint on `actions` | Permission gate stores `awaiting_approval` | `action:*` tests |
| 5 | Every output has a source | deferred trigger on `generated_outputs`, `NOT NULL source_ref_id` on items | Output guard | `output:*`, `plan:*` tests |
| 6 | Warning levels come from written instructions | `alert_level` check, `recovery_entries` check | Rule table assigns levels | `plan:*`, `recovery:*` tests |
| 7 | Emergency Card copies only documented facts | hash-only tokens, public read-only policies | Renderer fails loudly without a source | RLS public-card tests |
| 8 | No recording without consent | `NOT NULL` consent ids on `visits`, must differ | Consent screen | `visit:*` tests |

## 4. Allergy matching

`find_allergy_conflicts(item_id)` returns one row per finding, using only exact matches against the reference list:

| Result | Meaning | What happens |
| --- | --- | --- |
| `direct` | The new medicine's ingredient is the substance the patient is allergic to | Urgent flag to the family, question drafted for the doctor or pharmacist |
| `drug_family` | The ingredient shares a family with the allergy (or with the allergy's family) | Same |
| `unresolved` | An ingredient is not in the reference list, so it could not be checked | "Could not check this ingredient, please ask the pharmacist" |
| no rows | No match found in the reference list | **Never shown as safe.** The screen says only that no conflict was found in the list |

Limits to state honestly: the seed list in `db/seed_drug_families.sql` is a starter set, not clinically reviewed (`review_status = 'unreviewed'`); cross-reactivity between classes (for example penicillins and cephalosporins) is not modelled; brand names are only matched if listed. The app must show a "reference list not reviewed" banner until a doctor or pharmacist signs it off, and must not run checks for real patients before that.

## 5. Row-level security

| Role | Used by | Sees |
| --- | --- | --- |
| `caresaathi_app` | The API | Only patients its current user belongs to, through RLS. Cannot change or delete the audit log, consents, or the drug reference list |
| `caresaathi_auth` | Login, registration, invitations | The `users` table only |
| `caresaathi_worker` | Scheduler, outbox sender, pipelines | All patients (`BYPASSRLS`), because background jobs cross patients. Its credentials never go to the web process |
| `caresaathi_readonly` | Dashboards, evaluation reports | Read only, RLS applies |

Per request, the API runs `SET LOCAL app.user_id = '<uuid>'` (or `app.device_patient_id` for a paired phone, or `app.public_card_patient_id` after validating an Emergency Card token). Policies call `app_can_access_patient(patient_id)`, a `SECURITY DEFINER` function so it can read membership without recursion. The public card context gets read-only policies on only the tables the card prints. For UPDATE and DELETE, RLS reduces the visible rows to zero instead of raising an error; for INSERT it raises an error. The tests check both.

Gaps to be aware of:

- `drug_*` and `eval_*` tables have no patient data and no RLS.
- A bug that sets the wrong `app.user_id` defeats RLS. Keep context setting in one middleware and test it.
- `caresaathi_worker` is powerful. Run it in its own container with its own secret.

## 6. Versioning pattern

```sql
-- change a medicine: add version 2, retire version 1, in one transaction
INSERT INTO care_plan_items (patient_id, item_key, version, supersedes_id, kind, title, details, source_ref_id)
VALUES (:patient, :item_key, 2, :old_id, 'medicine', :title, :details, :source_ref);
UPDATE care_plan_items SET is_current = false WHERE id = :old_id;   -- allowed: only this flag may change
```

A partial unique index guarantees one current version per `item_key`. Reading "now" is `WHERE is_current`; reading history is by `item_key` ordered by `version`. Stopping a medicine is a new version with `status = 'stopped'`.

## 7. Operations

| Topic | Decision |
| --- | --- |
| Migrations | Alembic, one baseline from `db/schema.sql`, then incremental revisions. Never edit the database by hand |
| Backups | Nightly `pg_dump -Fc` to encrypted off-host storage; restore drill before the demo; point-in-time recovery is a post-hackathon goal |
| Encryption | Disk encryption on the host and encrypted backups from day one. Field-level encryption of free text is decided before any real patient data (D-04) |
| Connection pooling | One pool per role. Use `SET LOCAL` inside transactions so settings do not leak between requests on pooled connections |
| Time | `timestamptz` everywhere. Reminders store an IANA time zone |
| IDs | UUIDs (`gen_random_uuid()`). `audit_log` and card access log use identity bigints so they stay ordered |
| JSONB | Used for `details`, raw model output and snapshots. Shapes are validated in the application (`14-data-mapping.md`) |
| Long memory | Structured queries and periodic summaries first; `pgvector` can be added later in the same database (D-14) |
| Scale notes | Index list in `schema.sql` covers current-version lookups, due dates, pending approvals and open conflicts. Revisit with real load |

## 8. Running the database tests

```bash
# any reachable PostgreSQL 16 and a superuser
PGHOST=localhost PGUSER=postgres ./db/tests/run_tests.sh
```

The script rebuilds a scratch database, loads the schema, seed list and roles, runs `test_schema.sql`, then `test_rls.sh` as the real application roles. It exits non-zero if any case fails. Add a test whenever you add a constraint.

## 9. Planned additions (Alembic migrations after kickoff)

`db/schema.sql` is the pre-hackathon baseline (D-25). The tables below do not exist yet. They are added as migrations during the event, each with row-level security by patient, audit triggers where the existing pattern uses them, and a test per constraint.

| Table | Purpose | Key columns and constraints |
| --- | --- | --- |
| `reconciliation_flags` | Omission flags from S10 | `patient_id`, `previous_item_id`, `new_document_id`, `state` (open, asked, resolved), `question_output_id`. Unique per previous item and new document. Check: a flag needs a source for the previous item |
| `follow_ups` | Dated to-dos from visits and documents (A1) | `patient_id`, `source_ref_id`, `quote`, `due_text`, `due_date` (computed), `anchor_date`, `status` (pending, confirmed, done, dismissed), `confirmed_by`. Check: `confirmed_by` is required when `status` is not pending |
| `supply_records` | Quantity and start date for refills (A6) | `care_plan_item_id`, `quantity`, `quantity_unit`, `daily_units`, `start_date`, `estimated_run_out`, `confirmed_by`. Check: quantity is positive; an estimate needs `daily_units` |
| `second_reads` | Two-reader results (A5) | `document_id`, `reading_a`, `reading_b` (jsonb), `differing_fields`, `chosen_by`, `chosen_reading`. Check: a choice needs `chosen_by` |
| `policies` | Insurance policy facts entered by the family (A7) | `patient_id`, `insurer_name` (free text), `policy_label`, `intimation_deadline_days`, `submission_deadline_days`, all entered by hand and nullable. Synthetic values only |
| `claim_files` | One per admission (A7) | `patient_id`, `policy_id`, `admission_date`, `discharge_date`, `accident_related`, `state`, `built_object_key`, `built_sha256` |
| `claim_checklist_items` | Editable checklist (A7) | `claim_file_id`, `label`, `matches_document_type`, `required`, `sort_order` |
| `claim_documents` | Documents in the claim file (A7) | `claim_file_id`, `document_id`, `document_type`, `sequence_no`. Unique `sequence_no` per claim file |

Changes to existing tables:

- `generated_outputs` gains `draft_text` and `guard_report` (jsonb) for the trust panel (A2).
- `documents` gains a `completeness` field (`complete`, `incomplete`, `unknown`) used by the omission catch.
- `document_type` enum gains the values in `14-data-mapping.md`, section 14.1.
- `eval_runs` is reused for the adversarial scoreboard.

New tests (names): `omit:*`, `follow:*`, `refill:*`, `second:*`, `claim:*`, `dup:*`, `trace:*`.
