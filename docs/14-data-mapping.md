# Data mapping

How data moves from raw inputs, through model output, into tables, and out to the screen. This is the contract between the extraction prompts, the validators, the database and the UI. If a field is not in this file, it does not exist.

Companion files: `db/schema.sql` (tables), `16-database-design.md` (why), `15-api-spec.md` (endpoints).

## 1. Principles

1. **Models propose, code decides.** Model output is parsed into a fixed JSON contract, validated, then written by deterministic code. A model never writes to the database directly.
2. **Every fact carries a source.** A source is a document page and line with the quoted text, a transcript segment with the doctor's exact words, a family statement, or a named system rule. No source, no row.
3. **Quotes are checked.** Every `quote` the model returns must appear (after whitespace and case normalization) in the page text or transcript segment it points to. If not, the item is dropped to `needs_review`.
4. **Unknown stays unknown.** A missing date, dose or allergy statement is stored as missing (`date_missing`, `not_recorded`), never guessed and never defaulted to "none".
5. **Untrusted input.** Document text and transcripts are data, never instructions. They are passed to the model inside a delimited block and the model's only output channel is the JSON contract.

## 2. End-to-end flow of one document

| Step | Input | Process | Output | Written to |
| --- | --- | --- | --- | --- |
| 1 | Photo or PDF | Validate type and size, hash with SHA-256, store the original | Object key, hash | `documents` (status `uploaded`), object storage |
| 2 | Stored file | Muse Spark 1.3 reads it with the extraction prompt and `extract.v1` contract | Raw JSON | `extractions.raw_output`, `model_calls` |
| 3 | Raw JSON | Schema validation, quote verification, date and unit normalization | Validated items or errors | `extractions.validated`, `validation_errors` |
| 4 | Validated items | Create `source_refs` (document, page, lines, quote) | Source ids | `source_refs` |
| 5 | Items | Diff against current care plan items with the same normalized key | `new`, `changed`, `stopped` | `plan_changes` |
| 6 | New or changed medicines | Resolve ingredients to the reference list | Ingredient rows | `medicine_ingredients` |
| 7 | New or changed medicines | `find_allergy_conflicts(item_id)` | Matches or none | `allergy_conflicts` (open) |
| 8 | Document-derived changes | Apply as new versions (visit-derived changes wait for confirmation) | New current versions | `care_plan_items`, old rows `is_current = false` |
| 9 | Changes and conflicts | Spark words the explanation; output guard checks it | Text in the family's language | `generated_outputs`, `output_sources` |
| 10 | Everything above | Notify and record | Outbox rows, audit rows, timeline events | `outbox`, `audit_log`, `timeline_events` |

## 3. Extraction contract `extract.v1` (documents)

The model returns exactly this shape. Anything else fails validation.

```json
{
  "schema_version": "extract.v1",
  "document": {
    "doc_type": "prescription | lab_report | discharge_summary | specialist_letter | imaging_report | other",
    "doc_date": "YYYY-MM-DD or null",
    "issuer": "string or null",
    "language": "en | hi | mr | mixed"
  },
  "items": [
    {
      "kind": "medicine | condition | test | appointment | warning_sign | restriction | instruction | result",
      "title": "short human title",
      "details": { "...depends on kind, see section 4..." },
      "source": { "page": 1, "line_start": 3, "line_end": 3, "quote": "exact text from the page" },
      "confidence": 0.0
    }
  ],
  "allergy_statement": "listed | none_stated | not_mentioned",
  "allergies": [
    {
      "substance": "Penicillin",
      "reaction": "rash or null",
      "severity": "mild | moderate | severe | unknown",
      "source": { "page": 1, "line_start": 9, "line_end": 9, "quote": "Allergic to penicillin (rash)" }
    }
  ],
  "providers": [ { "name": "", "specialty": "", "hospital": "", "phone": "" } ],
  "unreadable": [ { "page": 2, "note": "handwriting unclear near medicine list" } ]
}
```

Rules:

- `allergy_statement = "none_stated"` only when the page literally says no known allergies (or equivalent). If the page says nothing, it is `not_mentioned`, which maps to **no change** to `allergy_status`.
- `confidence` below 0.6, or any item in `unreadable`, sets the document to `needs_review` and shows the family an "unclear, please check" prompt.
- A second pass is not used to "fix" low confidence by guessing. The family fixes it.

## 4. `details` shape by item kind

`details` is stored as `care_plan_items.details` (JSONB) and validated in the application before every write.

| Kind | Fields | Notes |
| --- | --- | --- |
| `medicine` | `ingredients[] {name, strength}`, `form`, `dose_text`, `frequency_text`, `schedule {morning, noon, evening, night}`, `duration_days`, `start_date`, `end_date`, `route`, `with_food`, `indication`, `instructions_text` | `dose_text` and `frequency_text` are copied as written. `schedule` is derived by code from patterns like `1-0-1` (section 6) and left null if not parseable. |
| `condition` | `name`, `status_text`, `since` | No automatic coding. |
| `test` | `test_name`, `due_date`, `fasting`, `reason` | A missing `due_date` sets `care_plan_items.date_missing = true`. |
| `appointment` | `with_name`, `when`, `purpose`, `location` | `when` null sets `date_missing`. |
| `warning_sign` | `description`, `action_text`, `level_basis_quote` | The level is stored in the `alert_level` column, see section 5. |
| `restriction` | `description`, `category` (diet, activity, medicine, other), `until` | |
| `instruction` | `text` | General advice from the doctor. |
| `result` | `test_name`, `value`, `unit`, `reference_range`, `flag` (low, normal, high, unknown), `result_date` | Copied as written. The app never interprets whether a value is good or bad. |

Columns lifted out of `details` for querying: `title`, `due_at`, `date_missing`, `alert_level`. Medicine ingredients are also split into `medicine_ingredients`.

## 5. Warning-sign levels

The level shown to the family comes only from the patient's own written instruction.

| Wording in the quoted instruction (examples) | `alert_level` |
| --- | --- |
| "go to the emergency", "call an ambulance", "immediately", "come to casualty" | `emergency` |
| "call the clinic", "contact your doctor", "inform the doctor", "report to OPD" | `call_doctor_today` |
| "keep an eye on", "monitor", "note if", "watch for" | `watch` |

- A keyword rule table in code assigns the level from `level_basis_quote`. The model may suggest a level, but if its suggestion differs from the rule result, the item goes to `needs_review` and the more urgent level is shown until the family confirms.
- A warning sign without a level-bearing quote cannot be saved (database check: `kind = 'warning_sign'` requires `alert_level`).
- The Recovery Timeline (stretch) may raise an alert only by pointing at one of these stored items (`recovery_entries.source_item_id`).

## 6. Normalization rules

| Field | Rule |
| --- | --- |
| Medicine name | Lowercase, trim, strip dosage form words (tab, cap, syp, inj) and punctuation, collapse spaces. Brand names are matched against `drug_substances.brand_names` and `synonyms`. The original text is always kept in `ingredient_raw`. |
| Ingredient resolution | Exact match on `substance_normalized`, then `synonyms`, then `brand_names`. No fuzzy matching in the allergy path. No match means `substance_id = NULL`, which the conflict finder returns as `unresolved`. |
| Combination products | Split into one `medicine_ingredients` row per ingredient ("amoxicillin + clavulanic acid" gives two). |
| Indian dosing notation | `1-0-1` means morning 1, noon 0, evening 1 (night null). `1-1-1-1` fills all four slots. `0-0-1` is night only. `SOS` and `PRN` set `schedule` null and keep the text. Anything else: `schedule` null, text preserved. |
| Dates | Indian documents use day first. Parse `dd/mm/yyyy` and `dd-mm-yyyy` as day first. If day and month are both 12 or less and the document gives no other cue, flag `needs_review` instead of guessing. Store as ISO dates. |
| Time zone | Store `timestamptz` in UTC. Reminders carry `timezone` (default `Asia/Kolkata`) and are evaluated in it. |
| Units | Keep the unit exactly as written (`mg`, `mcg`, `ml`, `IU`). No conversion. |
| Language codes | Store `en`, `hi`, `mr` for pure language, `mixed` for code-switched speech, `unknown` when not detected. UI and explanation language is `pref_lang` (`en`, `hi`, `mr`). |
| Phone numbers | E.164 (`+91...`). |
| Person names | Stored as given. No splitting into first and last name. |

## 7. Visit extraction contract `visit.v1`

Input is the diarized transcript, one segment per turn with a database id. Output must cite segment ids.

```json
{
  "schema_version": "visit.v1",
  "speaker_roles": [ { "label": "A", "role": "doctor | patient | family | nurse | other | unknown", "name": "optional" } ],
  "items": [
    {
      "kind": "medicine | test | appointment | warning_sign | restriction | instruction | condition",
      "change": "new | changed | stopped | unchanged_mention",
      "title": "",
      "details": { "...same shapes as section 4..." },
      "source": { "segment_ids": ["uuid"], "quote": "the doctor's exact words" },
      "confidence": 0.0
    }
  ],
  "allergies_mentioned": [
    { "substance": "", "reaction": "", "stated_by": "doctor | patient | family", "source": { "segment_ids": ["uuid"], "quote": "" } }
  ],
  "unclear": [ { "segment_ids": ["uuid"], "note": "overlapping speech" } ]
}
```

Rules:

- Items whose `quote` is not a substring of the cited segments (normalized) are rejected.
- Visit-derived changes are written as `plan_changes` with `requires_confirmation = true` and `status = 'pending'`. They become care plan versions only after a family member confirms.
- Speaker labels `A`, `B` and so on come from Muse Voice Transcribe. Role mapping is a model suggestion stored with `mapped_by = 'model'`, replaced by `family` after the family corrects it.
- Overlapping speech is not diarized by the model (Meta documents this limit). Segments the model flags as unclear are shown to the family, not guessed.

## 8. Field-level mapping: extraction output to database

| Contract field | Table.column | Transform |
| --- | --- | --- |
| `document.doc_type` | `documents.doc_type` | Enum cast |
| `document.doc_date` | `documents.doc_date` | ISO date |
| `document.language` | `documents.language` | `lang_code` |
| `items[].kind` | `care_plan_items.kind` | Enum cast |
| `items[].title` | `care_plan_items.title` | Trim |
| `items[].details` | `care_plan_items.details` | Validated JSON per kind |
| `items[].details.ingredients[]` | `medicine_ingredients.*` | One row each, normalized, resolved |
| `items[].details.due_date` or `when` | `care_plan_items.due_at`, `date_missing` | UTC, `date_missing = true` if absent |
| warning sign level | `care_plan_items.alert_level` | Rule table, section 5 |
| `items[].source.*` | `source_refs.page`, `line_start`, `line_end`, `quote`, `document_id` | One row per item |
| `allergy_statement` | `allergy_status.state` | `listed` is implied by rows; `none_stated` gives `no_known_allergies` with that source; `not_mentioned` changes nothing |
| `allergies[]` | `allergies.*` | `source_type = 'document'`; `substance_id` and `family_id` resolved by exact match |
| `providers[]` | `care_providers.*` | Upsert by name and hospital |
| `unreadable[]` | `extractions.validation_errors` | Shown to the family |
| whole response | `extractions.raw_output` | Stored as returned |
| model usage | `model_calls.*` | Tokens, latency, cost |

Visit equivalents: `items[].source.segment_ids` points to `transcript_segments.id`, the segment becomes `source_refs.segment_id`, and the quote becomes `source_refs.quote`. Allergies from a visit use `source_type = 'visit'`.

## 9. Care plan to Emergency Card

The card is built by code from current rows. The model writes only the short "recent changes" summary, and that summary goes through the output guard.

| Card section | Source | Rule |
| --- | --- | --- |
| Patient (name, age, language, contacts) | `patients`, `family_members`, `users` | Age from `date_of_birth`. Contacts are members with `notify_urgent = true`. |
| Allergies (first after name) | `v_allergy_effective`, `allergies` | Show "Allergies: none known (per document)", "Allergies: not recorded" or the list with reaction and source. The view makes an empty list read "not recorded". |
| Conditions | `care_plan_items` kind `condition`, current | Copied as written. |
| Current medicines | `care_plan_items` kind `medicine`, current, status `active` | Name, strength and schedule as written, with the document date. |
| Recent changes (30 days) | `plan_changes` status `applied` | Short summary, guarded. |
| Recent results | `care_plan_items` kind `result`, latest per test | Value, unit, date as written. |
| Regular doctors | `care_providers` | Name, hospital, phone. |
| Trust details | `emergency_cards`, plan timestamps | "Last updated", and "verify with patient or family". If the plan is older than a set number of days, show a visible out-of-date warning. |

The card renderer fails loudly if any item it prints has no source row.

## 10. API payload to database mapping (main endpoints)

| Endpoint | Request fields | Written | Read |
| --- | --- | --- | --- |
| `POST /documents` | file, `doc_type?` | `documents`, object storage, `audit_log` | none |
| `GET /care-plan/{patient}` | none | none | `care_plan_items` (current), `source_refs`, `v_allergy_effective`, `allergies` |
| `POST /allergies` | `substance`, `reaction?`, `severity?`, `confirmed: true` | `source_refs` (family_input), `allergies`, `allergy_status`, `allergy_conflicts`, `audit_log` | `drug_substances`, `drug_families` |
| `POST /visits` | consent payloads, `language_hint?` | `consents` x2, `visits`, `audit_log` | none |
| `POST /plan-changes/{id}/decision` | `decision`, `comment?` | `plan_changes`, `care_plan_items`, `medicine_ingredients`, `allergy_conflicts`, `audit_log` | `plan_changes` |
| `POST /actions/{id}/approve` | `comment?` | `actions`, then the action's own writes, `audit_log` | `actions` |
| `POST /emergency-card` | `expires_in_days?` | `emergency_cards`, object storage, `audit_log` | care plan, allergies, providers |
| `GET /e/{token}` | none | `emergency_card_access_log` | care plan, allergies, providers (via public policies) |
| `POST /agent/message` | `text` or audio | `messages`, `agent_runs`, `actions`, `generated_outputs` | care plan |

## 11. Model call to rows written

| Call | Model | Purpose key | Rows produced |
| --- | --- | --- | --- |
| Document extraction | `muse-spark-1.3` | `extract_document` | `extractions`, then `source_refs`, `plan_changes`, `care_plan_items`, `medicine_ingredients`, `allergies` |
| Visit transcription | `muse-voice-transcribe-1.0` (diarization) | `asr_visit` | `transcript_segments` |
| Speaker role mapping | `muse-spark-1.3` | `map_speakers` | `visit_speakers` |
| Visit extraction | `muse-spark-1.3` | `extract_visit` | `extractions`, then `plan_changes` |
| Voice message transcription | `muse-voice-transcribe-1.0` (endpointing) | `asr_message` | `messages.transcript` |
| Explanation | `muse-spark-1.3` | `explain` | `generated_outputs`, `output_sources` |
| Allergy flag and doctor question wording | `muse-spark-1.3` | `word_flag` | `generated_outputs` (`allergy_flag`, `doctor_question`) |
| Agent reply with tools | `muse-spark-1.3` | `agent_turn` | `agent_runs`, `actions`, `generated_outputs` |
| Spoken reply | external TTS | `tts` | object storage, `generated_outputs.audio_storage_key` |
| Wound photo mask (stretch) | `sam-3.1` | `segment_photo` | `recovery_entries.photo_region` |

Every call also writes one `model_calls` row. The development setting for synthetic data may use the Contributor variants (`contributor_mode = true`); production-style runs must not.

## 12. State machines

| Entity | States | Rules |
| --- | --- | --- |
| Document | `uploaded`, `processing`, `extracted`, `needs_review`, `failed` | `needs_review` returns to `extracted` when the family corrects it. |
| Extraction | `pending`, `needs_review`, `applied`, `rejected`, `failed` | `applied` only after validation passes. |
| Plan change | `pending`, `applied`, `rejected`, `superseded` | If `requires_confirmation`, `applied` needs `decided_by` and `decided_at` (database check). |
| Action | `proposed`, `awaiting_approval`, `approved`, `executing`, `done`, `refused`, `failed`, `expired` | An `ask_first` action passes `awaiting_approval` only with a named approver (database check). |
| Visit | `recording`, `processing`, `needs_review`, `completed`, `failed`, `cancelled` | Created only with two different consent rows (database check). |
| Allergy status | `listed`, `no_known_allergies`, `not_recorded` | The UI reads only `v_allergy_effective`. |
| Reminder | `scheduled`, `sent`, `done`, `missed`, `snoozed`, `cancelled` | Spoken reminders are answered "done" or "not yet". |
| Allergy conflict | `open`, `acknowledged`, `resolved`, `dismissed_by_doctor` | Only a person can move it off `open`. |

See `diagrams/08-states.png`.

## 13. Retention and deletion

| Data | Where | Default retention | Deletion |
| --- | --- | --- | --- |
| Visit audio | Object storage | Deleted after transcription when `delete_audio_after_transcription` is true (the default); `audio_deleted_at` records it | Job after the transcript is stored |
| Transcripts | `transcript_segments` | While the patient's account exists | Deleted with the visit or the patient |
| Documents and photos | Object storage, `documents` | While the patient's account exists | Soft delete first (`deleted_at`), purge after a grace period |
| Care plan, allergies | `care_plan_items`, `allergies` | Permanent history by design | Patient deletion purges all versions |
| Audit log | `audit_log` | Kept after patient deletion in reduced form (no content, ids and actions only), decision to confirm with a lawyer | Never edited |
| Emergency Card links | `emergency_cards` | Until expiry or revocation | Hash only is stored; the token cannot be recovered |
| Model call logs | `model_calls` | 90 days for request and response objects, metadata longer | Job |
| Hackathon data | all | Synthetic only (D-13) | Drop the database after judging |

Real patient data needs a legal and consent review first (D-13).

## 14. Additions after kickoff (proposed contract `extract.v1.1`)

Implemented after Oct 26 (D-25). Existing fields do not change.

### 14.1 New or extended fields

| Field | Where | Notes |
| --- | --- | --- |
| `document_type` values `bill`, `pharmacy_bill`, `claim_form`, `policy_copy`, `id_proof`, `investigation_report`, `doctor_recommendation` | Document level | Used by the claim file. The model proposes, code validates against the list |
| `quantity` and `quantity_unit` | `medicine` items | As written, for example "30" and "tablets". Used by the refill tracker. Missing means no estimate |
| `follow_up` item kind with `what`, `due_text` and `quote` | Visits and documents | The model returns the words ("in two weeks"). Code computes the date |
| `patient_name_as_written`, `date_range`, `total_amount_text` | Bills and reports | Text as written plus a parsed value. Used by the mismatch check |

### 14.2 Derived values (code only, D-31)

| Value | Rule |
| --- | --- |
| Follow-up due date | Anchor date plus the stated interval. The anchor is the visit date or the document date, whichever the quote relates to. Dates are IST. A vague phrase ("soon", "after some time") gives no date and is marked for review |
| Refill run-out estimate | Start date plus the quantity divided by the daily units. Daily units come from the documented frequency (for example twice a day is 2). "As needed" or an unparsable frequency gives no estimate. The inputs are shown beside the result |
| Claim deadline reminder | Only from dates the family enters from their own policy. No default deadlines |

### 14.3 Omission matching

1. Resolve each item to its ingredient set through `medicine_ingredients`.
2. A previous item is "carried" if any current item shares its full ingredient set.
3. An item that is not carried becomes an omission candidate.
4. If an ingredient is unresolved, the item is "could not compare" and no omission is raised for it.
5. If the new document is incomplete, no candidates are raised at all.
6. Strength, frequency or brand differences do not create omissions. They are handled by the what-changed diff (S5).

### 14.4 Two-reader comparison

| Compared field | Difference counts as |
| --- | --- |
| Medicine name (normalized) | Blocking |
| Strength value and unit | Blocking |
| Frequency, timing, duration | Blocking |
| Quantity | Blocking |
| Quote text (whitespace and case ignored) | Not blocking |
| Page and line | Not blocking, but shown |

A blocking difference puts the item in review, shows both readings, and applies nothing until a person chooses.

### 14.5 Claim checklist mapping

| Checklist item (editable, generic) | Matches `document_type` |
| --- | --- |
| Itemized hospital bills | `bill` |
| Pharmacy bills with prescriptions | `pharmacy_bill` and a linked prescription |
| Discharge summary | `discharge_summary` |
| Prescriptions | `prescription` |
| Investigation reports | `investigation_report` or `lab_report` |
| Identity proof | `id_proof` |
| Claim form | `claim_form` |
| Policy copy | `policy_copy` |
| Doctor's recommendation for admission | `doctor_recommendation` |
| Accident report (only if the family marks the claim as accident related) | `accident_report` |

The list is generic guidance from consumer articles. Insurers differ, so the screen says "check your insurer's list" and lets the family add or remove items.

### 14.6 Mismatch checks

| Check | Rule |
| --- | --- |
| Patient name | Compare normalized names; a different spelling beyond a small edit distance is flagged with both quotes |
| Dates | A bill date outside the admission and discharge dates is flagged |
| Amounts | The sum of line items must equal the stated total, within rounding, or it is flagged |

A flag is a question for the family to check the paper. It is never a statement that a claim is wrong.
