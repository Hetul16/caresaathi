"""Care crew trace (C2, D-47): every step of an agent run is a row, so the screen shows exactly what happened.

Revision ID: 0009
Revises: 0008

agent_runs gains the goal the family typed, who asked, and the final result (the visit brief). agent_steps holds one row per tool call
with its permission level, what the code decided (ran, waiting for approval, refused, failed), and the action it queued if any.
A step that waits for approval must point at its action (a CHECK enforces it), and a step cannot be both refused and linked to an action.
"""
from alembic import op

revision = "0009"
down_revision = "0008"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
    ALTER TABLE agent_runs ADD COLUMN goal text;
    ALTER TABLE agent_runs ADD COLUMN requested_by uuid REFERENCES users(id);
    ALTER TABLE agent_runs ADD COLUMN result jsonb;
    ALTER TABLE agent_runs ADD COLUMN step_count integer NOT NULL DEFAULT 0 CHECK (step_count BETWEEN 0 AND 6);
    GRANT UPDATE (goal, requested_by, result, step_count) ON agent_runs TO caresaathi_app, caresaathi_worker;

    CREATE TABLE agent_steps (
      id          uuid PRIMARY KEY DEFAULT gen_random_uuid(),
      run_id      uuid NOT NULL REFERENCES agent_runs(id) ON DELETE CASCADE,
      patient_id  uuid NOT NULL REFERENCES patients(id),
      seq         integer NOT NULL CHECK (seq BETWEEN 1 AND 6),
      tool        text NOT NULL,
      permission  permission_level,
      status      text NOT NULL CHECK (status IN ('ran', 'awaiting_approval', 'refused', 'failed')),
      why         text,
      input       jsonb NOT NULL DEFAULT '{}'::jsonb,
      output      jsonb,
      reason      text,
      action_id   uuid REFERENCES actions(id),
      created_at  timestamptz NOT NULL DEFAULT now(),
      UNIQUE (run_id, seq),
      CHECK (status <> 'awaiting_approval' OR action_id IS NOT NULL),
      CHECK (status <> 'refused' OR action_id IS NULL)
    );
    CREATE INDEX ix_agent_steps_run ON agent_steps (run_id, seq);
    ALTER TABLE agent_steps ENABLE ROW LEVEL SECURITY;
    CREATE POLICY p_member ON agent_steps USING (app_can_access_patient(patient_id)) WITH CHECK (app_can_access_patient(patient_id));
    GRANT SELECT, INSERT, UPDATE ON agent_steps TO caresaathi_app, caresaathi_worker;
    GRANT SELECT ON agent_steps TO caresaathi_readonly;
    """)


def downgrade() -> None:
    op.execute("""
    DROP TABLE agent_steps;
    ALTER TABLE agent_runs DROP COLUMN step_count, DROP COLUMN result, DROP COLUMN requested_by, DROP COLUMN goal;
    """)
