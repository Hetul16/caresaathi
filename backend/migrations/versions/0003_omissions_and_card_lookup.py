"""Omission flags (S10), document completeness, and the public Emergency Card lookup.

Revision ID: 0003
Revises: 0002

- documents.completeness: 'complete' only when a "page N of M" marker shows every page is present (invariant 10).
- reconciliation_flags: one flag per earlier medicine per new document. A flag must carry the source of the
  earlier item, so it can always be shown with both sources (docs/16-database-design.md section 9).
- app_resolve_emergency_card(): the public link is checked and logged inside one SECURITY DEFINER function, so the
  web process never needs a role that can read every card. It writes an access row for every outcome.
"""
from alembic import op

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
    ALTER TABLE documents
      ADD COLUMN completeness text NOT NULL DEFAULT 'unknown'
      CHECK (completeness IN ('complete', 'incomplete', 'unknown'));
    """)

    op.execute("""
    CREATE TABLE reconciliation_flags (
      id                    uuid PRIMARY KEY DEFAULT gen_random_uuid(),
      patient_id            uuid NOT NULL REFERENCES patients(id),
      previous_item_id      uuid NOT NULL REFERENCES care_plan_items(id),
      previous_source_ref_id uuid NOT NULL REFERENCES source_refs(id),
      new_document_id       uuid NOT NULL REFERENCES documents(id),
      medicine_title        text NOT NULL,
      state                 text NOT NULL DEFAULT 'open' CHECK (state IN ('open', 'asked', 'resolved')),
      question_output_id    uuid REFERENCES generated_outputs(id),
      state_changed_by      uuid REFERENCES users(id),
      state_changed_at      timestamptz,
      created_at            timestamptz NOT NULL DEFAULT now(),
      -- A flag a person has moved on must say who.
      CHECK (state = 'open' OR (state_changed_by IS NOT NULL AND state_changed_at IS NOT NULL)),
      UNIQUE (previous_item_id, new_document_id)
    );
    CREATE INDEX ix_reconciliation_open ON reconciliation_flags (patient_id) WHERE state = 'open';

    ALTER TABLE reconciliation_flags ENABLE ROW LEVEL SECURITY;
    CREATE POLICY p_member ON reconciliation_flags
      USING (app_can_access_patient(patient_id)) WITH CHECK (app_can_access_patient(patient_id));
    GRANT SELECT, INSERT, UPDATE, DELETE ON reconciliation_flags TO caresaathi_app, caresaathi_worker;
    GRANT SELECT ON reconciliation_flags TO caresaathi_readonly;
    """)

    op.execute("""
    CREATE FUNCTION app_resolve_emergency_card(p_hash bytea, p_ip bytea, p_ua text)
    RETURNS TABLE (r_card_id uuid, r_patient_id uuid, r_outcome card_access_outcome)
    LANGUAGE plpgsql SECURITY DEFINER SET search_path = public AS $$
    DECLARE
      c emergency_cards%ROWTYPE;
      o card_access_outcome;
    BEGIN
      SELECT * INTO c FROM emergency_cards WHERE token_hash = p_hash;
      IF NOT FOUND THEN o := 'not_found';
      ELSIF c.revoked_at IS NOT NULL THEN o := 'revoked';
      ELSIF c.expires_at IS NOT NULL AND c.expires_at <= now() THEN o := 'expired';
      ELSE o := 'ok';
      END IF;
      INSERT INTO emergency_card_access_log (patient_id, card_id, outcome, ip_hash, user_agent)
      VALUES (c.patient_id, c.id, o, p_ip, left(p_ua, 200));
      RETURN QUERY SELECT c.id, CASE WHEN o = 'ok' THEN c.patient_id END, o;
    END $$;
    REVOKE ALL ON FUNCTION app_resolve_emergency_card(bytea, bytea, text) FROM PUBLIC;
    GRANT EXECUTE ON FUNCTION app_resolve_emergency_card(bytea, bytea, text) TO caresaathi_app, caresaathi_worker;
    """)


def downgrade() -> None:
    op.execute("""
    DROP FUNCTION app_resolve_emergency_card(bytea, bytea, text);
    DROP TABLE reconciliation_flags;
    ALTER TABLE documents DROP COLUMN completeness;
    """)
