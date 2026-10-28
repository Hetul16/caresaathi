"""A doctor's reply can be the source of a pending plan change (C1, D-46).

Revision ID: 0010
Revises: 0009

- source_kind gains 'doctor_message': the doctor's exact words written in the link. It must not be filed as 'family_input', which would
  attribute the words to a family member.
- source_refs.doctor_message_id points at the stored reply; a CHECK requires it, and the quote, for this kind.
- doctor_messages.read_at / read_by: a reply is read into plan changes at most once, by a named member.
"""
from alembic import op

revision = "0010"
down_revision = "0009"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.get_context().autocommit_block():          # a new enum value cannot be used in the transaction that adds it
        op.execute("ALTER TYPE source_kind ADD VALUE IF NOT EXISTS 'doctor_message'")
    op.execute("""
    ALTER TABLE source_refs ADD COLUMN doctor_message_id uuid REFERENCES doctor_messages(id);
    ALTER TABLE source_refs ADD CONSTRAINT source_refs_doctor_message_ck
      CHECK (kind <> 'doctor_message' OR (doctor_message_id IS NOT NULL AND length(btrim(coalesce(quote, ''))) > 0));
    ALTER TABLE doctor_messages ADD COLUMN read_at timestamptz;
    ALTER TABLE doctor_messages ADD COLUMN read_by uuid REFERENCES users(id);
    ALTER TABLE doctor_messages ADD CONSTRAINT doctor_messages_read_ck
      CHECK ((read_at IS NULL) = (read_by IS NULL) AND (read_at IS NULL OR direction = 'from_doctor'));
    """)


def downgrade() -> None:
    op.execute("""
    ALTER TABLE doctor_messages DROP CONSTRAINT doctor_messages_read_ck, DROP COLUMN read_by, DROP COLUMN read_at;
    ALTER TABLE source_refs DROP CONSTRAINT source_refs_doctor_message_ck, DROP COLUMN doctor_message_id;
    """)
    # An enum value cannot be dropped in place; 'doctor_message' stays in the type after a downgrade.
