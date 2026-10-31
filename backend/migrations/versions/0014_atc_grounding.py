"""The drug-family reference list carries its WHO ATC classification (D-63).

Revision ID: 0014
Revises: 0013

The allergy check matches in code against our own family list (CLAUDE.md invariant 3). Hand-written is hard to trust, so each substance now
carries the ATC classes the WHO gives it, looked up once through the US National Library of Medicine's RxClass API and committed as
`data/reference/atc_snapshot.json` (`backend/scripts/atc_check.py`). A membership whose ATC code matches its family is marked confirmed.

This changes no decision: a conflict is still raised by the same code against the same list, so an unconfirmed member still flags. It only
records WHY a family match can be trusted, so a flag can cite a public class code instead of only our own list. It is not a pharmacist
review and says nothing about cross-reactivity between families.
"""
import json
from pathlib import Path

from alembic import op

revision = "0014"
down_revision = "0013"
branch_labels = None
depends_on = None

SNAPSHOT = Path(__file__).resolve().parents[3] / "data" / "reference" / "atc_snapshot.json"


def upgrade() -> None:
    op.execute("""
    ALTER TABLE drug_families
      ADD COLUMN atc_prefix text,                       -- the ATC group this family is, e.g. M01A for NSAIDs
      ADD COLUMN atc_name   text;

    ALTER TABLE drug_substances
      ADD COLUMN rxcui      text,                       -- NLM's id for the ingredient, so the lookup can be repeated
      ADD COLUMN atc_codes  text[] NOT NULL DEFAULT '{}';

    -- Per membership: did the WHO ATC classification agree that this substance belongs to this family?
    ALTER TABLE drug_family_members
      ADD COLUMN atc_confirmed boolean NOT NULL DEFAULT false;

    -- Where the answer came from and when, so the screens can say it and a later run can refresh it.
    CREATE TABLE reference_checks (
      id          uuid PRIMARY KEY DEFAULT gen_random_uuid(),
      kind        text NOT NULL UNIQUE,
      source      text NOT NULL,
      caveat      text NOT NULL,
      checked_on  date NOT NULL,
      summary     jsonb NOT NULL DEFAULT '{}'::jsonb,
      created_at  timestamptz NOT NULL DEFAULT now()
    );
    GRANT SELECT ON reference_checks TO caresaathi_app, caresaathi_worker, caresaathi_readonly;
    """)

    if not SNAPSHOT.exists():            # a database built without the snapshot keeps every membership unconfirmed, which is the safe state
        return
    snap = json.loads(SNAPSHOT.read_text(encoding="utf-8"))
    for fam, info in snap.get("families", {}).items():
        op.execute(_sql("UPDATE drug_families SET atc_prefix = {p}, atc_name = {n} WHERE code = {c}",
                        p=info.get("atc_prefix"), n=info.get("atc_name"), c=fam))
    for name, got in snap.get("substances", {}).items():
        codes = "{" + ",".join(f'"{a["code"]}"' for a in got.get("atc", [])) + "}"
        op.execute(_sql("UPDATE drug_substances SET rxcui = {r}, atc_codes = {a}::text[] WHERE substance_normalized = {s}",
                        r=got.get("rxcui"), a=codes, s=name))
        for fam, ok in (got.get("families") or {}).items():
            if ok:
                op.execute(_sql("""UPDATE drug_family_members m SET atc_confirmed = true
                                   FROM drug_families f, drug_substances s
                                   WHERE m.family_id = f.id AND m.substance_id = s.id AND f.code = {f} AND s.substance_normalized = {s}""",
                                f=fam, s=name))
    op.execute(_sql("""INSERT INTO reference_checks (kind, source, caveat, checked_on, summary)
                       VALUES ('drug_families', {src}, {cav}, {d}::date, {sum}::jsonb)
                       ON CONFLICT (kind) DO UPDATE SET source = EXCLUDED.source, caveat = EXCLUDED.caveat,
                                                        checked_on = EXCLUDED.checked_on, summary = EXCLUDED.summary""",
                    src=snap["source"], cav=snap["caveat"], d=snap["checked_on"], sum=json.dumps(snap.get("summary", {}))))


def _sql(template: str, **vals: object) -> str:
    """Literal SQL for a migration: reference data only, no user input."""
    return template.format(**{k: "NULL" if v is None else "'" + str(v).replace("'", "''") + "'" for k, v in vals.items()})


def downgrade() -> None:
    op.execute("""
    DROP TABLE IF EXISTS reference_checks;
    ALTER TABLE drug_family_members DROP COLUMN IF EXISTS atc_confirmed;
    ALTER TABLE drug_substances DROP COLUMN IF EXISTS atc_codes, DROP COLUMN IF EXISTS rxcui;
    ALTER TABLE drug_families DROP COLUMN IF EXISTS atc_name, DROP COLUMN IF EXISTS atc_prefix;
    """)
