"""Rate limiting for the ways in (D-64).

Password guessing is cheap without it: Argon2 makes one guess slow, but nothing stopped a thousand of them. Two counters run together,
one per account identifier and one per client address, so a spray across many accounts from one address is caught as well as a single
account hammered from many.

What it is not: the counters live in this process's memory. One API process is what `docs/19-deployment.md` deploys and the spend ledger
already assumes, so this holds there; behind several processes each would keep its own count. A shared store (Redis, or a table) is the
production answer and is written down as such, not pretended away.

A locked account says the same thing as a wrong password, so the reply never reveals whether an account exists.
"""
from __future__ import annotations

import threading
import time
from dataclasses import dataclass, field


@dataclass
class Rule:
    limit: int                 # how many attempts
    window: float              # in this many seconds
    block: float               # locked out for this long once the limit is passed


@dataclass
class _Bucket:
    hits: list[float] = field(default_factory=list)
    blocked_until: float = 0.0


class RateLimiter:
    """Fixed set of named rules; every call is (rule name, key). Not a general-purpose limiter."""

    def __init__(self, rules: dict[str, Rule], clock=time.monotonic) -> None:
        self._rules = rules
        self._clock = clock
        self._lock = threading.Lock()
        self._buckets: dict[tuple[str, str], _Bucket] = {}

    def retry_after(self, rule: str, key: str) -> int:
        """Seconds the caller must wait, or 0 when it may proceed. Does not count the attempt."""
        r = self._rules[rule]
        now = self._clock()
        with self._lock:
            b = self._buckets.get((rule, key))
            if b and b.blocked_until > now:
                return max(1, int(b.blocked_until - now))
            return 0

    def record_failure(self, rule: str, key: str) -> int:
        """Count one failed attempt. Returns the seconds to wait if that attempt tripped the limit, else 0."""
        r = self._rules[rule]
        now = self._clock()
        with self._lock:
            b = self._buckets.setdefault((rule, key), _Bucket())
            b.hits = [h for h in b.hits if h > now - r.window]
            b.hits.append(now)
            if len(b.hits) >= r.limit:
                b.blocked_until = now + r.block
                b.hits.clear()
                return int(r.block)
            return 0

    def clear(self, rule: str, key: str) -> None:
        """A success wipes the slate for that key, so a person who finally remembers their password is not punished."""
        with self._lock:
            self._buckets.pop((rule, key), None)

    def prune(self) -> None:
        now = self._clock()
        with self._lock:
            for k, b in list(self._buckets.items()):
                if b.blocked_until <= now and not [h for h in b.hits if h > now - self._rules[k[0]].window]:
                    del self._buckets[k]


# Chosen to be invisible to a family that mistypes a password and expensive for anything automated.
RULES = {
    "login_identifier": Rule(limit=8, window=900, block=900),     # 8 wrong tries for one account in 15 min -> 15 min lock
    "login_ip":         Rule(limit=25, window=900, block=900),    # a spray from one address across many accounts
    "register_ip":      Rule(limit=10, window=3600, block=3600),  # account-creation spam
    "doctor_token":     Rule(limit=10, window=900, block=1800),   # guessing a doctor-link or Emergency Card token
}

limiter = RateLimiter(RULES)


def client_key(request) -> str:
    """The caller's address. Behind the deployed reverse proxy this comes from X-Forwarded-For, whose first entry Caddy sets."""
    fwd = request.headers.get("x-forwarded-for", "")
    if fwd:
        return fwd.split(",")[0].strip()[:64]
    return (request.client.host if request.client else "unknown")[:64]
