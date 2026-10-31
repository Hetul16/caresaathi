"""The trust panel's data: run the adversarial suite, store the result, and show the latest run to anyone.

The latest result is public on purpose (no sign-in): a judge or a family should be able to see the numbers, failures included."""
from __future__ import annotations

import json
import subprocess
from datetime import datetime, timezone

from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.orm import Session

from ..config import ROOT, get_settings
from ..db import request_session
from ..trust.suite import run_suite
from .deps import db

router = APIRouter(tags=["trust"])

DISCLAIMER = ("These cases test the code around the model: the output guard, the permission gate, the injection detector, the chat's refusals and the "
              "date, omission and refill logic. They do not measure how often the model is right. The offline reader is a rule-based stand-in; "
              "live model accuracy is measured separately. Misses are shown, not hidden.")


def _git_sha() -> str | None:
    try:
        return subprocess.run(["git", "rev-parse", "--short", "HEAD"], cwd=ROOT, capture_output=True, text=True, timeout=5).stdout.strip() or None
    except Exception:
        return None


def _payload(run_id: str | None, ran_at: str, sha: str | None, model: str, summary: dict, stored: bool) -> dict:
    return {"run_id": run_id, "ran_at": ran_at, "git_sha": sha, "model": model, "stored": stored, **summary, "disclaimer": DISCLAIMER}


@router.post("/trust/run")
def run(s: Session = Depends(db, scope="function")):
    result = run_suite()
    summary = result.summary()
    mode = "fake-reader (offline)" if get_settings().model_mode != "live" else get_settings().meta_spark_model
    rid = s.execute(text("""INSERT INTO eval_runs (suite, git_sha, model, finished_at, metrics, notes)
                            VALUES ('trust', :g, :m, now(), CAST(:x AS jsonb), :n) RETURNING id"""),
                    {"g": _git_sha(), "m": mode, "x": json.dumps({"total": summary["total"], "passed": summary["passed"],
                                                                   "by_category": {c["name"]: [c["passed"], c["total"]] for c in summary["categories"]}}),
                     "n": DISCLAIMER}).scalar_one()
    for r in result.results:
        s.execute(text("""INSERT INTO eval_results (run_id, case_id, category, expected, actual, passed, failure_reason)
                          VALUES (:r, :c, :cat, CAST(:e AS jsonb), CAST(:a AS jsonb), :p, :f)"""),
                  {"r": rid, "c": r.id, "cat": r.category, "e": json.dumps({"input": r.input, "expected": r.expected}), "a": json.dumps({"actual": r.actual}),
                   "p": r.passed, "f": None if r.passed else r.actual})
    return _payload(str(rid), datetime.now(timezone.utc).isoformat(), _git_sha(), mode, summary, True)


@router.get("/trust/latest")
def latest():
    with request_session() as s:
        row = s.execute(text("SELECT id, git_sha, model, finished_at FROM eval_runs WHERE suite = 'trust' ORDER BY started_at DESC LIMIT 1")).mappings().first()
        if row is None:
            summary = run_suite().summary()
            return _payload(None, datetime.now(timezone.utc).isoformat(), _git_sha(), "fake-reader (offline)", summary, False)
        results = s.execute(text("SELECT case_id, category, expected, actual, passed FROM eval_results WHERE run_id = :r ORDER BY category, case_id"), {"r": row["id"]}).mappings().all()
    from ..trust.suite import CATEGORIES
    cats = []
    for name, desc in CATEGORIES.items():
        rs = [r for r in results if r["category"] == name]
        if rs:
            cats.append({"name": name, "description": desc, "total": len(rs), "passed": sum(1 for r in rs if r["passed"]),
                         "failures": [{"id": r["case_id"], "input": (r["expected"] or {}).get("input"), "expected": (r["expected"] or {}).get("expected"),
                                       "actual": (r["actual"] or {}).get("actual")} for r in rs if not r["passed"]]})
    summary = {"total": len(results), "passed": sum(1 for r in results if r["passed"]), "categories": cats}
    return _payload(str(row["id"]), row["finished_at"].isoformat() if row["finished_at"] else "", row["git_sha"], row["model"], summary, True)


LIVE_RESULTS = ROOT / "data" / "live_results" / "latest.json"


@router.get("/trust/live")
def live_results():
    """What was measured on the LIVE Meta model, from the committed report (`scripts/live_report.py`). Public: failures are included.
    It is a file, not a live call, so opening this page never spends credit and never depends on the model being reachable."""
    try:
        data = json.loads(LIVE_RESULTS.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {"available": False}
    return {"available": True, **data}
