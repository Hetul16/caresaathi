"""Refresh tokens, and the policy that lets a patient's creator add themselves as the first member.

Revision ID: 0002
Revises: 0001

Found while building registration: the baseline policy on family_members requires existing membership, so the
first member of a new patient could never be inserted (chicken and egg). The new policy allows exactly one case:
a user adding themselves as a member of a patient they created, while that patient has no members yet.
"""
from alembic import op

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
    CREATE TABLE refresh_tokens (
      id          uuid PRIMARY KEY DEFAULT gen_random_uuid(),
      user_id     uuid NOT NULL REFERENCES users(id) ON DELETE CASCADE,
      token_hash  bytea NOT NULL UNIQUE,
      expires_at  timestamptz NOT NULL,
      revoked_at  timestamptz,
      user_agent  text,
      created_at  timestamptz NOT NULL DEFAULT now()
    );
    CREATE INDEX ix_refresh_user ON refresh_tokens (user_id) WHERE revoked_at IS NULL;
    GRANT SELECT, INSERT, UPDATE, DELETE ON refresh_tokens TO caresaathi_auth;
    """)

    op.execute("""
    CREATE FUNCTION app_is_creator_without_members(p uuid) RETURNS boolean
    LANGUAGE sql STABLE SECURITY DEFINER SET search_path = public AS $$
      SELECT EXISTS (SELECT 1 FROM patients WHERE id = p AND created_by = app_user_id())
         AND NOT EXISTS (SELECT 1 FROM family_members WHERE patient_id = p)
    $$;
    GRANT EXECUTE ON FUNCTION app_is_creator_without_members(uuid) TO caresaathi_app, caresaathi_worker, caresaathi_readonly;

    CREATE POLICY p_first_member ON family_members FOR INSERT
      WITH CHECK (user_id = app_user_id() AND app_is_creator_without_members(patient_id));
    """)


def downgrade() -> None:
    op.execute("""
    DROP POLICY p_first_member ON family_members;
    DROP FUNCTION app_is_creator_without_members(uuid);
    DROP TABLE refresh_tokens;
    """)
