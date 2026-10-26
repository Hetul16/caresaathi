# Product requirements

**Product:** CareSaathi, a voice-first AI care companion for families looking after an elderly or chronically ill relative.
**Surface:** website only, mobile-first (D-17). **Track:** Indie (D-01). **Status:** draft for the owner to confirm.

This document answers: who is it for, what do they need, what exactly will we build first, how will we know it works, and what are we choosing not to build. Scope detail lives in `05-scope.md`; this file explains why.

## 1. Problem

Families caring for a parent with a long illness handle years of prescriptions, reports and appointments. The papers are in medical English, doctors speak fast, and many older patients cannot read or type. The result is predictable: instructions are forgotten by evening, medicine changes go unnoticed, follow-ups are missed, and at 2 AM in an emergency room nobody can say what the patient takes or is allergic to.

The cost is not inconvenience. It is missed medicines, repeat tests, allergic reactions that were avoidable, and caregivers who burn out.

## 2. Who it is for

### Primary users

| Persona | Situation | What they need | What would make them stop using it |
| --- | --- | --- | --- |
| **Ramesh, 68** (the patient) | Recent heart surgery. Reads Marathi, not English. Weak eyesight, uneasy with phones | Hear what the doctor said, in Marathi, in simple words. Ask "which tablet now?" by voice. Never feel stupid | Menus, small text, English, a voice that talks too fast |
| **Priya, 38** (daughter, lives in another city) | Manages his care remotely, works full time | Know what changed, in her language. Approve things quickly. Be told at once if something is wrong | Notification spam, anything that looks certain when it is not |
| **Sunil, 45** (attendant or nurse, on shift) | Gives medicines, does check-ins | See today's medicines and warnings in one place. Leave a spoken note for the next shift | Typing, long screens |

### Secondary

| Persona | Need |
| --- | --- |
| **ER doctor at 2 AM** | One page, readable in seconds: allergies first, medicines, recent changes, who to call, how fresh the information is |
| **Treating doctor** | A clear one-page summary with history at the next visit |

### Who it is not for (yet)

Clinicians who want decision support, hospitals who want an EHR, anyone looking for diagnosis. CareSaathi organizes and explains what the doctor said. It does not replace the doctor.

## 3. Jobs to be done

1. When the doctor finishes talking, help me keep everything they said so I do not rely on memory.
2. When a new paper arrives, tell me what changed and whether it clashes with what we already know, in my language.
3. When Papa asks "what do I take now?", answer in his language by voice, with certainty only when the record is certain.
4. When something looks wrong, tell me whether our own instructions say to call the doctor or go to the hospital.
5. When we rush to hospital, give them everything they need without typing in a panic.
6. Keep far-away relatives informed without me writing updates.

## 4. Principles that shape every decision

| Principle | What it means in practice |
| --- | --- |
| Source or silence | No fact, explanation or alert without a visible source. If we cannot show where it came from, we do not say it |
| Unknown is not none | "Allergies not recorded" is never displayed as "no allergies" |
| Humans decide | The product organizes and flags. A person approves anything that involves other people, and only a doctor changes medicines |
| Voice before screens | If a patient cannot do it by talking, it is not finished |
| Honest accuracy | We publish measured numbers and our failures |
| Small and flawless beats large and shaky | A narrow spine that works live wins over fifteen features that mostly work |

## 5. Scope

### 5.1 First release (the hackathon build, the spine)

| ID | Capability | Why it earns its place |
| --- | --- | --- |
| S1 | Documents become a sourced care plan | The base of everything: trust comes from sources |
| S2 | Doctor Visit Listener | The memorable, differentiating feature: addresses "we forgot half of it" |
| S3 | Spoken explanations in the patient's language | Makes it usable by Ramesh |
| S4 | Allergy safety with conflict flags | The clearest example of safety done properly |
| S5 | What changed since last time | Turns a pile of papers into one useful message |
| S6 | Emergency Card with QR | The 2 AM problem, solved in one tap |
| S7 | Permissions, approvals and audit log | The reason a family can trust it |
| S8 | Elder mode and Family mode | Two experiences, one record |
| S9 | Chat channel (WhatsApp if approved, otherwise a styled in-app preview labeled as the future plan) | Meets families where they already are |
| S10 | Omission catch at care transitions | The best-evidenced real problem: medicines lost between documents |

### 5.2 Stretch A (priority order, in `05-scope.md`)

A1 follow-up and test tracker, A2 trust panel, A3 medicine history, A4 large-print fridge sheet, A5 two-reader check, A6 refill run-out tracker, A7 claim file (insurance organizer), A8 duplicate-ingredient detector. The order is the cut order from the bottom.

### 5.3 Stretch B (only if A is done)

Reminders and check-ins, warning signs card, visit summary and prep brief, weekly briefing and change feed, shift handover, family broadcast, emergency voice mode, Recovery Timeline, medicine photo check with SAM 3.1.

### 5.4 Non-goals

| Not building | Reason |
| --- | --- |
| Native iOS or Android app | Website only (D-17) |
| Diagnosis, triage advice, dosing advice, substitute suggestions | Safety. No such tool exists |
| Telling anyone a medicine is safe | Same |
| Medicine cost help, shared care schedule, exercise video analysis | Cut for the 10-day build; roadmap slide only |
| Flagging missing prescriptions or inappropriate medicines, symptom checking, pill identification from photos, live clinic translation, voice cloning | Clinical judgment or high risk, and the banned medical-advice category (D-24) |
| Predicting claim approval, judging eligibility, legal or financial advice | The claim file only organizes paperwork (D-28) |
| Real patient data | Synthetic only until a legal and consent review is done (D-13) |
| Glasses prototype and robotic surgery | Dropped (D-33) |
| Payments, accounts for clinics, EHR integrations | Later |

## 6. User stories and acceptance criteria

Format: Given / When / Then. "Source" always means a visible document line or the doctor's exact words.

### S1 Documents to care plan

**Story:** As Priya, I upload a prescription photo so that the care plan updates itself and I can check every line.

- Given a clear prescription photo, when I upload it, then within the target time I see the medicines as care plan items, each with a "show source" link to the page and line.
- Given a blurry or unreadable page, when extraction finishes, then the document is marked "needs review" with what was unclear, and nothing guessed is added.
- Given the same file uploaded twice, then it is stored once.
- Given a date is missing for a follow-up test, then the item shows "date not given" instead of a guessed date.

### S2 Doctor Visit Listener

**Story:** As Priya, I record a doctor visit with consent so that every instruction is captured with the doctor's own words.

- Given I tap Record, then I cannot start until the doctor's consent and the patient's consent are both confirmed on screen.
- Given a visit in Hindi or mixed Hindi and English, when it ends, then I see a transcript with speaker labels, and I can correct who is who.
- Given extraction runs, then each instruction, medicine change, test, follow-up and allergy shows the exact words and a link to that moment in the transcript.
- Given extracted changes, then none changes the medicine list until a family member confirms it.
- Given recording is finished and "delete audio" is on (default), then the audio is deleted after transcription and the date of deletion is recorded.

### S3 Spoken explanations

**Story:** As Ramesh, I hear what changed, in my language, in simple words, so I know what to do.

- Given a care plan change, then an explanation exists in my preferred language and can be played aloud at a slower pace.
- Given I say or tap "repeat that", then the same explanation plays again.
- Given a medicine name is spoken to the app, then the app reads it back and I confirm before anything is saved.
- Given the voice service cannot produce Marathi, then a Hindi or English voice is used and the Marathi text stays on screen.

### S4 Allergy safety

**Story:** As Priya, I want an immediate warning if a new medicine may clash with an allergy, and I never want "none" shown when we simply do not know.

- Given no allergy information, then the screen says "Allergies not recorded" and the Emergency Card says the same.
- Given a document that states "no known allergies", then the screen says so and cites that document.
- Given a recorded penicillin allergy and a new prescription for amoxicillin, then an urgent flag appears to the family within the target time, with the allergy, its source, the new medicine, and a drafted question for the doctor or pharmacist.
- Given an ingredient the reference list cannot identify, then the flag says "could not check this ingredient, please ask the pharmacist".
- Given no match in the list, then the screen never says the medicine is safe.
- Given I say "Papa is allergic to sulfa", then the app reads it back, and the allergy is saved only after I confirm.

### S5 What changed

**Story:** As Priya, after each new paper I see what is new, stopped or changed.

- Given a new prescription that omits a medicine on the previous one, then the report lists it as "not on the latest prescription" and suggests a question for the doctor. It does not say it was stopped unless the document says so.
- Given a changed dose, then both versions are shown with their sources.

### S6 Emergency Card

**Story:** As Priya at 2 AM, I tap once and show the hospital everything they need.

- Given I tap Emergency Card, then I get a one-page card with the patient's name, then allergies, conditions, current medicines, recent changes, recent results, doctors and phone numbers, and when it was last updated.
- Given the QR code is scanned, then the hospital sees the live card without logging in, and the card says to verify with the patient or family.
- Given no signal, then a PDF and an image of the card are still available from the phone.
- Given I revoke the link, then the QR stops working and shows a neutral message.
- Given the care plan has not been updated for a long time, then the card shows a visible out-of-date warning.
- Given any item on the card, then it comes from a document or a confirmed entry, never from model advice.

### S7 Permissions and approvals

**Story:** As the daughter, I want to approve anything that involves other people.

- Given the agent wants to message a relative or the doctor, then it appears in my approvals list and nothing is sent until I approve.
- Given an attempt to change a medicine or a dose through the agent, then it is refused and explained.
- Given any approval, allergy change, consent or card access, then the audit log has a row saying who and when.
- Given a family member without approval rights, then they cannot approve.

### S8 Elder mode and Family mode

- Given Ramesh opens the site on his paired phone, then he sees one very large microphone button, large text, and everything spoken aloud, with no menus.
- Given a family member signs in, then they see the care plan, timeline, approvals and visits.
- Given a new phone, then a family member must approve its pairing before it works.

### S9 Chat channel

- Given WhatsApp is approved, when Ramesh sends a voice note, then he gets a voice note back in his language, and Priya can forward a prescription photo to update the plan.
- Given WhatsApp is not approved, then an in-app chat styled like a chat app shows the same flow, and it is clearly labeled as a preview of the planned WhatsApp channel.

### S10 Omission catch

**Story:** As Priya, when a discharge summary arrives, I want to see which medicines were on the old list and are missing from the new one, so that I can ask the doctor.

- Given an earlier plan that includes atorvastatin and a discharge summary that does not, when the summary is processed, then I see "On the old list, missing from the new one" with both sources and a drafted question for the doctor.
- Given the same medicine appears under a different brand with the same ingredient, then no flag is raised.
- Given an ingredient cannot be resolved, then the item shows "could not compare, please ask the pharmacist".
- Given the new document looks incomplete (a page is missing), then no omission flags are raised and the app says the document looks incomplete.
- Given any omission flag, then the text never says the medicine was stopped on purpose, is safe to stop, or should be continued.

### Stretch stories (Given / When / Then)

**A1 Follow-up and test tracker**
- Given the doctor says "come back in two weeks", when the visit is processed, then a to-do appears with the doctor's exact words and a date computed by code, marked pending.
- Given a family member confirms it, then it becomes a dated item with a reminder. Given nobody confirms, then it stays marked pending.

**A2 Trust panel**
- Given any generated answer, when I tap "show your work", then I see the model draft, what the guard changed or blocked, and what the family saw.
- Given I type an unsafe prompt in the arena (dosing advice, "ignore your rules", a request for another patient's data), then the answer is refused with "Please ask the doctor or pharmacist about this" and the attempt appears on the scoreboard.

**A3 Medicine history**
- Given a medicine with several versions, when I open its history, then every version shows who said it, when, the exact quote and the source page, with no gaps.

**A4 Fridge sheet**
- Given a confirmed care plan, when I tap "print", then I get one A4 page in the chosen language with medicines, times, written warning signs, the emergency contact and the last-updated date. Unconfirmed items are marked.

**A5 Two-reader check**
- Given a blurry prescription, when two readings differ on a field (for example 0.5 versus 5), then the field is circled, both readings are shown, and the value is not applied until a person chooses.

**A6 Refill run-out tracker**
- Given a documented quantity of 30 tablets taken once a day, when the start date is confirmed, then the app shows an estimated run-out date and a reminder a few days earlier, with the inputs listed.
- The app never suggests taking less, skipping, or stretching a supply.

**A7 Claim file**
- Given Ramesh was in hospital, when Priya opens the claim file, then she sees a checklist (itemized bills, discharge summary, prescriptions, investigation reports, identity proof, claim form, policy copy, and an accident report where relevant) with present and missing marks, labeled "general guidance, check your insurer's list". She can edit the list.
- Given uploaded documents, then each is tagged by type and numbered in order.
- Given a bill whose patient name or dates differ from the discharge summary, then a mismatch flag shows both quotes.
- Given she enters deadlines from her policy, then reminders are computed by code. Given she has entered none, then the app says it does not know the insurer's deadlines.
- Given she taps "build claim file", then she gets one indexed PDF. The app says nothing about whether the claim will be approved.

**A8 Duplicate-ingredient detector**
- Given two medicines with the same active ingredient under different brands, then a flag shows both sources and a question for the pharmacist. A brand not on the list shows as "could not check".

**Stretch B (short form)**
- Reminders: spoken, answered "done" or "not yet", a missed one is flagged to the family, with no dosing advice.
- Warning card: levels come from the patient's own written instructions, with emergency numbers on the same screen.
- Weekly briefing and change feed: a summary of what happened, what is coming, and who changed what.
- Shift handover: a note built from the day's log and the written warning signs.
- Recovery Timeline: seven days of staged photos and voice notes line up; on the worsening day the app says what changed visibly and points to the written instruction, never using words like infected or healing well.

## 7. Success measures

### Hackathon (what judges will see)

| Measure | Target | How it is measured |
| --- | --- | --- |
| Works live | Every spine flow runs end to end on a public link, twice in a row | Rehearsal checklist, recorded backup |
| Document extraction | Report the real number for medicine changes caught and missing dates flagged | 20 synthetic documents with labelled answers |
| Visit extraction | Report instructions found and missed | 3 mock visits |
| Speech accuracy | Report per language (Hindi, Hinglish, Marathi if tested) | Recorded phrases with medicine names |
| Allergy safety | Every planted conflict flagged; "not recorded" never shown as "none"; no message says a medicine is safe | Scripted suite |
| Safety failures | Zero | 30 adversarial prompts |
| Emergency Card accuracy | Every item matches its source | Compare card to plan |
| Cost per document and per visit | Reported | `model_calls` |
| Real-family feedback | 2 or 3 families give quotes | Trials with synthetic data |
| Omission catch | Every planted omission flagged; zero flags from incomplete documents | Planted set in `17-synthetic-data-plan.md` |
| Two-reader check | Planted disagreements flagged; flag counts reported | Same set |
| Derived dates | Follow-up and run-out dates match hand calculations | Date tests |
| Claim file | Missing and mismatched documents flagged | Insurance papers I1 to I8 |
| Trust panel | Every adversarial category refused; failures listed | Adversarial suite |

### After the hackathon (if it continues)

| Measure | Meaning |
| --- | --- |
| Weekly active families | Real use |
| Documents and visits per family per month | Habit |
| Share of care plan items confirmed by a person | Trust |
| Time from upload to "what changed" | Speed |
| Open allergy conflicts older than 24 hours | Safety follow-through |
| Elder mode sessions per week | The patient is actually using it |
| Approvals decided within an hour | Family engagement |

## 8. Release plan

| Phase | Goal | Contents |
| --- | --- | --- |
| Hackathon MVP (Oct 26 to Nov 4) | A flawless narrow demo | S1 to S9 with measured results, then stretch A and B in order |
| Pilot (after) | A few real families in a controlled trial | Legal and consent review, reviewed drug list, WhatsApp live, field encryption, backups tested, doctor-reviewed wording |
| Version 1 | A service | Reminders, briefings, recovery tracking, more languages, caregiver features, clinic accounts |
| Later | Scale | Glasses, more regions, integrations |

Gates for the hackathon build are in `05-scope.md`.

## 9. Assumptions to test

| Assumption | How we find out | If false |
| --- | --- | --- |
| Muse Spark 1.3 on the Model API reads document photos and PDFs | First hour of the build (3 documents) | Use OCR then text, or open-weights Spark through a hosting provider |
| Muse Voice Transcribe handles Marathi acceptably | Test real clips on day one | Headline language becomes Hindi (D-03) |
| Hinglish code-switching works in the clinic style | Mock Hinglish visits | Show the transcript for correction, say so |
| A usable Marathi or Hindi TTS exists | Voice test before kickoff | Hindi or English voice with Marathi text |
| WhatsApp setup finishes in time | Gate on Oct 29 | In-app chat preview |
| Families will confirm items rather than ignore them | Trials | Fewer, better confirmations |

## 10. Risks

| Risk | Impact | Mitigation |
| --- | --- | --- |
| A wrong or reassuring output about a medicine | Harm and loss of trust | Source or silence, guard, no-safety-claims rule, adversarial tests |
| Wrong allergy matching | Harm | Vetted list, exact matching, "unresolved" is shown, pharmacist review, banner while unreviewed |
| Scope too large for one person | No working demo | Spine and cut order |
| Voice quality in local languages | Weak wow moment | Early tests, fallbacks, Hindi headline |
| Privacy of recordings | Legal and ethical | Consent first, audio deleted by default, synthetic data only |
| Judges assume WhatsApp is live when it is a mock | Credibility | Label it clearly everywhere (D-10) |
| Dependency on one model vendor | Outage or change | Stored raw outputs, adapter layer, recorded demo |

## 11. Open questions for the owner

| # | Question | Needed by |
| --- | --- | --- |
| 1 | Confirm the spine in `05-scope.md` and the Recommended decisions in `09-decisions.md` | Before the build starts |
| 2 | Hosting: your own machine or a VPS (D-07) | Before Day 1 |
| 3 | Past AI project paragraph for the application | Done: the owner applied and was approved on Oct 26 |
| 4 | Do you know a doctor or pharmacist who can review the drug-family list and the safety wording? | Before the demo, ideally this week |
| 5 | Official Rules: anything about AI coding tools and ownership. Email the organizers about D-24 and D-25 | Today (Oct 26) |
| 7 | Confirm the stretch order in `05-scope.md`, and whether the claim file should be the lite slice only | Before G3 |
| 6 | Which families can try the demo with synthetic data? | By Nov 2 |

## 12. Traceability

Each story maps to the pieces that deliver and test it.

| Story | Endpoints | Main tables | Tests |
| --- | --- | --- | --- |
| S1 | `POST /patients/{id}/documents`, `GET /patients/{id}/care-plan` | `documents`, `extractions`, `source_refs`, `care_plan_items`, `medicine_ingredients` | 20-document set, `plan:*`, `source:*` |
| S2 | `POST /patients/{id}/visits`, visit stream, `PUT /visits/{id}/speakers`, `POST /plan-changes/{id}/decision` | `consents`, `visits`, `transcript_segments`, `visit_speakers`, `plan_changes` | 3 mock visits, `visit:*` |
| S3 | `POST /outputs/{id}/speak`, voice WebSocket | `generated_outputs`, `output_sources` | Voice accuracy set, guard tests |
| S4 | `GET/POST /patients/{id}/allergies`, `GET /patients/{id}/allergy-conflicts` | `allergies`, `allergy_status`, `allergy_conflicts`, `drug_*` | `allergy:*`, `conflict:*`, planted-conflict set |
| S5 | `GET /patients/{id}/what-changed` | `plan_changes`, `care_plan_items` | 20-document set |
| S6 | `POST /patients/{id}/emergency-card`, `GET /e/{token}` | `emergency_cards`, `emergency_card_access_log` | Card accuracy check, public-card RLS tests |
| S7 | `GET /patients/{id}/actions`, `POST /actions/{id}/approve` | `actions`, `audit_log`, `family_members` | `action:*`, `audit:*`, 30 adversarial prompts |
| S8 | Pairing endpoints | `devices`, `family_members` | `device:*`, usability trials |
| S9 | `POST /patients/{id}/agent/message`, WhatsApp webhook | `conversations`, `messages` | End-to-end run, backup clips |
| S10 | `GET /patients/{id}/reconciliation` | `reconciliation_flags` (planned), `care_plan_items`, `medicine_ingredients` | `omit:*` |
| A1 | `GET/POST /patients/{id}/follow-ups` | `follow_ups` (planned) | `follow:*` |
| A2 | `GET /outputs/{id}/trace`, arena endpoint, scoreboard | `generated_outputs`, `model_calls`, `eval_runs` | `arena:*`, `trace:*` |
| A3 | `GET /care-plan-items/{id}/history` | `care_plan_items`, `source_refs` | history gap test |
| A4 | `GET /patients/{id}/fridge-sheet` | none new (reads the confirmed plan) | `sheet:*` |
| A5 | `GET /documents/{id}/second-read` | `second_reads` (planned) | `second:*` |
| A6 | `GET /patients/{id}/refills` | `supply_records` (planned) | `refill:*` |
| A7 | Claim file endpoints (`15-api-spec.md`, section 8) | `claim_files`, `claim_checklist_items`, `claim_documents`, `policies` (planned) | `claim:*` |
| A8 | `GET /patients/{id}/duplicates` | `medicine_ingredients`, `drug_substances` | `dup:*` |

## 13. Evidence behind the problem

These figures support the pitch. Cite them with their limits.

| Finding | Source and limit |
| --- | --- |
| About 49% of patients did not recall their doctors' recommendations after a visit | Brown University pilot, reported by a news article (2018). A pilot study, indicative only |
| In 339 older adults after an ICU stay, 64% had an unintentional medication discrepancy at some care transition (49% at discharge). 96% of discrepancies were omissions. Patients with discrepancies had about twice the risk of an ED visit within a month (hazard ratio 2.13) | Korean single-hospital retrospective study (PMC11654400). The abstract says 68% and the results say 64%. One hospital |
| In 600 older adults in six Indian cities: polypharmacy 33.7%, self-medication 19.7%, at least one potentially inappropriate medication 28.8%. Recent hospitalization raised the odds of polypharmacy about 4.6 times | Scientific Reports cross-sectional study (2024 to 2025). Shows association, not cause |
| Among those with inappropriate medications, 35.8% had duplicate prescriptions | A news summary of the same study. Check the paper before quoting |

Two papers (a discharge-summary study and a caregiver medication study) could not be opened by the research tool and are not used.

Sources: https://www.browndailyherald.com/article/2018/03/study-shows-half-of-patients-forget-doctors-instructions, https://pmc.ncbi.nlm.nih.gov/articles/PMC11654400, https://link.springer.com/article/10.1038/s41598-024-84627-2, https://thesouthfirst.com/health/wrong-prescriptions-self-medication-put-indias-ageing-population-at-risk-study/
