# 24. Manual test walkthrough

A full pass over the running website by hand, in the order a judge would meet it. About 30 minutes. Everything here uses the fictional
patients in `demo_uploads/`; never upload a real person's records.

Tick each box. When something fails, note the screen and the exact words on it, because that is what is needed to fix it.

## 0. Before you start

- [ ] Docker Desktop is running, and `docker ps` lists the database container.
- [ ] Backend answers: open `http://127.0.0.1:8000/healthz` and see `{"status":"ok"}`.
- [ ] Website opens at `http://localhost:3000`.
- [ ] The upload folders are on your desktop: `CareSaathi_Demo_Uploads/Sunita_Deshmukh/`.
- [ ] Open the browser console (F12). Leave it open the whole way. **An error there is a finding even if the screen looks right.**

## 1. Signing up (3 min)

1. Go to `http://localhost:3000`. Read the landing page.
2. Sign up with a new email, e.g. `test1@example.com`, password `correct-horse-battery`.
3. Tick the consent boxes.
4. On the onboarding screen, add a patient: **Sunita Deshmukh**, language **Hindi**.

- [ ] Sign-up works and lands on the app.
- [ ] A password shorter than 10 characters is refused with a clear message.
- [ ] Nothing in the console.

## 2. Documents become a plan (6 min) — the core claim

Open **Documents** and upload from `Sunita_Deshmukh/` **one at a time, in order**, waiting for each to finish:

| # | File | What should happen |
| --- | --- | --- |
| 1 | `01_allergy_card.png` | Allergy banner turns red: **NSAIDs** |
| 2 | `02_orthopaedic_prescription.png` | 5 medicines appear in the care plan |
| 3 | `03_mri_lumbar_spine_report.png` | 4 findings as results, nothing interpreted |
| 4 | `04_physiotherapy_plan.png` | Instructions and warning signs with levels |
| 5 | `05_lab_report.png` | 3 lab values with their printed reference range |
| 6 | `06_second_doctor_prescription.png` | **Diclofenac flagged against the NSAID allergy**, and a paracetamol duplicate question |

- [ ] Each document reaches "Added to the plan" or "Some lines need a check" (both are fine; "Could not be read" is a finding).
- [ ] **Every single plan line has a blue source chip.** Click one: it shows the page and the quoted line.
- [ ] The allergy banner never says "no allergies" before the card is uploaded; it says **not recorded**.
- [ ] The Diclofenac conflict card appears, and the **Why** line opens to show the WHO ATC class **M01A**.
- [ ] A lab value shows as printed, with no verdict like "high" or "normal".

## 3. The Timeline (2 min) — the moment to show a judge

Open **Timeline**.

- [ ] Six bars, each starting on its document's printed date.
- [ ] Calpol and Dolo overlap, and the overlap is **striped** on both bars.
- [ ] The Diclofenac bar is **red with a "!"**.
- [ ] Dolo's bar **fades out** ("no end given"), because no number of days is printed.
- [ ] Tap a bar: it shows the sum in words, e.g. "Document dated 23 Oct 2026, plus 5 days as printed: last day 27 Oct 2026."

## 4. Confirming, and Today (3 min)

1. **Care plan** → **Confirm all**.
2. Open **Today**.

- [ ] Confirmations are recorded with **your name**.
- [ ] Today shows the doses by time slot. **Diclofenac is NOT scheduled** (held by the open allergy flag).
- [ ] "Mark taken" records your name and the time.
- [ ] A pain number and a note can be saved.

## 5. Asking, and the refusal (2 min) — the other moment to show

Open **Ask**.

- [ ] "What are my medicines?" is answered from the plan, with sources.
- [ ] **"Is it safe to stop Pregabalin?"** is **refused** and sends you to the doctor or pharmacist. This must never be answered.
- [ ] "Do I have any allergies?" names NSAIDs with its source.

## 6. The chat preview (2 min)

Open **Chat**.

- [ ] The amber badge says **WhatsApp-style preview, not connected to WhatsApp**.
- [ ] "Today's medicines" returns tap buttons; tapping one marks the dose taken.
- [ ] The **+** button sends a photo from the folder and the reply explains what happened.
- [ ] An unsafe question is refused here too.

## 7. Label check (2 min)

Open **Label check**, use `Sunita_Deshmukh/extras/`.

- [ ] `strip_diclofenac_50.png` is read, matched to the documents, and **flagged against the NSAID allergy**.
- [ ] `loose_pill.png` is **refused**: a loose pill cannot be identified from how it looks.

## 8. Elder mode and languages (3 min)

Press **Elder mode** in the dashboard header. This is a preview: you are still signed in as yourself, so you can go back. Section 9 is the
real thing.

- [ ] The screen opens on **Take now** with the medicines due at this hour, not the whole day. Each one has a full-width **I took it**.
- [ ] Only **confirmed** medicines appear, and nothing under an open allergy flag. A held medicine shows "Your family is checking something
      with the doctor" instead.
- [ ] **Later today** and **Finished today** are each one folded line. Open and close them.
- [ ] **How are you feeling?** is folded too. Open it, tap a number, and it comes back pressed with the number shown on the folded line.
- [ ] Tapping **I took it** moves that medicine into Finished today, and "Saved. Your family can see it." appears where the row was.
- [ ] Switch to **हिन्दी**: the medicines, the buttons and the folded lines all become Hindi.
- [ ] On this laptop, read-aloud says **"this device has no Hindi voice"** and the Listen buttons are disabled. That is correct (D-65).
- [ ] In **English**, **Read this to me** speaks the medicines due now.
- [ ] **Open the site on your Android phone** (same Wi-Fi, the laptop's IP) and check Hindi read-aloud there. This is the one test only you
      can do.

## 9. The patient's own sign-in (4 min) — the separation claim

The person being cared for is a member of their own circle with no rights over it (D-66). Do this in a **private window**, or you will still
be signed in as yourself and prove nothing.

- [ ] **Family → Invite someone → The patient.** The three permission checkboxes dim and strike through, and cannot be ticked.
- [ ] Make the link, open it in a private window, and create her account. Signing up sends her straight to **Elder mode**.
- [ ] In that window, type `/app` in the address bar. It bounces back to `/app/elder`. She never sees the dashboard.
- [ ] There is **no link off her screen** except the Emergency card. The logo is plain text, and there is no Trust link.
- [ ] Mark a dose and tap a pain number as her.
- [ ] Back in **your** window, open **Today**. Both appear, under **her** name, not yours. That attribution is the point of the whole
      section: before this, Elder mode ran on a relative's session and her pain number was filed under their name.
- [ ] Still in your window, **Family**: she is listed as "The patient · Elder mode", with no button to give her approval rights.

## 10. Emergency Card and sharing (2 min)

- [ ] **Emergency Card** shows allergies first and when it was last updated.
- [ ] Open its link in a **private window**: it works with no sign-in.
- [ ] **Revoke** it, reload the private window: it is gone.
- [ ] **Doctor link**: create one, open it in a private window, send a reply, and see the reply come back verbatim.

## 11. Permissions (2 min) — the security claim

- [ ] Sign up a **second account** in a private window, with its own patient.
- [ ] From that account, paste the **first** patient's URL. It must refuse. This is row-level security in the database, not only in the API.
- [ ] Sign out and back in. The session survives.
- [ ] Type a wrong password **8 times**: you are locked out with "Too many attempts". The right password then also says the same thing, which is intended, because the lockout must not reveal that an account exists.

## 12. Trust page and phone layout (2 min)

- [ ] `/trust` opens **without signing in** and lists the live measurements **and the failures**.
- [ ] Resize the window to phone width (or use the phone). No sideways scrolling of the page. The Timeline scrolls sideways on its own, which is intended.

## What counts as a finding

- Any red error in the browser console.
- A plan line with no source chip.
- Any sentence that says a medicine is safe, or tells anyone to stop, skip or change something.
- An allergy shown as "none" when nothing was recorded.
- A date shown that is not printed on the document.
- A document stuck on "Reading…" for more than about two minutes.
