# Official Rules and how we comply

**Source:** the rules text below was pasted by the owner on Oct 26, 2026 from the hackathon materials. It was not independently verified, because the public event page only says the Official Rules are published before the event. If the full Official Rules say anything different, they win. Re-read them on Oct 27 and update this file.

## The rules (as pasted)

| Rule | Summary |
| --- | --- |
| New work only | Everything presented must be built during the hackathon, Oct 26 to Nov 4 |
| Identify contributions | The demo must show only features, code and functionality built during the event. If judges cannot tell what is new, the project is disqualified |
| Public repo | The submitted repository must be public |
| Teams | Maximum 4 people, solo allowed. One track (Indie or Startup). One person submits |
| Demo video | 3 minutes, required, and one of the main things judges score |
| Banned projects | Disqualified if they break legal, ethical or platform policies, or use code, data or assets without rights. Also avoid generic categories: AI medical or health advice, basic RAG apps, simple image analyzers, "AI for education" chatbots, job application screeners, nutrition coaches, personality analyzers, sports analyzers or coaches |
| Theme | Build for Your World, or Push the Frontier |
| Submit | By Wed Nov 4, 9:00 PM ET (Nov 5, 7:30 AM IST). Public repo, working demo video link, every team member added |
| Waiver | 18 or older and of legal age where you live. Meta and Cerebral Valley staff, contractors, government-affiliated people and their households cannot participate |

The pasted text does not mention AI coding assistants, ownership of the work or video hosting. Check the full Official Rules for those.

## Risk 1: the banned "AI medical or health advice" category (D-24)

CareSaathi touches healthcare, so the framing and the behavior both matter.

| What we do | What we never do |
| --- | --- |
| Copy what the doctor and the documents say, with the source | Answer "should he take this?", "is this safe?" or "what does this symptom mean?" |
| Compare documents with each other and flag differences for a human | Judge whether a prescription is right or whether a medicine is missing from the treatment |
| Match allergies in code and send a question to the doctor or pharmacist | Say a medicine is safe, or suggest a substitute |
| Repeat the doctor's written warning signs | Create new warning thresholds or triage |
| Organize paperwork (claim file) | Predict whether a claim will be approved |

Wording rules for the README, video, slides and UI:

- Call it a care-coordination and document-organization tool for family caregivers.
- Avoid "medical assistant", "health advisor", "diagnose", "treatment recommendation".
- Every flag ends with a question for the doctor or pharmacist.

Ask the organizers in writing (draft below). Keep their reply.

## Risk 2: the new-work rule (D-25)

Before kickoff the project already has planning documents, diagrams, a 37-table database schema with 69 tests, a Docker file and a design canvas. A judge could read the schema as pre-existing work.

Plan:

1. Ask the organizers whether pre-event planning, design documents and a database schema are allowed.
2. Make the first commit of the public repo a clearly labeled baseline: "Pre-hackathon planning and design (before Oct 26 kickoff). No application code."
3. List the baseline files in the README under "What existed before the hackathon".
4. Build everything the demo shows after kickoff, with commits that prove it: the Alembic migrations (re-creating the schema), backend, frontend, agent, prompts, tests, and every stretch feature.
5. If the organizers say the schema must not be reused, recreate it as migrations during the event from the design documents. The design documents are the plan; the migrations are new work.
6. In the demo, say what is new. Show only post-kickoff features.

README text to use:

> **What existed before the hackathon (Oct 24 to Oct 25, 2026):** product and architecture documents, diagrams, a database design with SQL and tests, a Docker Compose file and a design mockup. These are in the first commit. Everything else in this repository, including all application code, migrations, prompts, tests and the demo, was built between Oct 26 and Nov 4, 2026. AI coding assistance (Claude Code) was used and is described below.

## Email to the organizers (draft)

> Subject: Two quick questions on the Indie track (Meta Global AI Developer Hackathon)
>
> Hi, I am entering the Indie track with CareSaathi, a tool that helps family caregivers organize a relative's medical paperwork and doctor-visit instructions, with a source for every item. It does not give medical advice, diagnose or recommend treatment; it flags differences between documents and sends questions back to the doctor or pharmacist.
>
> 1. Does this fit the rule on avoiding "AI medical or health advice" projects?
> 2. Before kickoff I wrote planning documents and a database design. I will label them clearly as pre-event work and build all code during the event. Is that acceptable under the new-work rule?
>
> Thank you.

## Other requirements

| Item | Plan |
| --- | --- |
| Public repo without secrets | Add `.gitignore` for `.env` and audio; scan history before making the repo public; only synthetic data |
| Rights to assets | Own diagrams and mockups, invented brand names, fictional documents, a TTS service whose licence allows this use, fonts from Google Fonts |
| Solo submission | Add yourself as the only team member. Pick the Indie track |
| Demo video | 3 minutes, recorded Nov 2 as backup and Nov 3 as final; hosted where judges can open it without signing in |
| Deadline | Submit on the evening of Nov 4 IST, many hours before Nov 5 7:30 AM IST |
| Eligibility | Owner confirms they are 18 or older and not in an excluded group |
| AI coding tools | Disclose Claude Code in the README. Check whether the full Official Rules say anything about them |

## Pre-submission checklist

- [ ] Repository is public and opens in a private browser window
- [ ] No secrets in the files or the git history
- [ ] README has the pre-hackathon disclosure, the test results (including failures) and the labeled WhatsApp-style preview if WhatsApp is not live
- [ ] Demo video is 3 minutes or less and shows only post-kickoff features
- [ ] Track is Indie, and the project description does not use advice language
- [ ] Live link works over HTTPS
