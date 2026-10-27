"""The demo family is built by the real pipeline from the synthetic documents. Every flag below is a computed result."""
from __future__ import annotations

import time

import pytest

pytestmark = pytest.mark.usefixtures("scratch_db")


def seed(family):
    r = family.post("/demo/seed", {"display_name": "Priya Kulkarni"})
    assert r.status_code == 202, r.text
    pid = r.json()["patient_id"]
    for _ in range(200):
        plan = family.client.get(f"/api/v1/patients/{pid}/care-plan", headers=family.h).json()
        if any(t["text"].startswith("Demo family ready") for t in plan["timeline"]):
            return pid, plan
        time.sleep(0.1)
    raise AssertionError("the demo was not ready in time")


def test_the_demo_story_produces_every_planted_flag(family):
    family.post("/demo/seed", {})                          # (a first call only to make sure repeated seeding is safe)
    pid, plan = seed(family)
    assert plan["patient"]["name"] == "Ramesh Kulkarni"

    assert plan["allergies"]["state"] == "listed" and plan["allergies"]["items"][0]["substance"] == "Penicillin"
    assert any(c["medicine"].startswith("Amoxicillin") and c["match"] == "drug_family" for c in plan["open_conflicts"])
    assert [o["medicine"] for o in plan["omissions"]] == ["Atorvastatin 20 mg"]
    assert [d["ingredient"] for d in plan["duplicates"]] == ["paracetamol"]

    changed = [c for c in plan["pending_changes"] if c["change_type"] == "changed"]
    assert [c["title"] for c in changed] == ["Amlodipine 5 mg"] and changed[0]["source"]["quote"].startswith("ab main amlodipine")
    assert any("emergency" in c["title"].lower() for c in plan["pending_changes"])

    # nothing is confirmed on the family's behalf
    assert not any(i["confirmed"] for i in plan["items"])
    assert len(family.get(f"/patients/{pid}/follow-ups").json()) >= 3 and family.get(f"/patients/{pid}/supply").json()


def test_seeding_twice_returns_the_same_patient_and_does_not_duplicate(family):
    first, _ = seed(family)
    again = family.post("/demo/seed", {"display_name": "Priya Kulkarni"}).json()
    assert again == {"patient_id": first, "status": "exists"}
    # the family's own hand-made patient plus exactly one demo patient
    ids = [p["id"] for p in family.get("/patients").json()]
    assert len(ids) == 2 and first in ids and family.pid in ids


def test_the_demo_patient_is_marked_synthetic(family):
    seed(family)
    assert all(p["is_synthetic"] for p in family.get("/patients").json())
