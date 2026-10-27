"""Inviting and managing family members. Who can confirm, approve, hear recordings and manage others is enforced here."""
from __future__ import annotations

import uuid

import pytest

pytestmark = pytest.mark.usefixtures("scratch_db")


def join_as(family, code_url: str, name="Anil Kulkarni"):
    """A brand-new person signs up and accepts an invitation. Returns their auth header."""
    email = f"j{uuid.uuid4().hex[:10]}@example.com"
    r = family.client.post("/api/v1/auth/register", json={"display_name": name, "email": email, "password": "correct-horse-battery"})
    h = {"Authorization": f"Bearer {r.json()['access_token']}"}
    code = code_url.rsplit("/join/", 1)[1]
    return h, family.client.post("/api/v1/invites/accept", headers=h, json={"code": code})


def test_an_invited_person_joins_with_exactly_the_permissions_given(family):
    inv = family.post(f"/patients/{family.pid}/invites", {"member_role": "child", "relationship_label": "Son", "can_approve": False,
                                                           "can_view_recordings": False}).json()
    assert "/join/" in inv["url"] and len(inv["url"].rsplit("/join/", 1)[1]) >= 20
    h, r = join_as(family, inv["url"])
    assert r.status_code == 200 and r.json() == {"patient_id": family.pid, "status": "joined"}
    # they can now see the patient, but not approve
    assert family.client.get(f"/api/v1/patients/{family.pid}/care-plan", headers=h).status_code == 200
    family.upload("Tab Metformin 500 mg 1-0-1\n", doc_type="prescription")
    key = family.plan()["items"][0]["item_key"]
    assert family.client.post(f"/api/v1/patients/{family.pid}/plan-items/{key}/confirm", headers=h).status_code == 403
    members = {m["name"]: m for m in family.get(f"/patients/{family.pid}/members").json()}
    assert members["Anil Kulkarni"]["relationship"] == "Son" and members["Anil Kulkarni"]["can_approve"] is False


def test_an_invitation_works_once(family):
    inv = family.post(f"/patients/{family.pid}/invites", {}).json()
    _, first = join_as(family, inv["url"])
    _, second = join_as(family, inv["url"], name="Someone Else")
    assert first.status_code == 200 and second.status_code == 404 and second.json()["type"].endswith("invite-unavailable")


def test_a_revoked_or_expired_or_unknown_invitation_looks_the_same(family, admin):
    revoked = family.post(f"/patients/{family.pid}/invites", {}).json()
    family.post(f"/invites/{revoked['id']}/revoke")
    expired = family.post(f"/patients/{family.pid}/invites", {}).json()
    admin.execute("UPDATE member_invites SET expires_at = now() - interval '1 minute' WHERE id = %s", (expired["id"],))
    results = []
    for url in (revoked["url"], expired["url"], "http://x/join/" + "z" * 24):
        _, r = join_as(family, url)
        results.append((r.status_code, r.json()["title"]))
    assert len(set(results)) == 1 and results[0][0] == 404


def test_only_a_manager_can_invite_or_change_permissions(family):
    inv = family.post(f"/patients/{family.pid}/invites", {"can_approve": True}).json()
    h, _ = join_as(family, inv["url"])
    assert family.client.post(f"/api/v1/patients/{family.pid}/invites", headers=h, json={}).status_code == 403
    assert family.client.get(f"/api/v1/patients/{family.pid}/invites", headers=h).status_code == 403
    mid = next(m["id"] for m in family.get(f"/patients/{family.pid}/members").json() if m["name"] == "Anil Kulkarni")
    assert family.client.patch(f"/api/v1/members/{mid}", headers=h, json={"can_manage_members": True}).status_code == 403


def test_a_manager_can_change_permissions_and_remove_a_member(family, admin):
    inv = family.post(f"/patients/{family.pid}/invites", {"can_approve": False}).json()
    h, _ = join_as(family, inv["url"])
    mid = next(m["id"] for m in family.get(f"/patients/{family.pid}/members").json() if m["name"] == "Anil Kulkarni")
    assert family.client.patch(f"/api/v1/members/{mid}", headers=family.h, json={"can_approve": True}).status_code == 200
    family.upload("Tab Metformin 500 mg 1-0-1\n", doc_type="prescription")
    key = family.plan()["items"][0]["item_key"]
    assert family.client.post(f"/api/v1/patients/{family.pid}/plan-items/{key}/confirm", headers=h).status_code == 200
    assert family.client.patch(f"/api/v1/members/{mid}", headers=family.h, json={"remove": True}).status_code == 200
    assert family.client.get(f"/api/v1/patients/{family.pid}/care-plan", headers=h).status_code == 404         # no longer a member
    assert admin.execute("SELECT count(*) FROM audit_log WHERE patient_id = %s AND action IN ('member.permissions_changed','member.removed','member.joined')",
                         (family.pid,)).fetchone()[0] == 3


def test_the_last_manager_cannot_be_removed_or_demoted(family):
    me = next(m["id"] for m in family.get(f"/patients/{family.pid}/members").json() if m["user_id"] == family.user_id)
    assert family.client.patch(f"/api/v1/members/{me}", headers=family.h, json={"remove": True}).status_code == 409
    assert family.client.patch(f"/api/v1/members/{me}", headers=family.h, json={"can_manage_members": False}).status_code == 409


def test_a_stranger_cannot_list_members_or_invites(family, stranger):
    assert stranger.get(f"/patients/{family.pid}/members").status_code == 404
    assert stranger.get(f"/patients/{family.pid}/invites").status_code == 404


def test_the_code_is_stored_only_as_a_hash(family, admin):
    inv = family.post(f"/patients/{family.pid}/invites", {}).json()
    code = inv["url"].rsplit("/join/", 1)[1]
    row = admin.execute("SELECT to_jsonb(m)::text FROM member_invites m WHERE id = %s", (inv["id"],)).fetchone()[0]
    assert code not in row and inv["hint"] == code[-4:]
