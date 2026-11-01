"""Prints the live-model spend ledger. Run from backend/ with: python scripts/spend.py

The ledger is the `model_spend` table (D-68), so this needs the database the API uses. `--import-file` moves an old `spend.jsonl` into
the table once and renames the file; run it on the machine that holds the file, pointed at the database you are keeping.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.clients import spend  # noqa: E402
from app.config import get_settings  # noqa: E402

if "--import-file" in sys.argv:
    n, usd = spend.import_file()
    print(f"imported {n} entries worth ${usd:.4f}" if n else "nothing to import")

s = get_settings()
for purpose, n, usd in spend.by_purpose():
    print(f"  {purpose:<22} {n:>4} calls  ${usd:.4f}")
print(f"baseline ${s.spend_baseline_usd:.2f} + ledger = ${spend.total():.4f} of limit ${s.spend_limit_usd:.2f}")
