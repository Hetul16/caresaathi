#!/usr/bin/env bash
# Row-level security and privilege tests. Runs as the real app, worker and read-only roles,
# against the fixtures that test_schema.sql leaves in the scratch database.
set -uo pipefail
fails=0
PA=aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa
PB=bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb
PRIYA=11111111-1111-1111-1111-111111111111
STRANGER=22222222-2222-2222-2222-222222222222

# q ROLE "SET LOCAL ..." "query"  -> prints the single value, or ERROR:<message>
q() {
  local role="$1" setup="$2" sql="$3" out
  out=$(psql -U "$role" -Atq -v ON_ERROR_STOP=1 -c "BEGIN; $setup; $sql; ROLLBACK;" 2>&1 | grep -v -E '^(BEGIN|ROLLBACK|SET)$' | tail -1)
  case "$out" in *ERROR*) echo "ERROR:${out#*ERROR:  }" ;; *) echo "$out" ;; esac
}
check() { # label got expected
  if [[ "$2" == "$3" ]]; then echo "PASS  $1"; else echo "FAIL  $1 (got '$2', expected '$3')"; fails=$((fails+1)); fi
}
check_err() { # label got  (expects an error)
  if [[ "$2" == ERROR:* ]]; then echo "PASS  $1  [${2:0:80}]"; else echo "FAIL  $1 (no error: '$2')"; fails=$((fails+1)); fi
}

echo "--- row-level security ---"
check "member sees their own patient" \
  "$(q caresaathi_app "SET LOCAL app.user_id='$PRIYA'" "SELECT count(*) FROM patients WHERE id='$PA'")" 1
check "member cannot see another family's patient" \
  "$(q caresaathi_app "SET LOCAL app.user_id='$PRIYA'" "SELECT count(*) FROM patients WHERE id='$PB'")" 0
check "member sees their own care plan only" \
  "$(q caresaathi_app "SET LOCAL app.user_id='$PRIYA'" "SELECT count(DISTINCT patient_id) FROM care_plan_items")" 1
check "stranger sees none of the first family's care plan" \
  "$(q caresaathi_app "SET LOCAL app.user_id='$STRANGER'" "SELECT count(*) FROM care_plan_items WHERE patient_id='$PA'")" 0
check "no user context sees nothing" \
  "$(q caresaathi_app "SELECT 1" "SELECT count(*) FROM care_plan_items")" 0
check_err "stranger cannot insert into another family's care plan" \
  "$(q caresaathi_app "SET LOCAL app.user_id='$STRANGER'" "INSERT INTO timeline_events (patient_id, event_type, actor_type, summary) VALUES ('$PA','x','user','intrusion')")"
check "a paired device sees only its own patient" \
  "$(q caresaathi_app "SET LOCAL app.device_patient_id='$PA'" "SELECT count(DISTINCT patient_id) FROM care_plan_items")" 1

check "a member sees themselves and co-members, not strangers" \
  "$(q caresaathi_app "SET LOCAL app.user_id='$PRIYA'" "SELECT count(*) FROM users")" 1
check "stranger cannot read the first family's user record" \
  "$(q caresaathi_app "SET LOCAL app.user_id='$STRANGER'" "SELECT count(*) FROM users WHERE id='$PRIYA'")" 0
check "no user context sees no users (no email enumeration)" \
  "$(q caresaathi_app "SELECT 1" "SELECT count(*) FROM users")" 0
check "auth role can look up a user by email for login" \
  "$(q caresaathi_auth "SELECT 1" "SELECT count(*) FROM users WHERE email='priya@example.test'")" 1
check_err "auth role cannot read patient data" \
  "$(q caresaathi_auth "SELECT 1" "SELECT count(*) FROM care_plan_items")"
check "model call metadata follows patient access" \
  "$(q caresaathi_app "SET LOCAL app.user_id='$STRANGER'" "SELECT count(*) FROM model_calls WHERE patient_id='$PA'")" 0

echo "--- public Emergency Card route ---"
check "public card context can read the card's care plan" \
  "$(q caresaathi_app "SET LOCAL app.public_card_patient_id='$PA'" "SELECT count(*) > 0 FROM care_plan_items")" t
check "public card context can read allergies" \
  "$(q caresaathi_app "SET LOCAL app.public_card_patient_id='$PA'" "SELECT count(*) > 0 FROM allergies")" t
check "public card context cannot read documents" \
  "$(q caresaathi_app "SET LOCAL app.public_card_patient_id='$PA'" "SELECT count(*) FROM documents")" 0
check "public card context cannot read messages" \
  "$(q caresaathi_app "SET LOCAL app.public_card_patient_id='$PA'" "SELECT count(*) FROM messages")" 0
check "public card context cannot read another patient" \
  "$(q caresaathi_app "SET LOCAL app.public_card_patient_id='$PA'" "SELECT count(*) FROM care_plan_items WHERE patient_id='$PB'")" 0
# Under row-level security an UPDATE or DELETE that is not allowed affects zero rows (no error); an INSERT errors.
check "public card context: UPDATE changes zero rows" \
  "$(q caresaathi_app "SET LOCAL app.public_card_patient_id='$PA'" "WITH u AS (UPDATE allergy_status SET state='not_recorded' WHERE patient_id='$PA' RETURNING 1) SELECT count(*) FROM u")" 0
check "public card context: DELETE removes zero rows" \
  "$(q caresaathi_app "SET LOCAL app.public_card_patient_id='$PA'" "WITH d AS (DELETE FROM care_plan_items WHERE patient_id='$PA' RETURNING 1) SELECT count(*) FROM d")" 0
check_err "public card context: INSERT is rejected" \
  "$(q caresaathi_app "SET LOCAL app.public_card_patient_id='$PA'" "INSERT INTO timeline_events (patient_id, event_type, actor_type, summary) VALUES ('$PA','x','public_link','nope')")"
check "stored allergy status is unchanged after those attempts" \
  "$(psql -U postgres -Atqc "SELECT state FROM allergy_status WHERE patient_id='$PA'")" no_known_allergies

echo "--- privileges ---"
check_err "app role cannot update the audit log" \
  "$(q caresaathi_app "SET LOCAL app.user_id='$PRIYA'" "UPDATE audit_log SET action='tampered'")"
check_err "app role cannot delete from the audit log" \
  "$(q caresaathi_app "SET LOCAL app.user_id='$PRIYA'" "DELETE FROM audit_log")"
check "app role can append to the audit log" \
  "$(q caresaathi_app "SET LOCAL app.user_id='$PRIYA'" "INSERT INTO audit_log (actor_type, patient_id, action) VALUES ('user','$PA','test.append') RETURNING action")" test.append
check_err "worker role cannot update the audit log" \
  "$(q caresaathi_worker "SELECT 1" "UPDATE audit_log SET action='tampered'")"
check_err "app role cannot edit the drug reference list" \
  "$(q caresaathi_app "SET LOCAL app.user_id='$PRIYA'" "UPDATE drug_families SET review_status='reviewed', reviewed_by='me', reviewed_at=now()")"
check_err "app role cannot delete consents" \
  "$(q caresaathi_app "SET LOCAL app.user_id='$PRIYA'" "DELETE FROM consents")"
check_err "read-only role cannot write" \
  "$(q caresaathi_readonly "SELECT 1" "INSERT INTO timeline_events (patient_id, event_type, actor_type, summary) VALUES ('$PA','x','user','nope')")"
check "worker role works across patients (bypasses row-level security)" \
  "$(q caresaathi_worker "SELECT 1" "SELECT count(DISTINCT id) FROM patients")" 2

echo
if [[ $fails -eq 0 ]]; then echo "RLS TESTS: all passed"; else echo "RLS TESTS: $fails failed"; exit 1; fi
