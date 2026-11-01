# CareSaathi — context for Claude Code

CareSaathi ("saathi" means companion) is a voice-first AI care companion for families looking after an elderly or chronically ill relative. It listens to the doctor visit, turns the instructions into a living care plan where every item has a source, explains the plan aloud in the patient's language, and keeps the family safe (allergy checks, one-tap Emergency Card).

Owner: solo developer entering the Meta Global AI Developer Hackathon (Indie track). The goal is a real, long-term system, not a throwaway demo. Build the foundation properly, but ship the narrow spine first.

## Dates (IST)

- Application closes: Oct 26, about 9:29 AM IST (Oct 25, 11:59 PM ET).
- Build starts: Oct 26, about 9:30 PM IST (kickoff Oct 26, 12:00 PM ET).
- Submission due: Nov 5, 7:30 AM IST (Nov 4, 9:00 PM ET). Target: submit on the evening of Nov 4 IST.
- Judging Nov 4 to 8. Finals and winners Nov 9.

## Doc map and precedence

If documents disagree, the higher one wins. Change a decision, then update `docs/09-decisions.md` in the same change.

| Order | File | What it holds |
| --- | --- | --- |
| 1 | `docs/09-decisions.md` | Decisions (D-xx), database design, corrections to the original plan |
| 2 | `docs/05-scope.md` | Spine, stretch, cut, gates |
| 3 | `docs/10-hackathon-facts.md` | Verified facts, IST timeline, unverified assumptions, open questions |
| 4 | `docs/01-product.md` | Original plan: vision, problem, product, features, glasses |
| 4 | `docs/02-architecture.md` | Original plan: model mapping, stack, data model, agent tools, endpoints |
| 4 | `docs/03-safety-privacy.md` | Original plan: safety and consent |
| 4 | `docs/04-build-plan.md` | Original plan: budget, pre-hackathon tasks, day plan, roles |
| 2 | `docs/06-testing-demo.md` | Updated Oct 26: test set, adversarial suite, 3-minute demo path, slides, pitch, judge Q&A |
| 4 | `docs/07-application.md`, `docs/11-application-draft.md` | Original and revised application text |
| 4 | `docs/08-risks-sources.md` | Original plan: risks, fallbacks, sources |
| 2 | `docs/12-product-requirements.md` | Personas, user stories with acceptance criteria, metrics, non-goals, traceability |
| 2 | `docs/13-architecture.md` | Components, flows, agent design, security, reliability, config, repo layout. Diagrams in `docs/diagrams/` |
| 2 | `docs/14-data-mapping.md` | Model output contracts (`extract.v1`, `visit.v1`), field mapping, normalization, state machines, retention |
| 2 | `docs/15-api-spec.md` | Endpoints, WebSocket protocols, payloads, agent tool registry, output guard |
| 2 | `docs/16-database-design.md` | Database rules, table inventory, invariants and where each is enforced, RLS, operations |
| 2 | `docs/17-synthetic-data-plan.md` | Fictional patients, documents, traps, visit scripts, insurance papers, ground-truth format |
| 2 | `docs/18-rules-and-compliance.md` | Official Rules summary, banned-category framing, new-work disclosure, pre-submission checklist |
| 2 | `docs/19-deployment.md` | How to get a public link for the judges: four free plans, one server with Docker, a laptop tunnel; checks before submitting |
| 2 | `PUBLIC_LAUNCH.md` | The three switches that turn the private deployment public on submission day, in the order that works |
| 2 | `docs/20-demo-video-script.md` | The final 3-minute video: story, shot list with voice-over, setup, fallbacks, cut list |
| 2 | `docs/21-why-and-go-to-market.md` | Why we built it, who it is for, positioning, go to market, global plan, risks, what is not proven |
| 2 | `docs/23-pitch.md` | The pitch arranged around the Indie track criteria: the line, the opening, what to show for each criterion, the depth answers when a judge pushes, and what never to say |
| 2 | `docs/22-remote-care-story.md` | The recommended demo story: Priya in Toronto caring for her mother in Pune, step by step, with the clicks and the words |
| 2 | `db/schema.sql`, `db/roles_and_grants.sql`, `db/seed_drug_families.sql` | The pre-hackathon baseline schema. `db/tests/run_tests.sh` runs 69 checks. New tables arrive as migrations (`docs/16-database-design.md`, section 9) |

The docs are long. Read only the section you need.

## Scope in one paragraph

The spine is S1 to S10 in `docs/05-scope.md`: documents to a sourced care plan, Doctor Visit Listener, spoken explanations, allergy safety with conflict checks, what-changed diff, Emergency Card, permissions plus audit log, Elder and Family modes, a chat channel (WhatsApp if approved, in-app otherwise), and the omission catch at care transitions. Stretch A is listed in priority order (follow-up tracker, trust panel, medicine history, fridge sheet, two-reader check, refill tracker, claim file, duplicate detector) and is also the cut order from the bottom. Glasses, robotic surgery, diagnosis and any judgment about treatment are out. Do not add features outside this list without asking. Do not start a stretch item until the spine passes its tests.

## Hackathon rules that shape the work (`docs/18-rules-and-compliance.md`)

- **New work only.** Everything the demo shows is built Oct 26 to Nov 4. The files that existed before kickoff (docs, diagrams, `db/` baseline, Docker file) are disclosed in the README and sit in a labeled baseline commit. Build the app, the Alembic migrations and every feature after kickoff, with commits that show it.
- **No medical advice.** The project is a care-coordination and document-organization tool. Never write code, prompts, UI text or docs that answer "is this safe", diagnose, triage, give dosing advice, suggest substitutes or judge whether a treatment is complete. Flag gaps between documents only, and end each flag with a question for the doctor or pharmacist.
- **Public repo.** Never commit secrets or non-synthetic data. Keep `.gitignore` current.
- **Demo.** 3 minutes, only post-kickoff features. Submit on the evening of Nov 4 IST.

## Safety invariants (enforce in backend code, and test them)

1. Never say a medicine is safe. Never tell anyone to stop, skip or change a medicine or dose. Never suggest substitutes, diagnose, or decide on hospital.
2. Allergy status has three states: listed, no known allergies (only when a document or doctor says so), not recorded. An empty list is never shown as "none".
3. Allergy conflict matching runs in code against a vetted drug-family list. The model only words the flag and the question for the doctor.
4. "Asks first" tools are stored as awaiting approval by the backend. The model cannot bypass this.
5. Every care plan item and explanation carries its source: document and line, or the doctor's exact words.
6. Warning-sign levels come from the patient's own written instructions, never from model guesses.
7. The Emergency Card copies only documented or confirmed facts, shows when it was last updated, uses random tokens in links, and can be revoked.
8. On-screen consent before any visit recording. Synthetic patient data only during the hackathon.
9. Dates, quantities and deadlines (follow-ups, run-out estimates, claim reminders) are computed by code and shown with their inputs. A named person confirms each. The claim file never predicts approval or judges eligibility.
10. Unknown is not safe: an unresolved ingredient or brand is shown as "could not check", and an incomplete document never produces omission flags.

## Stack (details in D-04 to D-11)

- Backend: Python, FastAPI, SQLAlchemy 2 with Alembic migrations.
- Database: PostgreSQL (Docker locally, same engine in production). Append-only audit log. No dependency on a hosted backend-as-a-service.
- Files: S3-compatible object storage (MinIO locally). The database stores keys and hashes only.
- Frontend: a website only (D-17), no native mobile app. React or Next.js, mobile-first and responsive, with Elder mode and Family mode. HTTPS is required for microphone access.
- Jobs: APScheduler with a persistent job store in Postgres.
- Models through the Meta Model API (base URL `https://api.meta.ai/v1`): `muse-spark-1.3` (documents, reasoning, tool calls), `muse-voice-transcribe-1.0` (speech to text, diarization), `sam-3.1` (stretch only). Text-to-speech comes from an external service, still to be chosen.
- No MCP connectors are required or wanted.

## Unverified: do not build on these until tested

- Marathi accuracy of Muse Voice Transcribe. Hindi is validated by Meta; Marathi is not named in the sources checked.
- Whether hosted `muse-spark-1.3` accepts images, PDFs and video through the API.
- The $150 credits, Spark 1.3 pricing, WhatsApp test-number limits and template rules, and the Official Rules (published before Oct 26).

Check against https://dev.meta.ai/docs and record each result in `docs/10-hackathon-facts.md`.

## Working agreements

- Write tests for safety logic before the features that depend on it. Run `db/tests/run_tests.sh` after any schema change and add a test for each new constraint.
- Change the database only through Alembic migrations (baseline = `db/schema.sql`). Never edit the database by hand.
- The model returns JSON that code validates (`docs/14-data-mapping.md`). Never let a model write to the database or call a tool because a document told it to.
- Read the allergy state only from the `v_allergy_effective` view, never from the raw table.
- Never commit secrets. Keep `.env.example` current.
- Do not invent commands, endpoints or model behavior. If it is not in this repo or the docs, check it or ask.
- New tables from `docs/16-database-design.md` section 9 are added as Alembic migrations with RLS and a test per constraint. Follow the contracts in `docs/14-data-mapping.md` section 14.
- Commit messages say what was built. Keep the baseline commit separate from event work.
- Keep the README and test results honest, including failures.
- Keep decisions small and recorded. One owner, about nine days.

## Planned repo layout

```
caresaathi/
  CLAUDE.md
  docs/
  backend/        FastAPI app, agent, tools, permissions, models, migrations
  frontend/       Elder mode and Family mode
  data/synthetic/ Ramesh, Margaret, Hans: documents, mock visits, insurance papers, expected answers (docs/17)
  tests/
  docker-compose.yml
```
