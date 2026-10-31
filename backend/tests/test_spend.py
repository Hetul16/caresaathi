"""Spend guard (D-50): live calls are priced, logged, and refused before they are made once the limit is reached."""
from types import SimpleNamespace

import pytest

from app.clients import models, spend


def _settings(tmp_path, **kw):
    base = dict(local_storage_dir=str(tmp_path), spend_limit_usd=1.00, spend_baseline_usd=0.0, price_contrib_in=0.10, price_contrib_out=0.20,
                price_std_in=1.25, price_std_out=4.25, price_voice_per_hour=0.18, allow_contributor_models=True, meta_spark_dev_model="dev",
                meta_spark_model="std", meta_asr_model="asr", effort_read="low", effort_judge="minimal", effort_word="minimal")
    base.update(kw)
    return SimpleNamespace(**base)


@pytest.fixture
def cfg(tmp_path, monkeypatch):
    s = _settings(tmp_path)
    monkeypatch.setattr(spend, "get_settings", lambda: s)
    return s


def test_prices_follow_the_published_rates(cfg):
    assert spend.price("m", True, 1_000_000, 1_000_000) == pytest.approx(0.30)
    assert spend.price("m", False, 1_000_000, 1_000_000) == pytest.approx(5.50)
    assert spend.price("asr", False, None, None, audio_seconds=3600) == pytest.approx(0.18)


def test_total_is_baseline_plus_ledger_and_the_check_stops_at_the_limit(cfg):
    cfg.spend_baseline_usd = 0.40
    spend.add(0.30, model="m", purpose="a")
    assert spend.total() == pytest.approx(0.70)
    spend.check()                                           # under the limit
    spend.add(0.30, model="m", purpose="b")
    with pytest.raises(spend.SpendLimitReached):
        spend.check()


def _client(cfg, usage):
    calls = []

    class Http:
        def post(self, path, json=None, **kw):
            calls.append(path)
            return SimpleNamespace(status_code=200, raise_for_status=lambda: None,
                                   json=lambda: {"choices": [{"message": {"content": "ok"}}], "usage": usage})
    c = models.LiveModelClient.__new__(models.LiveModelClient)
    c.s, c.http = cfg, Http()
    return c, calls


def test_a_live_call_is_logged_and_the_next_one_is_refused_without_calling_out(cfg, monkeypatch):
    monkeypatch.setattr(models, "get_settings", lambda: cfg)
    c, calls = _client(cfg, {"prompt_tokens": 1_000_000, "completion_tokens": 4_000_000})   # 0.10 + 0.80 = 0.90
    c._chat("t", [{"type": "text", "text": "hi"}])
    assert spend.total() == pytest.approx(0.90) and len(calls) == 1
    c._chat("t", [{"type": "text", "text": "hi"}])          # 0.90 < 1.00: still allowed, takes it to 1.80
    assert len(calls) == 2
    with pytest.raises(models.ModelError, match="spend limit"):
        c._chat("t", [{"type": "text", "text": "hi"}])
    assert len(calls) == 2                                  # the refused call never reached the network


def test_a_refused_judge_call_fails_closed(cfg, monkeypatch):
    monkeypatch.setattr(models, "get_settings", lambda: cfg)
    spend.add(5.0, model="m", purpose="x")
    c, calls = _client(cfg, {})
    flagged, _ = c.judge_text("anything")
    assert flagged is None and calls == []                  # None means undecided, which the guard treats as blocked


def test_a_dropped_connection_is_retried_and_only_the_completed_call_is_priced(cfg, monkeypatch):
    import httpx
    monkeypatch.setattr(models, "get_settings", lambda: cfg)
    monkeypatch.setattr(models.time, "sleep", lambda s: None)
    c, calls = _client(cfg, {"prompt_tokens": 1_000_000, "completion_tokens": 0})
    real_post, state = c.http.post, {"n": 0}

    def flaky(path, json=None, **kw):
        state["n"] += 1
        if state["n"] < 3:
            raise httpx.RemoteProtocolError("server disconnected")
        return real_post(path, json=json, **kw)
    c.http.post = flaky
    text, _ = c._chat("t", [{"type": "text", "text": "hi"}])
    assert text == "ok" and state["n"] == 3 and spend.total() == pytest.approx(0.10)


def test_a_connection_that_never_recovers_fails_after_three_tries_without_cost(cfg, monkeypatch):
    import httpx
    monkeypatch.setattr(models, "get_settings", lambda: cfg)
    monkeypatch.setattr(models.time, "sleep", lambda s: None)
    c, _ = _client(cfg, {})
    state = {"n": 0}

    def dead(path, json=None, **kw):
        state["n"] += 1
        raise httpx.RemoteProtocolError("server disconnected")
    c.http.post = dead
    with pytest.raises(models.ModelError):
        c._chat("t", [{"type": "text", "text": "hi"}])
    assert state["n"] == 3 and spend.total() == 0


def test_the_language_hint_is_sent_to_the_speech_endpoint_only_when_the_family_gave_one(cfg, monkeypatch):
    from app.services.visits import language_bias
    assert language_bias("mr") == ["Marathi"] and language_bias("hi") == ["Hindi"] and language_bias("en") == ["English"]
    assert language_bias("unknown") is None and language_bias(None) is None
    monkeypatch.setattr(models, "get_settings", lambda: cfg)
    sent = []

    class Http:
        def post(self, path, headers=None, files=None, **kw):
            sent.append(json.loads(files["request"][1]))
            return SimpleNamespace(status_code=200, raise_for_status=lambda: None, json=lambda: {"turns": []})
    import json
    c = models.LiveModelClient.__new__(models.LiveModelClient)
    c.s, c.http = cfg, Http()
    c.transcribe_audio(b"\x00" * 64, language_bias=["Marathi"])
    c.transcribe_audio(b"\x00" * 64)
    assert sent[0]["languageBias"] == ["Marathi"] and "languageBias" not in sent[1]
