# Safety, privacy and consent (original plan section 8)

> **Note (Oct 24, 2026):** These rules are non-negotiable invariants. `09-decisions.md` D-12 says how each one is enforced in backend code and tests.

## 8. Safety, privacy and consent

CareSaathi organizes and explains what the doctor said; it never replaces the doctor. Judges will ask about safety, so this is a strength to show, not a footnote.

| Level | What the agent does |
| --- | --- |
| Does automatically | Reads and explains documents, updates the care plan, sets reminders, prepares summaries, organizes history |
| Asks first | Messages family or the doctor, assigns tasks, shares information with a new caregiver |
| Never does | Changes medicines or doses, diagnoses symptoms, decides on its own whether to go to hospital |

- Source on every output: every explanation and reminder links to the document line or the doctor’s exact words.
- Warning signs come from the doctor’s instructions, not model guesses, with the hospital and emergency numbers on the same screen.
- Voice safety: medicine names are read back and matched against the written prescription; unclear speech means asking again; in an emergency the agent alerts family instead of waiting.
- Allergies: never shown as “none” unless a document or doctor says so; conflicts are flagged for a doctor or pharmacist, and the agent never says a medicine is safe.
- Emergency Card: only copies documented or confirmed facts, shows when it was last updated, uses private random links, and can be turned off anytime.
- Consent: visit recording only with on-screen consent from the doctor and patient; the patient controls who sees what and can remove access anytime.
- Data: synthetic patient data only during the hackathon; state clearly whether voice recordings are deleted after transcription.
