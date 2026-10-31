"""Outcomes board (C6, D-52): every flag is a question that stays open until a person records the answer and where it came from.

Revision ID: 0011
Revises: 0010

question_answers holds ONE answer per flag. The answer is either a stored doctor reply (copied word for word, linked to the reply) or a note
typed by a named member who says what the doctor or pharmacist told them. A CHECK ties the source kind to the link. Recording an answer is a
person's act, so recorded_by is required. Nothing here says a medicine is safe: the board counts questions and answers only.
"""
from alembic import op

revision = "0011"
down_revision = "0010"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
    CREATE TABLE question_answers (
      id                uuid PRIMARY KEY DEFAULT gen_random_uuid(),
      patient_id        uuid NOT NULL REFERENCES patients(id),
      subject_kind      text NOT NULL CHECK (subject_kind IN ('allergy_conflict', 'reconciliation_flag')),
      subject_id        uuid NOT NULL,
      answer_text       text NOT NULL CHECK (length(btrim(answer_text)) BETWEEN 1 AND 4000),
      answered_by       text NOT NULL CHECK (length(btrim(answered_by)) BETWEEN 1 AND 80),
      source_kind       text NOT NULL CHECK (source_kind IN ('doctor_message', 'family_note')),
      doctor_message_id uuid REFERENCES doctor_messages(id),
      recorded_by       uuid NOT NULL REFERENCES users(id),
      created_at        timestamptz NOT NULL DEFAULT now(),
      CHECK ((source_kind = 'doctor_message') = (doctor_message_id IS NOT NULL)),
      UNIQUE (subject_kind, subject_id)
    );
    CREATE INDEX ix_question_answers_patient ON question_answers (patient_id, created_at DESC);
    ALTER TABLE question_answers ENABLE ROW LEVEL SECURITY;
    CREATE POLICY p_member ON question_answers USING (app_can_access_patient(patient_id)) WITH CHECK (app_can_access_patient(patient_id));
    GRANT SELECT, INSERT ON question_answers TO caresaathi_app, caresaathi_worker;
    GRANT SELECT ON question_answers TO caresaathi_readonly;
    """)


def downgrade() -> None:
    op.execute("DROP TABLE question_answers;")
