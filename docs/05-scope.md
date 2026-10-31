# Scope: spine, stretch, cut

**Status:** Updated Oct 26, 2026 on the owner's direction. More helpful features were added (including the insurance claim file) and the glasses idea was dropped. The stretch lists are in priority order, and that order is also the cut order from the bottom (D-26).

## Why this exists

The original plan had about 13 features across three models plus WhatsApp and glasses. The owner is solo, the Indie track is judged on creativity, technical ambition and whether it works, and the build window is about nine days. Judges remember one flawless thing, not a long list of shaky ones.

Time reality (IST): kickoff is Oct 26 at about 9:30 PM and the submission deadline is Nov 5 at 7:30 AM. That is roughly 9.4 days, and about 8.8 usable days if the submission goes in on the evening of Nov 4.

## Ground rules from the Official Rules (details in `18-rules-and-compliance.md`)

- Everything shown in the demo must be built during the event (Oct 26 to Nov 4), and the demo must show only what was built then. Pre-kickoff planning files are disclosed, not hidden (D-25).
- Projects that offer "AI medical or health advice" are banned. CareSaathi is a care-coordination and document-organization tool. It copies what the doctor and the documents say and sends questions back to the doctor or pharmacist (D-24).
- The repository must be public, the demo video is 3 minutes, and one track is chosen (Indie).

## The spine (must work live, end to end)

| ID | Capability | Done when | Models |
| --- | --- | --- | --- |
| S1 | Documents to a sourced care plan: upload a prescription, lab report or discharge summary (photo or PDF); every item stored with its source document and quote; "show source" in the UI | The synthetic document set runs by script and the real accuracy number is recorded | Muse Spark 1.3 |
| S2 | Doctor Visit Listener: on-screen consent, record, diarized transcript, Spark maps speaker labels to roles (owner can correct), extracts instructions, medicine changes, tests, follow-ups and allergies with the doctor's exact words | 3 mock visits (Hinglish, and Marathi-English if verified) extracted, with found and missed items reported | Muse Voice Transcribe, Muse Spark 1.3 |
| S3 | Spoken explanations: plain-language explanation read aloud with slower pace, "repeat that", and read-back of medicine names | Hindi works end to end; Marathi works if transcription and TTS are good enough | Muse Spark 1.3, Muse Voice Transcribe, external TTS |
| S4 | Allergy safety: three states, capture from documents, visits and confirmed family input, conflict check in code against a vetted drug-family list, urgent family flag | Every planted conflict is flagged, and no message ever says a medicine is safe | Code, Muse Spark 1.3 for wording only |
| S5 | What-changed diff: code compares care plan versions; Spark explains the difference; feeds S4 | New, stopped and changed medicines are caught on the test set | Code, Muse Spark 1.3 |
| S6 | Emergency Card: one page, PDF and image, QR link with random token, allergies first, last-updated shown, revoke and expiry | Every item matches its source; revoked links stop working | Code, Muse Spark 1.3 for the short recent-changes summary |
| S7 | Permissions, approvals and audit log enforced in the backend | "Asks first" tools never run without approval; every action has an audit row | None (code) |
| S8 | Elder mode (one big mic button, everything spoken) and Family mode (care plan, approvals, visit recordings) | A non-technical person can use Elder mode unaided | None |
| S9 | Chat channel: WhatsApp if approved by the Oct 29 gate, otherwise an in-app chat screen styled like a chat app and labeled as a future-plan WhatsApp preview (see D-10) | Voice note in, voice note out | Muse Voice Transcribe, external TTS |
| S10 | Omission catch at care transitions: when a new discharge summary arrives, code compares it with the earlier plan by ingredient and lists medicines that were on the old list and are missing from the new one, with both sources and a drafted question for the doctor (D-27) | Every planted omission in the set is flagged. An incomplete document raises no omission flags. No message says a medicine was stopped on purpose or should be continued | Code, Muse Spark 1.3 for wording only |

## Stretch A (priority order, each only after the spine passes its tests)

| ID | Feature | What the user gets | Done when | Models |
| --- | --- | --- | --- | --- |
| A1 | Follow-up and test tracker | "Come back in two weeks" and "repeat the sugar test in three months" become dated to-dos with the doctor's exact words. A family member confirms them | Dates are computed by code and match the labels; unconfirmed items are marked | Code, Muse Spark 1.3 for extraction |
| A2 | Trust panel | "Show your work" on any answer (model draft, guard changes, what the family saw), a "try to break it" arena where a judge types an unsafe prompt, and a live safety scoreboard (D-30) | The arena refuses every adversarial category in the suite and the scoreboard shows real results, failures included | Code, Muse Spark 1.3 |
| A3 | Medicine history | Tap a medicine and see every version: who said it, when, the exact quote, the source page, and a slider to replay the plan over time | History matches the stored versions with no gaps | Code |
| A4 | Large-print fridge sheet | One printable A4 page in Hindi, Marathi or English: medicines, times, the doctor's written warning signs, emergency contact, last-updated date | Printed sheet matches the confirmed plan; unconfirmed items are marked | Code, Muse Spark 1.3 for wording |
| A5 | Two-reader check (wired Oct 31, D-54; runs only when the first reading reports unclear text) | A blurry document is read twice independently. Fields where the two readings differ (for example 0.5 versus 5) are circled for a human (D-29) | Planted disagreement cases are flagged; the count of flags per test set is reported | Muse Spark 1.3, code |
| A6 | Refill run-out tracker | From a documented quantity and daily frequency, code estimates when a medicine runs out and reminds the family to reorder early (D-31) | Dates match hand calculations on the set. It never suggests stretching or skipping doses | Code |
| A7 | Claim file (insurance organizer) | Documents are tagged and numbered, checked against an editable checklist, compared for mismatches, and built into one indexed PDF (D-28) | Lite: checklist plus indexed PDF. Full: adds the mismatch check and policy deadline reminders. No statement about approval | Muse Spark 1.3 for tagging, code |
| A8 | Duplicate-ingredient detector | Two brands with the same active ingredient are flagged with a question for the pharmacist | Every planted duplicate is flagged; unknown brands show as "could not check" | Code |

A7 is the largest item and the one most likely to become a roadmap slide. If time is short, build the lite slice only.

## Stretch B (only if Stretch A is done and time remains)

- Reminders and check-ins, with a "done" or "not yet" answer. A missed dose is flagged to the family and never answered with dosing advice.
- Warning signs card built from the doctor's written instructions, read aloud.
- One-page visit summary and a visit prep brief (what changed since last time, what is unconfirmed, questions to ask).
- Weekly family briefing and a "since you last looked" change feed from the audit log.
- Shift handover note for attendants and nurses.
- One-tap family broadcast: the same plan explained in several languages side by side (Marathi stays unverified until tested).
- Emergency voice mode: the card read aloud for a bystander, documented facts only.
- Recovery Timeline in a single flow: staged photo plus voice update, matched to the patient's own written warning signs. No exercise video.
- Medicine photo check with SAM 3.1 (replaced by C4, label check, which reads printed text only).

## Stretch C (added Oct 28, 2026 by the owner; built after the spine passes, in this order)

| ID | Feature | What the user gets | Done when | Models |
| --- | --- | --- | --- | --- |
| C1 | Doctor link | An expiring, revocable, read-only page for one doctor: the sourced plan, allergy state, open flags and the family's drafted questions. The doctor replies in a form; the reply is stored as the doctor's exact words and shown in the family thread. Approving "message the doctor" is what puts a question on the page (D-46) | A revoked or expired link shows nothing; every access is logged; the page never shows unconfirmed items as confirmed; a reply cannot change the plan by itself | Code, Muse Spark 1.3 for wording |
| C2 | Care crew with a visible trace | The family asks for a goal ("prepare us for Thursday's visit"). A bounded agent calls registered tools one at a time. Every step (tool, permission level, input, result, who approved) is shown live. "Asks first" steps wait for a named person (D-47) | At most 6 steps; an unknown tool or an untrusted trigger is refused and shown as refused; no step can change a medicine or dose; the trace matches the stored rows | Muse Spark 1.3 picks steps, code decides and runs them |
| C3 | Visit prep brief and after-visit diff | Before a visit: one page with what changed since last time, what is unconfirmed, open flags, and questions for the doctor. After it: what changed, with sources | Every line carries its source or "from the doctor's words"; questions end as questions; no advice | Code, Muse Spark 1.3 for wording |
| C4 | Label check | The caregiver photographs a strip, box, bottle or tube with PRINTED text. Muse Spark reads the text; code compares it with the plan and the allergy list and says "matches line N of document X", "not in the plan, ask the pharmacist" or "could not read". Loose pills are refused by design (D-48) | Every planted label case ends in one of those three states; an unreadable label never becomes "matches"; an ingredient that cannot be resolved shows "could not check" | Muse Spark 1.3 (reading only), code |
| C5 | Picture schedule | A large-print daily card with sun and moon icons, the time of day, the medicine name as written in the plan, and the source, in English, Hindi or Marathi. Built by code from the confirmed plan (D-49) | Slots match the documented schedule; unconfirmed items are marked; no pictures of medicines | Code |
| C6 | Outcomes board | Every flag is a tracked question until a named person records the answer, who gave it and where it came from (a stored doctor reply copied word for word, or a typed note). The board counts raised, answered, waiting, closed with no answer on record, days open, follow-ups and doctor-thread activity (D-52) | A flag leaves the open list only with a recorded answer; an answer needs words, a name and a recorder; one answer per flag; no wording says a medicine is safe or the answer is right | Code |
| C7 | Daily check-ins (remote care) | Today tab for the family and a check-in on the elder's screen: tap each dose as taken or not taken, tap a pain number, with names and times; counts of what is marked and what is not (D-58) | Only confirmed, scheduled, unheld medicines appear; not marked only means nobody marked it; no advice about a missed dose; pain is shown as entered with no label | Code |
| C8 | Family task board | Add, assign and finish tasks between family members (D-59) | Done needs a name and time; a task goes only to a member of the same family | Code |

C5 extends the fridge sheet (A4). Identification of loose, unlabelled pills by shape or colour is not built and is refused by design (D-48).

## Cut and dropped (not built)

- Glasses: dropped on Oct 26 (D-33). No prototype and no concept clip in the demo.
- Robotic surgery or any clinical procedure.
- Diagnosis, symptom checking, triage, dosing advice, substitutes.
- Flagging "missing" prescriptions or "inappropriate" medicines. That is clinical judgment and sits in the banned medical-advice category. We flag gaps between documents, never gaps in treatment.
- Live clinic translation, voice cloning, pill identification from photos.
- Medicine cost help, exercise video comparison.

## If behind schedule

Cut Stretch B first, then Stretch A from the bottom (A8, then A7, and so on). Spine items are never cut, but they can be simplified (for example, the in-app chat instead of WhatsApp). This supersedes the shorter cut order in `08-risks-sources.md`.

## Gates

| Gate | By | What must be true |
| --- | --- | --- |
| G0 | Before kickoff (Oct 26, 9:30 PM IST) | Application submitted (done); Official Rules read; organizers asked about pre-event work (D-25); synthetic data and labels written (`17-synthetic-data-plan.md`); TTS shortlist tested; Docker running; WhatsApp setup started |
| G1 | End of Oct 28 | S1, S5, S7 and S10 working: document to care plan to diff and omission flags, with approvals and audit rows. Day-1 checks done: Spark on 3 documents, Voice Transcribe on Hindi, Hinglish and Marathi clips |
| G2 | End of Oct 30 | S3 voice loop and S2 Visit Listener working on a mock visit. WhatsApp go or no-go decided on Oct 29 |
| G3 | End of Nov 1 | S4, S6, S8 and S9 complete, plus whichever of A1 to A3 passed their tests. Feature freeze: no new features after this |
| G4 | Nov 2 | Test set run by script, adversarial suite run, bugs fixed, numbers recorded. Backup demo video recorded |
| Demo | Nov 3 | Final demo video (3 minutes), README with the pre-hackathon disclosure, deployed live link, slides |
| Submit | Evening of Nov 4 IST | Public repo, video link and form submitted early, with a buffer for problems |

## What the demo should show

The path is in `06-testing-demo.md` and the screens are in the design canvas "CareSaathi End-to-End Flow": a discharge summary becomes a sourced care plan, the omission catch asks the doctor a question, a mock visit produces a "what changed" diff that a family member confirms, a new prescription triggers the allergy catch, Ramesh hears his plan in Hindi, and the Emergency Card is opened and then revoked. Safety and measured results come second.
