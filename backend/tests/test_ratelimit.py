"""Rate limiting on the ways in, and the headers every answer carries (D-64).

Argon2 makes one password guess slow; nothing stopped a thousand of them before this."""
import uuid

import pytest

from app.safety.ratelimit import RateLimiter, Rule


class Clock:
    def __init__(self) -> None:
        self.t = 1000.0

    def __call__(self) -> float:
        return self.t


def test_the_limit_trips_only_after_the_allowed_number_of_failures():
    c = Clock()
    rl = RateLimiter({"r": Rule(limit=3, window=60, block=120)}, clock=c)
    assert rl.record_failure("r", "a") == 0 and rl.record_failure("r", "a") == 0
    assert rl.retry_after("r", "a") == 0                      # two failures: still allowed through
    assert rl.record_failure("r", "a") == 120                 # the third trips it
    assert rl.retry_after("r", "a") == 120


def test_the_block_expires_and_old_failures_fall_out_of_the_window():
    c = Clock()
    rl = RateLimiter({"r": Rule(limit=3, window=60, block=120)}, clock=c)
    for _ in range(3):
        rl.record_failure("r", "a")
    c.t += 121
    assert rl.retry_after("r", "a") == 0                      # the lock has passed
    rl.record_failure("r", "a")
    c.t += 61                                                 # that failure is now older than the window
    assert rl.record_failure("r", "a") == 0 and rl.record_failure("r", "a") == 0


def test_keys_do_not_leak_into_each_other_and_a_success_clears_the_slate():
    rl = RateLimiter({"r": Rule(limit=2, window=60, block=60)})
    rl.record_failure("r", "a")
    assert rl.retry_after("r", "b") == 0                      # a different account is unaffected
    rl.clear("r", "a")
    assert rl.record_failure("r", "a") == 0                   # the earlier failure was forgotten


# ---- through the API ----------------------------------------------------------------------------------------------------
@pytest.fixture
def fresh_limiter():
    from app.safety.ratelimit import limiter
    limiter._buckets.clear()
    yield limiter
    limiter._buckets.clear()


def test_repeated_wrong_passwords_are_locked_out_and_say_nothing_about_the_account(client, fresh_limiter):
    email = f"lock{uuid.uuid4().hex[:8]}@example.com"
    client.post("/api/v1/auth/register", json={"display_name": "Priya", "email": email, "password": "correct-horse-battery"})
    seen = set()
    for _ in range(8):
        r = client.post("/api/v1/auth/login", json={"identifier": email, "password": "wrong-password-here"})
        seen.add(r.status_code)
    assert 429 in seen
    locked = client.post("/api/v1/auth/login", json={"identifier": email, "password": "wrong-password-here"})
    assert locked.status_code == 429 and "too many" in locked.json()["title"].lower()
    # an account that does not exist is answered exactly the same way, so the lockout never confirms an email
    other = client.post("/api/v1/auth/login", json={"identifier": email, "password": "correct-horse-battery"})
    assert other.status_code == 429 and other.json()["title"] == locked.json()["title"]


def test_the_right_password_still_works_and_clears_the_count(client, fresh_limiter):
    email = f"ok{uuid.uuid4().hex[:8]}@example.com"
    client.post("/api/v1/auth/register", json={"display_name": "Priya", "email": email, "password": "correct-horse-battery"})
    for _ in range(3):
        client.post("/api/v1/auth/login", json={"identifier": email, "password": "nope-nope-nope"})
    assert client.post("/api/v1/auth/login", json={"identifier": email, "password": "correct-horse-battery"}).status_code == 200
    for _ in range(4):                                        # the slate was wiped, so four more failures do not lock it
        assert client.post("/api/v1/auth/login", json={"identifier": email, "password": "nope-nope-nope"}).status_code == 401


def test_every_answer_carries_the_security_headers(client):
    h = client.get("/healthz").headers
    assert h["X-Content-Type-Options"] == "nosniff" and h["X-Frame-Options"] == "DENY"
    assert "frame-ancestors 'none'" in h["Content-Security-Policy"] and "default-src 'none'" in h["Content-Security-Policy"]
    assert "microphone=()" in h["Permissions-Policy"]
    assert "Strict-Transport-Security" not in h              # local development is http; the header appears on an https deployment


def test_the_docs_page_gets_its_own_policy_and_the_api_stays_locked_down(client):
    assert "cdn.jsdelivr.net" in client.get("/api/docs").headers["Content-Security-Policy"]
    assert "cdn.jsdelivr.net" not in client.get("/healthz").headers["Content-Security-Policy"]
