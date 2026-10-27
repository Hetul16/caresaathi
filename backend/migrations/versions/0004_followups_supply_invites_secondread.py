"""Follow-ups (A1), supply records (A6), member invitations (S7) and second reads (A5).

Revision ID: 0004
Revises: 0003

Each table has row-level security by patient. Constraints that carry a safety rule:
  - follow_ups: anything past 'pending' names the person who acted; a due date needs an anchor date.
  - supply_records: quantity is positive, and an estimate needs the daily units it was computed from.
  - second_reads: a chosen reading names who chose it.
  - member_invites: only a hash of the code is stored; acceptance happens inside one SECURITY DEFINER function so a
    new member can join without any broad access to family_members.
"""
from alembic import op

revision = "0004"
down_revision = "0003"
branch_labels = None
depends_on = None

_RLS = """
ALTER TABLE {t} ENABLE ROW LEVEL SECURITY;
CREATE POLICY p_member ON {t} USING (app_can_access_patient(patient_id)) WITH CHECK (app_can_access_patient(patient_id));
GRANT SELECT, INSERT, UPDATE, DELETE ON {t} TO caresaathi_app, caresaathi_worker;
GRANT SELECT ON {t} TO caresaathi_readonly;
"""


def upgrade() -> None:
    op.execute("""
    CREATE TABLE follow_ups (
      id              uuid PRIMARY KEY DEFAULT gen_random_uuid(),
      patient_id      uuid NOT NULL REFERENCES patients(id),
      source_ref_id   uuid NOT NULL REFERENCES source_refs(id),
      what            text NOT NULL,
      due_text        text NOT NULL,
      anchor_date     date,
      anchor_kind     text CHECK (anchor_kind IN ('document', 'visit')),
      due_date        date,
      status          text NOT NULL DEFAULT 'pending' CHECK (status IN ('pending', 'confirmed', 'done', 'dismissed')),
      confirmed_by    uuid REFERENCES users(id),
      confirmed_at    timestamptz,
      created_at      timestamptz NOT NULL DEFAULT now(),
      CHECK (status = 'pending' OR (confirmed_by IS NOT NULL AND confirmed_at IS NOT NULL)),
      CHECK (due_date IS NULL OR anchor_date IS NOT NULL),
      UNIQUE (patient_id, source_ref_id, what)
    );
    CREATE INDEX ix_follow_ups_open ON follow_ups (patient_id, due_date) WHERE status IN ('pending', 'confirmed');
    """ + _RLS.format(t="follow_ups"))

    op.execute("""
    CREATE TABLE supply_records (
      id                 uuid PRIMARY KEY DEFAULT gen_random_uuid(),
      patient_id         uuid NOT NULL REFERENCES patients(id),
      item_key           uuid NOT NULL,
      care_plan_item_id  uuid NOT NULL REFERENCES care_plan_items(id),
      quantity           numeric NOT NULL CHECK (quantity > 0),
      quantity_unit      text NOT NULL DEFAULT 'tablets',
      daily_units        numeric CHECK (daily_units > 0),
      start_date         date NOT NULL,
      estimated_run_out  date,
      source_ref_id      uuid REFERENCES source_refs(id),
      confirmed_by       uuid REFERENCES users(id),
      confirmed_at       timestamptz,
      created_at         timestamptz NOT NULL DEFAULT now(),
      CHECK (estimated_run_out IS NULL OR daily_units IS NOT NULL),
      CHECK ((confirmed_by IS NULL) = (confirmed_at IS NULL)),
      UNIQUE (care_plan_item_id)
    );
    """ + _RLS.format(t="supply_records"))

    op.execute("""
    CREATE TABLE second_reads (
      id               uuid PRIMARY KEY DEFAULT gen_random_uuid(),
      patient_id       uuid NOT NULL REFERENCES patients(id),
      document_id      uuid NOT NULL REFERENCES documents(id),
      item_title       text NOT NULL,
      reading_a        jsonb NOT NULL,
      reading_b        jsonb NOT NULL,
      differing_fields text[] NOT NULL,
      chosen_reading   text CHECK (chosen_reading IN ('a', 'b', 'neither')),
      chosen_by        uuid REFERENCES users(id),
      chosen_at        timestamptz,
      created_at       timestamptz NOT NULL DEFAULT now(),
      CHECK (chosen_reading IS NULL OR (chosen_by IS NOT NULL AND chosen_at IS NOT NULL)),
      CHECK (cardinality(differing_fields) > 0)
    );
    """ + _RLS.format(t="second_reads"))

    op.execute("""
    CREATE TABLE member_invites (
      id                   uuid PRIMARY KEY DEFAULT gen_random_uuid(),
      patient_id           uuid NOT NULL REFERENCES patients(id),
      code_hash            bytea NOT NULL UNIQUE,
      code_hint            text NOT NULL,
      member_role          member_role NOT NULL,
      relationship_label   text,
      can_approve          boolean NOT NULL DEFAULT false,
      can_manage_members   boolean NOT NULL DEFAULT false,
      can_view_recordings  boolean NOT NULL DEFAULT false,
      created_by           uuid NOT NULL REFERENCES users(id),
      expires_at           timestamptz NOT NULL,
      accepted_by          uuid REFERENCES users(id),
      accepted_at          timestamptz,
      revoked_at           timestamptz,
      created_at           timestamptz NOT NULL DEFAULT now(),
      CHECK ((accepted_by IS NULL) = (accepted_at IS NULL))
    );
    """ + _RLS.format(t="member_invites") + """
    CREATE FUNCTION app_accept_invite(p_hash bytea, p_user uuid)
    RETURNS TABLE (r_patient_id uuid, r_outcome text)
    LANGUAGE plpgsql SECURITY DEFINER SET search_path = public AS $$
    DECLARE i member_invites%ROWTYPE;
    BEGIN
      SELECT * INTO i FROM member_invites WHERE code_hash = p_hash FOR UPDATE;
      IF NOT FOUND OR i.revoked_at IS NOT NULL OR i.accepted_at IS NOT NULL OR i.expires_at <= now() THEN
        RETURN QUERY SELECT NULL::uuid, 'unavailable'::text; RETURN;
      END IF;
      IF EXISTS (SELECT 1 FROM family_members WHERE patient_id = i.patient_id AND user_id = p_user) THEN
        RETURN QUERY SELECT i.patient_id, 'already_member'::text; RETURN;
      END IF;
      INSERT INTO family_members (patient_id, user_id, member_role, relationship_label, status, can_approve,
                                  can_manage_members, can_view_recordings, invited_by)
      VALUES (i.patient_id, p_user, i.member_role, i.relationship_label, 'active', i.can_approve,
              i.can_manage_members, i.can_view_recordings, i.created_by);
      UPDATE member_invites SET accepted_by = p_user, accepted_at = now() WHERE id = i.id;
      INSERT INTO audit_log (actor_type, actor_id, patient_id, action, entity_type, entity_id)
      VALUES ('user', p_user, i.patient_id, 'member.joined', 'member_invite', i.id::text);
      RETURN QUERY SELECT i.patient_id, 'joined'::text;
    END $$;
    REVOKE ALL ON FUNCTION app_accept_invite(bytea, uuid) FROM PUBLIC;
    GRANT EXECUTE ON FUNCTION app_accept_invite(bytea, uuid) TO caresaathi_app;
    """)


def downgrade() -> None:
    op.execute("""
    DROP FUNCTION app_accept_invite(bytea, uuid);
    DROP TABLE member_invites;
    DROP TABLE second_reads;
    DROP TABLE supply_records;
    DROP TABLE follow_ups;
    """)
