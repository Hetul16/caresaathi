"""Drives a real browser through the website and fails on anything the screen or the console reports.

    pip install playwright && playwright install chromium
    python scripts\browser_check.py                       # against a local dev server on :3000
    python scripts\browser_check.py https://<the site>    # against the deployment

walkthrough.py proves the API answers correctly through the website's own proxy. This proves the pages built from
those answers actually render on a phone-sized screen: that signing up works, that every tab of Family mode fills
itself when opened, that Elder mode switches language, that the public Emergency Card opens with no account, and
that no page writes an error to the browser console. It creates one throwaway account and seeds the fictional demo
family; it never touches real data.
"""
from __future__ import annotations

import secrets
import sys

from playwright.sync_api import ConsoleMessage, Page, sync_playwright

TABS = ["Overview", "Care plan", "Documents", "Visits", "Tracker", "Timeline", "Ask", "Chat", "Today",
        "Tasks", "Outcomes", "Care crew", "Doctor link", "Label check", "Emergency Card", "Family",
        "Approvals", "History"]

# Noise the framework itself prints in development, plus the browser's own hints.
IGNORE = ("middleware", "React DevTools", "Partial Prerender", "favicon", "preload", "Fast Refresh",
          "was preloaded using link preload", "scroll-behavior",
          # The browser logs this for any response it considers an error, with no URL attached. Every response over
          # 400 is already judged precisely by the response handler below, so this line adds nothing but noise.
          "Failed to load resource")
# Requests whose failure is the correct answer: a signed-out visitor holds no refresh cookie, and an unknown
# Emergency Card token is answered the same way as an expired one.
EXPECTED_HTTP = ("/auth/refresh", "/e/")

ok = 0
bad: list[str] = []
noise: list[str] = []
failed: list[str] = []


def check(name: str, cond: object, ok_note: str = "", bad_note: str = "") -> bool:
    """ok_note is printed on a pass, bad_note only on a failure: a detail that reads as a complaint must not
    appear under PASS."""
    global ok
    if cond:
        ok += 1
        print(f"PASS  {name}" + (f"  {ok_note}" if ok_note else ""))
    else:
        bad.append(name)
        print(f"FAIL  {name}" + (f"  {bad_note or ok_note}" if (bad_note or ok_note) else ""))
    return bool(cond)


def watch(page: Page) -> None:
    def on_console(m: ConsoleMessage) -> None:
        if m.type in ("error", "warning") and not any(s in m.text for s in IGNORE):
            noise.append(f"{m.type}: {m.text[:150]}")

    page.on("console", on_console)
    page.on("response", lambda r: r.status >= 400
            and not any(s in r.url for s in EXPECTED_HTTP)
            and failed.append(f"{r.status} {r.request.method} {r.url.split('/api/v1')[-1][:60]}"))
    page.on("pageerror", lambda e: noise.append(f"pageerror: {str(e)[:150]}"))


def main(base: str) -> int:
    base = base.rstrip("/")
    email, pw = f"browser-{secrets.token_hex(4)}@example.com", "Str0ng-" + secrets.token_hex(10)

    with sync_playwright() as p:
        browser = p.chromium.launch()
        # A phone, because that is what a family actually holds.
        ctx = browser.new_context(viewport={"width": 390, "height": 844}, device_scale_factor=2)
        page = ctx.new_page()
        watch(page)

        page.goto(f"{base}/", wait_until="networkidle")
        check("the landing page draws", page.locator("h1").first.is_visible())
        check("no horizontal scroll on a phone",
              page.evaluate("document.documentElement.scrollWidth <= window.innerWidth + 1"))

        page.goto(f"{base}/signup", wait_until="networkidle")
        page.get_by_label("Your name").fill("Browser Check")
        page.get_by_label("Email", exact=True).fill(email)
        page.get_by_label("Password", exact=True).fill(pw)
        page.locator('input[type="checkbox"]').first.check()
        page.get_by_role("button", name="Create account").click()
        page.wait_for_url("**/onboarding", timeout=90_000)
        check("signing up leads to onboarding", "/onboarding" in page.url, page.url)

        page.get_by_role("button", name="Load the demo family").click()
        page.wait_for_url("**/app", timeout=180_000)
        page.wait_for_load_state("networkidle")
        check("the demo family loads and opens the dashboard", "/app" in page.url, page.url)

        page.wait_for_selector("text=/Allerg/", timeout=120_000)
        check("the allergy banner is on the dashboard", page.locator("text=/Allerg/").count() > 0)
        check("a plan item carries a visible source",
              page.locator("text=Show source").count() + page.locator(".source-chip").count() > 0)
        check("the dashboard is in one language",
              page.locator("text=/सुनिए|मंज़ूर|एलर्जी|स्रोत देखें/").count() == 0,
              bad_note="Hindi words found in the English dashboard")

        # Every tab must fill itself when opened: this is what the load-on-mount effects are for.
        empty, missing = [], []
        for tab in TABS:
            t = page.get_by_role("button", name=tab).first
            if t.count() == 0:
                missing.append(tab)
                continue
            t.click()
            page.wait_for_timeout(2200)
            if len(page.locator("main").first.inner_text().strip()) < 120:
                empty.append(tab)
        check("every tab of Family mode exists", not missing, f"{len(TABS)} tabs", "missing: " + ", ".join(missing))
        check("every tab fills itself when opened", not empty, bad_note="empty: " + ", ".join(empty))

        page.goto(f"{base}/app/elder", wait_until="networkidle")
        page.wait_for_timeout(2500)
        check("elder mode draws the speak button", page.locator(".orb").count() > 0)
        lang = page.locator('.lang-switch button[aria-label="हिन्दी"]').first
        if check("the language buttons are there", lang.count() > 0):
            lang.click()
            page.wait_for_timeout(1500)
            check("elder mode switches into Hindi", page.locator("text=/सुनिए|नमस्ते|दवाइयाँ|दबाइए/").count() > 0)

        for path in ("/app/schedule", "/app/fridge", "/app/emergency", "/trust"):
            page.goto(f"{base}{path}", wait_until="networkidle")
            page.wait_for_timeout(1800)
            check(f"{path} draws something", len(page.locator("body").inner_text().strip()) > 200)

        # The public card, opened the way a hospital opens it: no account at all.
        anon = browser.new_context(viewport={"width": 390, "height": 844})
        card = anon.new_page()
        watch(card)
        card.goto(f"{base}/e/demo-token", wait_until="networkidle")
        check("the emergency card opens with no account", card.locator("text=/Emergency|Allerg/").count() > 0)
        card.goto(f"{base}/e/{secrets.token_urlsafe(24)}", wait_until="networkidle")
        check("an invented card link says nothing about anyone", card.locator("text=/not available/i").count() > 0)
        anon.close()

        check("no request failed except the ones that are meant to", not failed, bad_note="; ".join(sorted(set(failed))[:3]))
        check("the browser console stayed quiet", not noise, bad_note="; ".join(noise[:2]))
        browser.close()

    print()
    print(f"{ok} passed, {len(bad)} failed")
    for b in bad:
        print("  failed:", b)
    for n in noise:
        print("  console:", n)
    for f in sorted(set(failed)):
        print("  http:", f)
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1] if len(sys.argv) > 1 else "http://localhost:3000"))
