#!/usr/bin/env bash
# Rebuilds a scratch database and runs every database test.
# Needs a reachable Postgres 16 and a superuser. Example (docker compose up db):
#   PGHOST=localhost PGUSER=postgres ./db/tests/run_tests.sh
set -euo pipefail
here="$(cd "$(dirname "$0")/.." && pwd)"
DB="${TEST_DB:-caresaathi_schema_test}"
psql -qd postgres -c "DROP DATABASE IF EXISTS $DB" -c "CREATE DATABASE $DB"
# roles are cluster-wide: drop any left from a previous run
for r in caresaathi_app caresaathi_worker caresaathi_readonly caresaathi_auth; do
  psql -qd postgres -c "DROP OWNED BY $r" -c "DROP ROLE IF EXISTS $r" 2>/dev/null || true
done
export PGDATABASE="$DB"
psql -v ON_ERROR_STOP=1 -q -f "$here/schema.sql"
psql -v ON_ERROR_STOP=1 -q -f "$here/seed_drug_families.sql"
psql -v ON_ERROR_STOP=1 -q -f "$here/roles_and_grants.sql"
psql -v ON_ERROR_STOP=1 -q -f "$here/tests/test_schema.sql"
bash "$here/tests/test_rls.sh"
echo "ALL DATABASE TESTS PASSED"
