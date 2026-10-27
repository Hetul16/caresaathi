# CareSaathi

Voice-first AI care companion for families looking after an elderly or chronically ill relative. Website only. Built for the Meta Global AI Developer Hackathon (Indie track). Synthetic data only.

Status (Oct 27, 2026): the backend and website run locally. Working: sign up and sign in, document upload (offline reader only, no live model yet), the sourced care plan, allergy conflicts found in code, confirmations, pending-change decisions, approvals, the Emergency Card (create, public link, revoke) and the omission catch. 90 backend tests pass against a real Postgres. Not built yet: the Doctor Visit Listener, spoken explanations, the chat channel, and any call to the live Meta models (not yet tested).

## What existed before the hackathon (Oct 24 to Oct 25, 2026)

Product and architecture documents, diagrams, a database design with SQL and tests, a Docker Compose file and a design mockup. These are in the first commit. Everything else in this repository, including all application code, migrations, prompts, tests and the demo, is built between Oct 26 and Nov 4, 2026. AI coding assistance (Claude Code) is used.

CareSaathi is a care-coordination and document-organization tool for family caregivers. It does not give medical advice.

## Start here

1. Read `CLAUDE.md` (Claude Code reads it automatically).
2. Install Docker Desktop. Copy `.env.example` to `.env` and fill in the passwords.
3. In `db/roles_and_grants.sql`, replace the `change-me-*` role passwords before the first start.
4. `docker compose up -d db minio`
5. Check: `docker compose exec db psql -U postgres -d caresaathi -c "\dt"`
6. Database tests (need the `psql` client): `PGHOST=localhost PGUSER=postgres ./db/tests/run_tests.sh`

## Docs

`docs/09-decisions.md` wins over every other file. `docs/05-scope.md` defines the spine and the gates.

Last database test run: all passed (schema checks and row-level security checks).
