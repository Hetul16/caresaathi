"""Spend guard for the live Meta models. Every live call is priced from its token counts and appended to a local ledger; once the total
reaches the limit, further live calls are refused BEFORE they are made. The limit protects the hackathon credit (D-50).

Prices are from dev.meta.ai/docs/pricing-rate-limits (Oct 28, 2026), in USD per million tokens, and live in config so a change in the
published price needs one edit. Reasoning tokens are billed like output tokens. `spend_baseline_usd` counts what was spent before the
ledger existed. The ledger is a plain file next to local storage: it survives restarts, and it is the single place scripts and the web
app both write to."""
from __future__ import annotations

import json
import threading
import time
from pathlib import Path

from ..config import get_settings

_lock = threading.Lock()


class SpendLimitReached(Exception):
    """Raised before a live call when the ledger total has reached the configured limit."""


def _path() -> Path:
    p = Path(get_settings().local_storage_dir) / "spend.jsonl"
    p.parent.mkdir(parents=True, exist_ok=True)
    return p


def price(model: str, contributor: bool, input_tokens: int | None, output_tokens: int | None, audio_seconds: float = 0.0) -> float:
    s = get_settings()
    if audio_seconds:
        return audio_seconds / 3600.0 * s.price_voice_per_hour
    pin, pout = (s.price_contrib_in, s.price_contrib_out) if contributor else (s.price_std_in, s.price_std_out)
    return ((input_tokens or 0) * pin + (output_tokens or 0) * pout) / 1_000_000.0


def total() -> float:
    f = _path()
    spent = 0.0
    if f.exists():
        for line in f.read_text(encoding="utf-8").splitlines():
            try:
                spent += float(json.loads(line)["usd"])
            except (ValueError, KeyError):
                continue
    return round(get_settings().spend_baseline_usd + spent, 6)


def check() -> None:
    limit = get_settings().spend_limit_usd
    with _lock:
        used = total()
    if used >= limit:
        raise SpendLimitReached(f"spend limit reached (${used:.2f} of ${limit:.2f})")


def add(usd: float, *, model: str, purpose: str) -> None:
    with _lock:
        with _path().open("a", encoding="utf-8") as fh:
            fh.write(json.dumps({"t": int(time.time()), "usd": round(usd, 8), "model": model, "purpose": purpose}) + "\n")
