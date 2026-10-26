# CareSaathi

**Master Plan for the Meta Global AI Developer Hackathon**

> A voice-first AI care coworker that listens to the doctor so your family doesn’t have to remember, and explains it to Papa in his own language, inside the WhatsApp he already uses.

Contents: vision and goals, the problem, the product, winning features, Meta glasses plan, technical architecture, model mapping, safety, budget, day-by-day build plan, team roles, testing, presentation guide, application text, risks and sources.

Hackathon dates: applications close October 25, 2026 (11:59 PM ET, or earlier if 20,000 spots fill). Build: October 26 to November 4. Submission due November 4, 9:00 PM ET (7:30 AM IST on November 5).

Prepared: October 2026.

> **Note (Oct 24, 2026):** This is the original plan text as written. The 10-day build is narrower than this document: see `05-scope.md` for what is spine, stretch or cut. Where Marathi is the demo language, see decision D-03 in `09-decisions.md`.

## 1. One-page summary

CareSaathi is a voice-first AI care coworker that helps families care for an elderly or chronically ill loved one, for as long as care is needed.

Families send it what happens: a photo of a prescription, a lab report, a caregiver’s voice note, or a recording of a doctor’s visit. The agent reads it, compares it with the patient’s full history, and acts. It explains everything in the family’s own language and reads it aloud, keeps reminders and follow-ups on track, alerts the family when something needs attention, and prepares for the next doctor visit. Patients who can’t read or type simply talk to it.

| Item | Decision |
| --- | --- |
| Project name | CareSaathi ("saathi" means companion) |
| Tagline | Your family’s lifelong companion for caring for someone you love. |
| Pitch line | CareSaathi listens to the doctor so your family doesn’t have to remember, and explains it to Papa in his own language, inside the WhatsApp he already uses. |
| Theme | Theme 1: Build for Your World |
| Track | Indie developer track if solo; Startup track if applying as a team (confirm on the application form) |
| Core Meta models | Muse Spark 1.3, Muse Voice Transcribe, plus SAM 3.1 and Muse Glimmer as options; Muse Code for building |
| Killer features | Doctor Visit Listener, WhatsApp-native agent, voice-first Elder mode |
| Safety essentials | Allergy tracking with conflict checks, and a one-tap Emergency Card for hospital visits |
| Recovery tracking | A visual, voice-and-vision Recovery Timeline for healing after surgery or injury |
| Future vision | CareSaathi on Ray-Ban Meta glasses for hands-free caregivers |

## 2. Vision and goals

### Vision

Every family caring for someone should have a patient, knowledgeable companion that never forgets, speaks their language, and takes the paperwork and worry off their shoulders.

CareSaathi rests on three ideas:

1. Long-term, not one-time. A hospital discharge is only the starting point. CareSaathi stays with the family for months and years, through every new prescription, report and doctor.
2. A coworker, not an app. The family doesn’t click through features. They tell CareSaathi what happened, and it decides what to do, does the safe tasks itself, and asks before anything important.
3. Voice-first, in your own language. An elderly patient who can’t read or type can use it just by talking, in Marathi, Hindi, English or mixed speech.

The long-term goal: no family should ever have to say “we didn’t know” about a changed medicine, a missed test, or a warning sign.

### Goals

| Goal | What success looks like |
| --- | --- |
| Get selected | Application submitted before October 25 with a clear idea and a strong description of a past AI project |
| Build a working product | Every core feature works end to end on a live link by November 2 |
| Prove it works | Published accuracy numbers on a synthetic test set, zero safety failures, and feedback from 2 or 3 real families |
| Win | A demo judges remember: Papa speaking Marathi, the Doctor Visit Listener filling the care plan live, and CareSaathi replying in WhatsApp |
| Long term | A product that could serve millions of Indian families through WhatsApp |

### Solution statement (for the application and slides)

CareSaathi is an AI care agent that does the work of caregiving alongside the family. It reads documents, follows up, and reminds, but it is more than an agent. It is a voice-first companion that speaks the patient’s language and stays with the family for as long as care is needed.

## 3. The problem

Caring for an ageing parent or a relative with diabetes, heart disease or kidney problems lasts years, and families do it with almost no support. Each feature of CareSaathi answers one of these real problems.

| Real-world problem | What families say |
| --- | --- |
| Confusing documents | “The papers are in English and full of medical words, and my father only reads Marathi.” |
| Changes go unnoticed | “The new caregiver didn’t know he’d stopped the blood pressure tablet.” |
| Missed follow-ups, tests and refills | “We forgot the appointment” or “nobody told us when to come back.” |
| Medicine costs | “I can’t afford all these medicines, so I’ll skip some.” |
| Not knowing when to worry | “Is this symptom normal, or should we go back to the hospital?” |
| Elders living alone | “No one checks on him every day.” |
| Family far away | “I live in another city and have no idea what’s going on.” |
| One exhausted caregiver | “I’m the only one caring for her, and I’m exhausted.” |
| Forgotten doctor advice | “The doctor spoke so fast. By evening we’d forgotten half of it.” |
| Short doctor visits | “We only get five minutes and forget what to ask.” |
| Emergency room visits | “At the hospital at 2 AM, the doctor asked about his medicines and allergies, and none of us could answer.” |
| Recovery is invisible | “Is the swelling getting better or worse? I can’t tell from looking at it every day.” |
| Allergies forgotten | “A new doctor prescribed something he’s allergic to, and we only noticed because my mother remembered.” |
| Typing and reading are hard | Weak eyesight, low literacy or unfamiliarity with keyboards make text apps unusable. |

## 4. The product

### How it works

Every input flows through one agent and one living care plan. Whatever comes in (a spoken message, a document photo, a caregiver’s note, a doctor visit recording, or a missed check-in) goes through five steps:

1. Receive: voice, photo, PDF, WhatsApp message, or a scheduled event.
2. Understand: speech is transcribed by Muse Voice Transcribe; documents are read by Muse Spark 1.3.
3. Compare: the agent checks the new information against the living care plan and the patient’s history.
4. Act: it does safe tasks automatically and asks permission for anything that involves other people.
5. Report: it replies in text and by voice, in the right language, to the right person.

### The living care plan

The care plan is the heart of the product. It is a structured record of medicines, conditions, appointments, tests, warning signs, restrictions, symptoms and history, built from every document the family adds. Each item stores where it came from (document, page, line, or the doctor’s exact words in a recording), so anyone can check it in seconds. Every feature reads from and writes to this one plan.

### Core features

| Stage | Feature | Problem it solves |
| --- | --- | --- |
| Understand | Documents explained in your language, read aloud | Medical English the patient can’t read |
| Understand | What changed since last time: new, stopped and changed medicines; mismatches turned into questions for the doctor | Changes and contradictions nobody notices |
| Stay on track | Appointments, tests and refills, with a flag when a date is missing | Missed follow-ups, medicines running out |
| Stay on track | Medicine cost help: generic names, public prices, a drafted request to the doctor | Skipping unaffordable medicines |
| Stay safe | Warning signs card: keep watching, call the doctor today, go to emergency now | Not knowing when to worry |
| Stay safe | Regular check-ins by voice or one tap, building a trend over months | Slow decline nobody sees |
| Stay safe | Allergy tracking: every allergy recorded with its source, and every new medicine checked against it | Allergies forgotten when doctors or prescriptions change |
| Stay safe | Emergency Card: one tap creates a one-page English summary with a QR code for hospital staff | Emergency doctors know nothing about the patient |
| Recover | Recovery Timeline: daily wound or swelling photos, voice updates and exercise videos lined up together, with visible change described in plain language | No way to see if healing is on track day to day |
| Share the care | Family updates in each relative’s language | Family far away left out |
| Share the care | Shared care schedule for siblings and relatives | One caregiver burning out |
| Share the care | Caregiver handoffs from spoken shift notes | Information lost between caregivers |
| Back to the doctor | Visit summary with history on one page | Short visits, new doctors with no history |

### Agent abilities

- Weekly family briefing every Sunday: how the week went, what’s coming, what it’s watching.
- Follows up on its own: “The blood test was due last week. Did Papa get it done? Send me the report.”
- Notices patterns: “Energy has been low three weeks in a row. I’ve added this to Thursday’s visit sheet.”
- Works with everyone: patient, children, attendant and nurse all talk to the same agent.
- Long memory: years of history, so “has he had this before?” always has an answer.

### Voice features

- Speak in Marathi, Hindi, English, or mixed speech such as Hinglish.
- Every explanation, reminder and warning card can be heard aloud.
- Elder-friendly speech: slower pace, louder volume, simple words, and “repeat that” anytime.
- Read-back confirmation for important details such as medicine names.
- Spoken medicine reminders that the patient answers with “done” or “not yet”.
- Check-ins by voice, and hands-free help with “Saathi, help”.

### Two modes in one app

| Mode | Who uses it | What it looks like |
| --- | --- | --- |
| Elder mode | The patient | One giant microphone button, very large text, everything spoken aloud, no menus |
| Family mode | Children, attendants, nurses | Care plan, timeline, reminders, schedule, visit recordings, approvals, briefings |

### Allergy tracking

Allergies are one of the most important safety facts in any health record, so CareSaathi treats them as a separate, always-visible part of the care plan rather than one line among many.

#### How allergies get into the care plan

| Source | How it is captured | Label shown |
| --- | --- | --- |
| Documents | Muse Spark 1.3 reads the allergy section of discharge summaries, prescriptions and specialist letters, with the source line saved | Doctor-documented |
| Doctor visit recording | The Doctor Visit Listener picks up allergies the doctor mentions, with the doctor’s exact words as source | Doctor-documented (from visit) |
| Family, by voice or text | “Papa is allergic to penicillin” is read back for confirmation, then saved after a family member confirms | Family-reported |

Each allergy stores the substance, the reaction (for example rash or breathing trouble), severity if known, its source, who confirmed it, and the date.

#### “No known allergies” is not the same as “unknown”

The care plan always shows one of three states: allergies listed, no known allergies (only when a document or doctor states it), or allergies not yet recorded. An empty list is never shown as “none”, because that mistake can be dangerous. When the status is unknown, the agent asks the family to check at the next visit and adds the question to the visit summary.

#### Allergy conflict check

Every time a new prescription, discharge summary or doctor visit adds a medicine, the agent checks it against the recorded allergies as part of the “what changed” step.

1. Direct match: the new medicine’s name or ingredient matches a recorded allergy.
2. Related medicine: the new medicine belongs to the same drug family as a recorded allergy (for example, a penicillin allergy and a new antibiotic from the penicillin family). This check uses a fixed, vetted drug-family reference list, not the model’s guess.
3. If either matches: the agent raises an urgent flag to the family immediately, and drafts a question for the doctor or pharmacist with the allergy, its source, and the new medicine. It says “please confirm with the doctor or pharmacist before taking this”.

Safety rule: the agent never says a medicine is safe for the patient, never tells anyone to stop or skip a medicine, and never suggests a substitute. It only points out the possible conflict and helps the family ask the right person quickly. A missing match is never shown as “no risk”.

#### Where allergies appear

- At the top of the care plan, in red, on every screen in Family mode.
- At the top of the warning signs card, read aloud in Elder mode when the card is opened.
- On the Emergency Card, as the first item after the patient’s name.
- On every visit summary, so a new doctor sees them first.
- In the “what changed” report whenever an allergy is added, edited or removed, with who changed it.

### Emergency Card

The problem: when a family rushes to an emergency room, often at night, the doctors there know nothing about the patient, and frightened relatives can’t remember medicine names, doses or allergies.

What it does: one tap (or saying “Saathi, emergency card”) creates a one-page summary in English for hospital staff, built from the living care plan. Nothing new has to be typed in a crisis.

#### What the card shows, in this order

| Section | Content |
| --- | --- |
| Patient | Name, age, photo (optional), preferred language, emergency contacts |
| Allergies | Each allergy with reaction and source, or clearly “no known allergies” or “allergies not recorded” |
| Conditions | Current diagnoses from documents (for example diabetes, high blood pressure, past heart surgery) |
| Current medicines | Name, strength and schedule exactly as written in the latest prescription, with its date |
| Recent changes | Medicines started or stopped and new findings in the last 30 days |
| Recent results | Latest key test results with dates, as written in reports |
| Regular doctors | Names, hospitals and phone numbers |
| Trust details | Last updated date and time, and “verify with patient or family; generated from family-held records” |

#### How it works

- One page, large type, readable in seconds by a busy doctor; English for hospital staff, with a copy in the family’s language for them.
- QR code on the card opens a read-only web version that always shows the latest information.
- Works without internet: the card is also saved as a PDF and an image that can be shown from the phone’s gallery or printed and kept in a wallet or on the fridge.
- Shared instantly: the family can send it on WhatsApp to a relative or to the hospital.
- Agent prompts: when a warning sign at the “go to emergency now” level appears, the agent offers the Emergency Card in the same message.

#### Privacy and safety for the card

- The QR link uses a long random token, never the patient’s name or details in the web address.
- The patient or family can turn the link off or create a new one at any time; links can also expire after a set time.
- The card only copies what documents and confirmed entries say. It never adds the model’s own advice.
- If the care plan has not been updated for a long time, the card shows a visible warning that it may be out of date.

### Recovery Timeline

The problem: after surgery, an injury, or starting a long treatment, nobody can easily tell if healing is on track. A wound might look a little different every day, pain comes and goes, and a prescribed exercise either gets done properly or skipped, with no record of any of it.

What it does: each day, the patient or caregiver sends a photo of the wound or swelling, a short voice update (“the pain increased after walking”), and, when relevant, a short video of a rehab exercise. CareSaathi lines all of this up on one visual, conversational timeline, next to the discharge instructions it relates to.

#### What it uses from each model

| Input | Model | What happens |
| --- | --- | --- |
| Daily wound or swelling photo | SAM 3.1 + Muse Spark 1.3 | SAM 3.1 isolates the area so photos line up fairly day to day; Spark describes visible change in plain language (for example “the area looks larger than on day 3”) |
| Voice update | Muse Voice Transcribe | Transcribed, tagged to that day, and shown beside the same day’s photo |
| Medication or discharge-instruction photo | Muse Spark 1.3 | Read into the care plan as usual, and used as the source for what “normal healing” and “call the doctor” look like for this patient |
| Rehab exercise video | Muse Spark 1.3 (video input) | Compared with the written exercise instructions, noting things like repetitions completed; never a judgement on medical technique |

#### How reasoning ties it together

The agent connects photos, voice notes, videos and the care plan to notice patterns a single update would miss, for example: “Swelling looks larger for two days, and pain is up after walking. Your discharge papers say to call the clinic if swelling increases.” It always points to the specific instruction behind the alert.

#### Human approval, always

- The agent never says a wound is “infected”, “healing well”, or “nothing to worry about”. It only describes visible change and matches it to the patient’s own written warning signs.
- Alert levels come only from the discharge instructions already in the care plan, the same levels used everywhere else (watch, call the doctor today, emergency).
- Photos and videos are private by default. A one-tap “Send to doctor” bundle (photo series, voice notes, summary) is an ask-first action, approved by a family member before anything is shared.

#### Why this feature matters for the hackathon

It makes CareSaathi one of the few projects that uses vision, voice and reasoning together in one feature: SAM 3.1 for the image comparison, Muse Spark 1.3 for documents, video and reasoning, and Muse Voice Transcribe for the daily updates, with a human always approving before anything medical gets shared. It also fits Ramesh’s own story well, since he has just had heart surgery.

## 5. Winning features

Many of the 20,000 participants will build medical summarizers. These features make CareSaathi stand out because they solve a real problem and showcase what only Meta’s models and products can do.

### 5.1 Doctor Visit Listener (the killer feature)

The problem: families forget most of what the doctor said within hours. The doctor speaks fast, mixing English with Marathi or Hindi, several people talk at once, and nobody takes notes.

What it does: with clear consent from the doctor and patient, a family member taps “Record visit”. Muse Voice Transcribe transcribes live, separates who said what (doctor, patient, daughter), and handles mixed-language speech. When the visit ends, Muse Spark 1.3 extracts every instruction, medicine change, test and follow-up date into the care plan, with the doctor’s exact words as the source. That evening, CareSaathi explains it to Papa in Marathi, by voice.

Why it wins: it shows off Muse Voice Transcribe’s speaker separation and code-switching in a use case almost nobody else will build, and it makes a stunning 60-second live demo.

Guardrails: recording only with consent shown on screen; the summary is always checked against the written prescription; nothing changes the medicine list without a family member confirming.

### 5.2 CareSaathi inside WhatsApp

The problem: elderly people won’t install new apps, but nearly every Indian family already has a WhatsApp group.

What it does: CareSaathi works through WhatsApp. Papa sends a voice note in Marathi and gets a voice note back. Priya forwards a prescription photo and the care plan updates. The weekly briefing arrives as a WhatsApp message.

Why it wins: Meta owns WhatsApp. Bringing Meta’s newest models into Meta’s biggest product, for a population that needs it, is a story Meta wants to tell, and it shows a realistic path to millions of users.

Practical note: the WhatsApp Business Cloud API offers a test number for development, but setup can take time. Start it before the hackathon and keep an in-app chat screen that works the same way as a fallback.

### 5.3 Optional: medicine photo check

The patient or caregiver photographs medicine strips or bottles on a table. SAM 3.1 separates each one, Muse Spark 1.3 reads the labels, and the app matches them against the care plan, flagging anything stopped, missing or unknown with “confirm with your pharmacist”. Build only if ahead of schedule.

## 6. Meta glasses plan

Ray-Ban Meta glasses are a natural fit for caregivers, whose hands are busy lifting, feeding and helping someone walk. This section explains what is possible today and how to include it without risking the core build.

### What Meta offers developers

- Meta’s Wearables Device Access Toolkit lets iOS and Android apps connect to the glasses’ hardware. Developers get camera access through the toolkit, and microphone and speakers through the phone’s Bluetooth audio.
- It supports Ray-Ban Meta (Gen 1 and Gen 2) and Meta Ray-Ban Display glasses, and in 2026 Meta added developer preview access to the Display glasses’ screen, including a web app path built with HTML, CSS and JavaScript.
- A Mock Device Kit lets you test integrations without owning glasses, by simulating a device, its permissions and media streaming.
- Full toolkit capabilities are only available in countries where Meta’s AI glasses are sold, so check availability for your country before planning a real build.

### CareSaathi on glasses: three use cases

| Use case | How it works | Models |
| --- | --- | --- |
| “Which tablet is next?” | The caregiver asks out loud through the glasses; CareSaathi answers through the glasses’ speakers from the care plan | Muse Voice Transcribe, Muse Spark 1.3, TTS |
| Hands-free medicine check | The caregiver looks at the tablets in hand; the glasses camera sends a photo; the agent confirms it matches the scheduled medicine or says to check with the pharmacist | SAM 3.1, Muse Spark 1.3 |
| Visit listening | Glasses microphones capture the doctor visit (with consent) for the Doctor Visit Listener | Muse Voice Transcribe, Muse Spark 1.3 |

### How to include it in the hackathon

| Level | What to do | When |
| --- | --- | --- |
| Level 1 (always) | One pitch slide plus a 10-second concept clip showing the caregiver use case. No code. | Day 9 |
| Level 2 (if ahead) | A small Android or iOS companion app using the toolkit’s Mock Device Kit: send a simulated camera frame to the backend and play the spoken answer. | Day 8, only if all core features pass testing |
| Level 3 (if you own glasses) | The same companion app on real glasses in Developer Mode, filmed for the demo video. | Day 8 to 9 |

Rule: glasses never come before the core demo. A polished core with a glasses slide beats a broken product with a glasses prototype.
