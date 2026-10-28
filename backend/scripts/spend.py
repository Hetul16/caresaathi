"""Prints the live-model spend ledger. Run from backend/:  .venv\Scripts\python.exe scripts\spend.py"""
import json
import sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.clients import spend  # noqa: E402
from app.config import get_settings  # noqa: E402

s = get_settings()
by = defaultdict(lambda: [0, 0.0])
f = Path(s.local_storage_dir) / "spend.jsonl"
for line in (f.read_text(encoding="utf-8").splitlines() if f.exists() else []):
    j = json.loads(line)
    by[j["purpose"]][0] += 1
    by[j["purpose"]][1] += j["usd"]
for k, (n, usd) in sorted(by.items(), key=lambda x: -x[1][1]):
    print(f"  {k:<22} {n:>4} calls  ${usd:.4f}")
print(f"baseline ${s.spend_baseline_usd:.2f} + ledger = ${spend.total():.4f} of limit ${s.spend_limit_usd:.2f}")
