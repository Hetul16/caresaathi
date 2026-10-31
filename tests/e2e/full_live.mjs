// Whole-product end-to-end run against the LIVE backend (MODEL_MODE=live), following docs/20-demo-video-script.md. Synthetic data only.
import { chromium } from "playwright-core";
const out = process.env.TEMP + "/shots";
const R = "C:/Users/Hetul/Desktop/caresaathi/data/synthetic/rendered";
const BASE = "http://localhost:3000";
const b = await chromium.launch({ executablePath: "C:/Program Files/Google/Chrome/Application/chrome.exe", headless: true });
const errs = [];
let pass = 0, fail = 0;
const ok = (n, c, x = "") => { c ? pass++ : fail++; console.log(c ? "PASS" : "FAIL", n, x); };
const wait = (ms) => new Promise((r) => setTimeout(r, ms));
function track(page, tag) {
  page.on("console", (m) => { if (m.type() === "error" && !/favicon|WebSocket|401|Failed to load resource|Cannot reach/.test(m.text())) errs.push(tag + ": " + m.text().slice(0, 160)); });
  page.on("pageerror", (e) => errs.push(tag + " PAGEERROR " + e.message.slice(0, 160)));
}
async function signup(ctx, tag) {
  const page = await ctx.newPage(); track(page, tag);
  await page.goto(BASE + "/signup", { waitUntil: "networkidle" });
  const inputs = page.locator("input");
  await inputs.nth(0).fill("Priya Kulkarni"); await inputs.nth(1).fill(`live${Date.now()}${tag}@example.com`);
  await page.locator("input[type=password]").fill("correct-horse-battery");
  for (const c of await page.locator("input[type=checkbox]").all()) await c.check();
  await page.locator("form .btn-primary").first().click();
  await page.waitForURL(/onboarding/, { timeout: 30000 });
  return page;
}
const tab = (page, name) => page.getByRole("button", { name: new RegExp("^" + name) }).first().click();

// ============================== PATIENT A: photos -> plan -> flags -> label check ==============================
const ctxA = await b.newContext({ viewport: { width: 1360, height: 900 } });
const A = await signup(ctxA, "a");
await A.getByLabel("Their name").fill("Ramesh Kulkarni");
await A.getByRole("button", { name: /continue to the care plan/i }).click();
await A.waitForURL(/\/app$/, { timeout: 30000 });
await A.getByText("Ramesh Kulkarni").first().waitFor({ timeout: 30000 });
await tab(A, "Documents");
let t0 = Date.now();
await A.locator("input[type=file]").first().setInputFiles([`${R}/R4_photo.png`, `${R}/R1_photo.png`, `${R}/R5_photo.png`]);
let added = 0;
for (let i = 0; i < 100 && added < 3; i++) {
  await wait(3000);
  added = await A.getByText("Added to the plan").count();
  if (await A.getByText("Could not be read").count()) break;
}
ok("three photos read by the live model", added === 3, `${added} added in ${Math.round((Date.now() - t0) / 1000)}s`);
ok("no document failed", (await A.getByText("Could not be read").count()) === 0);
await A.screenshot({ path: out + "/fl-1-docs.png", fullPage: true });
await tab(A, "Overview");
await A.waitForTimeout(1500);
ok("allergy banner shows Penicillin from the photo", await A.getByText(/Allergies:/).first().waitFor({ timeout: 20000 }).then(() => true).catch(() => false) && await A.getByText(/penicillin/i).count() > 0);
ok("Amoxicillin flagged against the allergy by code", await A.getByText(/Possible allergy conflict/).count() > 0 && await A.getByText(/Amoxicillin/).count() > 0);
await tab(A, "Care plan");
ok("plan has Metformin with a source", await A.getByText(/Metformin/).count() > 0 && await A.locator(".source-chip").count() > 0);
await A.locator(".source-chip").first().click();
ok("source drawer shows the exact quote", await A.locator("aside mark, .sheet mark, blockquote mark").count() > 0);
await A.keyboard.press("Escape");

await tab(A, "Label check");
await A.locator("#label-file").setInputFiles(`${R}/labels/strip_amlodipine_5.png`);
await A.getByText("Strength differs from the documents").waitFor({ timeout: 60000 });
ok("label check: strength differs from the documents", true);
ok("label check shows both numbers", await A.getByText(/5 mg/).count() > 0 && await A.getByText(/10 mg/).count() > 0);
await A.locator("#label-file").setInputFiles(`${R}/labels/loose_pill.png`);
await A.getByText(/cannot tell what a loose pill/i).first().waitFor({ timeout: 60000 });
ok("label check refuses a loose pill", true);
await A.locator("#label-file").setInputFiles(`${R}/labels/box_amoxicillin.png`);
await A.waitForTimeout(500);
await A.getByText(/matches an allergy|same family as the recorded allergy|belongs to the same family/i).first().waitFor({ timeout: 60000 }).then(() => ok("label check: Amoxicillin box raises the penicillin family question", true)).catch(() => ok("label check: Amoxicillin box raises the penicillin family question", false));
await A.screenshot({ path: out + "/fl-2-label.png", fullPage: true });

// ============================== PATIENT B: demo family -> crew -> doctor -> outcomes ==============================
const ctxB = await b.newContext({ viewport: { width: 1360, height: 900 }, permissions: ["clipboard-read", "clipboard-write"] });
const B = await signup(ctxB, "b");
await B.getByRole("button", { name: /load the demo family/i }).click();
await B.waitForURL(/\/app$/, { timeout: 120000 });
await B.getByText("Ramesh Kulkarni").first().waitFor({ timeout: 30000 });
await B.getByText("Two readings of the page disagree").waitFor({ timeout: 30000 });
ok("demo family loads in live mode with the blurry-page card", true);
await B.getByRole("button", { name: /use this reading/i }).nth(1).click();
await B.getByText(/Added to the plan with your name/).waitFor({ timeout: 20000 });
ok("two-reader choice applied", true);

await tab(B, "Doctor link");
await B.getByLabel("Doctor's name").fill("Dr. Joshi (fictional)");
await B.getByRole("button", { name: /create link/i }).click();
await B.getByText(/shown once/).waitFor({ timeout: 15000 });
const url = (await B.locator("code").first().innerText()).trim().replace(/^https?:\/\/[^/]+/, BASE);
const ctxD = await b.newContext({ viewport: { width: 1100, height: 900 } });
const D = await ctxD.newPage(); track(D, "d");
await D.goto(url, { waitUntil: "networkidle" });
ok("doctor page opens with no sign-in and shows the allergy", await D.getByText("Penicillin").count() > 0);

await tab(B, "Care crew");
t0 = Date.now();
await B.getByRole("button", { name: /run the care crew/i }).click();
await B.getByText("Waiting for approval").first().waitFor({ timeout: 90000 });
ok("care crew: six steps, last one waits for approval", (await B.locator(".tstep").count()) === 6, `${Math.round((Date.now() - t0) / 1000)}s`);
await B.screenshot({ path: out + "/fl-3-crew.png", fullPage: true });
await B.getByRole("button", { name: /approve and send to the doctor/i }).click();
await B.getByText(/Approved by Priya/).first().waitFor({ timeout: 20000 });
ok("approval is named in the trace", true);
await D.reload({ waitUntil: "networkidle" });
ok("doctor sees the family's questions after approval", await D.getByText(/Questions from the family/).count() > 0);
await D.getByLabel(/Your reply/).fill("Thanks for flagging this. I will speak to Dr. Rao today. Please come back in two weeks.");
await D.getByRole("button", { name: /send reply/i }).click();
await D.getByText(/Sent\. The family can see it/).waitFor({ timeout: 15000 });
ok("doctor reply sent", true);

await tab(B, "Doctor link");
await B.getByText(/exact words/).first().waitFor({ timeout: 20000 });
t0 = Date.now();
await B.getByRole("button", { name: /read changes from this reply/i }).click();
await B.getByText(/waiting for you on the Overview|Nothing in this reply/).first().waitFor({ timeout: 90000 });
ok("reply read into a follow-up by the live model", await B.getByText(/waiting for you on the Overview/).count() > 0, `${Math.round((Date.now() - t0) / 1000)}s`);

await tab(B, "Outcomes");
await B.getByText("questions raised").waitFor({ timeout: 15000 });
await B.getByRole("button", { name: /record the answer/i }).first().click();
await B.getByRole("radio").first().check();
await B.getByRole("button", { name: /record with my name/i }).click();
await B.getByText(/Answer recorded with your name/).waitFor({ timeout: 15000 });
ok("outcomes: answered with the doctor's exact words", await B.getByText(/exact words, from the doctor link/).first().waitFor({ timeout: 15000 }).then(() => true).catch(() => false));
await B.screenshot({ path: out + "/fl-4-outcomes.png", fullPage: true });

// visit, confirm, elder, schedule, card
await tab(B, "Visits");
await B.getByText("Mock visit · scripted").first().click();
await B.getByText("What the doctor said").waitFor({ timeout: 15000 });
ok("visit transcript with speakers opens", true);
await tab(B, "Overview");
const before = await B.getByRole("button", { name: /^Confirm$/ }).count();
await B.getByRole("button", { name: /^Confirm$/ }).first().click();
let after = before;
for (let i = 0; i < 20 && after >= before; i++) { await wait(500); after = await B.getByRole("button", { name: /^Confirm$/ }).count(); }
ok("pending change confirmed by a named person (card leaves the waiting list)", after < before, `${before} -> ${after}`);
await tab(B, "Care plan");
await B.getByRole("button", { name: /confirm all/i }).click();
await B.getByText(/Confirmed by Priya/).first().waitFor({ timeout: 30000 });
await B.getByRole("link", { name: /picture schedule/i }).click();
await B.locator(".psched").waitFor({ timeout: 60000 });
ok("picture schedule renders with medicines and sources", await B.locator(".pname").count() > 0);
await B.goBack(); await B.waitForTimeout(800);
await B.goto(BASE + "/app/elder", { waitUntil: "networkidle" });
ok("elder mode opens with a listen button", await B.getByRole("button", { name: /listen|सुन/i }).count() > 0);
await B.goto(BASE + "/app", { waitUntil: "networkidle" });
await tab(B, "Emergency Card");
await B.getByRole("button", { name: /make an emergency card link/i }).click();
await B.getByText(/New link/).waitFor({ timeout: 15000 });
const card = (await B.locator("code").first().innerText()).trim().replace(/^https?:\/\/[^/]+/, BASE);
const P = await (await b.newContext()).newPage(); track(P, "p");
await P.goto(card, { waitUntil: "networkidle" });
ok("emergency card shows allergies first, no sign-in", await P.getByText(/EMERGENCY CARD/).count() > 0 && await P.getByText("Penicillin").count() > 0);
await B.getByRole("button", { name: /switch off/i }).first().click();
await B.getByText(/Link switched off/).waitFor({ timeout: 10000 });
await P.reload({ waitUntil: "networkidle" });
ok("revoked card is no longer available", await P.getByText(/not available/).count() > 0);

// trust page
const T = await (await b.newContext({ viewport: { width: 1200, height: 900 } })).newPage(); track(T, "t");
await T.goto(BASE + "/trust", { waitUntil: "networkidle" });
await T.getByText("Measured on the live Meta model").waitFor({ timeout: 20000 });
ok("trust page: live measurements, speech and what is not measured", await T.getByText(/Hearing English, Hindi and Marathi/).count() > 0 && await T.getByText("Not measured yet").count() > 0);

console.log(`\n${pass} passed, ${fail} failed; console errors: ${errs.length}`, errs.slice(0, 5));
await b.close();
process.exit(fail ? 1 : 0);
