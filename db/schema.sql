-- CareSaathi reference schema. PostgreSQL 16+.
-- Source of truth for the first Alembic migration. See docs/16-database-design.md.
-- Rules: every table that holds patient data carries patient_id (for row-level security);
-- care plan items and allergies are versioned and never overwritten; audit_log is append-only.

BEGIN;

CREATE EXTENSION IF NOT EXISTS citext;
-- CREATE EXTENSION IF NOT EXISTS vector;  -- later, for semantic search over history (D-14)

-- ---------------------------------------------------------------------------
-- Types
-- ---------------------------------------------------------------------------
CREATE DOMAIN pref_lang AS text CHECK (VALUE IN ('en', 'hi', 'mr'));
CREATE DOMAIN lang_code AS text CHECK (VALUE IN ('en', 'hi', 'mr', 'mixed', 'unknown'));

CREATE TYPE member_role AS ENUM ('patient', 'child', 'spouse', 'relative', 'attendant', 'nurse', 'other');
CREATE TYPE invite_status AS ENUM ('invited', 'active', 'removed');
CREATE TYPE doc_type AS ENUM ('prescription', 'lab_report', 'discharge_summary', 'specialist_letter', 'imaging_report', 'other');
CREATE TYPE doc_status AS ENUM ('uploaded', 'processing', 'extracted', 'needs_review', 'failed');
CREATE TYPE plan_item_kind AS ENUM ('medicine', 'condition', 'test', 'appointment', 'warning_sign', 'restriction', 'instruction', 'result');
CREATE TYPE plan_item_status AS ENUM ('active', 'stopped', 'completed', 'entered_in_error');
CREATE TYPE alert_level AS ENUM ('watch', 'call_doctor_today', 'emergency');
CREATE TYPE allergy_state AS ENUM ('listed', 'no_known_allergies', 'not_recorded');
CREATE TYPE allergy_source AS ENUM ('document', 'visit', 'family_reported');
CREATE TYPE allergy_severity AS ENUM ('mild', 'moderate', 'severe', 'unknown');
CREATE TYPE source_kind AS ENUM ('document', 'visit_segment', 'family_input', 'system_rule');
CREATE TYPE actor_type AS ENUM ('user', 'agent', 'system', 'device', 'public_link');
CREATE TYPE permission_level AS ENUM ('automatic', 'ask_first', 'automatic_alert');
CREATE TYPE action_status AS ENUM ('proposed', 'awaiting_approval', 'approved', 'executing', 'done', 'refused', 'failed', 'expired');
CREATE TYPE change_type AS ENUM ('new', 'changed', 'stopped', 'allergy_added', 'allergy_changed', 'allergy_removed', 'other');
CREATE TYPE change_status AS ENUM ('pending', 'applied', 'rejected', 'superseded');
CREATE TYPE extraction_origin AS ENUM ('document', 'visit', 'family_input', 'recovery');
CREATE TYPE extraction_status AS ENUM ('pending', 'needs_review', 'applied', 'rejected', 'failed');
CREATE TYPE visit_status AS ENUM ('recording', 'processing', 'needs_review', 'completed', 'failed', 'cancelled');
CREATE TYPE consent_type AS ENUM ('visit_recording', 'share_with_doctor', 'share_emergency_card', 'data_processing');
CREATE TYPE speaker_role AS ENUM ('doctor', 'patient', 'family', 'nurse', 'other', 'unknown');
CREATE TYPE match_type AS ENUM ('direct', 'drug_family', 'unresolved');
CREATE TYPE conflict_status AS ENUM ('open', 'acknowledged', 'resolved', 'dismissed_by_doctor');
CREATE TYPE output_type AS ENUM ('explanation', 'allergy_flag', 'doctor_question', 'visit_summary', 'emergency_summary', 'weekly_briefing', 'chat_reply', 'recovery_description', 'warning_card');
CREATE TYPE guard_status AS ENUM ('pass', 'blocked', 'needs_review');
CREATE TYPE channel_kind AS ENUM ('in_app', 'whatsapp', 'sms', 'email');
CREATE TYPE message_direction AS ENUM ('inbound', 'outbound');
CREATE TYPE media_kind AS ENUM ('text', 'voice', 'image', 'document', 'video');
CREATE TYPE reminder_kind AS ENUM ('medicine', 'test', 'appointment', 'refill', 'checkin', 'followup', 'briefing');
CREATE TYPE reminder_status AS ENUM ('scheduled', 'sent', 'done', 'missed', 'snoozed', 'cancelled');
CREATE TYPE outbox_status AS ENUM ('pending', 'sending', 'sent', 'failed', 'dead');
CREATE TYPE card_access_outcome AS ENUM ('ok', 'expired', 'revoked', 'not_found');
CREATE TYPE model_provider AS ENUM ('meta', 'tts', 'whatsapp', 'other');

-- ---------------------------------------------------------------------------
-- Helper functions and triggers
-- ---------------------------------------------------------------------------
CREATE FUNCTION set_updated_at() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
  NEW.updated_at := now();
  RETURN NEW;
END $$;

-- Session context set by the API for every request: SET LOCAL app.user_id = '<uuid>' and so on.
CREATE FUNCTION app_user_id() RETURNS uuid LANGUAGE sql STABLE AS
  $$ SELECT nullif(current_setting('app.user_id', true), '')::uuid $$;
CREATE FUNCTION app_device_patient_id() RETURNS uuid LANGUAGE sql STABLE AS
  $$ SELECT nullif(current_setting('app.device_patient_id', true), '')::uuid $$;
CREATE FUNCTION app_public_card_patient_id() RETURNS uuid LANGUAGE sql STABLE AS
  $$ SELECT nullif(current_setting('app.public_card_patient_id', true), '')::uuid $$;

-- ---------------------------------------------------------------------------
-- Identity and access
-- ---------------------------------------------------------------------------
CREATE TABLE users (
  id                 uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  email              citext UNIQUE,
  phone_e164         text UNIQUE CHECK (phone_e164 ~ '^\+[1-9][0-9]{6,14}$'),
  display_name       text NOT NULL,
  preferred_language pref_lang NOT NULL DEFAULT 'en',
  password_hash      text,
  is_active          boolean NOT NULL DEFAULT true,
  created_at         timestamptz NOT NULL DEFAULT now(),
  updated_at         timestamptz NOT NULL DEFAULT now(),
  CHECK (email IS NOT NULL OR phone_e164 IS NOT NULL)
);

CREATE TABLE patients (
  id                 uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  full_name          text NOT NULL,
  date_of_birth      date,
  sex                text CHECK (sex IN ('female', 'male', 'other', 'unknown')),
  preferred_language pref_lang NOT NULL DEFAULT 'en',
  blood_group        text,
  is_synthetic       boolean NOT NULL DEFAULT true,   -- hackathon: synthetic data only (D-13)
  created_by         uuid REFERENCES users(id),
  deleted_at         timestamptz,
  created_at         timestamptz NOT NULL DEFAULT now(),
  updated_at         timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE family_members (
  id                   uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  patient_id           uuid NOT NULL REFERENCES patients(id),
  user_id              uuid NOT NULL REFERENCES users(id),
  member_role          member_role NOT NULL,
  relationship_label   text,
  language             pref_lang NOT NULL DEFAULT 'en',
  status               invite_status NOT NULL DEFAULT 'invited',
  can_approve          boolean NOT NULL DEFAULT false,
  can_manage_members   boolean NOT NULL DEFAULT false,
  can_view_recordings  boolean NOT NULL DEFAULT false,
  notify_urgent        boolean NOT NULL DEFAULT true,
  invited_by           uuid REFERENCES users(id),
  created_at           timestamptz NOT NULL DEFAULT now(),
  updated_at           timestamptz NOT NULL DEFAULT now(),
  UNIQUE (patient_id, user_id)
);

-- Elder mode: a phone paired to one patient, approved by a family member. No password.
CREATE TABLE devices (
  id                       uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  patient_id               uuid NOT NULL REFERENCES patients(id),
  label                    text NOT NULL,
  pairing_code_hash        bytea,
  pairing_expires_at       timestamptz,
  approved_by_member_id    uuid REFERENCES family_members(id),
  token_hash               bytea UNIQUE,
  last_seen_at             timestamptz,
  revoked_at               timestamptz,
  created_at               timestamptz NOT NULL DEFAULT now(),
  CHECK (token_hash IS NULL OR approved_by_member_id IS NOT NULL)
);

CREATE TABLE care_providers (
  id          uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  patient_id  uuid NOT NULL REFERENCES patients(id),
  name        text NOT NULL,
  specialty   text,
  hospital    text,
  phone       text,
  is_primary  boolean NOT NULL DEFAULT false,
  created_at  timestamptz NOT NULL DEFAULT now(),
  updated_at  timestamptz NOT NULL DEFAULT now()
);

-- Visible only to the app role. Used for cost tracking, debugging and evaluation.
CREATE TABLE model_calls (
  id                    uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  patient_id            uuid REFERENCES patients(id),
  provider              model_provider NOT NULL,
  model                 text NOT NULL,
  purpose               text NOT NULL,
  status                text NOT NULL DEFAULT 'ok' CHECK (status IN ('ok', 'error', 'timeout')),
  input_tokens          integer,
  output_tokens         integer,
  audio_seconds         numeric(10, 2),
  image_count           integer,
  cost_usd              numeric(12, 6),
  latency_ms            integer,
  contributor_mode      boolean NOT NULL DEFAULT false,  -- Meta may train on these prompts: synthetic data only
  request_id            text,
  request_storage_key   text,
  response_storage_key  text,
  error                 text,
  created_at            timestamptz NOT NULL DEFAULT now()
);

-- ---------------------------------------------------------------------------
-- Generated outputs (every explanation, flag and reply) and conversations
-- ---------------------------------------------------------------------------
CREATE TABLE generated_outputs (
  id                 uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  patient_id         uuid NOT NULL REFERENCES patients(id),
  output_type        output_type NOT NULL,
  language           lang_code NOT NULL DEFAULT 'en',
  body               text NOT NULL,
  audio_storage_key  text,
  tts_provider       text,
  tts_voice          text,
  model_call_id      uuid REFERENCES model_calls(id),
  guard_status       guard_status NOT NULL DEFAULT 'needs_review',
  guard_reasons      jsonb NOT NULL DEFAULT '[]'::jsonb,
  source_exempt      boolean NOT NULL DEFAULT false,
  created_at         timestamptz NOT NULL DEFAULT now(),
  -- Only plain conversational replies (for example "please say that again") may have no source.
  CHECK (NOT source_exempt OR output_type = 'chat_reply')
);

CREATE TABLE conversations (
  id           uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  patient_id   uuid NOT NULL REFERENCES patients(id),
  channel      channel_kind NOT NULL,
  external_id  text,
  created_at   timestamptz NOT NULL DEFAULT now(),
  UNIQUE (patient_id, channel, external_id)
);

CREATE TABLE messages (
  id                uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  patient_id        uuid NOT NULL REFERENCES patients(id),
  conversation_id   uuid NOT NULL REFERENCES conversations(id),
  direction         message_direction NOT NULL,
  sender_user_id    uuid REFERENCES users(id),
  sender_device_id  uuid REFERENCES devices(id),
  media             media_kind NOT NULL DEFAULT 'text',
  body              text,
  media_storage_key text,
  media_sha256      bytea,
  transcript        text,
  language          lang_code NOT NULL DEFAULT 'unknown',
  wa_message_id     text UNIQUE,
  output_id         uuid REFERENCES generated_outputs(id),
  created_at        timestamptz NOT NULL DEFAULT now()
);

-- ---------------------------------------------------------------------------
-- Documents, consent, visits and transcripts
-- ---------------------------------------------------------------------------
CREATE TABLE documents (
  id                uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  patient_id        uuid NOT NULL REFERENCES patients(id),
  doc_type          doc_type NOT NULL DEFAULT 'other',
  status            doc_status NOT NULL DEFAULT 'uploaded',
  original_filename text,
  mime_type         text NOT NULL,
  byte_size         bigint NOT NULL CHECK (byte_size > 0),
  sha256            bytea NOT NULL,
  storage_key       text NOT NULL,
  page_count        integer,
  doc_date          date,
  issuer            text,
  language          lang_code NOT NULL DEFAULT 'unknown',
  extracted_text    text,
  uploaded_by       uuid REFERENCES users(id),
  deleted_at        timestamptz,
  created_at        timestamptz NOT NULL DEFAULT now(),
  updated_at        timestamptz NOT NULL DEFAULT now(),
  UNIQUE (patient_id, sha256)
);

CREATE TABLE consents (
  id                    uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  patient_id            uuid NOT NULL REFERENCES patients(id),
  consent_type          consent_type NOT NULL,
  subject_role          speaker_role NOT NULL,         -- who is consenting: doctor, patient, family
  given_by_user_id      uuid REFERENCES users(id),
  given_by_name         text NOT NULL,
  on_behalf_of_patient  boolean NOT NULL DEFAULT false,
  consent_text_version  text NOT NULL,
  granted_at            timestamptz NOT NULL DEFAULT now(),
  revoked_at            timestamptz,
  revoked_by            uuid REFERENCES users(id),
  evidence              jsonb NOT NULL DEFAULT '{}'::jsonb,
  created_at            timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE visits (
  id                          uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  patient_id                  uuid NOT NULL REFERENCES patients(id),
  started_by                  uuid NOT NULL REFERENCES users(id),
  -- A visit cannot exist without both consents (safety invariant 8).
  patient_consent_id          uuid NOT NULL REFERENCES consents(id),
  doctor_consent_id           uuid NOT NULL REFERENCES consents(id),
  status                      visit_status NOT NULL DEFAULT 'recording',
  doctor_name                 text,
  hospital                    text,
  language_hint               lang_code NOT NULL DEFAULT 'unknown',
  audio_storage_key           text,
  audio_sha256                bytea,
  duration_ms                 integer,
  delete_audio_after_transcription boolean NOT NULL DEFAULT true,
  audio_deleted_at            timestamptz,
  started_at                  timestamptz NOT NULL DEFAULT now(),
  ended_at                    timestamptz,
  created_at                  timestamptz NOT NULL DEFAULT now(),
  updated_at                  timestamptz NOT NULL DEFAULT now(),
  CHECK (patient_consent_id <> doctor_consent_id)
);

CREATE TABLE transcript_segments (
  id             uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  patient_id     uuid NOT NULL REFERENCES patients(id),
  visit_id       uuid NOT NULL REFERENCES visits(id) ON DELETE CASCADE,
  turn_id        text NOT NULL,
  seq            integer NOT NULL,
  speaker_label  text NOT NULL,                 -- "A", "B", ... from Muse Voice Transcribe
  mapped_role    speaker_role NOT NULL DEFAULT 'unknown',
  mapped_by      text NOT NULL DEFAULT 'system' CHECK (mapped_by IN ('model', 'family', 'system')),
  start_ms       integer NOT NULL,
  end_ms         integer NOT NULL,
  body           text NOT NULL,
  language       lang_code NOT NULL DEFAULT 'unknown',
  created_at     timestamptz NOT NULL DEFAULT now(),
  UNIQUE (visit_id, turn_id),
  UNIQUE (visit_id, seq),
  CHECK (end_ms >= start_ms)
);

CREATE TABLE visit_speakers (
  id               uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  patient_id       uuid NOT NULL REFERENCES patients(id),
  visit_id         uuid NOT NULL REFERENCES visits(id) ON DELETE CASCADE,
  speaker_label    text NOT NULL,
  role             speaker_role NOT NULL DEFAULT 'unknown',
  display_name     text,
  mapped_by        text NOT NULL DEFAULT 'model' CHECK (mapped_by IN ('model', 'family')),
  confirmed_by     uuid REFERENCES users(id),
  confirmed_at     timestamptz,
  UNIQUE (visit_id, speaker_label)
);

-- ---------------------------------------------------------------------------
-- Sources: where every fact came from (safety invariant 5)
-- ---------------------------------------------------------------------------
CREATE TABLE source_refs (
  id                 uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  patient_id         uuid NOT NULL REFERENCES patients(id),
  kind               source_kind NOT NULL,
  document_id        uuid REFERENCES documents(id),
  page               integer,
  line_start         integer,
  line_end           integer,
  bbox               jsonb,
  segment_id         uuid REFERENCES transcript_segments(id),
  message_id         uuid REFERENCES messages(id),
  stated_by_user_id  uuid REFERENCES users(id),
  rule_code          text,
  quote              text,                       -- the document line or the doctor's exact words
  created_at         timestamptz NOT NULL DEFAULT now(),
  CHECK (kind <> 'document'      OR (document_id IS NOT NULL AND length(btrim(coalesce(quote, ''))) > 0)),
  CHECK (kind <> 'visit_segment' OR (segment_id IS NOT NULL AND length(btrim(coalesce(quote, ''))) > 0)),
  CHECK (kind <> 'family_input'  OR stated_by_user_id IS NOT NULL),
  CHECK (kind <> 'system_rule'   OR rule_code IS NOT NULL)
);

CREATE TABLE output_sources (
  output_id     uuid NOT NULL REFERENCES generated_outputs(id) ON DELETE CASCADE,
  source_ref_id uuid NOT NULL REFERENCES source_refs(id),
  patient_id    uuid NOT NULL REFERENCES patients(id),
  PRIMARY KEY (output_id, source_ref_id)
);

-- An output that passed the guard must have at least one source, unless it is an exempt chat reply.
CREATE FUNCTION enforce_output_has_source() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
  IF NEW.guard_status = 'pass' AND NOT NEW.source_exempt
     AND NOT EXISTS (SELECT 1 FROM output_sources s WHERE s.output_id = NEW.id) THEN
    RAISE EXCEPTION 'generated_output % passed the guard without a source', NEW.id
      USING ERRCODE = 'check_violation';
  END IF;
  RETURN NULL;
END $$;

CREATE CONSTRAINT TRIGGER trg_output_has_source
  AFTER INSERT OR UPDATE ON generated_outputs
  DEFERRABLE INITIALLY DEFERRED
  FOR EACH ROW EXECUTE FUNCTION enforce_output_has_source();

-- ---------------------------------------------------------------------------
-- Extraction staging, care plan and change log
-- ---------------------------------------------------------------------------
CREATE TABLE extractions (
  id                 uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  patient_id         uuid NOT NULL REFERENCES patients(id),
  origin             extraction_origin NOT NULL,
  document_id        uuid REFERENCES documents(id),
  visit_id           uuid REFERENCES visits(id),
  model_call_id      uuid REFERENCES model_calls(id),
  schema_version     text NOT NULL,
  raw_output         jsonb NOT NULL,
  validated          boolean NOT NULL DEFAULT false,
  validation_errors  jsonb NOT NULL DEFAULT '[]'::jsonb,
  status             extraction_status NOT NULL DEFAULT 'pending',
  created_at         timestamptz NOT NULL DEFAULT now(),
  applied_at         timestamptz,
  CHECK (origin <> 'document' OR document_id IS NOT NULL),
  CHECK (origin <> 'visit' OR visit_id IS NOT NULL)
);

CREATE TABLE care_plan_items (
  id             uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  patient_id     uuid NOT NULL REFERENCES patients(id),
  item_key       uuid NOT NULL,                    -- stable identity across versions
  version        integer NOT NULL DEFAULT 1 CHECK (version >= 1),
  is_current     boolean NOT NULL DEFAULT true,
  supersedes_id  uuid REFERENCES care_plan_items(id),
  kind           plan_item_kind NOT NULL,
  status         plan_item_status NOT NULL DEFAULT 'active',
  title          text NOT NULL,
  details        jsonb NOT NULL DEFAULT '{}'::jsonb,   -- shape depends on kind (docs/14-data-mapping.md)
  alert_level    alert_level,
  due_at         timestamptz,
  date_missing   boolean NOT NULL DEFAULT false,       -- "no date given": flag it, never guess
  source_ref_id  uuid NOT NULL REFERENCES source_refs(id),
  confirmed_by   uuid REFERENCES users(id),
  confirmed_at   timestamptz,
  created_by_type actor_type NOT NULL DEFAULT 'agent',
  created_by     uuid,
  created_at     timestamptz NOT NULL DEFAULT now(),
  UNIQUE (item_key, version),
  CHECK ((kind = 'warning_sign') = (alert_level IS NOT NULL))   -- levels come only from written instructions
);
CREATE UNIQUE INDEX uq_care_plan_current ON care_plan_items (item_key) WHERE is_current;
CREATE INDEX ix_care_plan_patient_current ON care_plan_items (patient_id, kind) WHERE is_current;
CREATE INDEX ix_care_plan_due ON care_plan_items (due_at) WHERE is_current AND due_at IS NOT NULL;

-- Medicine ingredients, split out so allergy matching is a plain join.
CREATE TABLE drug_families (
  id            uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  code          text NOT NULL UNIQUE,
  name          text NOT NULL,
  synonyms      text[] NOT NULL DEFAULT '{}',
  review_status text NOT NULL DEFAULT 'unreviewed' CHECK (review_status IN ('unreviewed', 'reviewed')),
  reviewed_by   text,
  reviewed_at   timestamptz,
  notes         text,
  CHECK (review_status <> 'reviewed' OR (reviewed_by IS NOT NULL AND reviewed_at IS NOT NULL))
);

CREATE TABLE drug_substances (
  id                    uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  substance_normalized  text NOT NULL UNIQUE,
  display_name          text NOT NULL,
  synonyms              text[] NOT NULL DEFAULT '{}',
  brand_names           text[] NOT NULL DEFAULT '{}'
);
CREATE INDEX ix_drug_substances_synonyms ON drug_substances USING gin (synonyms);
CREATE INDEX ix_drug_substances_brands ON drug_substances USING gin (brand_names);

CREATE TABLE drug_family_members (
  family_id    uuid NOT NULL REFERENCES drug_families(id) ON DELETE CASCADE,
  substance_id uuid NOT NULL REFERENCES drug_substances(id) ON DELETE CASCADE,
  PRIMARY KEY (family_id, substance_id)
);
CREATE INDEX ix_drug_family_members_substance ON drug_family_members (substance_id);

CREATE TABLE medicine_ingredients (
  id                    uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  patient_id            uuid NOT NULL REFERENCES patients(id),
  item_id               uuid NOT NULL REFERENCES care_plan_items(id) ON DELETE CASCADE,
  ingredient_raw        text NOT NULL,
  ingredient_normalized text NOT NULL,
  substance_id          uuid REFERENCES drug_substances(id),   -- NULL means "not in the reference list"
  strength_text         text
);
CREATE INDEX ix_med_ingredients_item ON medicine_ingredients (item_id);
CREATE INDEX ix_med_ingredients_substance ON medicine_ingredients (substance_id);

CREATE TABLE plan_changes (
  id                    uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  patient_id            uuid NOT NULL REFERENCES patients(id),
  extraction_id         uuid REFERENCES extractions(id),
  change_type           change_type NOT NULL,
  item_key              uuid,
  before_state          jsonb,
  after_state           jsonb,
  source_ref_id         uuid NOT NULL REFERENCES source_refs(id),
  requires_confirmation boolean NOT NULL DEFAULT true,
  status                change_status NOT NULL DEFAULT 'pending',
  explanation_output_id uuid REFERENCES generated_outputs(id),
  decided_by            uuid REFERENCES users(id),
  decided_at            timestamptz,
  applied_item_id       uuid REFERENCES care_plan_items(id),
  created_at            timestamptz NOT NULL DEFAULT now(),
  -- A change that needs confirmation can be applied only after a named person decided it.
  CHECK (NOT (requires_confirmation AND status = 'applied' AND (decided_by IS NULL OR decided_at IS NULL)))
);
CREATE INDEX ix_plan_changes_pending ON plan_changes (patient_id) WHERE status = 'pending';

-- ---------------------------------------------------------------------------
-- Allergies (safety invariants 2 and 3)
-- ---------------------------------------------------------------------------
CREATE TABLE allergies (
  id                    uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  patient_id            uuid NOT NULL REFERENCES patients(id),
  allergy_key           uuid NOT NULL,
  version               integer NOT NULL DEFAULT 1 CHECK (version >= 1),
  is_current            boolean NOT NULL DEFAULT true,
  supersedes_id         uuid REFERENCES allergies(id),
  substance             text NOT NULL,
  substance_normalized  text NOT NULL,
  substance_id          uuid REFERENCES drug_substances(id),   -- a specific drug, if known
  family_id             uuid REFERENCES drug_families(id),     -- a drug class, if the allergy names one
  reaction              text,
  severity              allergy_severity NOT NULL DEFAULT 'unknown',
  source_type           allergy_source NOT NULL,
  source_ref_id         uuid NOT NULL REFERENCES source_refs(id),
  active                boolean NOT NULL DEFAULT true,
  confirmed_by          uuid REFERENCES users(id),
  confirmed_at          timestamptz,
  created_at            timestamptz NOT NULL DEFAULT now(),
  UNIQUE (allergy_key, version),
  -- Family-reported allergies are saved only after a family member confirms the read-back.
  CHECK (source_type <> 'family_reported' OR (confirmed_by IS NOT NULL AND confirmed_at IS NOT NULL))
);
CREATE UNIQUE INDEX uq_allergy_current ON allergies (allergy_key) WHERE is_current;
CREATE INDEX ix_allergies_patient_current ON allergies (patient_id) WHERE is_current AND active;

CREATE TABLE allergy_status (
  patient_id      uuid PRIMARY KEY REFERENCES patients(id),
  state           allergy_state NOT NULL DEFAULT 'not_recorded',
  source_ref_id   uuid REFERENCES source_refs(id),
  last_checked_at timestamptz,
  updated_by      uuid REFERENCES users(id),
  updated_at      timestamptz NOT NULL DEFAULT now(),
  -- "No known allergies" needs a document or doctor saying so.
  CHECK (state <> 'no_known_allergies' OR source_ref_id IS NOT NULL)
);

-- The only state the UI may read. An empty list is never "none".
CREATE VIEW v_allergy_effective AS
SELECT p.id AS patient_id,
       CASE
         WHEN EXISTS (SELECT 1 FROM allergies a WHERE a.patient_id = p.id AND a.is_current AND a.active)
           THEN 'listed'::allergy_state
         WHEN s.state = 'no_known_allergies' AND s.source_ref_id IS NOT NULL
           THEN 'no_known_allergies'::allergy_state
         ELSE 'not_recorded'::allergy_state
       END AS state
FROM patients p
LEFT JOIN allergy_status s ON s.patient_id = p.id;

CREATE TABLE allergy_conflicts (
  id                  uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  patient_id          uuid NOT NULL REFERENCES patients(id),
  allergy_id          uuid REFERENCES allergies(id),
  care_plan_item_id   uuid NOT NULL REFERENCES care_plan_items(id),
  ingredient_id       uuid REFERENCES medicine_ingredients(id),
  match               match_type NOT NULL,
  family_id           uuid REFERENCES drug_families(id),
  status              conflict_status NOT NULL DEFAULT 'open',
  flag_output_id      uuid REFERENCES generated_outputs(id),
  question_output_id  uuid REFERENCES generated_outputs(id),
  raised_at           timestamptz NOT NULL DEFAULT now(),
  acknowledged_by     uuid REFERENCES users(id),
  acknowledged_at     timestamptz,
  resolution_note     text,
  CHECK ((match = 'unresolved') = (allergy_id IS NULL))
);
CREATE UNIQUE INDEX uq_conflict_pair ON allergy_conflicts (allergy_id, care_plan_item_id, coalesce(ingredient_id, '00000000-0000-0000-0000-000000000000'::uuid));
CREATE INDEX ix_conflicts_open ON allergy_conflicts (patient_id) WHERE status = 'open';

-- Deterministic conflict finder. The model never decides this (D-12 rule 3).
-- Returns: direct matches, same-family matches, and ingredients the reference list could not resolve.
-- An empty result means "no match found in the reference list", never "safe".
CREATE FUNCTION find_allergy_conflicts(p_item_id uuid)
RETURNS TABLE (allergy_id uuid, match match_type, ingredient_id uuid, family_id uuid)
LANGUAGE sql STABLE AS $$
  WITH item AS (SELECT patient_id FROM care_plan_items WHERE id = p_item_id),
  al AS (
    SELECT a.* FROM allergies a JOIN item i ON a.patient_id = i.patient_id
    WHERE a.is_current AND a.active
  ),
  ing AS (SELECT mi.id, mi.substance_id FROM medicine_ingredients mi WHERE mi.item_id = p_item_id)
  SELECT al.id, 'direct'::match_type, ing.id, NULL::uuid
    FROM al JOIN ing ON ing.substance_id IS NOT NULL AND ing.substance_id = al.substance_id
  UNION ALL
  SELECT al.id, 'drug_family'::match_type, ing.id, fm.family_id
    FROM al
    JOIN ing ON ing.substance_id IS NOT NULL
    JOIN drug_family_members fm ON fm.substance_id = ing.substance_id
   WHERE (fm.family_id = al.family_id
          OR fm.family_id IN (SELECT m2.family_id FROM drug_family_members m2 WHERE m2.substance_id = al.substance_id))
     AND NOT (ing.substance_id = al.substance_id)
  UNION ALL
  SELECT NULL::uuid, 'unresolved'::match_type, ing.id, NULL::uuid
    FROM ing
   WHERE ing.substance_id IS NULL AND EXISTS (SELECT 1 FROM al)
$$;

-- ---------------------------------------------------------------------------
-- Agent, permissions and actions (safety invariant 4)
-- ---------------------------------------------------------------------------
CREATE TABLE agent_runs (
  id               uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  patient_id       uuid NOT NULL REFERENCES patients(id),
  trigger          text NOT NULL CHECK (trigger IN ('message', 'document', 'visit', 'schedule', 'system')),
  trigger_ref      uuid,
  conversation_id  uuid REFERENCES conversations(id),
  status           text NOT NULL DEFAULT 'running' CHECK (status IN ('running', 'done', 'failed')),
  error            text,
  started_at       timestamptz NOT NULL DEFAULT now(),
  finished_at      timestamptz
);

CREATE TABLE actions (
  id                 uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  patient_id         uuid NOT NULL REFERENCES patients(id),
  agent_run_id       uuid REFERENCES agent_runs(id),
  tool               text NOT NULL,
  input              jsonb NOT NULL DEFAULT '{}'::jsonb,
  permission         permission_level NOT NULL,
  status             action_status NOT NULL DEFAULT 'proposed',
  result             jsonb,
  requested_by       actor_type NOT NULL DEFAULT 'agent',
  approved_by        uuid REFERENCES users(id),
  approved_at        timestamptz,
  approver_comment   text,
  expires_at         timestamptz,
  created_at         timestamptz NOT NULL DEFAULT now(),
  updated_at         timestamptz NOT NULL DEFAULT now(),
  -- An "ask first" action can only move past awaiting_approval with a named approver.
  CHECK (permission <> 'ask_first'
         OR status IN ('proposed', 'awaiting_approval', 'refused', 'expired')
         OR (approved_by IS NOT NULL AND approved_at IS NOT NULL))
);
CREATE INDEX ix_actions_waiting ON actions (patient_id) WHERE status = 'awaiting_approval';

-- ---------------------------------------------------------------------------
-- Reminders, timeline, notifications
-- ---------------------------------------------------------------------------
CREATE TABLE reminders (
  id                  uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  patient_id          uuid NOT NULL REFERENCES patients(id),
  kind                reminder_kind NOT NULL,
  title               text NOT NULL,
  due_at              timestamptz NOT NULL,
  recurrence_rule     text,                              -- RFC 5545 RRULE, evaluated in the timezone below
  timezone            text NOT NULL DEFAULT 'Asia/Kolkata',
  assigned_member_id  uuid REFERENCES family_members(id),
  channel             channel_kind NOT NULL DEFAULT 'in_app',
  status              reminder_status NOT NULL DEFAULT 'scheduled',
  source_item_id      uuid REFERENCES care_plan_items(id),
  attempts            integer NOT NULL DEFAULT 0,
  last_sent_at        timestamptz,
  created_by_type     actor_type NOT NULL DEFAULT 'agent',
  created_by          uuid,
  created_at          timestamptz NOT NULL DEFAULT now(),
  updated_at          timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX ix_reminders_due ON reminders (due_at) WHERE status IN ('scheduled', 'snoozed');

CREATE TABLE timeline_events (
  id           uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  patient_id   uuid NOT NULL REFERENCES patients(id),
  event_type   text NOT NULL,
  actor_type   actor_type NOT NULL,
  actor_id     uuid,
  entity_type  text,
  entity_id    uuid,
  summary      text NOT NULL,
  data         jsonb NOT NULL DEFAULT '{}'::jsonb,
  occurred_at  timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX ix_timeline_patient_time ON timeline_events (patient_id, occurred_at DESC);

-- Transactional outbox: messages are written in the same transaction as the change that caused them.
CREATE TABLE outbox (
  id                   uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  patient_id           uuid NOT NULL REFERENCES patients(id),
  recipient_member_id  uuid REFERENCES family_members(id),
  channel              channel_kind NOT NULL,
  template             text NOT NULL,
  payload              jsonb NOT NULL DEFAULT '{}'::jsonb,
  status               outbox_status NOT NULL DEFAULT 'pending',
  attempts             integer NOT NULL DEFAULT 0,
  next_attempt_at      timestamptz NOT NULL DEFAULT now(),
  sent_at              timestamptz,
  provider_message_id  text,
  last_error           text,
  dedupe_key           text UNIQUE,
  created_at           timestamptz NOT NULL DEFAULT now(),
  updated_at           timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX ix_outbox_ready ON outbox (next_attempt_at) WHERE status IN ('pending', 'failed');

-- ---------------------------------------------------------------------------
-- Emergency Card (safety invariant 7)
-- ---------------------------------------------------------------------------
CREATE TABLE emergency_cards (
  id                      uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  patient_id              uuid NOT NULL REFERENCES patients(id),
  token_hash              bytea NOT NULL UNIQUE,         -- SHA-256 of the random token; the token itself is never stored
  token_hint              text NOT NULL,                 -- last 4 characters, for the family to tell links apart
  created_by              uuid NOT NULL REFERENCES users(id),
  expires_at              timestamptz,
  revoked_at              timestamptz,
  revoked_by              uuid REFERENCES users(id),
  pdf_storage_key         text,
  image_storage_key       text,
  snapshot                jsonb,                         -- content frozen for the PDF and image
  snapshot_generated_at   timestamptz,
  created_at              timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX ix_cards_patient ON emergency_cards (patient_id) WHERE revoked_at IS NULL;

CREATE TABLE emergency_card_access_log (
  id           bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  patient_id   uuid REFERENCES patients(id),
  card_id      uuid REFERENCES emergency_cards(id),
  outcome      card_access_outcome NOT NULL,
  ip_hash      bytea,
  user_agent   text,
  accessed_at  timestamptz NOT NULL DEFAULT now()
);

-- ---------------------------------------------------------------------------
-- Recovery Timeline (stretch B)
-- ---------------------------------------------------------------------------
CREATE TABLE recovery_entries (
  id                  uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  patient_id          uuid NOT NULL REFERENCES patients(id),
  episode_label       text NOT NULL,
  entry_date          date NOT NULL,
  day_number          integer NOT NULL CHECK (day_number >= 0),
  photo_storage_key   text,
  photo_region        jsonb,                            -- SAM 3.1 mask or box
  voice_storage_key   text,
  transcript          text,
  description_output_id uuid REFERENCES generated_outputs(id),
  alert_level         alert_level,
  source_item_id      uuid REFERENCES care_plan_items(id),   -- the written instruction the alert came from
  created_by          uuid REFERENCES users(id),
  created_at          timestamptz NOT NULL DEFAULT now(),
  UNIQUE (patient_id, episode_label, entry_date),
  CHECK (alert_level IS NULL OR source_item_id IS NOT NULL)
);

-- ---------------------------------------------------------------------------
-- Audit log (append-only) and evaluation results
-- ---------------------------------------------------------------------------
CREATE TABLE audit_log (
  id           bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  occurred_at  timestamptz NOT NULL DEFAULT now(),
  actor_type   actor_type NOT NULL,
  actor_id     uuid,
  patient_id   uuid,
  action       text NOT NULL,
  entity_type  text,
  entity_id    text,
  before_state jsonb,
  after_state  jsonb,
  request_id   text,
  ip_hash      bytea,
  prev_hash    bytea,                                -- hash chain: each row commits to the one before it
  row_hash     bytea
);
CREATE INDEX ix_audit_patient_time ON audit_log (patient_id, occurred_at DESC);
CREATE INDEX ix_audit_entity ON audit_log (entity_type, entity_id);

CREATE FUNCTION audit_log_is_append_only() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
  RAISE EXCEPTION 'audit_log is append-only' USING ERRCODE = 'insufficient_privilege';
END $$;
CREATE TRIGGER trg_audit_no_update BEFORE UPDATE OR DELETE ON audit_log
  FOR EACH ROW EXECUTE FUNCTION audit_log_is_append_only();
CREATE TRIGGER trg_audit_no_truncate BEFORE TRUNCATE ON audit_log
  FOR EACH STATEMENT EXECUTE FUNCTION audit_log_is_append_only();

CREATE TABLE eval_runs (
  id           uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  suite        text NOT NULL,
  git_sha      text,
  model        text,
  started_at   timestamptz NOT NULL DEFAULT now(),
  finished_at  timestamptz,
  metrics      jsonb NOT NULL DEFAULT '{}'::jsonb,
  notes        text
);

CREATE TABLE eval_results (
  id              uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  run_id          uuid NOT NULL REFERENCES eval_runs(id) ON DELETE CASCADE,
  case_id         text NOT NULL,
  category        text NOT NULL,
  expected        jsonb,
  actual          jsonb,
  passed          boolean NOT NULL,
  failure_reason  text,
  UNIQUE (run_id, case_id)
);

-- ---------------------------------------------------------------------------
-- Immutability of versioned rows: content never changes, only the current flag and confirmation.
-- ---------------------------------------------------------------------------
CREATE FUNCTION care_plan_items_immutable() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
  IF (NEW.patient_id, NEW.item_key, NEW.version, NEW.kind, NEW.status, NEW.title, NEW.details,
      NEW.alert_level, NEW.due_at, NEW.date_missing, NEW.source_ref_id, NEW.supersedes_id)
     IS DISTINCT FROM
     (OLD.patient_id, OLD.item_key, OLD.version, OLD.kind, OLD.status, OLD.title, OLD.details,
      OLD.alert_level, OLD.due_at, OLD.date_missing, OLD.source_ref_id, OLD.supersedes_id) THEN
    RAISE EXCEPTION 'care_plan_items content is immutable; write a new version instead';
  END IF;
  RETURN NEW;
END $$;
CREATE TRIGGER trg_care_plan_items_immutable BEFORE UPDATE ON care_plan_items
  FOR EACH ROW EXECUTE FUNCTION care_plan_items_immutable();

CREATE FUNCTION allergies_immutable() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
  IF (NEW.patient_id, NEW.allergy_key, NEW.version, NEW.substance, NEW.substance_normalized,
      NEW.reaction, NEW.severity, NEW.source_type, NEW.source_ref_id, NEW.active, NEW.supersedes_id)
     IS DISTINCT FROM
     (OLD.patient_id, OLD.allergy_key, OLD.version, OLD.substance, OLD.substance_normalized,
      OLD.reaction, OLD.severity, OLD.source_type, OLD.source_ref_id, OLD.active, OLD.supersedes_id) THEN
    RAISE EXCEPTION 'allergies content is immutable; write a new version instead';
  END IF;
  RETURN NEW;
END $$;
CREATE TRIGGER trg_allergies_immutable BEFORE UPDATE ON allergies
  FOR EACH ROW EXECUTE FUNCTION allergies_immutable();

-- updated_at on every table that has the column
DO $$
DECLARE r record;
BEGIN
  FOR r IN SELECT table_name FROM information_schema.columns
           WHERE table_schema = 'public' AND column_name = 'updated_at'
             AND table_name IN (SELECT tablename FROM pg_tables WHERE schemaname = 'public')
  LOOP
    EXECUTE format('CREATE TRIGGER trg_%1$s_updated BEFORE UPDATE ON %1$I FOR EACH ROW EXECUTE FUNCTION set_updated_at()', r.table_name);
  END LOOP;
END $$;

-- ---------------------------------------------------------------------------
-- Row-level security: a user sees only patients they are an active member of;
-- a paired device sees only its own patient. The app role is not the table owner.
-- ---------------------------------------------------------------------------
CREATE FUNCTION app_can_access_patient(p uuid) RETURNS boolean
LANGUAGE sql STABLE SECURITY DEFINER SET search_path = public AS $$
  SELECT p IS NOT NULL AND (
    app_device_patient_id() = p
    OR EXISTS (SELECT 1 FROM family_members fm
               WHERE fm.patient_id = p AND fm.user_id = app_user_id() AND fm.status = 'active')
  )
$$;

DO $$
DECLARE t text;
BEGIN
  FOREACH t IN ARRAY ARRAY[
    'family_members', 'devices', 'care_providers', 'generated_outputs', 'conversations', 'messages',
    'documents', 'consents', 'visits', 'transcript_segments', 'visit_speakers', 'source_refs',
    'output_sources', 'extractions', 'care_plan_items', 'medicine_ingredients', 'plan_changes',
    'allergies', 'allergy_status', 'allergy_conflicts', 'agent_runs', 'actions', 'reminders',
    'timeline_events', 'outbox', 'emergency_cards', 'emergency_card_access_log', 'recovery_entries'
  ] LOOP
    EXECUTE format('ALTER TABLE %I ENABLE ROW LEVEL SECURITY', t);
    EXECUTE format('CREATE POLICY p_member ON %I USING (app_can_access_patient(patient_id)) WITH CHECK (app_can_access_patient(patient_id))', t);
  END LOOP;
END $$;

-- Users: a person sees themselves and the people who share a patient with them, nobody else.
-- Login lookups and invitations run through the separate caresaathi_auth role (see roles_and_grants.sql).
CREATE FUNCTION app_shares_patient(u uuid) RETURNS boolean
LANGUAGE sql STABLE SECURITY DEFINER SET search_path = public AS $$
  SELECT EXISTS (
    SELECT 1 FROM family_members a
    JOIN family_members b ON b.patient_id = a.patient_id
    WHERE a.user_id = app_user_id() AND a.status = 'active'
      AND b.user_id = u AND b.status <> 'removed')
$$;
ALTER TABLE users ENABLE ROW LEVEL SECURITY;
CREATE POLICY p_self_or_shared ON users
  USING (id = app_user_id() OR app_shares_patient(id))
  WITH CHECK (id = app_user_id());

-- Model call metadata is tied to a patient when it has one.
ALTER TABLE model_calls ENABLE ROW LEVEL SECURITY;
CREATE POLICY p_model_calls ON model_calls
  USING (patient_id IS NULL OR app_can_access_patient(patient_id))
  WITH CHECK (patient_id IS NULL OR app_can_access_patient(patient_id));

ALTER TABLE patients ENABLE ROW LEVEL SECURITY;
CREATE POLICY p_member ON patients USING (app_can_access_patient(id)) WITH CHECK (app_can_access_patient(id) OR created_by = app_user_id());

-- The public Emergency Card route first validates the token in the API, then sets
-- app.public_card_patient_id for the transaction. These read-only policies expose only what the card shows.
DO $$
DECLARE t text;
BEGIN
  FOREACH t IN ARRAY ARRAY['care_plan_items', 'allergies', 'allergy_status', 'care_providers', 'medicine_ingredients', 'source_refs', 'plan_changes', 'generated_outputs', 'output_sources']
  LOOP
    EXECUTE format('CREATE POLICY p_public_card ON %I FOR SELECT USING (patient_id = app_public_card_patient_id())', t);
  END LOOP;
END $$;
CREATE POLICY p_public_card ON patients FOR SELECT USING (id = app_public_card_patient_id());

ALTER TABLE audit_log ENABLE ROW LEVEL SECURITY;
CREATE POLICY p_audit_read ON audit_log FOR SELECT USING (app_can_access_patient(patient_id));
CREATE POLICY p_audit_insert ON audit_log FOR INSERT WITH CHECK (true);

COMMIT;
