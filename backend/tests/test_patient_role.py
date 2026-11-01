"""The patient is a member of their own care circle with no rights over it (D-66, migration 0015).

The person being cared for signs in, marks a dose taken and says how they feel. They can never confirm the care plan, approve a change,
read a visit transcript or invite anyone, and the limit holds at three levels: the form drops the flags, the service refuses to grant them
later, and the database refuses the row.
"""
from __future__ import annotations

import uuid

import pytest
pytestmark = pytest.mark.usefixtures("scratch_db")


def join_as(family, code_url: str, name="Sunita Deshmukh"):
    email = f"j{uuid.uuid4().hex[:10]}@example.com"
    r = family.client.post("/api/v1/auth/register", json={"display_name": name, "email": email, "password": "correct-horse-battery"})
    h = {"Authorization": f"Bearer {r.json()['access_token']}"}
    return h, family.client.post("/api/v1/invites/accept", headers=h, json={"code": code_url.rsplit("/join/", 1)[1]})


def invite_patient(family, **extra):
    return family.post(f"/patients/{family.pid}/invites", {"member_role": "patient", "relationship_label": "Mother", **extra}).json()


def test_the_patient_can_mark_a_dose_and_say_how_they_feel(family):
    family.upload("Tab Amlodipine 5 mg 1-0-0 for 30 days\n", doc_type="prescription")
    key = family.plan()["items"][0]["item_key"]
    family.post(f"/patients/{family.pid}/plan-items/{key}/confirm", {})
    h, r = join_as(family, invite_patient(family)["url"])
    assert r.status_code == 200

    assert family.client.get(f"/api/v1/patients/{family.pid}/today", headers=h).status_code == 200
    assert family.client.post(f"/api/v1/patients/{family.pid}/doses", headers=h,
                              json={"item_key": key, "slot": "morning", "status": "taken"}).status_code == 201
    assert family.client.post(f"/api/v1/patients/{family.pid}/wellbeing", headers=h, json={"pain": 6}).status_code == 201
    # and the family sees it under the patient's own name, not a relative's
    entry = family.get(f"/patients/{family.pid}/wellbeing?days=14").json()["entries"][0]
    assert entry["pain"] == 6 and entry["by"] == "Sunita Deshmukh"


@pytest.mark.parametrize("method,path,body", [
    ("post", "plan-items/{key}/confirm", {}),
    ("post", "invites", {"member_role": "child"}),
    ("post", "doctor-links", {"doctor_name": "Dr Rao"}),
])
def test_the_patient_is_refused_every_right_over_the_care_plan(family, method, path, body):
    family.upload("Tab Amlodipine 5 mg 1-0-0\n", doc_type="prescription")
    key = family.plan()["items"][0]["item_key"]
    h, _ = join_as(family, invite_patient(family)["url"])
    url = f"/api/v1/patients/{family.pid}/" + path.format(key=key)
    assert getattr(family.client, method)(url, headers=h, json=body).status_code == 403


def test_the_invitation_form_cannot_hand_the_patient_any_rights(family):
    """Every flag is sent as true; the member joins with all three false."""
    h, _ = join_as(family, invite_patient(family, can_approve=True, can_view_recordings=True, can_manage_members=True)["url"])
    m = next(m for m in family.get(f"/patients/{family.pid}/members").json() if m["role"] == "patient")
    assert (m["can_approve"], m["can_view_recordings"], m["can_manage_members"]) == (False, False, False)


def test_a_patient_cannot_be_promoted_afterwards(family):
    join_as(family, invite_patient(family)["url"])
    m = next(m for m in family.get(f"/patients/{family.pid}/members").json() if m["role"] == "patient")
    r = family.client.patch(f"/api/v1/members/{m['id']}", headers=family.h, json={"can_approve": True})
    assert r.status_code == 409 and r.json()["type"].endswith("patient-has-no-rights")


def test_the_database_refuses_a_patient_with_rights(family, admin):
    """The last line. A superuser write, past the API and past row-level security, is still refused."""
    with pytest.raises(Exception, match="patient_has_no_rights"):
        admin.execute("UPDATE family_members SET member_role = 'patient', can_approve = true WHERE patient_id = %s", (family.pid,))


def test_the_database_refuses_a_second_patient(family, admin):
    join_as(family, invite_patient(family)["url"])
    with pytest.raises(Exception, match="ux_one_patient_member"):
        # the rights are cleared in the same statement, so the unique index is what refuses it and not the CHECK above
        admin.execute("UPDATE family_members SET member_role = 'patient', can_approve = false, can_manage_members = false, "
                      "can_view_recordings = false WHERE patient_id = %s AND member_role <> 'patient'", (family.pid,))


def test_only_one_patient_per_care_circle(family):
    join_as(family, invite_patient(family)["url"])
    h, second = join_as(family, invite_patient(family)["url"], name="Someone Else")
    assert second.status_code == 409 and second.json()["type"].endswith("patient-exists")


def test_the_care_plan_tells_the_website_which_role_is_looking(family):
    h, _ = join_as(family, invite_patient(family)["url"])
    assert family.client.get(f"/api/v1/patients/{family.pid}/care-plan", headers=h).json()["member_role"] == "patient"
    assert family.plan()["member_role"] != "patient"
