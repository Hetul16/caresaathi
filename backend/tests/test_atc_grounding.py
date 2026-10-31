"""The drug-family list carries its WHO ATC classification (D-63), and says plainly when the classification did not confirm an entry.

The ATC check records WHY a family match can be trusted. It must never change WHETHER a conflict is raised: an entry the lookup could not
confirm still flags, because unknown is not safe (CLAUDE.md invariant 10)."""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SNAP = ROOT / "data" / "reference" / "atc_snapshot.json"
SUNITA = ROOT / "data" / "synthetic" / "sunita" / "docs"
RAMESH = ROOT / "data" / "synthetic" / "ramesh" / "docs"


def test_the_committed_snapshot_covers_every_membership_the_seed_list_claims():
    import sys
    sys.path.insert(0, str(ROOT / "backend" / "scripts"))
    from atc_check import seed_members                      # noqa: E402
    snap = json.loads(SNAP.read_text(encoding="utf-8"))
    for fam, subs in seed_members().items():
        for name in subs:
            assert name in snap["substances"], f"{name} was never looked up"
            assert fam in snap["substances"][name]["families"], f"{name} in {fam} is not covered"
    assert snap["summary"]["memberships_checked"] == sum(len(v) for v in seed_members().values())
    assert "not a pharmacist review" in snap["caveat"].lower()


def test_the_snapshot_records_what_the_lookup_could_not_confirm():
    snap = json.loads(SNAP.read_text(encoding="utf-8"))
    # Found on Oct 31: the WHO ATC classification puts aspirin in N02BA/B01AC, not in M01A with the other NSAIDs, and the bare word
    # "penicillin" is a class name with no ATC code of its own. Both stay in our list and still flag; they are labelled, not hidden.
    assert snap["substances"]["aspirin"]["families"]["nsaids"] is False
    assert not any(c["code"].startswith("M01A") for c in snap["substances"]["aspirin"]["atc"])
    assert snap["substances"]["penicillin"]["atc"] == []
    assert snap["summary"]["not_confirmed"] >= 2


def test_a_confirmed_family_match_cites_its_atc_group(family):
    for stem, kind in (("S1", "other"), ("S5", "prescription")):
        f = next(SUNITA.glob(f"{stem}_*.txt"))
        family.upload(f.read_text(encoding="utf-8"), f.name, doc_type=kind)
    plan = family.plan()
    c = next(x for x in plan["open_conflicts"] if x["medicine"].lower().startswith("diclofenac"))
    assert c["match"] == "drug_family"
    b = c["basis"]
    assert b["confirmed"] is True and b["atc_group"] == "M01A" and b["atc_code"].startswith("M01A")
    assert "WHO ATC" in b["text"] and "not a medical judgement" in b["text"].lower()
    assert "nlm" in (b["source"] or "").lower() and b["checked_on"]
    # the basis explains the match; it never says what to do about it
    assert not any(w in b["text"].lower() for w in ("stop", "safe", "unsafe", "do not take", "avoid"))


def test_the_check_records_its_source_and_keeps_the_pharmacist_banner(family):
    plan = family.plan()
    assert plan["reference_list_reviewed"] is False               # the ATC check is not a pharmacist review
    chk = plan["reference_check"]
    assert "ATC" in chk["source"] and "nlm" in chk["source"].lower() and chk["checked_on"]
    assert chk["confirmed_by_atc"] >= 1 and chk["memberships_checked"] >= chk["confirmed_by_atc"]


def test_an_unconfirmed_entry_still_raises_the_conflict_and_says_so(family, monkeypatch):
    """Penicillin's family membership is not ATC-confirmed, yet Amoxicillin must still flag against a recorded penicillin allergy."""
    for stem, kind in (("R4", "other"), ("R5", "prescription")):
        f = next(RAMESH.glob(f"{stem}_*.txt"))
        family.upload(f.read_text(encoding="utf-8"), f.name, doc_type=kind)
    c = next(x for x in family.plan()["open_conflicts"] if x["medicine"].lower().startswith(("amoxicillin", "tab amoxicillin")))
    assert c["match"] == "drug_family"                            # the decision is unchanged by the ATC check
    assert c["basis"]["text"] and ("WHO ATC" in c["basis"]["text"] or "own reference list" in c["basis"]["text"])


def test_a_direct_name_match_needs_no_family_basis(family):
    assert all(x["basis"] is None or x["match"] == "drug_family" for x in family.plan()["open_conflicts"])
