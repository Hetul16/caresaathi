# 20. Demo video: scenario, shot list and recording guide

Written for the owner, who records the video. It replaces the table in `06-testing-demo.md` section 14 for the final cut; that file keeps the slides, the pitch and the judge Q&A. Everything shown is fictional and was built after Oct 26. The video is 3:00. Record in separate takes and edit; do not try to do it live in one pass.

## The story (one family, one problem)

Ramesh Kulkarni is 72, home in Nashik after a hospital stay. He has four papers: an allergy card, a clinic prescription, a discharge summary, and a second doctor's prescription. His daughter Priya lives in Pune. Dr. Joshi is the family doctor; Dr. Rao is the other doctor. Everyone is fictional.

The one thread through the video: **a mix-up between two papers is found early, a question goes to the doctor, the doctor answers, and the answer is written down.** Every scene serves that thread. Features that do not serve it are cut.

## Shot list

| Time | Scene | On screen (what you do) | Voice-over (read as written) | Proof to show |
| --- | --- | --- | --- | --- |
| 0:00 to 0:16 | **Hook** | Title card, then a still of four papers. Cut to the app's landing page | "Ramesh is 72, just home from hospital with four papers and a new prescription. His daughter Priya lives in another city. In one hospital study, almost all medication mix-ups at discharge were omissions: something missing between two papers. This is CareSaathi." | Caption: "Fictional family. Everything built since Oct 26." |
| 0:16 to 0:36 | **Photos to plan** | Patient A (fresh). Documents tab, upload `R4_photo.png`, `R1_photo.png`, `R5_photo.png` (sped up 4x while they read). Open Care plan. Click one line's source | "Priya photographs each paper. Muse Spark reads them. Every line in the plan points to its page and line, or to the doctor's own words. A line that cannot be found on the page is dropped." | The source drawer showing the exact quote |
| 0:36 to 0:56 | **Two catches, in code** | Demo family, Overview. Point at the Amoxicillin flag, then the Atorvastatin card | "Amoxicillin from one doctor, a penicillin allergy on another paper. Code matches it against a drug-family list and drafts a question for the doctor. It never says whether it is safe. And atorvastatin was on the old list and is missing from the new one." | Both cards with their two sources and the question text |
| 0:56 to 1:10 | **A blurry page** | Overview card "Two readings of the page disagree" (Losartan 5 mg or 50 mg). Click "Use this reading" on one | "A smudged strength is read twice. When the readers disagree, nothing is added. A person looks at the paper and chooses." | Both readings side by side, then the plan line with the choice |
| 1:10 to 1:25 | **Label check** | Label check tab. Upload `strip_amlodipine_5.png`, then `loose_pill.png` | "Hold a strip to the camera. It reads the printed words and compares them with the papers: label says 5 milligrams, papers say 10. And a loose pill? It refuses. It only reads print." | "Strength differs" card, then the refusal text |
| 1:25 to 2:00 | **Care crew, doctor link, answer** | Care crew tab, "Run the care crew": six steps appear. Approve the last step. Switch to the doctor window: the question is there, type the reply, send. Back on Priya's screen: Doctor link tab shows the reply, then Outcomes tab: "Record the answer", pick the doctor's reply | "Priya asks the care crew to prepare for the visit. It can only use six registered tools, and the last step, sending questions to the doctor, waits for her approval, with her name. Dr. Joshi opens a link, no sign-in, sees the plan and the question, and answers in his own words. Priya records it, and the flag closes with his exact words, her name, and how long it took." | The trace with "Asks first" and "Approved by Priya"; the Outcomes tile going from waiting to answered (the time shows as today, which is fine) |
| 2:00 to 2:20 | **The visit, in Hindi** | Visits tab: click "New visit" to show the two consent boxes, close it, then open the already-processed mock visit (speakers and transcript). Back on the Overview, the pending change Amlodipine 10 mg to 5 mg with the doctor's words. Click Confirm | "At the visit, with consent, Muse Voice Transcribe hears who said what. The doctor halves a dose; it appears as a pending change with his exact words, and only Priya can confirm it. Hindi is measured at about 10 percent word errors; Marathi is experimental." | The consent step; the "waiting for you" card with the quote |
| 2:20 to 2:38 | **Papa's side** | Elder mode (Hindi): press the button, it reads the next medicine. Then Care plan, "Picture schedule" in Hindi | "For Ramesh, one big button. It reads his medicine in Hindi, with the source. And a large-print schedule with the sun and the moon." | The elder screen and the schedule card |
| 2:38 to 2:50 | **Emergency Card** | Emergency Card tab: open the link in a private window, show allergies first and "last updated". Switch the link off, reload: not available | "A stranger scans a code and sees only what the papers confirm, and when it was updated. Priya switches it off, and it stops working." | The page before and after revoke |
| 2:50 to 3:00 | **Proof and close** | `/trust`: scroll the live-results section (14/14, 40/40, 5/5, the one miss shown) | "Every number here is public, failures included. CareSaathi never gives medical advice. It finds the mix-up early, asks the doctor, and keeps the question open until someone writes down the answer. Built on Muse Spark and Muse Voice Transcribe." | The 7 of 8 line, visible: it shows we hide nothing |

About 410 spoken words at a calm pace. If a scene runs long, use the cut list below.

## Before you record

1. **Run the preflight:** `cd backend` then `python scripts\demo_preflight.py`. All lines must say PASS. It makes one tiny live call.
2. **Two accounts or two patients.**
   - *Patient A:* a fresh patient with no documents, used only for the photo scene. Do the upload, record it, and speed it up in editing (each photo takes 17 to 50 seconds).
   - *Patient B:* the demo family ("Load the demo family"). It loads the offline reader, so it is identical every time and takes seconds.
3. **Prepare the doctor side before recording scene 6.** In Patient B's Doctor link tab, create a link for "Dr. Joshi (fictional)", open it in a second browser window (a private window or another profile), and leave it on the page that says "No questions have been sent yet".
4. **Rehearse scene 6 once.** It was rehearsed end to end on Oct 31 in live mode: the care crew run took about 18 seconds and reading the doctor's reply into changes took about 16. Speed both up. Use this reply: *"Thanks for flagging this. I will speak to Dr. Rao today. Please come back in two weeks."* It produces one follow-up ("come back, in two weeks", waiting for confirmation) and no plan change. Pre-record that step and cut the wait.
5. **Screen setup:** 1920 by 1080, browser zoom 110 to 125 percent, dark theme (the product's own look), bookmarks bar hidden, notifications off, one clean window for Priya, one for the doctor.
6. **Files in one folder:** `data\synthetic\rendered\` has the photos; `labels\` has `strip_amlodipine_5.png` and `loose_pill.png`. If a file is missing, run `python data\synthetic\render.py` and `python data\synthetic\render_labels.py`.
7. **Keep the backend in live mode** (`MODEL_MODE=live`). The photo, label, care crew and reply scenes use the real model. The demo family and the visit scene use the offline reader on purpose, so they are repeatable.

## Recording and editing

- Record each scene as its own clip. Record the voice-over separately after the picture is cut; it sounds better and avoids stumbles.
- Speed up waits (photo reading, care crew run) to 4x with a small "x4" label. Never hide a failure: if a step fails, record it again.
- Add a caption on the first frame: "Fictional data. Built Oct 26 to Nov 4." Name the models once each: Muse Spark (reading), Muse Voice Transcribe (the visit).
- Export 1080p, under the size limit on the submission form, and upload as unlisted. Watch the whole export once with sound.

## What to say, and what never to say

- Say: "synthetic" or "fictional" near the start; "it finds a mix-up and asks the doctor"; "a person approves"; "the model reads and drafts, code decides".
- Never say: that a medicine is safe or unsafe; that CareSaathi "prevents emergency visits" (we have not measured that); that Marathi is solved; that it replaces a doctor or a pharmacist.
- The one study fact: "in one hospital study, 96 percent of discrepancies at care transitions were omissions" (single hospital, 339 patients; see `12-product-requirements.md`). Say "one study".

## If something fails while recording

| Scene | If it fails | Do this |
| --- | --- | --- |
| Photo to plan | The model is slow or errors | Use the demo family's plan instead, and say nothing about speed. Re-record the upload later |
| Care crew | A step is refused or fails | That is a feature: show it as the trace working. If the run fails entirely, rerun it |
| Doctor reply | The reply reads into nothing | Use the reply text in the rehearsal step above |
| Label check | A read error | Retry once; the client already retries dropped connections |
| Visit | Not instant | Use the demo family's already-processed visit |
| Anything | The live model is down | Switch `MODEL_MODE=fake`, use the demo family for every scene, and drop the photo and label scenes |

## Cut list, if the video runs over 3:00 (cut from the top)

1. Emergency Card (12 seconds).
2. Picture schedule (keep Elder mode alone).
3. Label check (15 seconds).
4. The blurry page (14 seconds). Keep the two catches.

Never cut: the photo to plan, the flag with its question, the doctor link answer, the Trust page, and the "asks first" approval.

## After recording: submission checklist

- Public link opens on a phone on mobile data (see `19-deployment.md`).
- Repository is public, has no `.env`, and the README separates the pre-kickoff files from the hackathon work.
- Video uploaded; the form's text matches what the video shows. Do not claim a feature the video does not show or the repo does not contain.
- Submit the evening of Nov 4 IST, with time left for a retry.
