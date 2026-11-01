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
ok("there is exactly one list of today's medicines", (await P.locator(".elder-title").filter({ hasText: /Today|आज/ }).count()) === 1);
await P.screenshot({ path: out + "/pr-2-elder-top.png", fullPage: true });

const med = await P.locator("p").filter({ hasText: /× \d/ }).first().innerText();
await P.getByRole("button", { name: /I took it/i }).first().click();
await P.locator(".pill-leaf").first().waitFor({ timeout: 15000 });
ok("one tap marks a dose as taken", /Taken/.test(await P.locator(".pill-leaf").first().innerText()), med.replace(/\s+/g, " "));

await P.getByRole("button", { name: "6", exact: true }).first().click();
await P.getByText(/Saved|सेव/).first().waitFor({ timeout: 15000 });
ok("she can say how she feels", true);

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
