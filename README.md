# CareSaathi

Voice-first AI care companion for families looking after an elderly or chronically ill relative. Website only. Built for the Meta Global AI Developer Hackathon (Indie track). Synthetic data only.

Status (Oct 27, 2026): the backend and website run locally and the whole spine is built: sign up, family invitations and permissions, document upload (offline reader only until the Meta key is tested), the sourced care plan, allergy checks in code, the omission catch, the Doctor Visit Listener (consent, recording, mock visits, pending changes), spoken explanations and an in-app chat that reads the plan back and refuses advice, the Emergency Card, Elder and Family modes, and a public trust panel. Stretch: follow-up tracker, refill estimates, medicine history, fridge sheet, duplicate-ingredient detector. Added Oct 28 (Stretch C): doctor link, care crew with a visible step trace, visit brief, label check (printed text only; loose pills refused) and a picture schedule in English, Hindi and Marathi. Not built: the claim file, the two-reader check's wiring, WhatsApp, a text-to-speech provider (the browser voice is used). **No call to the live Meta models has been made yet**; `backend/scripts/live_smoke.py` does that once the key is set.

Honest numbers: 310 backend tests pass against a real Postgres, and the 220-case adversarial suite passes 215. The 5 it does not pass are paraphrased reassurances the keyword guard misses; they are listed at `/trust`. The offline reader is a small rule-based stand-in: numbers measured with it describe the pipeline, not a model.

## What existed before the hackathon (Oct 24 to Oct 25, 2026)

Product and architecture documents, diagrams, a database design with SQL and tests, a Docker Compose file and a design mockup. These are in the first commit. Everything else in this repository, including all application code, migrations, prompts, tests and the demo, is built between Oct 26 and Nov 4, 2026. AI coding assistance (Claude Code) is used.

CareSaathi is a care-coordination and document-organization tool for family caregivers. It does not give medical advice.

## Start here

1. Read `CLAUDE.md` (Claude Code reads it automatically).
2. Install Docker Desktop. Copy `.env.example` to `.env` and fill in the passwords.
3. In `db/roles_and_grants.sql`, replace the `change-me-*` role passwords before the first start.
4. `docker compose up -d db minio`
5. Check: `docker compose exec db psql -U postgres -d caresaathi -c "\dt"`
6. Database tests (need the `psql` client): `PGHOST=localhost PGUSER=postgres ./db/tests/run_tests.sh` (it drops the `caresaathi_*` roles, so run it only against a throwaway Postgres)
7. Backend: `cd backend`, `python -m venv .venv`, `.venv\Scripts\pip install -e ".[dev]"`, `.venv\Scripts\alembic upgrade head`, `.venv\Scripts\python -m uvicorn app.main:app --port 8000`. Tests: `.venv\Scripts\python -m pytest tests` (API tests use a scratch database cloned from your dev schema).
8. Frontend: `cd frontend`, `npm install`, `npm run dev`, then open `http://localhost:3000`.
9. Demo data: sign up, then "Load the demo family". Synthetic documents and visit scripts live in `data/synthetic/`; `python data/synthetic/render.py` makes photos and PDFs for the live reader; `backend/scripts/live_smoke.py` measures the live models.

## Docs

`docs/09-decisions.md` wins over every other file. `docs/05-scope.md` defines the spine and the gates.

Last database test run: all passed (schema checks and row-level security checks).
