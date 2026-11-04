# 23. Pitching CareSaathi against the Indie track criteria

The Indie track is judged on **creativity, technical ambition, and whether it works**, under Theme 1, *Build for Your World*. This file is the
pitch arranged around those three words. The story and shot list are in `docs/20-demo-video-script.md` and `docs/22-remote-care-story.md`; the
market case is in `docs/21-why-and-go-to-market.md`. This one is about what to say, in what order, and what to say when a judge pushes.

## 1. The line

> **A care plan where every line cites the page it came from, and an AI that knows when to refuse.**

Not "AI that reads prescriptions". Hundreds of entries read prescriptions. The sentence above names the two things almost none of them do.

The thirty-second version:

> My mother sees three doctors. Each writes a prescription without seeing the others. Somebody in the family is supposed to notice when two of
> them collide, and that somebody is usually a daughter in another city who was not at any of the appointments.
> CareSaathi turns those papers into one care plan where every single line shows the document and line number it came from. It catches the
> collisions in code, not in the model. And when you ask it "is this safe to take", it refuses and gives you the question to ask the doctor.
> That refusal is the product.

## 2. The opening (needs your own sentence)

Theme 1 asks for a problem you know firsthand. A true, specific first sentence is worth more than any feature.

Fill this in yourself, out loud, in one or two sentences:
- Who you have helped with their medicines or their hospital papers.
- The moment it nearly went wrong, or the moment you realised nobody was tracking it.

Say the true version or none at all. If there is no personal story, open on Priya instead: *"Priya lives in Toronto. Her mother lives in Pune.
Her mother saw a second doctor last Tuesday and Priya found out on Saturday."* That is honest and it still lands.

## 3. What to show for each criterion

### Whether it works (judged first, weighted most, and the easiest to lose)

What a judge must be able to do: open the link, press one button, and watch a real document become a real plan.

- Open the public link. Sign up. Press **Load the demo family**. No file hunting, no setup.
- Upload the real photographs from `demo_uploads/Sunita_Deshmukh/` in order. They are tilted and shadowed on purpose: they are phone pictures, not clean scans.
- Show `/trust`: the safety suite with its **failures listed**, and live Meta-model measurements on documents, labels, visits and speech.
- Say the number out loud: **447 backend tests, 19 browser checks, and the five adversarial cases we still fail are named on that page.**

Rehearse this path three times on the real link, on a phone and a laptop, before recording.

### Technical ambition

Do not list models. Show one sentence of design and then the evidence for it:

> **The model proposes. Code decides.**

- The allergy match is a SQL function against a vetted list, not a model judgement. The model only writes the sentence, and the sentence passes an output guard and a second-pass judge that **fails closed**.
- Every plan line carries a source, and the database refuses to store a passed output with no source attached. It is a trigger, not a convention.
- The reference list is grounded in the **WHO ATC classification** via the US NLM, and the flag shows the class code behind the match (D-63).
- Three allergy states, so an empty list is never shown as "no allergies".
- A document line that reads like an instruction to the app is ignored and surfaced to the family.
- Row-level security in Postgres: a bug in the API still cannot show one family another family's patient.

### Creativity

The two moments a judge will repeat afterwards:

1. **The Timeline.** Two doctors, one patient, one calendar. Calpol from the orthopaedist and Dolo from the family doctor are both paracetamol, and the stretch where they overlap is striped on both bars. The Diclofenac bar is red because it is an NSAID and an NSAID allergy is on file. Three failures of coordination visible in one screen, with every date computed by code from the printed page.
2. **The refusal.** Type *"Is it safe to stop Amlodipine?"* and it will not answer. It says it can only read back what is in the plan, and hands you the question for the doctor. In a field full of confident health chatbots, the one that declines is the one they remember.

## 4. Depth: what to say when a judge pushes

These are the questions that separate a demo from a system. Each answer is true and checkable in the repository.

**"How do you know the model did not hallucinate that line?"**
Every line stores the document, page and line number, and the exact quote. The screen shows it. A line whose quote is not actually on the page is dropped before it reaches the plan, and there is a test for exactly that.

**"What happens when the model is unsure?"**
The line does not vanish and it does not get applied. It becomes a pending change with its page line, and a named person decides. We found this the hard way: on 31 October a physiotherapy plan's emergency instruction was held for low confidence and silently never reached the plan. It is now a test (`test_held_lines.py`).

**"Two documents arrive at once. Does the allergy check still fire?"**
Yes, and it did not use to. Processing an allergy card and a prescription in parallel could miss the conflict. There is now a per-patient advisory lock and a re-check when a new allergy arrives. Three tests fail if you remove it.

**"Who says Diclofenac is an NSAID?"**
The WHO ATC classification says it is M01AB, inside M01A. We look every substance up through the US National Library of Medicine and commit the answer as a dated file. Two of seventeen came back unconfirmed and we show that on screen rather than hiding it: the WHO puts aspirin in N02BA, not with the other NSAIDs, and bare "penicillin" is a class name with no code of its own. It is still not a pharmacist review, and the banner says so.

**"Is this medical advice?"**
No, and it is engineered not to be. It never says a medicine is safe, never tells anyone to stop or change anything, never diagnoses. It flags gaps between documents and ends every flag with a question for the doctor. The adversarial suite tries to make it break that rule 211 times and the failures are published.

**"What about security?"**
Argon2 passwords, HttpOnly rotating refresh tokens, row-level security in the database, an append-only audit log, random revocable tokens on shared links, rate limiting on login with the same reply for a locked account as a wrong password, and CSP and HSTS headers. Nothing is encrypted at rest by the application and no penetration test has been done. Real patient data would need a compliance review first. That is why the hackathon build uses fictional patients only.

**"Why Meta's models?"**
Vision reads the phone photographs, speech handles the Hindi and English of a real consulting room, and one model does the extraction, the wording and the second-pass judging. The measurements for each are on `/trust`, including what failed.

**"What is not proven?"**
Say it plainly and early. No real users. Marathi speech is experimental. The Hindi and Marathi wording has not been reviewed by a native speaker. A real recorded Hinglish consultation has not been tested. The drug list is not pharmacist-reviewed. Judges trust the project that volunteers this more than the one that waits to be caught.

## 5. What never to say

- Any sentence with "safe", "should take", "don't take", "better than", or "diagnoses".
- "It prevents hospital visits." There is no evidence and the claim is not ours to make.
- "WhatsApp integration." The chat screen is a preview on our own endpoints and it is labelled that way (D-61).
- "99% accurate." Give the measured number from `/trust` or give none.
- Anything about what the models will do in future. Show what they did.

## 6. The shape of the three minutes

| Time | Beat | The point it makes |
| --- | --- | --- |
| 0:00–0:20 | Your own opening sentence, or Priya in Toronto | Theme 1: a problem you know |
| 0:20–1:00 | Phone photos of two doctors' prescriptions become a sourced plan | It works, and sources are visible |
| 1:00–1:40 | **The Timeline**: two paracetamols overlap, the NSAID bar is red | Creativity: the moment they repeat |
| 1:40–2:10 | Open the flag: the WHO ATC class behind it, and the question for the doctor | Technical ambition: code decides, not the model |
| 2:10–2:30 | Ask "is it safe to stop this" and let it refuse | The thing nobody else shows |
| 2:30–2:50 | Elder mode **on an Android phone**, in Hindi, with the picture schedule | Who it is actually for |
| 2:50–3:00 | `/trust`, including the failures, and one line of what is not proven | Credibility |

Record the Hindi read-aloud on a phone. The voices belong to the viewer's device, and this laptop has no Hindi or Marathi voice (D-65); on it the app honestly says so instead of reading Devanagari in an English voice.

Cut from the bottom if it runs long, but never cut the refusal or the Timeline.
