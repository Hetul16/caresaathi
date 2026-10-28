"""Doctor link (C1, D-46): who can see what, when a question reaches the doctor, and what a reply can and cannot do."""
import json

import psycopg
import pytest

from test_api_flow import DISCHARGE


def _make(family, name="Dr. Joshi (fictional)", days=7):
    r = family.post(f"/patients/{family.pid}/doctor-links", {"doctor_name": name, "expires_in_days": days})
    assert r.status_code == 201, r.text
    link = r.json()
    return link, link["url"].rsplit("/d/", 1)[1]


def test_page_shows_only_documented_facts_and_logs_each_visit(family, client, admin):
    family.upload(DISCHARGE)
    link, token = _make(family)
    assert len(token) >= 30
    # Only a hash is stored.
    assert admin.execute("SELECT count(*) FROM doctor_links WHERE id = %s AND token_hash <> %s::bytea", (link["id"], token.encode())).fetchone()[0] == 1
    r = client.get(f"/api/v1/d/{token}")
    assert r.status_code == 200 and r.headers["cache-control"] == "no-store"
    body = r.json()
    assert body["doctor_name"].startswith("Dr. Joshi") and body["can_reply"] is False
    assert body["card"]["allergies"]["state"] == "listed" and all(m["source"]["quote"] for m in body["card"]["medicines"])
    assert "email" not in json.dumps(body).lower()
    assert [r[0] for r in admin.execute("SELECT outcome FROM doctor_link_access_log WHERE link_id = %s ORDER BY id", (link["id"],)).fetchall()] == ["ok"]


def test_a_question_reaches_the_doctor_only_after_approval(family, client, admin):
    link, token = _make(family)
    q = family.post(f"/doctor-links/{link['id']}/questions", {"body": "Could you confirm the Amlodipine strength?"})
    assert q.status_code == 202 and q.json()["status"] == "awaiting_approval"
    assert client.get(f"/api/v1/d/{token}").json()["thread"] == []                   # not visible yet
    assert client.post(f"/api/v1/d/{token}/reply", json={"body": "hello"}).status_code == 409   # nothing to answer yet

    assert family.post(f"/actions/{q.json()['id']}/approve", {}).json()["status"] == "done"
    page = client.get(f"/api/v1/d/{token}").json()
    assert [m["direction"] for m in page["thread"]] == ["to_doctor"] and page["can_reply"] is True
    assert admin.execute("SELECT status::text FROM actions WHERE id = %s", (q.json()["id"],)).fetchone()[0] == "done"


def test_a_refused_question_never_reaches_the_doctor(family, client):
    link, token = _make(family)
    q = family.post(f"/doctor-links/{link['id']}/questions", {"body": "A question"}).json()
    family.post(f"/actions/{q['id']}/refuse", {"comment": "Not now"})
    assert client.get(f"/api/v1/d/{token}").json()["thread"] == []


def test_the_database_refuses_a_message_to_the_doctor_without_an_approved_action(family, admin):
    link, _ = _make(family)
    with pytest.raises(psycopg.errors.CheckViolation):
        admin.execute("INSERT INTO doctor_messages (patient_id, link_id, direction, body) VALUES (%s, %s, 'to_doctor', 'sneaky')", (family.pid, link["id"]))


def test_doctor_reply_is_stored_verbatim_and_seen_by_the_family(family, client):
    link, token = _make(family)
    q = family.post(f"/doctor-links/{link['id']}/questions", {"body": "Is the strength 5 mg?"}).json()
    family.post(f"/actions/{q['id']}/approve", {})
    words = "  Yes, 5 mg once in the morning.  Please come back in 2 weeks. "
    assert client.post(f"/api/v1/d/{token}/reply", json={"body": words}).json() == {"ok": True}
    thread = family.get(f"/patients/{family.pid}/doctor-links").json()["links"][0]["messages"]
    assert [m["direction"] for m in thread] == ["to_doctor", "from_doctor"]
    assert thread[1]["body"] == words.strip()
    # The reply alone changes nothing in the plan.
    assert family.plan()["approvals"] == [] and family.plan()["items"] == []


def test_revoked_and_expired_links_look_like_unknown_ones(family, client, admin):
    link, token = _make(family)
    q = family.post(f"/doctor-links/{link['id']}/questions", {"body": "Q"}).json()
    assert family.post(f"/doctor-links/{link['id']}/revoke").json()["status"] == "revoked"
    gone, unknown = client.get(f"/api/v1/d/{token}"), client.get("/api/v1/d/" + "x" * 32)
    assert gone.status_code == unknown.status_code == 404 and gone.json() == unknown.json() == {"available": False}
    assert client.post(f"/api/v1/d/{token}/reply", json={"body": "hi"}).status_code == 404
    # A question cannot be delivered through a switched-off link.
    assert family.post(f"/actions/{q['id']}/approve", {}).json()["status"] == "approved"
    assert admin.execute("SELECT count(*) FROM doctor_messages WHERE link_id = %s", (link["id"],)).fetchone()[0] == 0
    assert family.post(f"/doctor-links/{link['id']}/questions", {"body": "again"}).status_code == 409

    link2, token2 = _make(family, days=1)
    admin.execute("UPDATE doctor_links SET expires_at = now() - interval '1 minute', created_at = now() - interval '2 days' WHERE id = %s", (link2["id"],))
    assert client.get(f"/api/v1/d/{token2}").status_code == 404
    assert admin.execute("SELECT outcome FROM doctor_link_access_log WHERE link_id = %s", (link2["id"],)).fetchone()[0] == "expired"


def test_another_family_cannot_see_or_use_the_link(family, client, admin):
    from conftest import Family
    link, _ = _make(family)
    other = Family(client, admin, "Someone Else")
    assert other.get(f"/patients/{family.pid}/doctor-links").status_code == 404
    assert other.post(f"/doctor-links/{link['id']}/revoke").status_code in (403, 404)
    assert other.post(f"/doctor-links/{link['id']}/questions", {"body": "hi"}).status_code in (403, 404)


def test_doctor_cannot_flood_the_thread(family, client):
    link, token = _make(family)
    q = family.post(f"/doctor-links/{link['id']}/questions", {"body": "Q"}).json()
    family.post(f"/actions/{q['id']}/approve", {})
    codes = [client.post(f"/api/v1/d/{token}/reply", json={"body": f"r{i}"}).status_code for i in range(22)]
    assert codes.count(200) == 20 and codes[-1] == 409
