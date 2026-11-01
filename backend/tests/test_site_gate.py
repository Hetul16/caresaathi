"""Private deployment (D-69): while SITE_GATE_TOKEN is set the API answers 404 to anyone who does not carry it.

This is how the submission can be live and unreachable for the days before Nov 4. The website adds the header server-side, so the token
never reaches a browser; the host's health checks stay open because they read nothing.
"""
from types import SimpleNamespace

import pytest

from app import main
from app.config import Settings, production_problems

TOKEN = "gate-" + "z" * 30
PUBLIC_PATH = "/api/v1/trust/live"       # needs no sign-in, so a 404 here can only come from the gate


@pytest.fixture
def gated(monkeypatch):
    monkeypatch.setattr(main, "get_settings", lambda: SimpleNamespace(site_gate_token=TOKEN))


def test_without_the_gate_the_api_answers_anyone(client):
    assert client.get(PUBLIC_PATH).status_code == 200


def test_a_stranger_who_finds_the_address_is_told_nothing(client, gated):
    r = client.get(PUBLIC_PATH)
    assert r.status_code == 404 and "trust" not in r.text.lower()


def test_a_wrong_or_empty_token_is_refused(client, gated):
    assert client.get(PUBLIC_PATH, headers={"X-Site-Gate": "almost-right"}).status_code == 404
    assert client.get(PUBLIC_PATH, headers={"X-Site-Gate": ""}).status_code == 404
    assert client.get(PUBLIC_PATH, headers={"X-Site-Gate": TOKEN[:-1]}).status_code == 404


def test_the_matching_token_gets_through(client, gated):
    assert client.get(PUBLIC_PATH, headers={"X-Site-Gate": TOKEN}).status_code == 200


def test_sign_in_is_closed_too_so_nobody_can_make_an_account_on_a_private_deployment(client, gated):
    r = client.post("/api/v1/auth/register", json={"display_name": "A Stranger", "email": "stranger@example.com",
                                                   "password": "correct-horse-battery", "consent_terms": True})
    assert r.status_code == 404


def test_the_host_can_still_see_that_the_container_is_alive(client, gated):
    assert client.get("/healthz").status_code == 200


def test_a_weak_gate_token_is_refused_on_a_public_address():
    base = dict(public_base_url="https://care.example.org", jwt_secret="j" * 40, token_pepper="p" * 40,
                database_url_app="postgresql+psycopg://a:strong@db/x", database_url_auth="postgresql+psycopg://b:strong@db/x",
                database_url_worker="postgresql+psycopg://c:strong@db/x", allow_demo_seed=False)
    assert production_problems(Settings(**base, site_gate_token="short")) != []
    assert production_problems(Settings(**base, site_gate_token=TOKEN)) == []
    assert production_problems(Settings(**base, site_gate_token="")) == []        # empty is the public deployment, not a mistake
