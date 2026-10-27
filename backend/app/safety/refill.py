"""Refill run-out estimate (docs/14-data-mapping.md section 14.2, D-31). Code only: start date plus quantity divided by
the daily units from the documented frequency. "As needed" or an unparsable frequency gives no estimate, and the
inputs are always shown beside the result. A named person confirms it; nothing here says when to refill."""
from __future__ import annotations

from datetime import date, timedelta


def estimate_run_out(start: date | None, quantity: float | None, daily_units: float | None) -> date | None:
    if start is None or quantity is None or daily_units is None:
        return None
    if quantity <= 0 or daily_units <= 0:
        return None
    return start + timedelta(days=int(quantity // daily_units))
