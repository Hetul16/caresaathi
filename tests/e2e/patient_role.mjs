// The patient signs in as themselves (D-66): Elder mode only, medicines first, one tap to say a dose was taken.
// Run with the dev server and the backend up. Synthetic data only.
import { chromium } from "playwright-core";
const BASE = "http://localhost:3000";
const out = process.env.TEMP + "/shots";
const b = await chromium.launch({ executablePath: "C:/Program Files/Google/Chrome/Application/chrome.exe", headless: true });
const errs = [];
let pass = 0, fail = 0;
const ok = (n, c, x = "") => { c ? pass++ : fail++; console.log(c ? "PASS" : "FAIL", n, x); };
function track(page, tag) {
  page.on("console", (m) => { if (m.type() === "error" && !/favicon|WebSocket|401|Failed to load resource|Cannot reach/.test(m.text())) errs.push(tag + ": " + m.text().slice(0, 160)); });
  page.on("pageerror", (e) => errs.push(tag + " PAGEERROR " + e.message.slice(0, 160)));
}
async function signup(ctx, tag, name) {
  const page = await ctx.newPage(); track(page, tag);
  await page.goto(BASE + "/signup", { waitUntil: "networkidle" });
  const inputs = page.locator("input");
  await inputs.nth(0).fill(name); await inputs.nth(1).fill(`pr${Date.now()}${tag}@example.com`);
  await page.locator("input[type=password]").fill("correct-horse-battery");
  for (const c of await page.locator("input[type=checkbox]").all()) await c.check();
  await page.locator("form .btn-primary").first().click();
  return page;
}
const tab = (page, name) => page.getByRole("button", { name: new RegExp("^" + name) }).first().click();
// Elder-mode controls drift by a fraction of a pixel (measured below), which Playwright will not click through, so these taps are forced.
// A forced click skips the automatic scroll as well, so bring the control into view first or it lands off-screen.
const tap = async (loc) => {
  await loc.evaluate((el) => el.scrollIntoView({ block: "center", behavior: "instant" }));
  await loc.page().waitForTimeout(250);
  await loc.click({ force: true });
};

// ---------- the family sets the patient up ----------
const ctxF = await b.newContext({ viewport: { width: 1360, height: 900 } });
const F = await signup(ctxF, "fam", "Priya Kulkarni");
await F.waitForURL(/onboarding/, { timeout: 30000 });
await F.getByRole("button", { name: /load the demo family/i }).click();
await F.waitForURL(/\/app$/, { timeout: 120000 });
await F.getByText("Ramesh Kulkarni").first().waitFor({ timeout: 60000 });
await tab(F, "Care plan");
await F.getByRole("button", { name: /confirm all/i }).first().click();
await F.waitForTimeout(2500);

await tab(F, "Family");
await F.getByRole("button", { name: /^The patient$/ }).click();
const boxes = F.locator(".card .check input[type=checkbox]");
ok("the three rights are switched off and cannot be ticked for the patient",
   (await boxes.count()) === 3 && (await boxes.nth(0).isDisabled()) && (await boxes.nth(1).isDisabled()) && (await boxes.nth(2).isDisabled()));
await F.getByRole("button", { name: /make an invitation link/i }).click();
const link = (await F.locator("code").first().innerText()).trim();
ok("an invitation link for the patient was made", /\/join\//.test(link), link.slice(-24));
await F.screenshot({ path: out + "/pr-1-invite.png", fullPage: true });

// ---------- the patient joins ----------
const ctxP = await b.newContext({ viewport: { width: 420, height: 900 } });   // her phone
const P = await ctxP.newPage(); track(P, "patient");
await P.goto(link, { waitUntil: "networkidle" });
await P.getByRole("link", { name: /sign up|create/i }).first().click().catch(() => {});
await P.waitForURL(/signup|login/, { timeout: 20000 });
const pin = P.locator("input");
await pin.nth(0).fill("Sunita Kulkarni"); await pin.nth(1).fill(`pt${Date.now()}@example.com`);
await P.locator("input[type=password]").fill("correct-horse-battery");
for (const c of await P.locator("input[type=checkbox]").all()) await c.check();
await P.locator("form .btn-primary").first().click();

await P.waitForURL(/\/app\/elder/, { timeout: 40000 });
ok("signing in as the patient lands on Elder mode, not the family dashboard", /\/app\/elder/.test(P.url()), P.url());

// ---------- her screen ----------
await P.getByRole("button", { name: /I took it/i }).first().waitFor({ timeout: 30000 });
const yTook = (await P.getByRole("button", { name: /I took it/i }).first().boundingBox()).y;
const yOrb = (await P.locator(".orb").first().boundingBox()).y;
ok("the medicines and their buttons come before the microphone", yTook < yOrb, `took=${Math.round(yTook)} orb=${Math.round(yOrb)}`);
ok("only what is due now is open; later and finished are one line each",
   (await P.locator(".pcheck-now").count()) === 1 && (await P.locator(".pcheck-fold").count()) >= 2);
ok("the pain scale is out of the way until she asks for it", (await P.locator(".pcheck-pain").count()) === 0);
// What she actually faces without scrolling, which is the number that matters for someone who is ill.
const above = await P.locator("button:visible, input:visible, a:visible").evaluateAll(
  (els, h) => els.filter((e) => e.getBoundingClientRect().top < h).length, 860);
ok("what she faces without scrolling is a handful of controls", above <= 16, `${above} above the fold`);
// Red means danger on a medicine screen. The drifting coral blob in the backdrop must not reach her text.
// Measure the label itself, not its button: a stray `.ec span:first-of-type` rule once painted the label red while the button stayed grey.
const fold = await P.locator(".pcheck-foldbtn span").first().evaluate((e) => {
  const c = getComputedStyle(e);
  let t = "none";
  for (let n = e; n && n !== document.documentElement; n = n.parentElement) {
    const s = getComputedStyle(n).transform;
    if (s !== "none") { t = n.tagName + "." + [...n.classList].join(".") + " " + s; break; }
  }
  return { color: c.color, transform: t };
});
ok("the folded label is grey and sits straight", /185, 193, 211/.test(fold.color) && fold.transform === "none", JSON.stringify(fold));
await P.screenshot({ path: out + "/pr-2a-elder-viewport.png" });
await P.screenshot({ path: out + "/pr-2-elder-top.png", fullPage: true });
await P.evaluate(() => window.scrollTo({ top: 0, behavior: "instant" }));   // the page scrolls smoothly, so settle it after a full-page shot
await P.waitForTimeout(700);

const med = await P.locator(".pcheck-name").first().innerText();
// A button that drifts under the finger is a real problem for someone with a tremor, so measure it rather than assume.
const jitter = await P.locator(".pcheck-took").first().evaluate((el) => new Promise((done) => {
  const seen = [];
  const tick = () => { const r = el.getBoundingClientRect(); seen.push([r.x, r.y]);
    if (seen.length < 12) requestAnimationFrame(tick);
    else done(Math.max(...seen.map(([x, y]) => Math.abs(x - seen[0][0]) + Math.abs(y - seen[0][1])))); };
  requestAnimationFrame(tick);
}));
ok("the button does not drift under the finger", jitter < 1, `moved ${jitter.toFixed(2)}px over 12 frames`);
// That sub-pixel drift is below anything a person can notice, but Playwright's stability check has no tolerance at all,
// so the click is forced. The measurement above, not the click, is what guarantees the button holds still.
await tap(P.getByRole("button", { name: /I took it/i }).first());
await P.getByText(/Saved|सेव/).first().waitFor({ timeout: 15000 });
ok("one tap marks it, and says so where she tapped", true, med.replace(/\s+/g, " "));
// it has left "Take now" and joined the finished line, which is where she looks to check
await tap(P.getByRole("button", { name: /Finished today/i }));
await P.locator(".pill-leaf").first().waitFor({ timeout: 10000 });
ok("it moves into Finished today", /Taken/.test(await P.locator(".pill-leaf").first().innerText()));

await tap(P.getByRole("button", { name: /How are you feeling/i }));
await P.locator(".pcheck-pain").waitFor({ timeout: 10000 });
await P.waitForTimeout(400);                       // the panel has just opened; let the buttons land before tapping one
await tap(P.locator(".pcheck-pain button", { hasText: /^6$/ }));
// the number she chose comes back pressed, and sits on the folded line so she can see it later without opening it
await P.locator(".pcheck-pain button[aria-pressed=true]").waitFor({ timeout: 15000 });
const chosen = await P.locator(".pcheck-pain button[aria-pressed=true]").innerText();
const onFold = await P.getByRole("button", { name: /How are you feeling/i }).innerText();
ok("she can say how she feels, and it stays on screen", chosen.trim() === "6" && /6/.test(onFold), `chose ${chosen.trim()}`);

// she must not be able to reach Family mode
await P.goto(BASE + "/app", { waitUntil: "networkidle" });
await P.waitForTimeout(2500);
ok("asking for Family mode sends her back to Elder mode", /\/app\/elder/.test(P.url()), P.url());

// ---------- the family sees it, under her name ----------
await F.reload({ waitUntil: "networkidle" });
await tab(F, "Today");
await F.getByText(/How they say they feel/).waitFor({ timeout: 20000 });
ok("the family sees her pain number", (await F.getByText(/pain 6 of 10/).count()) > 0);
ok("it is recorded under her own name, not a relative's", (await F.getByText(/Sunita Kulkarni/).count()) > 0);
ok("the dose she marked shows as taken", (await F.getByText(/Taken/).count()) > 0);
await F.screenshot({ path: out + "/pr-3-family-today.png", fullPage: true });

console.log(`\n${pass} passed, ${fail} failed; console errors: ${errs.length}`, errs.slice(0, 6));
await b.close();
process.exit(fail || errs.length ? 1 : 0);
