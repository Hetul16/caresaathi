"""Checks the drug-family reference list against the WHO ATC classification, and writes a dated snapshot.

    python scripts/atc_check.py            # look it up and write data/reference/atc_snapshot.json
    python scripts/atc_check.py --verify   # fail if the committed snapshot disagrees with the seed list (no network)

Why: the allergy check matches in code against a hand-written family list (CLAUDE.md invariant 3). Hand-written is hard to trust, so every
substance is looked up in the WHO ATC classification through the US National Library of Medicine's RxClass API, and the answer is committed as
a file. The app then cites a public class code instead of only our own list.

This is NOT a pharmacist review and NOT a statement about cross-reactivity. ATC is a classification of what a substance is, nothing more.
A substance the lookup cannot place keeps `confirmed: false` and the app goes on treating it as our own unreviewed entry.

Terms: the RxNorm APIs are free and need no key; NLM asks for at most 20 requests a second and for results to be cached, which is what the
snapshot is. Attribution is in the README. https://rxnav.nlm.nih.gov/TermOfService.html
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import time
from datetime import date
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parents[2]
SEED = ROOT / "db" / "seed_drug_families.sql"
OUT = ROOT / "data" / "reference" / "atc_snapshot.json"
BASE = "https://rxnav.nlm.nih.gov/REST"

# What each family in our seed list is, in WHO ATC terms. A substance confirms its family when one of its ATC codes starts with this.
FAMILY_ATC = {
    "penicillins":    ("J01C", "Beta-lactam antibacterials, penicillins"),
    "cephalosporins": ("J01D", "Other beta-lactam antibacterials (cephalosporins)"),
    "sulfonamides":   ("J01E", "Sulfonamides and trimethoprim"),
    "nsaids":         ("M01A", "Antiinflammatory and antirheumatic products, non-steroids"),
    "macrolides":     ("J01F", "Macrolides, lincosamides and streptogramins"),
}


def seed_members() -> dict[str, list[str]]:
    """family code -> substance names, read from the seed file so the check follows the list the database is built from."""
    sql = SEED.read_text(encoding="utf-8")
    block = sql.split("INSERT INTO drug_family_members")[1]
    out: dict[str, list[str]] = {}
    for fam, sub in re.findall(r"\('([a-z_]+)',\s*'([^']+)'\)", block):
        out.setdefault(fam, []).append(sub)
    return out


def atc_for(c: httpx.Client, name: str) -> dict:
    """The ATC classes WHO gives this ingredient, through NLM RxClass. Anything unresolved comes back empty, never guessed."""
    r = c.get(f"{BASE}/rxcui.json", params={"name": name, "search": 1})
    r.raise_for_status()
    ids = r.json().get("idGroup", {}).get("rxnormId") or []
    if not ids:
        return {"rxcui": None, "atc": []}
    time.sleep(0.1)                                            # NLM asks for no more than 20 requests a second
    r2 = c.get(f"{BASE}/rxclass/class/byRxcui.json", params={"rxcui": ids[0], "relaSource": "ATC"})
    r2.raise_for_status()
    items = r2.json().get("rxclassDrugInfoList", {}).get("rxclassDrugInfo", []) or []
    seen, atc = set(), []
    for x in items:
        m = x.get("rxclassMinConceptItem", {})
        if m.get("classId") and m["classId"] not in seen:
            seen.add(m["classId"])
            atc.append({"code": m["classId"], "name": m.get("className", "")})
    return {"rxcui": ids[0], "atc": sorted(atc, key=lambda a: a["code"])}


def build() -> int:
    members = seed_members()
    snap: dict = {
        "checked_on": date.today().isoformat(),
        "source": "WHO ATC classification, via the US National Library of Medicine RxClass API (https://rxnav.nlm.nih.gov)",
        "caveat": "A classification of what a substance is. Not a pharmacist review, and not a statement about cross-reactivity "
                  "between families. A substance with confirmed=false stays an unreviewed entry in our own list.",
        "families": {}, "substances": {},
    }
    agreed = checked = 0
    with httpx.Client(timeout=30, headers={"User-Agent": "CareSaathi/0.1 (hackathon project; synthetic data)"}) as c:
        for fam, subs in sorted(members.items()):
            prefix, label = FAMILY_ATC.get(fam, (None, ""))
            snap["families"][fam] = {"atc_prefix": prefix, "atc_name": label, "members": sorted(subs)}
            for name in sorted(subs):
                if name in snap["substances"]:
                    got = snap["substances"][name]
                else:
                    try:
                        got = atc_for(c, name)
                    except httpx.HTTPError as e:
                        print(f"  ! {name}: lookup failed ({e})")
                        got = {"rxcui": None, "atc": []}
                    snap["substances"][name] = got
                    time.sleep(0.1)
                ok = bool(prefix) and any(a["code"].startswith(prefix) for a in got["atc"])
                got.setdefault("families", {})[fam] = ok
                checked += 1
                agreed += ok
                codes = ", ".join(a["code"] for a in got["atc"]) or "no ATC class found"
                print(f"  {'OK ' if ok else '-- '} {name:<22} {fam:<15} {codes}")
    snap["summary"] = {"memberships_checked": checked, "confirmed_by_atc": agreed, "not_confirmed": checked - agreed}
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(snap, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"\n{agreed} of {checked} memberships confirmed by the WHO ATC classification. Written to {OUT.relative_to(ROOT)}")
    return 0


def verify() -> int:
    """No network: the committed snapshot must still cover every membership the seed list claims."""
    if not OUT.exists():
        print("No snapshot. Run: python scripts/atc_check.py")
        return 1
    snap = json.loads(OUT.read_text(encoding="utf-8"))
    missing = [f"{s} in {fam}" for fam, subs in seed_members().items() for s in subs
               if fam not in snap["substances"].get(s, {}).get("families", {})]
    if missing:
        print("The seed list has memberships the snapshot does not cover:\n  " + "\n  ".join(missing))
        return 1
    su = snap["summary"]
    print(f"Snapshot of {snap['checked_on']}: {su['confirmed_by_atc']} of {su['memberships_checked']} memberships confirmed by WHO ATC, "
          f"{su['not_confirmed']} not confirmed (shown as our own unreviewed entry).")
    return 0


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--verify", action="store_true", help="check the committed snapshot without calling the network")
    sys.exit(verify() if p.parse_args().verify else build())
