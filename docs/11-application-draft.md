> **Status (Oct 26, 2026):** The owner submitted the application and was approved. This file is kept for reference.

# Application draft (revised)

**Status:** Draft for the owner to edit. The original text is in `07-application.md`.

## Why a revision

Reviewers score clarity and feasibility, and the original text lists about fifteen features. The draft below leads with the spine from `05-scope.md` and keeps only claims the project can back up.

## Project idea field (trim to the form's limit)

CareSaathi is a voice-first AI care companion for families looking after an elderly or chronically ill parent. Medical papers are in English, doctors speak fast, and many older patients cannot read or type, so families forget instructions, miss medicine changes, and arrive at emergency rooms unable to say what the patient takes or is allergic to.

With consent, CareSaathi listens to a doctor visit, separates who said what, and turns the instructions into a living care plan in which every item links to the doctor's exact words or the document line it came from. It explains the plan aloud in the patient's own language (Hindi first, Marathi next, including mixed speech with English). It tracks allergies and flags any new medicine that may conflict with them using a vetted drug-family list, not model guesses. One tap creates an Emergency Card with a QR code for hospital staff.

Safety is enforced in code: the agent never changes medicines, never calls a medicine safe, and asks a family member before sharing anything. We build on Muse Spark 1.3 and Muse Voice Transcribe through the Meta Model API, delivered through WhatsApp where possible because that is where these families already are. We test on synthetic patient data and publish accuracy results, including failures.

## Past AI project field (owner to complete)

This field carries half the review weight. Fill it with facts only.

- **What you built:** one sentence on the problem and the result.
- **Techniques:** for example agents with tool calling, document extraction, speech pipelines, retrieval, evaluation harnesses. Name only what you actually used.
- **Evidence:** a number, a user count, a test result or a demo that works.
- **Link:** GitHub or a live product (optional, but it helps).

TODO: owner to provide the project details. Do not invent any of them.

## Before submitting

- Submit before Oct 26, about 9:29 AM IST.
- Choose the Indie developer track and the Build for Your World theme.
- Keep claims to what is verified. Marathi is a target, not a promise.
- Use only form answers; links are optional.
