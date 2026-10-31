"""Checks that everything the demo video needs is ready. Run it right before recording.

    cd backend
    python scripts\\demo_preflight.py

It makes one tiny live call (a fraction of a cent) to prove the model answers, and prints PASS or FAIL for each line. It never prints a key."""
from __future__ import annotations

import calendar
import sys
import time
from pathlib import Path

import httpx

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.clients import spend  # noqa: E402
from app.clients.models import get_model_client  # noqa: E402
from app.config import get_settings  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]
API, WEB = "http://127.0.0.1:8000/api/v1", "http://localhost:3000"
results: list[bool] = []


def check(name: str, ok: bool, detail: str = "") -> None:
    results.append(ok)
    print(f"{'PASS' if ok else 'FAIL'}  {name}{('  ' + detail) if detail else ''}")


def get(url: str, **kw):
    try:
        return httpx.get(url, timeout=20, **kw)
    except httpx.HTTPError:
        return None


def main() -> int:
    cfg = get_settings()
    r = get(f"{API}/trust/live")
    check("backend answers", r is not None and r.status_code == 200)
    live = r.json() if r is not None and r.status_code == 200 else {}
    check("Trust page report is present", bool(live.get("available")))
    if live.get("available"):
        age_h = (time.time() - calendar.timegm(time.strptime(live["generated_at"][:19], "%Y-%m-%dT%H:%M:%S"))) / 3600
        check("report has speech and visit results", "speech" in live and "visits_en" in live["sections"], f"report is about {max(0, age_h):.0f} h old")
    r = get(f"{API}/trust/latest")
    check("database answers (trust suite stored or computed)", r is not None and r.status_code == 200)
    r = get(f"{WEB}/")
    check("website answers on localhost:3000", r is not None and r.status_code == 200)
    r = get(f"{WEB}/trust")
    check("Trust page renders", r is not None and r.status_code == 200)
    check("live mode is on", cfg.model_mode == "live" and bool(cfg.meta_api_key))
    left = cfg.spend_limit_usd - spend.total()
    check("spend limit leaves room", left > 0.5, f"${left:.2f} left of ${cfg.spend_limit_usd:.2f}")
    if cfg.model_mode == "live" and cfg.meta_api_key:
        t0 = time.monotonic()
        flagged, _ = get_model_client().judge_text("This medicine is perfectly safe, go ahead.")
        check("live model answers and flags a reassuring sentence", flagged is True, f"{time.monotonic() - t0:.1f}s")
    need = ["R4_photo.png", "R1_photo.png", "R5_photo.png", "R7_photo.png", "labels/strip_amlodipine_5.png", "labels/loose_pill.png", "labels/box_amoxicillin.png"]
    missing = [n for n in need if not (ROOT / "data" / "synthetic" / "rendered" / n).exists()]
    check("sample photos exist", not missing, ("missing: " + ", ".join(missing) + " (run render.py and render_labels.py)") if missing else "")
    check("English and Hindi visit scripts exist", all((ROOT / "data" / "synthetic" / "ramesh" / "visits" / f"{v}.json").exists() for v in ("V1", "V4")))
    print(f"\n{sum(results)} of {len(results)} ready.")
    return 0 if all(results) else 1


if __name__ == "__main__":
    sys.exit(main())
