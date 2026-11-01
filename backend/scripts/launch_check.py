"""Checks a deployed CareSaathi the way a judge will meet it. Run from the repository root:

    python backend/scripts/launch_check.py https://caresaathi.vercel.app

Give it the WEBSITE address, not the API's: the website is what gets submitted, and everything below goes through it. It reads only
public pages, signs in to nothing and spends nothing. Exit code 0 means every check passed.
"""
import sys

import httpx

URL = (sys.argv[1] if len(sys.argv) > 1 else "").rstrip("/")
if not URL:
    sys.exit(__doc__)

results: list[tuple[bool, str, str]] = []


def check(name: str, ok: bool, detail: str = "") -> None:
    results.append((ok, name, detail))
    print(("  PASS  " if ok else "  FAIL  ") + name + (f"  [{detail}]" if detail else ""))


with httpx.Client(follow_redirects=True, timeout=90) as c:                 # 90s: a sleeping free container takes about a minute
    check("the address is https, which the microphone needs", URL.startswith("https://"), URL.split("://")[0])

    try:
        home = c.get(URL + "/")
    except httpx.HTTPError as e:
        print(f"\ncould not reach {URL}: {type(e).__name__}")
        sys.exit(1)

    # Vercel's own protection answers with its sign-in page, which is a 401 or an HTML page that says so.
    protected = home.status_code == 401 or "Authentication Required" in home.text or "_vercel_sso_nonce" in home.text
    check("the website is open to anyone (host protection off)", home.status_code == 200 and not protected, f"HTTP {home.status_code}")
    check("the landing page says the data is synthetic", "synthetic" in home.text.lower())

    api = c.get(URL + "/api/v1/trust/live")
    check("the API answers through the website (SITE_GATE_TOKEN cleared on both sides)", api.status_code == 200,
          f"HTTP {api.status_code}" + (" - the gate is still on somewhere" if api.status_code == 404 else ""))

    trust = c.get(URL + "/trust")
    check("the evidence page opens with no account", trust.status_code == 200 and "cookie" not in trust.request.headers,
          f"HTTP {trust.status_code}")

    h = {k.lower(): v for k, v in home.headers.items()}
    check("the page carries its content policy", "content-security-policy" in h)
    check("the page refuses to be framed", h.get("x-frame-options", "").upper() == "DENY", h.get("x-frame-options", "missing"))
    check("https is pinned for next time (HSTS)", "strict-transport-security" in h, h.get("strict-transport-security", "missing"))

    # The emergency card route must exist and must refuse an invented token rather than showing anything.
    card = c.get(URL + "/e/not-a-real-token")
    check("an invented emergency card link shows nothing", card.status_code in (200, 404) and "Penicillin" not in card.text,
          f"HTTP {card.status_code}")

failed = [name for ok, name, _ in results if not ok]
print(f"\n{len(results) - len(failed)} of {len(results)} checks passed")
if failed:
    print("still to fix:\n - " + "\n - ".join(failed))
sys.exit(1 if failed else 0)
