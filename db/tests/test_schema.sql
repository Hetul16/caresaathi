-- Database safety tests. Run against a scratch database that already has schema.sql, seed_drug_families.sql
-- and roles_and_grants.sql applied:   psql -v ON_ERROR_STOP=1 -f db/tests/test_schema.sql
-- Part 1 runs as the owner and checks constraints, triggers and the allergy logic.
-- Part 2 (test_rls.sh) runs as the app role and checks row-level security.
-- Every case reports PASS or FAIL; the script exits non-zero if any case fails.

\set ON_ERROR_STOP on
SET client_min_messages = warning;

-- ---- fixtures (committed, reused by the RLS tests) -------------------------------------------
INSERT INTO users (id, email, display_name) VALUES
  ('11111111-1111-1111-1111-111111111111', 'priya@example.test', 'Priya (daughter)'),
  ('22222222-2222-2222-2222-222222222222', 'stranger@example.test', 'Stranger');
INSERT INTO patients (id, full_name, date_of_birth, preferred_language, created_by) VALUES
  ('aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa', 'Ramesh (synthetic)', '1958-03-01', 'mr', '11111111-1111-1111-1111-111111111111'),
  ('bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb', 'Other patient (synthetic)', '1950-01-01', 'hi', '22222222-2222-2222-2222-222222222222');
INSERT INTO family_members (patient_id, user_id, member_role, status, can_approve) VALUES
  ('aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa', '11111111-1111-1111-1111-111111111111', 'child', 'active', true),
  ('bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb', '22222222-2222-2222-2222-222222222222', 'child', 'active', true);
INSERT INTO documents (id, patient_id, doc_type, mime_type, byte_size, sha256, storage_key) VALUES
  ('dddddddd-dddd-dddd-dddd-dddddddddddd', 'aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa', 'prescription', 'image/jpeg', 1000, '\x01', 'p/a/d1.jpg');
INSERT INTO source_refs (id, patient_id, kind, document_id, page, line_start, quote) VALUES
  ('5c5c5c5c-0000-0000-0000-000000000001', 'aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa', 'document',
   'dddddddd-dddd-dddd-dddd-dddddddddddd', 1, 3, 'Tab Amoxicillin 500 mg 1-0-1 for 5 days');
INSERT INTO care_plan_items (id, patient_id, item_key, kind, title, details, source_ref_id) VALUES
  ('c1c1c1c1-0000-0000-0000-000000000001', 'aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa',
   'c1c1c1c1-aaaa-0000-0000-000000000001', 'medicine', 'Amoxicillin 500 mg', '{"frequency":"1-0-1"}',
   '5c5c5c5c-0000-0000-0000-000000000001');
INSERT INTO emergency_cards (id, patient_id, token_hash, token_hint, created_by) VALUES
  ('ecececec-0000-0000-0000-000000000001', 'aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa', '\xdeadbeef', 'beef', '11111111-1111-1111-1111-111111111111');

-- ---- test helpers -----------------------------------------------------------------------------
CREATE TEMP TABLE results (label text, ok boolean, detail text);

CREATE FUNCTION pg_temp.expect_error(p_label text, p_stmt text) RETURNS void LANGUAGE plpgsql AS $$
BEGIN
  BEGIN
    EXECUTE p_stmt;
    RAISE EXCEPTION 'no_error_raised' USING ERRCODE = 'P0001';
  EXCEPTION WHEN OTHERS THEN
    IF SQLERRM = 'no_error_raised' THEN
      INSERT INTO results VALUES (p_label, false, 'statement succeeded but should have been rejected');
    ELSE
      INSERT INTO results VALUES (p_label, true, left(SQLERRM, 90));
    END IF;
  END;
END $$;

CREATE FUNCTION pg_temp.expect_ok(p_label text, p_stmt text) RETURNS void LANGUAGE plpgsql AS $$
BEGIN
  BEGIN
    EXECUTE p_stmt;
    RAISE EXCEPTION 'rollback_probe' USING ERRCODE = 'P0001';
  EXCEPTION WHEN OTHERS THEN
    IF SQLERRM = 'rollback_probe' THEN
      INSERT INTO results VALUES (p_label, true, 'accepted');
    ELSE
      INSERT INTO results VALUES (p_label, false, left(SQLERRM, 90));
    END IF;
  END;
END $$;

CREATE FUNCTION pg_temp.expect_value(p_label text, p_query text, p_expected text) RETURNS void LANGUAGE plpgsql AS $$
DECLARE v text;
BEGIN
  EXECUTE p_query INTO v;
  INSERT INTO results VALUES (p_label, v IS NOT DISTINCT FROM p_expected, 'got ' || coalesce(v, 'NULL') || ', expected ' || p_expected);
END $$;

\o /dev/null

-- ---- sourcing: every fact needs a source ------------------------------------------------------
SELECT pg_temp.expect_error('source: document source with empty quote is rejected',
  $$INSERT INTO source_refs (patient_id, kind, document_id, quote) VALUES ('aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa','document','dddddddd-dddd-dddd-dddd-dddddddddddd','  ')$$);
SELECT pg_temp.expect_error('source: visit_segment source without a segment is rejected',
  $$INSERT INTO source_refs (patient_id, kind, quote) VALUES ('aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa','visit_segment','take it daily')$$);
SELECT pg_temp.expect_error('plan: care plan item without a source is rejected',
  $$INSERT INTO care_plan_items (patient_id, item_key, kind, title) VALUES ('aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa', gen_random_uuid(), 'medicine', 'Mystery tablet')$$);

-- ---- warning-sign levels come only from written instructions ----------------------------------
SELECT pg_temp.expect_error('plan: warning_sign without an alert level is rejected',
  $$INSERT INTO care_plan_items (patient_id, item_key, kind, title, source_ref_id) VALUES ('aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa', gen_random_uuid(), 'warning_sign', 'Swelling', '5c5c5c5c-0000-0000-0000-000000000001')$$);
SELECT pg_temp.expect_error('plan: alert level on a non-warning item is rejected',
  $$INSERT INTO care_plan_items (patient_id, item_key, kind, title, alert_level, source_ref_id) VALUES ('aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa', gen_random_uuid(), 'medicine', 'X', 'emergency', '5c5c5c5c-0000-0000-0000-000000000001')$$);
SELECT pg_temp.expect_ok('plan: warning_sign with a level and source is accepted',
  $$INSERT INTO care_plan_items (patient_id, item_key, kind, title, alert_level, source_ref_id) VALUES ('aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa', gen_random_uuid(), 'warning_sign', 'Call clinic if swelling increases', 'call_doctor_today', '5c5c5c5c-0000-0000-0000-000000000001')$$);

-- ---- versioning and immutability --------------------------------------------------------------
SELECT pg_temp.expect_error('plan: editing a stored item title is rejected',
  $$UPDATE care_plan_items SET title = 'Amoxicillin 1000 mg' WHERE id = 'c1c1c1c1-0000-0000-0000-000000000001'$$);
SELECT pg_temp.expect_error('plan: editing a stored item details is rejected',
  $$UPDATE care_plan_items SET details = '{"frequency":"2-0-2"}' WHERE id = 'c1c1c1c1-0000-0000-0000-000000000001'$$);
SELECT pg_temp.expect_ok('plan: flipping is_current on a superseded version is accepted',
  $$UPDATE care_plan_items SET is_current = false WHERE id = 'c1c1c1c1-0000-0000-0000-000000000001'$$);
SELECT pg_temp.expect_error('plan: two current versions of the same item are rejected',
  $$INSERT INTO care_plan_items (patient_id, item_key, version, kind, title, source_ref_id) VALUES ('aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa','c1c1c1c1-aaaa-0000-0000-000000000001', 2, 'medicine', 'Amoxicillin 250 mg', '5c5c5c5c-0000-0000-0000-000000000001')$$);

-- ---- allergy states: an empty list is never "none" --------------------------------------------
SELECT pg_temp.expect_value('allergy: patient with nothing recorded is not_recorded',
  $$SELECT state::text FROM v_allergy_effective WHERE patient_id = 'aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa'$$, 'not_recorded');
SELECT pg_temp.expect_error('allergy: no_known_allergies without a source is rejected',
  $$INSERT INTO allergy_status (patient_id, state) VALUES ('aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa', 'no_known_allergies')$$);
SELECT pg_temp.expect_error('allergy: family-reported allergy without confirmation is rejected',
  $$INSERT INTO allergies (patient_id, allergy_key, substance, substance_normalized, source_type, source_ref_id) VALUES ('aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa', gen_random_uuid(), 'penicillin', 'penicillin', 'family_reported', '5c5c5c5c-0000-0000-0000-000000000001')$$);

-- A document says "no known allergies": the effective state follows it while no allergy is listed.
INSERT INTO allergy_status (patient_id, state, source_ref_id)
  VALUES ('aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa', 'no_known_allergies', '5c5c5c5c-0000-0000-0000-000000000001');
SELECT pg_temp.expect_value('allergy: documented no_known_allergies is shown as such',
  $$SELECT state::text FROM v_allergy_effective WHERE patient_id = 'aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa'$$, 'no_known_allergies');

-- Record a penicillin allergy (a drug class) and check the view flips to "listed" even though the status row says none.
INSERT INTO allergies (id, patient_id, allergy_key, substance, substance_normalized, substance_id, family_id, reaction, severity, source_type, source_ref_id)
SELECT 'a1a1a1a1-0000-0000-0000-000000000001', 'aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa', 'a1a1a1a1-aaaa-0000-0000-000000000001',
       'penicillin', 'penicillin',
       (SELECT id FROM drug_substances WHERE substance_normalized = 'penicillin'),
       (SELECT id FROM drug_families WHERE code = 'penicillins'),
       'rash', 'moderate', 'document', '5c5c5c5c-0000-0000-0000-000000000001';
SELECT pg_temp.expect_value('allergy: a listed allergy overrides a stale no_known_allergies status',
  $$SELECT state::text FROM v_allergy_effective WHERE patient_id = 'aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa'$$, 'listed');
SELECT pg_temp.expect_error('allergy: editing a stored allergy reaction is rejected',
  $$UPDATE allergies SET reaction = 'none' WHERE id = 'a1a1a1a1-0000-0000-0000-000000000001'$$);

-- ---- allergy conflict finder: deterministic, never says "safe" --------------------------------
-- Restore the amoxicillin item as current so the finder can use it (the earlier probe was rolled back).
INSERT INTO medicine_ingredients (patient_id, item_id, ingredient_raw, ingredient_normalized, substance_id)
SELECT 'aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa', 'c1c1c1c1-0000-0000-0000-000000000001', 'Amoxicillin', 'amoxicillin',
       (SELECT id FROM drug_substances WHERE substance_normalized = 'amoxicillin');
SELECT pg_temp.expect_value('conflict: penicillin allergy vs amoxicillin is a drug_family match',
  $$SELECT string_agg(match::text, ',') FROM find_allergy_conflicts('c1c1c1c1-0000-0000-0000-000000000001')$$, 'drug_family');

-- A second medicine: ibuprofen, in a different family. No match found, which must not be read as "safe".
INSERT INTO care_plan_items (id, patient_id, item_key, kind, title, source_ref_id) VALUES
  ('c2c2c2c2-0000-0000-0000-000000000002', 'aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa', gen_random_uuid(), 'medicine', 'Ibuprofen 400 mg', '5c5c5c5c-0000-0000-0000-000000000001');
INSERT INTO medicine_ingredients (patient_id, item_id, ingredient_raw, ingredient_normalized, substance_id)
SELECT 'aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa', 'c2c2c2c2-0000-0000-0000-000000000002', 'Ibuprofen', 'ibuprofen',
       (SELECT id FROM drug_substances WHERE substance_normalized = 'ibuprofen');
SELECT pg_temp.expect_value('conflict: unrelated family returns no rows (not "safe", just no match)',
  $$SELECT count(*)::text FROM find_allergy_conflicts('c2c2c2c2-0000-0000-0000-000000000002')$$, '0');

-- A third medicine with an ingredient the reference list does not know: must come back as unresolved.
INSERT INTO care_plan_items (id, patient_id, item_key, kind, title, source_ref_id) VALUES
  ('c3c3c3c3-0000-0000-0000-000000000003', 'aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa', gen_random_uuid(), 'medicine', 'Brandname-XR', '5c5c5c5c-0000-0000-0000-000000000001');
INSERT INTO medicine_ingredients (patient_id, item_id, ingredient_raw, ingredient_normalized, substance_id)
  VALUES ('aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa', 'c3c3c3c3-0000-0000-0000-000000000003', 'Zorbamycin', 'zorbamycin', NULL);
SELECT pg_temp.expect_value('conflict: ingredient missing from the reference list is returned as unresolved',
  $$SELECT string_agg(match::text, ',') FROM find_allergy_conflicts('c3c3c3c3-0000-0000-0000-000000000003')$$, 'unresolved');

-- Direct match: a specific amoxicillin allergy against amoxicillin.
INSERT INTO allergies (id, patient_id, allergy_key, substance, substance_normalized, substance_id, source_type, source_ref_id)
SELECT 'a2a2a2a2-0000-0000-0000-000000000002', 'aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa', 'a2a2a2a2-aaaa-0000-0000-000000000002',
       'amoxicillin', 'amoxicillin', (SELECT id FROM drug_substances WHERE substance_normalized = 'amoxicillin'),
       'document', '5c5c5c5c-0000-0000-0000-000000000001';
SELECT pg_temp.expect_value('conflict: specific allergy vs the same drug includes a direct match',
  $$SELECT string_agg(match::text, ',' ORDER BY match::text) FROM find_allergy_conflicts('c1c1c1c1-0000-0000-0000-000000000001')$$, 'direct,drug_family');
SELECT pg_temp.expect_error('conflict: unresolved conflict that names an allergy is rejected',
  $$INSERT INTO allergy_conflicts (patient_id, allergy_id, care_plan_item_id, match) VALUES ('aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa','a1a1a1a1-0000-0000-0000-000000000001','c3c3c3c3-0000-0000-0000-000000000003','unresolved')$$);

-- ---- outputs must carry a source --------------------------------------------------------------
SELECT pg_temp.expect_error('output: passed explanation with no source is rejected',
  $$SET CONSTRAINTS trg_output_has_source IMMEDIATE;
    INSERT INTO generated_outputs (patient_id, output_type, body, guard_status) VALUES ('aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa','explanation','Take this tablet twice a day','pass')$$);
SELECT pg_temp.expect_ok('output: passed explanation with a source is accepted',
  $$SET CONSTRAINTS trg_output_has_source IMMEDIATE;
    WITH o AS (INSERT INTO generated_outputs (patient_id, output_type, body, guard_status) VALUES ('aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa','explanation','Take this tablet twice a day','pass') RETURNING id, patient_id)
    INSERT INTO output_sources (output_id, source_ref_id, patient_id) SELECT id, '5c5c5c5c-0000-0000-0000-000000000001', patient_id FROM o$$);
SELECT pg_temp.expect_ok('output: exempt chat reply with no source is accepted',
  $$SET CONSTRAINTS trg_output_has_source IMMEDIATE;
    INSERT INTO generated_outputs (patient_id, output_type, body, guard_status, source_exempt) VALUES ('aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa','chat_reply','Please say that again','pass',true)$$);
SELECT pg_temp.expect_error('output: source exemption on a non-chat output is rejected',
  $$INSERT INTO generated_outputs (patient_id, output_type, body, guard_status, source_exempt) VALUES ('aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa','allergy_flag','x','pass',true)$$);
SELECT pg_temp.expect_ok('output: blocked output with no source is accepted (it is never shown)',
  $$SET CONSTRAINTS trg_output_has_source IMMEDIATE;
    INSERT INTO generated_outputs (patient_id, output_type, body, guard_status) VALUES ('aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa','explanation','this medicine is safe','blocked')$$);

-- ---- approvals: ask-first actions cannot run without a named approver -------------------------
SELECT pg_temp.expect_error('action: ask_first action marked done without an approver is rejected',
  $$INSERT INTO actions (patient_id, tool, permission, status) VALUES ('aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa','send_family_message','ask_first','done')$$);
SELECT pg_temp.expect_ok('action: ask_first action waiting for approval is accepted',
  $$INSERT INTO actions (patient_id, tool, permission, status) VALUES ('aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa','send_family_message','ask_first','awaiting_approval')$$);
SELECT pg_temp.expect_ok('action: approved ask_first action with approver is accepted',
  $$INSERT INTO actions (patient_id, tool, permission, status, approved_by, approved_at) VALUES ('aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa','send_family_message','ask_first','done','11111111-1111-1111-1111-111111111111', now())$$);
SELECT pg_temp.expect_error('plan change: applied without a decision is rejected',
  $$INSERT INTO plan_changes (patient_id, change_type, source_ref_id, status) VALUES ('aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa','new','5c5c5c5c-0000-0000-0000-000000000001','applied')$$);

-- ---- consent before recording -----------------------------------------------------------------
INSERT INTO consents (id, patient_id, consent_type, subject_role, given_by_user_id, given_by_name, consent_text_version) VALUES
  ('c0c0c0c0-0000-0000-0000-000000000001', 'aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa', 'visit_recording', 'patient', '11111111-1111-1111-1111-111111111111', 'Priya for Ramesh', 'v1'),
  ('c0c0c0c0-0000-0000-0000-000000000002', 'aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa', 'visit_recording', 'doctor', NULL, 'Dr Kulkarni', 'v1');
SELECT pg_temp.expect_error('visit: a visit with no consent is rejected',
  $$INSERT INTO visits (patient_id, started_by) VALUES ('aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa','11111111-1111-1111-1111-111111111111')$$);
SELECT pg_temp.expect_error('visit: the same consent used for patient and doctor is rejected',
  $$INSERT INTO visits (patient_id, started_by, patient_consent_id, doctor_consent_id) VALUES ('aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa','11111111-1111-1111-1111-111111111111','c0c0c0c0-0000-0000-0000-000000000001','c0c0c0c0-0000-0000-0000-000000000001')$$);
SELECT pg_temp.expect_ok('visit: a visit with both consents is accepted',
  $$INSERT INTO visits (patient_id, started_by, patient_consent_id, doctor_consent_id) VALUES ('aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa','11111111-1111-1111-1111-111111111111','c0c0c0c0-0000-0000-0000-000000000001','c0c0c0c0-0000-0000-0000-000000000002')$$);

-- ---- audit log is append-only -----------------------------------------------------------------
INSERT INTO audit_log (actor_type, actor_id, patient_id, action, entity_type, entity_id)
  VALUES ('user', '11111111-1111-1111-1111-111111111111', 'aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa', 'allergy.confirmed', 'allergy', 'a1a1a1a1-0000-0000-0000-000000000001');
SELECT pg_temp.expect_error('audit: updating a row is rejected', $$UPDATE audit_log SET action = 'x'$$);
SELECT pg_temp.expect_error('audit: deleting a row is rejected', $$DELETE FROM audit_log$$);
SELECT pg_temp.expect_error('audit: truncating is rejected', $$TRUNCATE audit_log$$);

-- ---- misc invariants --------------------------------------------------------------------------
SELECT pg_temp.expect_error('drug family: marked reviewed without a reviewer is rejected',
  $$UPDATE drug_families SET review_status = 'reviewed' WHERE code = 'penicillins'$$);
SELECT pg_temp.expect_error('device: token issued without a family approver is rejected',
  $$INSERT INTO devices (patient_id, label, token_hash) VALUES ('aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa','Papa phone','\xabcd')$$);
SELECT pg_temp.expect_error('recovery: an alert level without a source instruction is rejected',
  $$INSERT INTO recovery_entries (patient_id, episode_label, entry_date, day_number, alert_level) VALUES ('aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa','knee','2026-11-01',5,'call_doctor_today')$$);

\o

-- ---- report -----------------------------------------------------------------------------------
SELECT CASE WHEN ok THEN 'PASS' ELSE 'FAIL' END AS result, label, detail FROM results ORDER BY ok, label;
SELECT count(*) FILTER (WHERE ok) AS passed, count(*) FILTER (WHERE NOT ok) AS failed FROM results;
DO $$
BEGIN
  IF EXISTS (SELECT 1 FROM pg_temp.results WHERE NOT ok) THEN
    RAISE EXCEPTION 'schema tests failed';
  END IF;
END $$;
