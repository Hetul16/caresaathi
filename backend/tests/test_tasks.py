"""Family task board (C8, D-59): who does what, with names on everything, and nothing that reads like a medical instruction."""
import psycopg
import pytest


def test_a_task_is_assigned_done_and_named(family):
    brother = family.second_member(can_approve=False)
    uid = None
    members = family.get(f"/patients/{family.pid}/members").json()
    uid = next(m["user_id"] for m in members if m["name"] != "Priya Kulkarni")
    r = family.post(f"/patients/{family.pid}/tasks", {"title": "Pick up the Pregabalin refill", "assigned_to": uid, "due_date": "2099-01-01"})
    assert r.status_code == 201
    t = family.get(f"/patients/{family.pid}/tasks").json()["tasks"][0]
    assert t["title"] == "Pick up the Pregabalin refill" and t["assigned_to"] and t["created_by"] == "Priya Kulkarni" and t["status"] == "open" and not t["overdue"]
    # the assigned brother can see it and finish it, with his own name on it
    import httpx  # noqa: F401
    done = family.client.post(f"/api/v1/tasks/{t['id']}/done", headers=brother, json={})
    assert done.status_code == 200
    after = family.get(f"/patients/{family.pid}/tasks").json()["tasks"][0]
    assert after["status"] == "done" and after["done_by"] and after["done_by"] != "Priya Kulkarni" and after["done_at"]
    assert family.client.post(f"/api/v1/tasks/{t['id']}/done", headers=brother, json={}).status_code == 409
    texts = [e["text"] for e in family.plan()["timeline"]]
    assert any(x.startswith("New task:") for x in texts) and any(x.startswith("Done:") for x in texts)


def test_overdue_is_computed_from_the_due_date(family):
    family.post(f"/patients/{family.pid}/tasks", {"title": "Book the physiotherapy slot", "due_date": "2020-01-01"})
    assert family.get(f"/patients/{family.pid}/tasks").json()["tasks"][0]["overdue"] is True


def test_a_task_can_only_go_to_a_member_of_this_family_and_needs_words(family, client, admin):
    from conftest import Family
    other = Family(client, admin, "Someone Else")
    assert family.post(f"/patients/{family.pid}/tasks", {"title": "x", "assigned_to": other.user_id}).status_code == 422
    assert family.post(f"/patients/{family.pid}/tasks", {"title": "   "}).status_code in (422,)
    assert other.get(f"/patients/{family.pid}/tasks").status_code == 404
    assert other.post(f"/patients/{family.pid}/tasks", {"title": "sneaky"}).status_code == 404


def test_the_database_ties_done_to_who_and_when(family, admin):
    family.post(f"/patients/{family.pid}/tasks", {"title": "Call the pharmacy"})
    tid = family.get(f"/patients/{family.pid}/tasks").json()["tasks"][0]["id"]
    with pytest.raises(psycopg.errors.CheckViolation):
        admin.execute("UPDATE care_tasks SET status = 'done' WHERE id = %s", (tid,))
