# Budget, pre-hackathon tasks, day-by-day plan, roles (original plan sections 9 to 12)

> **Note (Oct 24, 2026):** Original schedule. Kickoff is 9:30 PM IST on Oct 26, so Day 1 is mostly lost. Revised gates and cut order are in `05-scope.md`. The owner is solo, so the roles table collapses to one person; Claude acts as collaborator.

## 9. Budget plan

A third-party report says each participant gets $150 in Meta Model API credits. This was not on Meta’s own hackathon page, so confirm it in your account. Reported prices: Muse Spark 1.3 about $1.25 per million input tokens and $4.25 per million output tokens; Muse Voice Transcribe about $3 per 1,000 audio minutes; Muse Image about $0.01 per image.

1. Build and debug with Muse Glimmer or the cheap Contributor tier (synthetic data only); use full Muse Spark 1.3 for final tests and the demo.
2. Send only the relevant care plan fields in each request, not the full history every time.
3. Use prompt caching for the system prompt and repeated context.
4. Run the test set with a script in one batch instead of many manual retries.
5. Voice transcription is cheap, so test it early and freely.
6. Check credits at the end of Day 4; if spending is high, simplify cost help and the shared schedule first.

## 10. Before the hackathon (now to October 25)

This time is free. Use it to remove every risk you can.

| Task | Why it matters | Done |
| --- | --- | --- |
| Submit the application | Spots can fill before the deadline | ☐ |
| Write the synthetic patient’s year: 1 discharge summary, 3 prescriptions, 4 lab reports, 1 specialist letter | Test data and demo story | ☐ |
| Write and record 3 mock doctor visits in Hinglish and Marathi-English with friends or family acting | Doctor Visit Listener test and demo | ☐ |
| Prepare 7 days of synthetic wound/swelling photos (same mock wound, staged to show one improving set and one worsening set) plus matching voice updates | Tests the Recovery Timeline and makes a strong demo moment | ☐ |
| Add allergies to the synthetic patient (for example a penicillin allergy) and one prescription with a related antibiotic | Tests the conflict check and makes a strong demo moment | ☐ |
| Prepare a small vetted drug-family list for common allergies, ideally reviewed by a doctor or pharmacist | The conflict check must not rely on model guesses | ☐ |
| Label the expected answers for every synthetic document | Accuracy measurement on Day 7 | ☐ |
| Sketch UI screens: Elder home, Family dashboard, care plan, visit recording, approvals | Fast frontend work on Day 1 | ☐ |
| Choose and test a TTS option for Marathi and Hindi | The model lineup has no TTS | ☐ |
| Start WhatsApp Business Cloud API setup with a test number | Approval can take time | ☐ |
| Check Meta glasses toolkit availability for your country | Decides glasses Level 2 or 3 | ☐ |
| Set up the code repository, project structure and hosting accounts | Day 1 starts with code, not setup | ☐ |
| Split roles if working as a team | No overlap or gaps | ☐ |

## 11. Day-by-day plan

Six days of building, two days of testing and extra features, and two days for the demo and buffer.

| Day | Focus | Build | Models | End-of-day check |
| --- | --- | --- | --- | --- |
| Day 1, Oct 26 | Foundation | Backend setup and database tables; API keys; test Spark on 3 documents and Voice Transcribe on Marathi and Hindi recordings; app shell with Elder and Family modes | Muse Spark 1.3, Muse Voice Transcribe | Both models answer correctly from the backend |
| Day 2, Oct 27 | Documents to care plan | Photo or PDF to structured care plan with sources, including allergies and the three allergy states; plain-language explanation; upload screen and care plan view with “show source” and the red allergy banner | Muse Spark 1.3 | Upload a prescription, see an explained care plan |
| Day 3, Oct 28 | The agent | Tool calling; permission levels enforced in code; what-changed comparison with the allergy conflict check and drug-family list; reminder scheduler; approvals screen | Muse Spark 1.3 | New prescription updates the plan, sets reminders, asks before messaging |
| Day 4, Oct 29 | Voice | Live speech input; TTS replies at slower speed; read-back confirmation; “repeat that”; warning signs card read aloud | Muse Voice Transcribe, TTS, Muse Spark 1.3 | Papa speaks Marathi, CareSaathi answers in Marathi |
| Day 5, Oct 30 | Doctor Visit Listener and caregiving | Visit recording with speaker separation; instruction and allergy extraction; caregiver voice handoffs; daily check-ins; Recovery Timeline: daily photo, voice update and exercise video, compared against discharge instructions | Muse Voice Transcribe, Muse Spark 1.3 | Play a mock visit, watch the care plan update itself |
| Day 6, Oct 31 | Family and WhatsApp | WhatsApp integration or fallback chat; family updates; weekly briefing; shared schedule; cost help; visit summary; Emergency Card with PDF, image and QR link | Muse Spark 1.3, Muse Voice Transcribe | Every feature works end to end |
| Day 7, Nov 1 | Testing | Run full test set by script; voice accuracy test; safety tests (dosing requests, medicine changes, unclear speech); fix worst bugs | All | First accuracy numbers and a bug list |
| Day 8, Nov 2 | Testing and extras | Fix failures and rerun; real-family trials with synthetic data; polish Elder mode; optional SAM 3.1 photo check or glasses Level 2 | SAM 3.1 (optional) | Final numbers, quotes from testers |
| Day 9, Nov 3 | Demo | Record 3-minute demo video; README with setup, architecture and safety; deploy live link; glasses slide | - | Video, README, live link |
| Day 10, Nov 4 | Buffer and submit | Final checks and fixes; submit by the evening of November 4 IST | - | Submitted early |

Deadline reminder: submissions are due 9:00 PM ET on November 4. US daylight saving time ends November 1, so that is 7:30 AM IST on November 5. Submit by the evening of November 4 IST to leave room for problems.

## 12. Team roles

| Role | Owns | Key days |
| --- | --- | --- |
| AI and backend | Agent loop, Muse Spark prompts, tools, care plan logic, permission enforcement, test harness | Days 1 to 3, 7 |
| Voice and integrations | Muse Voice Transcribe, TTS, Doctor Visit Listener, WhatsApp, glasses (optional) | Days 4 to 6, 8 |
| Frontend and product | Elder and Family modes, UI polish, real-family testing, demo video, slides | Days 1 to 2, 6, 8 to 9 |

Solo plan: follow the same days, use the fallback chat instead of WhatsApp unless setup is already approved, and skip SAM 3.1 and glasses Level 2 unless ahead of schedule.
