"""The live-model spend ledger moves from a file into the database (D-68).

Revision ID: 0016
Revises: 0015

The guard that stops live calls once the hackathon credit is used up (D-50) counted from `spend.jsonl`, a file beside local storage. That
file survives a restart on a server with a disk, and does not on a free platform that gives the API container no persistent disk: every
redeploy, restart and idle spin-down reset the total to zero, so the cap stopped capping exactly where the deployment is public and the
spending is out of our hands. The ledger belongs next to the data it protects.

`model_spend` is append-only, like `audit_log`: no UPDATE or DELETE is granted, and a trigger refuses both for every role. It carries no
patient column and no patient meaning -- it is an operational record of money, and the guard has to see every row of it whoever is signed
in, so its policy is deliberately unscoped rather than absent (a table with RLS on and no policy would be invisible to the app role).
"""
from alembic import op

revision = "0016"
down_revision = "0015"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
    CREATE TABLE model_spend (
      id        bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
      spent_at  timestamptz NOT NULL DEFAULT now(),
      usd       numeric(12, 8) NOT NULL CHECK (usd >= 0),
      model     text NOT NULL,
      purpose   text NOT NULL,
      source    text NOT NULL DEFAULT 'live' CHECK (source IN ('live', 'imported'))
    );
    COMMENT ON TABLE model_spend IS 'Append-only: one row per completed live model call, priced from its token counts (D-50, D-68).';

    ALTER TABLE model_spend ENABLE ROW LEVEL SECURITY;
    -- Not patient data. The guard must total every row regardless of who is signed in, so this policy is unscoped on purpose.
    CREATE POLICY p_spend_unscoped ON model_spend USING (true) WITH CHECK (true);

    -- SELECT and INSERT only: there is no statement anywhere that should change or remove a priced call.
    GRANT SELECT, INSERT ON model_spend TO caresaathi_app, caresaathi_worker;
    GRANT SELECT ON model_spend TO caresaathi_readonly;

    CREATE FUNCTION model_spend_is_append_only() RETURNS trigger LANGUAGE plpgsql AS $$
    BEGIN
      RAISE EXCEPTION 'model_spend is append-only' USING ERRCODE = 'insufficient_privilege';
    END $$;
    CREATE TRIGGER trg_spend_no_update BEFORE UPDATE OR DELETE ON model_spend
      FOR EACH ROW EXECUTE FUNCTION model_spend_is_append_only();
    CREATE TRIGGER trg_spend_no_truncate BEFORE TRUNCATE ON model_spend
      FOR EACH STATEMENT EXECUTE FUNCTION model_spend_is_append_only();
    """)


def downgrade() -> None:
    op.execute("DROP TABLE model_spend; DROP FUNCTION model_spend_is_append_only();")
