"""Family task board (C8, D-59): who is doing what for the patient (pick up the refill, go with her to physiotherapy).

Revision ID: 0013
Revises: 0012

A task is plain coordination between family members. It is not a medical order: it never says what to give or when. Completing a task needs
a named person, and a CHECK ties the done state to who and when.
"""
from alembic import op

revision = "0013"
down_revision = "0012"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
    CREATE TABLE care_tasks (
      id           uuid PRIMARY KEY DEFAULT gen_random_uuid(),
      patient_id   uuid NOT NULL REFERENCES patients(id),
      title        text NOT NULL CHECK (length(btrim(title)) BETWEEN 1 AND 200),
      assigned_to  uuid REFERENCES users(id),
      due_date     date,
      status       text NOT NULL DEFAULT 'open' CHECK (status IN ('open', 'done')),
      created_by   uuid NOT NULL REFERENCES users(id),
      created_at   timestamptz NOT NULL DEFAULT now(),
      done_by      uuid REFERENCES users(id),
      done_at      timestamptz,
      CHECK ((status = 'done') = (done_by IS NOT NULL AND done_at IS NOT NULL))
    );
    CREATE INDEX ix_care_tasks_open ON care_tasks (patient_id, due_date) WHERE status = 'open';
    ALTER TABLE care_tasks ENABLE ROW LEVEL SECURITY;
    CREATE POLICY p_member ON care_tasks USING (app_can_access_patient(patient_id)) WITH CHECK (app_can_access_patient(patient_id));
    GRANT SELECT, INSERT, UPDATE ON care_tasks TO caresaathi_app, caresaathi_worker;
    GRANT SELECT ON care_tasks TO caresaathi_readonly;
    """)


def downgrade() -> None:
    op.execute("DROP TABLE care_tasks;")
