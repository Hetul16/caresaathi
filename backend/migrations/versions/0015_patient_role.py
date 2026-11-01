"""The patient is a member too, with no rights over their own care plan (S7, D-66).

Revision ID: 0015
Revises: 0014

Until now every member of a care circle was a family member. The person being cared for had no sign-in of their own: Elder mode was a view
of a relative's session, so a pain number the patient entered was stored under the relative's name.

This adds the patient as a real member with the role that already existed in the enum, and makes the limits structural rather than a habit:

- A member whose role is 'patient' can never hold can_approve, can_manage_members or can_view_recordings. The database refuses the row, so
  neither a careless invitation form nor a future bug can hand someone approval rights over their own care plan.
- One patient per care circle. The partial unique index counts only active rows, so a patient who leaves can be replaced.

What the patient may still do is unchanged and needs no new permission: mark a dose taken or not taken, record how they feel, and ask a
question. Those endpoints ask only for membership (backend/app/api/checkins.py).
"""
from alembic import op

revision = "0015"
down_revision = "0014"
branch_labels = None
depends_on = None

# Spelled out per column rather than as a loop: the constraint text is what a reader of the schema sees.
_NO_RIGHTS = """
ALTER TABLE {t} ADD CONSTRAINT {t}_patient_has_no_rights CHECK (
  member_role <> 'patient'
  OR (can_approve = false AND can_manage_members = false AND can_view_recordings = false)
);
"""


# Accepting an invitation runs inside app_accept_invite, so the "one patient" rule has to be answered there too. Without this the second
# patient invitation would hit the unique index and surface as a 500 instead of a sentence the inviter can act on.
_ACCEPT = """
CREATE OR REPLACE FUNCTION app_accept_invite(p_hash bytea, p_user uuid)
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
  IF i.member_role = 'patient' AND EXISTS (
       SELECT 1 FROM family_members WHERE patient_id = i.patient_id AND member_role = 'patient' AND status = 'active') THEN
    RETURN QUERY SELECT i.patient_id, 'patient_exists'::text; RETURN;
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
"""


def upgrade() -> None:
    op.execute(_NO_RIGHTS.format(t="family_members"))
    op.execute(_NO_RIGHTS.format(t="member_invites"))
    op.execute("""
    CREATE UNIQUE INDEX ux_one_patient_member ON family_members (patient_id)
      WHERE member_role = 'patient' AND status = 'active';
    """)
    op.execute(_ACCEPT)


def downgrade() -> None:
    # app_accept_invite keeps its 'patient_exists' branch, which is harmless: it only repeats in code the rule the index enforced.
    op.execute("DROP INDEX IF EXISTS ux_one_patient_member")
    op.execute("ALTER TABLE member_invites DROP CONSTRAINT IF EXISTS member_invites_patient_has_no_rights")
    op.execute("ALTER TABLE family_members DROP CONSTRAINT IF EXISTS family_members_patient_has_no_rights")
