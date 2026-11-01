"""Spend guard for the live Meta models. Every live call is priced from its token counts and appended to the ledger; once the total
reaches the limit, further live calls are refused BEFORE they are made. The limit protects the hackathon credit (D-50).

Prices are from dev.meta.ai/docs/pricing-rate-limits (Oct 28, 2026), in USD per million tokens, and live in config so a change in the
published price needs one edit. Reasoning tokens are billed like output tokens. `spend_baseline_usd` counts what was spent before the
ledger existed.

The ledger is the append-only `model_spend` table, not a file (D-68): a free host gives the API container no persistent disk, so a file
ledger resets to zero on every redeploy and idle spin-down, which is precisely when the deployment is public and the spending is out of
our hands. Two consequences, both deliberate:

- A priced call is written in its OWN transaction. The money left whether or not the request that spent it commits.
- If the ledger cannot be read, the call is refused. An unknown total is not a safe total (CLAUDE.md invariant 10).
"""
from __future__ import annotations

import json
from pathlib import Path

from sqlalchemy import text as sql
from sqlalchemy.orm import Session

from ..config import get_settings
from ..db import engine_app


class SpendLimitReached(Exception):
    """Raised before a live call when the ledger total has reached the configured limit, or could not be read."""


def price(model: str, contributor: bool, input_tokens: int | None, output_tokens: int | None, audio_seconds: float = 0.0) -> float:
    s = get_settings()
    if audio_seconds:
        return audio_seconds / 3600.0 * s.price_voice_per_hour
    pin, pout = (s.price_contrib_in, s.price_contrib_out) if contributor else (s.price_std_in, s.price_std_out)
    return ((input_tokens or 0) * pin + (output_tokens or 0) * pout) / 1_000_000.0


def total() -> float:
    with Session(engine_app()) as s:
        spent = s.execute(sql("SELECT coalesce(sum(usd), 0) FROM model_spend")).scalar_one()
    return round(get_settings().spend_baseline_usd + float(spent), 6)


def check() -> None:
    limit = get_settings().spend_limit_usd
    try:
        used = total()
    except Exception as e:                                  # unreachable database, missing table, wrong credentials
        raise SpendLimitReached(f"the spend ledger could not be read ({type(e).__name__}), so no live call was made") from e
    if used >= limit:
        raise SpendLimitReached(f"spend limit reached (${used:.2f} of ${limit:.2f})")


def add(usd: float, *, model: str, purpose: str, source: str = "live") -> None:
    """Record a completed call. Its own transaction on purpose: a request that fails after spending money still spent it."""
    with Session(engine_app()) as s, s.begin():
        s.execute(sql("INSERT INTO model_spend (usd, model, purpose, source) VALUES (:u, :m, :p, :src)"),
                  {"u": round(usd, 8), "m": model, "p": purpose, "src": source})


def by_purpose() -> list[tuple[str, int, float]]:
    """What the ledger holds, most expensive first. Used by `scripts/spend.py`."""
    with Session(engine_app()) as s:
        rows = s.execute(sql("SELECT purpose, count(*), sum(usd) FROM model_spend GROUP BY purpose ORDER BY sum(usd) DESC")).all()
    return [(r[0], int(r[1]), float(r[2])) for r in rows]


def import_file(path: Path | None = None) -> tuple[int, float]:
    """One-time move of an old `spend.jsonl` into the table, so the switch does not forget what was already spent.

    Refuses to run twice: imported rows are marked, and a second run would double the total. Run it with `scripts/spend.py --import-file`.
    """
    f = path or Path(get_settings().local_storage_dir) / "spend.jsonl"
    if not f.exists():
        return 0, 0.0
    with Session(engine_app()) as s:
        if s.execute(sql("SELECT count(*) FROM model_spend WHERE source = 'imported'")).scalar_one():
            raise RuntimeError("this ledger already holds imported rows; importing again would double the total")
    n, usd = 0, 0.0
    for line in f.read_text(encoding="utf-8").splitlines():
        try:
            j = json.loads(line)
            amount = float(j["usd"])
        except (ValueError, KeyError):
            continue
        add(amount, model=j.get("model", "unknown"), purpose=j.get("purpose", "unknown"), source="imported")
        n, usd = n + 1, usd + amount
    f.rename(f.with_suffix(".jsonl.imported"))
    return n, round(usd, 6)
