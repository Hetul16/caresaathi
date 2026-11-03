# CareSaathi

**A voice-first care companion for the family of an elderly or chronically ill person.** It reads the papers, listens
to the doctor visit, and turns both into one care plan where every line shows where it came from. It finds the places
where two documents disagree and sends each one to the doctor as a question. It never gives medical advice.

Built solo for the **Meta Global AI Developer Hackathon**, Indie track, between Oct 26 and Nov 4, 2026. Website only.
Fictional patients and documents throughout: no real medical records touch it.

| | |
| --- | --- |
| **Live site** | https://caresaathi-phi.vercel.app |
| **Demo video, 3 minutes** | _fill in before submitting_ |
| **Our own measurements, failures included** | `/trust` on the live site |

## Why this exists

Ramesh is 72 and just home from hospital with four papers: an allergy card, a clinic prescription, a discharge
summary, and a second doctor's prescription. The papers are in English; he reads Hindi. One of them leaves out a
medicine an earlier one listed. A new prescription names a drug in the same family as the allergy written on the card
in the drawer. His daughter Priya is in another city. Nobody has done anything wrong. The information is simply in
too many places, and the one person who could spot the gap is not in the room.

**What the evidence says.** In a study of 339 older adults after an ICU stay, 64% had an unintentional medication
discrepancy at a care transition, and **96% of those were omissions** -- a medicine on the earlier paper simply
missing from the later one. Patients with a discrepancy had about twice the risk of an emergency visit within a month
(hazard ratio 2.13). Source: PMC11654400.

**What that evidence does not say.** It is one hospital, retrospective, and the abstract and the results report
slightly different figures (68% and 64%). It supports the problem. It says nothing about our solution: we have not
measured whether CareSaathi changes any outcome for any family, and we do not claim it prevents emergency visits.

**Why a coordination tool and not an advice tool.** A model that answers "is this safe?" can be confidently wrong in
a way that hurts someone. The harm here is mostly lost information, not missing intelligence. So the product's job is
to hold the information together, show where each fact came from, notice the gaps, and route every judgement to the
person qualified to make it.

## What it does

```mermaid
flowchart LR
  docs["Phone photos and PDFs<br/>prescriptions, discharge<br/>summaries, labels"]
  room["The doctor's own words<br/>recorded after on-screen consent"]

  read["<b>Read it</b><br/>Muse Spark reads the papers.<br/>Muse Voice Transcribe<br/>writes down the room."]

  allergy["Allergy conflict<br/>against a vetted<br/>drug-family list"]
  omit["What the newest<br/>paper quietly dropped"]
  dates["Follow-up dates and<br/>refill run-out, with<br/>their inputs shown"]

  plan[("<b>The care plan</b><br/>every line carries its source:<br/>document and line, or the<br/>doctor's exact words")]

  elder["<b>Elder mode</b><br/>big type, spoken aloud,<br/>Hindi / Marathi / English"]
  fam["<b>Family mode</b><br/>sources, approvals,<br/>open questions, audit log"]
  card["<b>Emergency Card</b><br/>one link, no login,<br/>revocable"]

  docs --> read
  room --> read
  read -->|"JSON that code validates"| allergy
  read --> omit
  read --> dates
  allergy -->|"a flag is a question<br/>for the doctor,<br/>never an answer"| plan
  omit --> plan
  dates --> plan
  read --> plan
  plan --> elder
  plan --> fam
  plan --> card
```

Nothing here decides whether a medicine is safe. It finds the place where two papers disagree, and it keeps that
question open until a person writes down the answer.

## Model proposes, code decides

The model never has the last word on anything that matters. It proposes structured JSON, and it writes sentences.
Every number, date, allergy verdict and plan item is computed in code, and anything the model wrote has to be
grounded in a fact already stored.

```mermaid
flowchart TB
  A["A document, or a recording of the visit"] --> B["<b>Muse Spark proposes</b><br/>structured JSON only, no prose"]
  B --> C{"Does it validate?<br/>extract.v1 / visit.v1"}
  C -->|"no"| X["Rejected. Nothing is stored,<br/>and nothing is shown."]
  C -->|"yes"| D["Stored with its source"]

  D --> E1["Allergy match in code<br/>against the vetted list"]
  D --> E2["Dates and arithmetic in code,<br/>shown with their inputs"]
  D --> E3["Omission, and only when<br/>the document is complete"]

  E1 --> F["<b>Now the model writes</b><br/>the wording of the flag and<br/>the question for the doctor"]
  E2 --> F
  E3 --> F

  F --> G{"Output guard, and in live mode<br/>a second-pass judge that fails closed"}
  G -->|"ungrounded, or reads<br/>like reassurance"| Y["Blocked, and the block is logged"]
  G -->|"every sentence names a stored fact,<br/>the doctor, or the pharmacist"| H["On the screen, with its source"]
```

An unresolved ingredient is shown as **could not check**, never as safe. An empty allergy list is shown as
**not recorded**, never as *none*.

## What we measured

Every number below was produced by a script in this repository and can be regenerated. The failures are in the table
on purpose, and they are on the `/trust` page too.

| Check | Result |
| --- | --- |
| Fictional documents read into the care plan (Muse Spark) | 14 / 14 |
| The allergy card | 2 / 2 |
| Second-pass judge catching unsafe wording | 40 / 40 |
| Second-pass judge leaving plain read-backs alone | **7 / 8** -- one plain sentence was wrongly blocked |
| Printed medicine labels | 5 / 5 |
| Scripted doctor visits, Hindi | 3 / 3 |
| Scripted doctor visits, English | 3 / 3 |
| Adversarial safety suite, run offline | **222 / 227** -- five paraphrased reassurances the keyword guard cannot catch |
| Backend tests against a real PostgreSQL | 447 passing |
| The whole product end to end, over HTTP, invariants checked on real responses | 23 / 23 |
| The same product in a real browser on a phone-sized screen, all 18 tabs | 20 / 20 |

The five misses are one tuned paraphrase probe and four held-out ones: sentences that reassure without using a word a
keyword list can catch. In live mode the suite runs 206 of 211 (it skips the 16 offline-reader cases), and those five
are the cases the second-pass judge exists to cover.

Speech, measured with Muse Voice Transcribe on the public FLEURS test set (word error rate, lower is better):

| Language | Without a language hint | With a language hint |
| --- | --- | --- |
| English | 8.4% | 8.9% |
| Hindi | 10.2% | 10.1% |
| Marathi | 57.3% | **23.2%** |

Marathi is why the app always sends the language hint, and why Marathi stays labelled experimental in the interface.

**Not measured.** A real recorded Hinglish conversation in a consulting room. Real phone photographs of medicine
packaging. Whether any of this changes an outcome for a family.

Raw report: `data/live_results/latest.json`, regenerated by `backend/scripts/live_report.py` and `speech_eval.py`.
The end-to-end row is `backend/scripts/walkthrough.py`, which drives the website rather than the API, so a pass
also proves the proxy, the HttpOnly refresh cookie and the site gate. It takes a URL, so the same 23 checks can
be run against the deployment.

## Who sees what

```mermaid
flowchart LR
  pt(["The patient"]) --> em["<b>Elder mode</b><br/>one mic button, tap to mark a dose,<br/>a pain number. No way out of it<br/>except the Emergency Card."]
  fa(["Family, in the house or abroad"]) --> fm["<b>Family mode</b><br/>the plan with its sources, daily<br/>check-ins, a task board, and every<br/>flag held open as a question"]
  dr(["The doctor"]) --> dl["<b>Doctor link</b><br/>reads the question, replies in their<br/>own words. The reply is quoted,<br/>never summarised."]
  er(["Hospital, in an emergency"]) --> ec["<b>Emergency Card</b><br/>random token, no login, documented<br/>facts only, and the date it was<br/>last updated"]

  fm --> perm{"Every right is granted<br/>per person"}
  perm -->|"a right that cannot be granted<br/>is shown as unavailable"| ask["Anything marked <b>asks first</b> waits as a<br/>pending change until a named person<br/>approves it. The model cannot bypass this."]
  ask --> audit[("Append-only audit log")]
```

## How it runs

```mermaid
flowchart LR
  b["<b>Browser</b><br/>Next.js, mobile-first.<br/>HTTPS, because the mic needs it."]
  a["<b>FastAPI</b><br/>agent, tools, safety engine,<br/>scheduled jobs"]
  d[("<b>PostgreSQL</b><br/>row-level security,<br/>append-only audit log")]
  f[("<b>Object storage</b><br/>the database keeps<br/>keys and SHA-256 only")]
  m["<b>Meta Model API</b><br/>muse-spark-1.3<br/>muse-voice-transcribe-1.0"]

  b -->|"same-origin proxy, so the refresh<br/>cookie stays first-party"| a
  a --> d
  a --> f
  a -->|"every call priced and capped;<br/>the spend ledger is a table"| m
```

One free plan per box: Vercel for the website, Render for the API, Neon for PostgreSQL. Files are written to the
container's own disk rather than object storage, because every S3 provider wanted a payment card and this build had to
cost nothing (D-73); a restart therefore costs a visitor one press of "Load the demo family", and nothing else.
Steps in `docs/19-deployment.md`; `PUBLIC_LAUNCH.md` is the order to flip it public.

## What is built, and what is not

**Built and tested:** documents and photos to a sourced care plan, the Doctor Visit Listener with on-screen consent,
spoken explanations in English, Hindi and Marathi, allergy conflict checks in code, the omission catch, the
what-changed diff, the Emergency Card, per-person permissions with an append-only audit log, Elder and Family modes,
an in-app chat that refuses advice, a doctor link with verbatim replies, label check on printed text, an outcomes
board that holds every flag open as a question, daily check-ins and a family task board, refill estimates, a
duplicate-ingredient detector, a two-reader check for unclear pages, a spend cap on live model calls, and the public
trust panel.

**Not built:** the insurance claim file, WhatsApp as a channel, and a studio-quality voice (the browser's own voice is
used). Marathi speech is experimental. No real-patient data, by design.

## Where to look

- **Safety rules in code:** `backend/app/safety/` (output guard, permission gate, injection detector, two-reader
  comparison), the database CHECKs in `backend/migrations/`, and one test file per feature in `backend/tests/`.
- **How the allergy check is grounded:** the drug-family list is checked against the WHO ATC classification
  (`data/reference/atc_snapshot.json`, rebuilt by `backend/scripts/atc_check.py`). A flag shows the ATC group behind
  it. Two of seventeen memberships came back unconfirmed and say so on screen. It is not a pharmacist review.
- **The demo story:** `docs/22-remote-care-story.md` follows Priya abroad caring for her mother in Pune, click by
  click. `docs/20-demo-video-script.md` is the video.
- **Why it exists, who pays, what is unproven:** `docs/21-why-and-go-to-market.md`.
- **Decisions and the reasoning behind them:** `docs/09-decisions.md` wins over every other document;
  `docs/13-architecture.md` is the system map.

## Run it yourself

1. Install Docker Desktop. Copy `.env.example` to `.env` and fill it in. In `db/roles_and_grants.sql`, replace the
   `change-me-*` role passwords.
2. `docker compose up -d db minio`
3. Backend: `cd backend`, `python -m venv .venv`, `.venv\Scripts\pip install -e ".[dev]"`,
   `.venv\Scripts\alembic upgrade head`, `.venv\Scripts\python -m uvicorn app.main:app --port 8000`
4. Frontend: `cd frontend`, `npm install`, `npm run dev`, then open `http://localhost:3000`
5. Sign up, then **Load the demo family**. The fictional documents and visit scripts live in `data/synthetic/`;
   `python data/synthetic/render.py` turns them into photographs and PDFs.
6. Walk the whole product, the way a judge would, with both servers running:
   `backend/.venv/Scripts/python backend/scripts/walkthrough.py` (23 checks, including the safety invariants).
7. And in a real browser: `.venv\Scripts\pip install -e ".[browser]"`, `.venv\Scripts\playwright install chromium`,
   then `backend/.venv/Scripts/python backend/scripts/browser_check.py` (20 checks: sign-up, the demo family, every
   tab, Elder mode in Hindi, the public card, and nothing in the browser console).
8. Tests: `backend/.venv/Scripts/python -m pytest tests` (447) and
   `PGHOST=localhost PGUSER=postgres ./db/tests/run_tests.sh` (database constraints; it drops the `caresaathi_*`
   roles, so point it at a throwaway PostgreSQL).

## What existed before the hackathon (Oct 24 to 25, 2026)

Product and architecture documents, the diagrams in `docs/diagrams/`, a database design with SQL and tests, a Docker
Compose file and a design mockup. These sit in the first commit. Everything else in this repository -- all
application code, migrations, prompts, tests, the diagrams in this README and the demo -- was built between Oct 26
and Nov 4, 2026, and the commit history shows the order. AI coding assistance (Claude Code) was used throughout.

## Not medical advice

CareSaathi is a care-coordination and document-organization tool for family caregivers. It does not diagnose, does
not triage, does not give dosing advice, does not suggest substitutes, and never says a medicine is safe or tells
anyone to stop, skip or change one. Every gap it finds between two documents ends in a question for the doctor or
pharmacist.

## Attribution

This product uses publicly available data from the U.S. National Library of Medicine (NLM), National Institutes of
Health, Department of Health and Human Services; NLM is not responsible for the product and does not endorse or
recommend this or any other product. The drug-class data is the WHO ATC classification served through NLM's RxClass
API (https://rxnav.nlm.nih.gov), looked up once and committed as `data/reference/atc_snapshot.json`.
