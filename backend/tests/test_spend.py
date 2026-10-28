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
            return SimpleNamespace(raise_for_status=lambda: None,
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
