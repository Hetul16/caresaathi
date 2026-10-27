"""Measures the LIVE Meta models on the synthetic set. Run this once the API key is in .env and MODEL_MODE=live.

    cd backend
    .venv\\Scripts\\python.exe ..\\data\\synthetic\\render.py              # make photos and PDFs first
    .venv\\Scripts\\python.exe scripts\\live_smoke.py --docs               # Muse Spark reading photos and PDFs
    .venv\\Scripts\\python.exe scripts\\live_smoke.py --judge              # the second-pass judge on the paraphrase probes
    .venv\\Scripts\\python.exe scripts\\live_smoke.py --audio V1 path.wav  # Muse Voice Transcribe against a scripted visit
    .venv\\Scripts\\python.exe scripts\\live_smoke.py --dry-run            # no key needed: checks the plumbing with the offline reader

Every call is made against FICTIONAL data only (and the Spark contributor variant may train on prompts, D-11). Results are printed and
written to data/live_runs/ (git-ignored) so the real numbers, failures included, can be copied into docs/10-hackathon-facts.md."""
from __future__ import annotations

import argparse
import json
import sys
import time
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.clients.models import DocFile, FakeModelClient, ModelError, PageText, get_model_client  # noqa: E402
from app.config import get_settings  # noqa: E402
from app.safety.normalize import brand_key  # noqa: E402
from app.safety.validate import validate_extraction  # noqa: E402
from app.trust.suite import HOLDOUT, PARAPHRASE, UNSAFE  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]
SYN = ROOT / "data" / "synthetic"
OUT = ROOT / "data" / "live_runs"
DOCS = ["R1", "R2", "R4", "R5", "R7", "R9", "R10"]


def truth_of(doc_id: str) -> dict:
    f = next(iter((SYN / "ramesh" / "truth").glob(f"{doc_id}.truth.json")), None)
    return json.loads(f.read_text(encoding="utf-8")) if f else {"items": []}


def medicines(truth: dict) -> set[tuple[str, str | None]]:
    return {(i["name"].lower(), i.get("frequency")) for i in truth["items"] if i.get("kind") == "medicine"}


def read_docs(client, dry: bool) -> list[dict]:
    rows = []
    for doc_id in DOCS:
        variants = [(SYN / "ramesh" / "docs" / next(p.name for p in (SYN / "ramesh" / "docs").glob(f"{doc_id}_*.txt")), "text/plain")] if dry else \
                   [(SYN / "rendered" / f"{doc_id}_photo.png", "image/png"), (SYN / "rendered" / f"{doc_id}.pdf", "application/pdf")]
        for path, mime in variants:
            if not path.exists():
                rows.append({"doc": doc_id, "file": path.name, "ok": False, "note": "missing: run data/synthetic/render.py first"})
                continue
            t0 = time.monotonic()
            try:
                pages, u1 = client.transcribe_pages(DocFile(path.read_bytes(), mime, path.name))
                raw, u2 = client.extract_document(pages, None)
                v = validate_extraction(raw, {p.page: p.text for p in pages})
                got = {(brand_key(i.title), i.details.get("frequency_text")) for k, i in enumerate(v.data.items) if i.kind == "medicine" and k not in v.rejected_items} if v.data else set()
                want = medicines(truth_of(doc_id))
                rows.append({"doc": doc_id, "file": path.name, "ok": got == want, "found": sorted(map(str, got)), "wanted": sorted(map(str, want)),
                             "rejected_quotes": len(v.rejected_items), "injection_lines": v.injection_lines, "needs_review": v.needs_review,
                             "seconds": round(time.monotonic() - t0, 1), "tokens": (u1.input_tokens or 0) + (u2.input_tokens or 0)})
            except ModelError as e:
                rows.append({"doc": doc_id, "file": path.name, "ok": False, "note": f"model error: {e}"})
    return rows


def judge(client) -> list[dict]:
    rows = []
    bad = [("en", t) for t in UNSAFE["en"][:8]] + [("en", t) for t in PARAPHRASE + HOLDOUT]
    for lang, text in bad:
        flagged, _ = client.judge_text(text)
        rows.append({"text": text, "flagged": flagged, "ok": flagged is True})
    return rows


def wer(ref: str, hyp: str) -> float:
    r, h = ref.lower().split(), hyp.lower().split()
    d = list(range(len(h) + 1))
    for i in range(1, len(r) + 1):
        prev, d[0] = d[0], i
        for j in range(1, len(h) + 1):
            cur = d[j]
            d[j] = min(d[j] + 1, d[j - 1] + 1, prev + (r[i - 1] != h[j - 1]))
            prev = cur
    return d[len(h)] / max(1, len(r))


def audio(client, script_id: str, wav_path: Path) -> dict:
    script = json.loads((SYN / "ramesh" / "visits" / f"{script_id}.json").read_text(encoding="utf-8"))
    turns, usage = client.transcribe_audio(wav_path.read_bytes())
    ref = " ".join(s["text"] for s in script["segments"])
    hyp = " ".join(t.text for t in turns)
    return {"script": script_id, "language": script["language"], "turns": len(turns), "speakers": sorted({t.speaker for t in turns}),
            "wer": round(wer(ref, hyp), 3), "seconds": (usage.latency_ms or 0) / 1000, "hypothesis": hyp[:400],
            "note": "TTS audio must never be used for the accuracy numbers (docs/17)."}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--docs", action="store_true")
    ap.add_argument("--judge", action="store_true")
    ap.add_argument("--audio", nargs=2, metavar=("SCRIPT", "WAV"))
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()
    if not (a.docs or a.judge or a.audio or a.dry_run):
        ap.print_help()
        return 2
    cfg = get_settings()
    if a.dry_run:
        client = FakeModelClient()
    else:
        if cfg.model_mode != "live" or not cfg.meta_api_key:
            print("Set META_API_KEY and MODEL_MODE=live in .env first (or use --dry-run).")
            return 2
        client = get_model_client()
    report: dict = {"at": datetime.now().isoformat(timespec="seconds"), "mode": "dry-run (offline reader)" if a.dry_run else cfg.meta_spark_dev_model if cfg.allow_contributor_models else cfg.meta_spark_model}
    if a.docs or a.dry_run:
        report["documents"] = rows = read_docs(client, a.dry_run)
        print(f"\nDocuments: {sum(r['ok'] for r in rows)}/{len(rows)} read exactly right")
        for r in rows:
            print(f"  {'PASS' if r['ok'] else 'FAIL'}  {r['file']:<24} {r.get('note') or ('found ' + ', '.join(r['found']))[:70]}")
    if a.judge:
        report["judge"] = rows = judge(client)
        print(f"\nJudge flagged {sum(r['ok'] for r in rows)}/{len(rows)} reassuring or advising drafts")
        for r in rows:
            print(f"  {'caught' if r['ok'] else 'MISSED'}  {r['text'][:80]}")
    if a.audio:
        report["audio"] = r = audio(client, a.audio[0], Path(a.audio[1]))
        print(f"\nAudio {r['script']}: WER {r['wer']}, {r['turns']} turns, speakers {r['speakers']}\n  {r['hypothesis'][:200]}")
    OUT.mkdir(parents=True, exist_ok=True)
    out = OUT / f"smoke-{datetime.now():%Y%m%d-%H%M%S}.json"
    out.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"\nwritten to {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
