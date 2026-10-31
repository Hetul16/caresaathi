"""Daily check-ins for remote care (C7, D-58): which doses were marked taken, and how the patient says they feel.

Revision ID: 0012
Revises: 0011

dose_logs: one row per medicine, slot and day, saying taken or not taken, and who marked it. A person marks it; nothing is inferred.
wellbeing_checkins: one row per patient per day with the patient's own pain number (0 to 10) and/or a short note. CareSaathi shows these
entries and counts them. It never labels a number high, low, better or worse, and never reads a pattern into them.
"""
from alembic import op

revision = "0012"
down_revision = "0011"
branch_labels = None
depends_on = None

_RLS = """
ALTER TABLE {t} ENABLE ROW LEVEL SECURITY;
CREATE POLICY p_member ON {t} USING (app_can_access_patient(patient_id)) WITH CHECK (app_can_access_patient(patient_id));
GRANT SELECT, INSERT, UPDATE ON {t} TO caresaathi_app, caresaathi_worker;
GRANT SELECT ON {t} TO caresaathi_readonly;
"""


def upgrade() -> None:
    op.execute("""
    CREATE TABLE dose_logs (
      id           uuid PRIMARY KEY DEFAULT gen_random_uuid(),
      patient_id   uuid NOT NULL REFERENCES patients(id),
      item_key     uuid NOT NULL,
      slot         text NOT NULL CHECK (slot IN ('morning', 'noon', 'evening', 'night')),
      for_date     date NOT NULL,
      status       text NOT NULL CHECK (status IN ('taken', 'not_taken')),
      recorded_by  uuid NOT NULL REFERENCES users(id),
      recorded_at  timestamptz NOT NULL DEFAULT now(),
      UNIQUE (patient_id, item_key, slot, for_date)
    );
    CREATE INDEX ix_dose_logs_day ON dose_logs (patient_id, for_date);
    """ + _RLS.format(t="dose_logs"))
    op.execute("""
    CREATE TABLE wellbeing_checkins (
      id           uuid PRIMARY KEY DEFAULT gen_random_uuid(),
      patient_id   uuid NOT NULL REFERENCES patients(id),
      for_date     date NOT NULL,
      pain         smallint CHECK (pain BETWEEN 0 AND 10),
      note         text CHECK (note IS NULL OR length(note) <= 300),
      recorded_by  uuid NOT NULL REFERENCES users(id),
      recorded_at  timestamptz NOT NULL DEFAULT now(),
      CHECK (pain IS NOT NULL OR length(btrim(coalesce(note, ''))) > 0),
      UNIQUE (patient_id, for_date)
    );
    """ + _RLS.format(t="wellbeing_checkins"))


def downgrade() -> None:
    op.execute("DROP TABLE wellbeing_checkins; DROP TABLE dose_logs;")
