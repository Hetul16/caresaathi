# 25. Recording the video against the live deployment

Written for the owner, who records the video. `docs/20-demo-video-script.md` holds the story, the shot list and the voice-over, and it
still stands. This file is the operational layer for recording against the **deployed** site rather than a laptop, and it exists because
three things behave differently there. Read it once before you set up, then keep the shot list from `20` open while you record.

The live site is **https://caresaathi-phi.vercel.app**. The API behind it is `https://caresaathi-api-51mf.onrender.com`; it is never shown
on screen and never typed into the submission.

## 1. Record against the live site, not localhost

The address bar is evidence. A judge who sees `localhost:3000` has to take the deployment on trust; one who sees the real domain does not.
Everything in the shot list has been exercised against the live site, so there is nothing the laptop can do that the deployment cannot.

Two consequences, both handled below: the free API sleeps, and account creation is rate limited.

**Do not run `backend/scripts/demo_preflight.py` for this.** It is hardcoded to `127.0.0.1:8000` and reads the local `.env`, so it tells you
about your laptop and nothing about the deployment. The live equivalents are in section 6.

## 2. The three live-only traps

**Account creation locks after ten.** `register_ip` allows ten new accounts per address per hour, and the eleventh attempt blocks that
address for a full hour (`backend/app/safety/ratelimit.py`). A recording session with retakes will burn through ten without noticing, and
then you are stopped for an hour in the middle of filming. **Create every account you need before you start, and never create one on
camera more than once.** Two is enough: Priya's and the second window's. This limit was measured against the deployment on Nov 4; it keys
on the real visitor, not on Vercel's proxy, so it protects you from strangers without ever counting their attempts against you.

**The API sleeps after fifteen idle minutes** and takes about a minute to answer the first request after that. Open the site and press one
button a minute before you hit record, and again after any long break. The keep-warm ping in section 5 removes this for judging, but set it
up anyway before you record.

**Uploaded files do not survive a restart** (D-73). The container has no persistent disk, so a redeploy or a wake-from-sleep loses every
file that was uploaded to it; the database rows stay, so a document can outlive its bytes. In practice this means: do not record the upload
scene, go away for two hours, and expect to film the plan built from it. Record a scene and the scenes that depend on it in the same
sitting, or press "Load the demo family" again and start that thread fresh.

## 3. Set-up, thirty minutes before you record

1. **Wake the API.** Open https://caresaathi-api-51mf.onrender.com/healthz and wait for `{"status":"ok"}`. First load can take a minute.
2. **Create both accounts now, by hand, and write the passwords down.**
   - *Priya* — the main window, everything is filmed here.
   - *Doctor* — not an account at all. The doctor opens a link with no sign-in, so this is just a second browser profile or a private
     window. It costs nothing against the rate limit.
3. **Load the demo family** in Priya's account. This is the repeatable patient: identical every time, and it takes seconds.
4. **Create a second, empty patient** for the upload scene, so the photos land somewhere with no history. Name it anything fictional.
5. **Prepare the doctor window.** In Priya's Doctor link tab, create a link for "Dr. Joshi (fictional)", open it in the second profile,
   and leave it sitting on "No questions have been sent yet".
6. **Have the files in one folder.** `data\synthetic\rendered\` holds the document photos; `data\synthetic\rendered\labels\` holds the
   label-check pictures. If any are missing, run `python data\synthetic\render.py` and `python data\synthetic\render_labels.py`.
7. **Screen:** 1920x1080, browser zoom 110-125%, bookmarks bar hidden, notifications off, one clean window per role.

## 3b. Two orderings that decide whether a scene works

Both were found by running the scenes on Nov 4, not by reading the code. Neither produces an error: the
scene simply comes out weaker, and you would not notice until editing.

**Create the doctor link before you run the care crew.** The crew has six registered tools and the sixth,
`message_doctor_draft`, is the one that waits for approval. It needs a doctor link to draft to. Run the crew
first and it stops after five steps, nothing lands in the approvals queue, and the whole point of the scene --
the model reaching for the one tool it is not allowed to finish -- never appears. With the link already there,
the trace ends `message_doctor_draft  awaiting_approval` and the queue holds one item.

**The doctor cannot reply until you approve the question.** Sending a question answers 202, which means queued,
not sent. Until a named member approves it, the doctor's page shows no question and a reply is refused outright
by the database function. So the order on camera is: send the question, show the approvals queue, approve it
with your name, *then* switch to the doctor window. Switch too early and the doctor window is empty, which looks
like a bug and is actually the safety rule holding.

That second one is worth saying out loud in the voice-over. It is the clearest demonstration in the whole product
that the model cannot act by itself.

## 4. What is verified, and what you must check yourself

Against the live site on Nov 4, 2026:

| Area | How it was checked | Result |
| --- | --- | --- |
| The whole judge path, and the safety invariants | `backend/scripts/walkthrough.py` against the live URL | 23 / 23 |
| Every page in a real browser at phone size, all 18 tabs | `backend/scripts/browser_check.py` against the live URL | 20 / 20 |
| Public reachability, headers, no login wall | `backend/scripts/launch_check.py` against the live URL | 9 / 9 |
| Approvals, invitations, a second member's access, doctor links, tasks, check-ins, outcomes, tracking, second reads | a feature sweep over the live API | 51 passed |
| Emergency Card and doctor link revocation | by hand against the live API and the live page | the API answers 404, the page shows no patient |
| Confirming a plan item, then recording a dose | by hand against the live API | the dose records and reads back "confirmed by <name>" |

**Three things no script here can check, and you must do by hand before you film them:**

1. **The microphone.** Nothing automated has ever exercised recording. Open the live site on your phone, go to Elder mode, and press the
   button. The browser must ask for permission and the level meter must move.
2. **Read-aloud in Hindi and Marathi.** The speech comes from the browser's own voices, not from the server, so it depends on the device.
   Android usually has a Hindi voice; Marathi is often missing. Check on the exact device you will film, and if Marathi is silent, film
   the Hindi one and say "Hindi" in the voice-over.
3. **The four README diagrams.** They have never been rendered. Open the README on GitHub and look at them before the repository goes
   public.

## 5. Keep it awake for judging

A free pinger on **cron-job.org** (no payment card) hitting

```
https://caresaathi-api-51mf.onrender.com/healthz
```

every 10 minutes. That is 744 hours a month, inside the 750 the free plan allows for one service. Set it up before you record, not after:
it makes the recording session smoother too.

## 6. The live check, right before you record

From the repository root, with the virtual environment already built:

```
backend\.venv\Scripts\python backend\scripts\launch_check.py  https://caresaathi-phi.vercel.app
backend\.venv\Scripts\python backend\scripts\walkthrough.py   https://caresaathi-phi.vercel.app
```

`launch_check` is instant and proves the site is open to a stranger. `walkthrough` takes a few minutes, creates one throwaway account
(**one of your ten**, so run it once, not repeatedly) and proves the whole chain still works end to end.

Do not run `browser_check.py` as well right before filming unless something looks wrong; it creates another account.

## 7. If something fails while the camera is rolling

- **A page hangs on first load:** the API went to sleep. Wait, let it answer, and re-take. Do not refresh repeatedly.
- **"Too many attempts":** you created your eleventh account. Stop creating accounts; sign in as Priya and carry on with the accounts you
  already have. The block clears in an hour.
- **An uploaded document has vanished:** the container restarted. Press "Load the demo family" and film that thread instead.
- **The model is slow on a photo:** this is normal, 17 to 50 seconds per page. Film it and speed it up 4x in editing, as `docs/20` says.

## 7b. The read, in one piece

The voice-over in `docs/20` lives inside a table, which is unreadable while you are also driving the mouse.
Here it is as one continuous read. The bracketed lines are what you do, not what you say. It is 433 spoken
words, which is 3:00 flat at about 145 words a minute and 3:12 at a slower 135. That is deliberately tight
against the limit: read it aloud with a timer once, and if you are over, take a whole scene out using the cut
list in `docs/20` rather than speaking faster.
The product's whole claim is that it slows a family down at the right moment; the voice-over should sound
like that.

> **[0:00 - title card, then four papers, then the landing page]**
>
> Ramesh is seventy-two and just home from hospital with four papers and a new prescription. His daughter
> Priya lives in another city. In one hospital study, almost all medication mix-ups at care transitions were
> omissions -- something missing between two papers. This is CareSaathi. Everything you are about to see is
> fictional.
>
> **[0:16 - fresh patient, Documents tab, upload three photos, speed up 4x, open Care plan, click a source]**
>
> Priya photographs each paper. Muse Spark reads them. Every line in the plan points back to its page and
> line, or to the doctor's own words. A line that cannot be found on the page is dropped rather than guessed.
>
> **[0:36 - demo family, Overview, point at the Amoxicillin flag, then the missing medicine]**
>
> Amoxicillin from one doctor. A penicillin allergy on another paper. Code matches that against a vetted
> drug-family list and drafts a question for the doctor. It never says whether it is safe. And here, a
> medicine that was on the old list and is missing from the new one.
>
> **[0:56 - the two-readings card, choose one]**
>
> A smudged strength is read twice. When the two readings disagree, nothing is added. A person looks at the
> paper and chooses.
>
> **[1:10 - Label check tab, upload a strip, then a loose pill]**
>
> Hold a strip to the camera. It reads the printed words and compares them with the papers. And a loose pill?
> It refuses. It only reads print.
>
> **[1:25 - Care crew tab, run it, six steps appear, the sixth is waiting]**
>
> Priya asks the care crew to prepare for the visit. It can only use six registered tools, and the sixth --
> sending the questions to the doctor -- stops and waits. Watch what happens if nobody approves it.
>
> **[1:40 - switch to the doctor window: it is empty. Switch back, approve with your name, switch again]**
>
> The doctor's page is empty. The question has not been sent, because the model cannot send it. Priya
> approves it, with her name on it. Now it is there.
>
> **[1:55 - the doctor types a reply and sends; back on Priya's screen, Outcomes]**
>
> Dr Joshi opens a link with no sign-in, reads the question, and answers in his own words. Priya records it,
> and the flag closes with his exact words, her name, and how long it took.
>
> **[2:15 - Visits tab: show the consent boxes, then the pending change with the doctor's quote, confirm it]**
>
> At the visit, with consent on screen, Muse Voice Transcribe hears who said what. The doctor halves a dose.
> It arrives as a pending change carrying his exact words, and only Priya can confirm it.
>
> **[2:32 - Elder mode in Hindi: press the button; then the picture schedule]**
>
> For Ramesh, one big button. It reads his medicine aloud in Hindi, with the source. And a large-print
> schedule he can keep on the fridge.
>
> **[2:45 - Emergency Card in a private window, then switch it off and reload]**
>
> A stranger sees only what the papers confirm, and when it was last updated. Priya switches the link off,
> and it stops working.
>
> **[2:52 - the Trust page, scrolling through the results including the failures]**
>
> Every number here is public, failures included. CareSaathi never gives medical advice. It finds the mix-up
> early, asks the doctor, and keeps the question open until somebody writes down the answer.

**The sentence to land, if you only land one:** *the model reads and drafts; code decides; a person approves.*

**Never say** that a medicine is safe or unsafe, that CareSaathi prevents emergency visits (not measured),
that Marathi is solved, or that it replaces a doctor or a pharmacist.

## 8. After recording

The submission checklist is in `docs/20-demo-video-script.md`, section "After recording". The three that are specific to the deployment:

- The link you submit is the **Vercel** address, never the Render one.
- `PUBLIC_LAUNCH.md` is the order for making it public: API gate first, then the website, then the repository.
- Fill the **Demo video** row in `README.md`; the **Live site** row is already filled.
