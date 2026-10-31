# 22. The remote-care story: how Priya looks after her mother from Toronto

Written for the owner, who records the demo. This is the demo's backbone: one believable family, one problem, every step with the exact clicks and the words to say. It replaces the Ramesh story in `20-demo-video-script.md` as the recommended video (that file stays as an alternative and for its setup and fallback tables).

**All people, documents and records here are fictional.** The story is inspired by a common situation, not by any real person's records. Do not use your own parents' real documents in the video, in the repository, or with the live model (see section 9).

## 1. The one sentence

Looking after a parent from far away is not about watching them. It is about **knowing** what the doctors said, **catching** the mix-up between papers, **asking** the doctor without flying home, **making sure** the plan is followed, and **knowing** that someone answered.

## 2. Why remote care is hard (and what we built for each)

| What a child far away struggles with | Where it shows up in real life | What CareSaathi does |
| --- | --- | --- |
| "What did the doctor actually say?" | A voice note, a blurry photo, "he said some tablets" | Photos and PDFs become one plan; every line shows its page and line or the doctor's exact words |
| "Are these papers consistent?" | Two doctors, two prescriptions, one allergy card in a drawer | Allergy match against a drug-family list, found by code; missing-medicine catch; duplicate-ingredient question |
| "Is this strip the one on the paper?" | Dad photographs the strip at home | Label check: reads the printed words, compares with the papers and the allergy, refuses loose pills |
| "I can't call the doctor at 3 a.m. their time" | Different time zones, a doctor who says "call the clinic" | Doctor link: the doctor sees the plan and the family's question, answers in their own words; Outcomes board keeps it open until answered |
| "Is she taking the medicines?" | A daily phone call, and "yes, yes" | **Today:** each dose is marked taken or not by whoever is with her; Elder mode with big buttons in Hindi, Marathi or English |
| "How is she really?" | Parents often say "all fine" so as not to worry you | **Pain and a note in her own words**, one entry a day, shown exactly as entered (never labelled good or bad) |
| "Who is doing what?" | Three siblings, one WhatsApp group, everything left to "someone" | **Tasks:** collect the refill, take her to physiotherapy, with a name and a date |
| "Will I know if something is wrong?" | You find out when she is already in hospital | Written warning signs from the doctor's own words; Emergency Card; the Overview shows today's gaps |

Real-world sources for the pain points: the U.S. National Institute on Aging's long-distance caregiving tips (keep one central place for the care plan and medication list; get permission before speaking with the medical team; attend telehealth visits with permission) via [MedlinePlus](https://magazine.medlineplus.gov/article/helping-from-miles-away-strategies-for-long-distance-caregiving) and [HealthDay](https://www.healthday.com/health-news/caregiving/health-tip-long-distance-caregiving-725637.html); a study of U.S.-based adult children supporting mothers in India describes "in absentia caregiver stress"; and several India-focused caregiver guides note that parents often minimise problems to avoid worrying children abroad. Several of those guides are written by care-service companies, so treat them as colour, not proof.

## 3. The cast (all fictional)

| Person | Who | Where |
| --- | --- | --- |
| **Sunita Deshmukh, 68** | The mother. Low back pain going down her left leg | Pune; speaks Marathi and Hindi |
| **Mohan Deshmukh, 72** | The father; handles the phone and the papers | Pune |
| **Priya, 34** | The daughter; software engineer, manages her mother's care | Toronto, about 9 to 10 hours behind Pune |
| **Anil, 31** | The brother; lives 20 minutes from the parents but works long hours | Pune |
| **Dr. Mehta** | Orthopaedic doctor | Pune |
| **Dr. Rao** | Family doctor who gave a second prescription | Pune |
| **Dr. Nair** | Physiotherapist | Pune |

## 4. The story, day by day

| When | What happens in real life | What Priya does in CareSaathi |
| --- | --- | --- |
| **Day 0, 6:40 a.m. in Toronto (4:10 p.m. in Pune)** | Dad sends five WhatsApp photos and a message: "Mummy's back and leg pain is not going. Doctor gave medicines. I did not understand." Mom is on the phone, tired. | Creates the patient, uploads the six pictures. Within a minute: the plan with sources, the MRI and lab report as written results, warning signs in the physiotherapist's own words |
| **Day 0, minutes later** | Priya sees two flags: Diclofenac against the NSAID allergy on a card nobody mentioned; Calpol and Dolo are two brands of one ingredient | She does not decide anything. She reads the question for the doctor |
| **Day 0, evening in Pune** | Mom takes out a strip her neighbour gave her. Dad photographs it | **Label check:** it reads "Diclofenac Sodium 50 mg", finds it on the second prescription, and shows the same flag. Priya now has a concrete question for the doctor |
| **Day 0, her night** | She cannot call a clinic at that hour | She runs the **care crew**: a visit brief with every question and its source, and a drafted message. She approves it. Dr. Mehta's link now shows the question |
| **Day 1, Pune morning** | Dr. Mehta opens the link on his phone, no sign-in, sees the allergy and the question, replies in his own words | Priya reads his exact words in the Doctor link tab and records them as the answer on the **Outcomes** board |
| **Day 3** | Clinic visit. Dad holds the phone on speaker, Priya listens from Toronto. Consent is given on screen | The visit is read: **the doctor tells them to stop the second doctor's Diclofenac**, continue the other two medicines, return in two weeks, and the written emergency signs. Priya sees the stop as a pending change with his quote and **confirms it with her name** |
| **Day 3 evening** | Mom needs the plan in a form she can follow | Priya confirms the plan. **Picture schedule** in Hindi; Elder mode on the home tablet; Anil gets an invitation to the family |
| **Days 4 to 14** | Mom taps "I took it" and a pain number each day; Anil picks up the refill; Dad keeps the Emergency Card in his wallet | Each morning in Toronto Priya opens **Today**: how many doses are marked, the pain number in Mom's own words, what is open. Tasks show who is doing what |
| **Day 14** | Follow-up due, refill estimate near | The follow-up and the refill date come from code, with their inputs shown; the Outcomes board shows every question answered |

What changed for Priya: she stopped phoning four times a day to ask "did you take it?", she asked the doctor the right question the same day, and she knew it was answered.

## 5. The demo, step by step (3:00)

Before you record, read sections 7 and 8.

**Setup.** Run `python data\synthetic\make_demo_folders.py`. Use the folder `CareSaathi_Demo_Uploads\Sunita_Deshmukh\` on your desktop. Sign in as the tour account or sign up fresh; create a patient "Sunita Deshmukh", language Hindi.

| Time | Scene | On screen: exactly what you do | Voice-over |
| --- | --- | --- | --- |
| 0:00 to 0:20 | **The message** | A reenactment WhatsApp screen (labelled "reenactment") with Dad's five photos and "I did not understand". A clock shows Toronto 6:40 a.m. and Pune 4:10 p.m. | "Priya lives in Toronto. Her mother in Pune has back and leg pain. Her father sends five photos of papers and says, I did not understand. This is the hardest part of caring from far away: you cannot see, and you cannot ask. This is CareSaathi." |
| 0:20 to 0:45 | **Papers to one plan** | Documents tab, choose all six pictures at once. While they read (speed up), say the next line. Then Care plan: click a source chip; click "Explain this" | "She uploads everything. Muse Spark reads the photos. In under a minute there is one plan, and every line points to its exact page and line. The MRI and the lab report are copied as written, never interpreted." |
| 0:45 to 1:10 | **Two catches** | Overview: the Diclofenac flag, then the paracetamol duplicate question. Point at the sources | "Two catches, both in code, not guessed by a model. A second doctor's Diclofenac is in the same family as an NSAID allergy on an old card. And two brands of paracetamol. It never says what is safe. It asks the doctor." |
| 1:10 to 1:25 | **The strip at home** | Label check tab: upload `extras\strip_diclofenac_50.png`, then `extras\loose_pill.png` | "That evening her father photographs the strip her mother is holding. It reads the printed words and finds the same flag. And a loose pill? It refuses. It only reads print." |
| 1:25 to 2:00 | **Asking the doctor from 9,000 kilometres** | Care crew tab: run it, six steps, approve the last one. Switch to the doctor's window: the question is there; type the reply. Back: Doctor link shows the reply; Outcomes: "Record the answer" with the reply | "She cannot call the clinic at night. The care crew prepares a brief. It can only use six registered tools, and sending the question waits for her approval, with her name. Dr. Mehta opens a link, no sign-in, and answers in his own words. The flag stays open until his words are written down." |
| 2:00 to 2:25 | **The visit, on speakerphone** | Visits tab: open the mock visit V5 (Hinglish). Overview: the pending stop of Diclofenac with the doctor's quote; click Confirm | "At the visit her father holds the phone. With consent, Muse Voice Transcribe hears who said what. The doctor tells them to stop that tablet. It appears as a pending change with his exact words, and only Priya can confirm it." |
| 2:25 to 2:50 | **Making it work at home** | Care plan: Confirm all, then the Picture schedule. Elder mode: tap "I took it" and a pain number. Back in Family mode: the Today tab and the Tasks tab (Anil: collect the refill) | "For her mother: one screen, her language, big buttons. Each dose she marks, and her pain in her own words, show up for Priya every morning. Her brother has his own task. No more four phone calls a day." |
| 2:50 to 3:00 | **Proof and close** | `/trust`: scroll the live numbers | "Every number here is public, failures included. CareSaathi never gives medical advice. It helps a family far away know, catch, ask, and be sure someone answered." |

**Cut list if you run over:** drop the strip at home, then the tasks, then the picture schedule.

## 6. Click path and what each step should show

1. **Sign in** at `http://localhost:3000/login`. Use `localhost`, not `127.0.0.1`.
2. **Documents tab → Choose files:** select the six pictures. Rows show "Added to the plan" within about 40 seconds.
3. **Overview:** red allergy banner (NSAIDs); a Diclofenac flag with a question; paracetamol duplicate question.
4. **Care plan tab:** medicines with schedules, the written warning signs with levels, MRI findings and lab values as results, instructions. Click any grey chip for the exact quote.
5. **Label check tab → "Take or choose a photo":** `strip_diclofenac_50.png` shows a match with the second prescription and the same family flag; `loose_pill.png` is refused.
6. **Doctor link tab:** type "Dr. Mehta (fictional)", Create link, copy it into a private window.
7. **Care crew tab → Run the care crew:** six steps; approve the last. In the private window refresh, type a reply, send.
8. **Doctor link tab → "Read changes from this reply"** (about 15 seconds; speed it up) if the reply contains a timing, then **Outcomes tab → Record the answer** and pick the doctor's reply.
9. **Visits tab:** start a new mock visit and pick **V5** (scripted: it replays the script's recorded extraction, so it is identical every time; the live model's reading of such scripts is measured on the Trust page); **Overview:** "Waiting for you" shows the stop of Diclofenac with the doctor's words; click Confirm.
10. **Care plan tab → Confirm all**, then **Picture schedule** (try हिन्दी and मराठी).
11. **Elder mode** (top right): tap "I took it" on a due dose and a pain number.
12. **Today tab:** the dose shows taken with Priya's name; the pain entry shows exactly as entered. **Tasks tab:** add "Collect the Pregabalin refill", assign it to a member, mark it done.
13. **Trust page** for the measured numbers.

## 7. How to make it feel real

- **Start with the human moment, not the product.** A 15-second reenactment of the WhatsApp message and a two-clock graphic (Toronto 6:40 a.m., Pune 4:10 p.m.) sets the stakes. Label it "reenactment" on screen; do not present a fabricated chat as genuine.
- **Show the clutter first.** Two seconds of the six pictures in a folder before they become one plan makes the "after" land.
- **Use the phone-photo versions.** The `_photo` pictures are tilted and shadowed on purpose.
- **Speak like a worried daughter, not like a brochure.** Short sentences, one emotion per scene: worry (the message), relief (one plan), alarm (the flag), calm (the doctor's answer), trust (the numbers).
- **Never hide waiting.** Speed it up and label it "x4". Never cut away from a failure; re-record instead.
- **Keep one thread.** Every scene answers one of: know, catch, ask, check in, coordinate.
- **Pick real-feeling details**, all fictional: a pharmacy bag, a strip with a batch number, a family WhatsApp group name ("Deshmukh family"), a clinic with a Pune address.
- **Be honest on screen.** A "fictional data" caption on the first frame; the Trust page's one miss left visible.
- **Do not involve a real parent.** If you want a person in the video, use an adult friend or relative who agrees to play the role, and do not show real documents.

## 8. What it does not do (say this if asked)

- **It cannot see or verify.** "Taken" means a person marked it. "Not marked" only means nobody marked it; it does not say what that means, and it never says to take a dose late or to skip one.
- **No push notifications yet.** It is a website. Priya has to open Today. WhatsApp and phone alerts are on the roadmap.
- **The parent needs a device and someone to set it up** (here, the tablet with the family's signed-in session). A device login for the elder alone is not built.
- **Pain numbers are shown as entered.** There is no trend line, no "better" or "worse", and no alert threshold, by design: reading a pattern into them is a clinical judgement.
- **Speech:** Hindi and English are solid; Marathi speech is experimental (see `/trust`).
- **It does not replace a doctor, a pharmacist or a carer on the ground.**

## 9. If you ever use it for your own parents (read this)

This build is for fictional data. Before any real use:
1. **Their agreement first.** The NIA tips say to get permission before speaking with the medical team; the same applies to putting their records in an app.
2. **Use the standard model tier, not the contributor tier.** The cheaper contributor tier may let Meta train on what is sent. Set `ALLOW_CONTRIBUTOR_MODELS=false`. The cost then rises about twelve-fold, which is still a few cents per document.
3. **Run it locally or on your own server,** not on a shared public deployment, and do not commit any record to the repository.
4. **A pharmacist should review the allergy and drug-family list.** It is a starter list.
5. **Legal advice** is needed before offering it to anyone else.
6. **It supports your care; it does not replace the doctor's advice.** Every flag ends with a question for them.

## 10. Files that tell this story

- Documents: `data/synthetic/sunita/docs/S1` to `S6` (pictures in `CareSaathi_Demo_Uploads\Sunita_Deshmukh\`).
- Strip and loose pill pictures: `CareSaathi_Demo_Uploads\Sunita_Deshmukh\extras\`.
- The speakerphone visit: `data/synthetic/ramesh/visits/V5.json` (the scripts live in one folder for historical reasons; V5 is about Sunita). Pick **V5** in the mock visit list.
- Tests that protect the story: `backend/tests/test_sunita_set.py`, `test_visits.py` (V5), `test_label_check.py` (salt name), `test_checkins.py`, `test_tasks.py`, `test_allergy_order.py`.
