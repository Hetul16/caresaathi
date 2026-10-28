"""Doctor link (C1, D-46): an expiring, revocable page for one doctor, with a message thread.

Revision ID: 0008
Revises: 0007

- doctor_links: random token stored as a SHA-256 hash only; always has an expiry; can be revoked.
- doctor_messages: the thread. A message TO the doctor must come from an approved action (a CHECK enforces it), so the
  model or the page cannot put words in front of a doctor without a named approver. A message FROM the doctor is stored verbatim.
- The public page never gets table access. Three SECURITY DEFINER functions validate the token, log every attempt, and
  read or write the thread: app_resolve_doctor_link, app_doctor_thread, app_doctor_reply.
"""
from alembic import op

revision = "0008"
down_revision = "0007"
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
    CREATE TABLE doctor_links (
      id            uuid PRIMARY KEY DEFAULT gen_random_uuid(),
      patient_id    uuid NOT NULL REFERENCES patients(id),
      token_hash    bytea NOT NULL UNIQUE,
      token_hint    text NOT NULL,
      doctor_name   text NOT NULL CHECK (length(btrim(doctor_name)) BETWEEN 1 AND 120),
      created_by    uuid NOT NULL REFERENCES users(id),
      expires_at    timestamptz NOT NULL,
      revoked_at    timestamptz,
      revoked_by    uuid REFERENCES users(id),
      created_at    timestamptz NOT NULL DEFAULT now(),
      CHECK (expires_at > created_at),
      CHECK ((revoked_at IS NULL) = (revoked_by IS NULL))
    );
    CREATE INDEX ix_doctor_links_patient ON doctor_links (patient_id, created_at DESC);
    """ + _RLS.format(t="doctor_links"))

    op.execute("""
    CREATE TABLE doctor_messages (
      id          uuid PRIMARY KEY DEFAULT gen_random_uuid(),
      patient_id  uuid NOT NULL REFERENCES patients(id),
      link_id     uuid NOT NULL REFERENCES doctor_links(id),
      direction   text NOT NULL CHECK (direction IN ('to_doctor', 'from_doctor')),
      body        text NOT NULL CHECK (length(btrim(body)) BETWEEN 1 AND 4000),
      action_id   uuid REFERENCES actions(id),
      created_at  timestamptz NOT NULL DEFAULT now(),
      -- Words reach the doctor only through an approved action.
      CHECK (direction <> 'to_doctor' OR action_id IS NOT NULL),
      CHECK (direction <> 'from_doctor' OR action_id IS NULL)
    );
    CREATE INDEX ix_doctor_messages_link ON doctor_messages (link_id, created_at);
    CREATE UNIQUE INDEX uq_doctor_messages_action ON doctor_messages (action_id) WHERE action_id IS NOT NULL;
    """ + _RLS.format(t="doctor_messages"))

    op.execute("""
    CREATE TABLE doctor_link_access_log (
      id          bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
      patient_id  uuid REFERENCES patients(id),
      link_id     uuid REFERENCES doctor_links(id),
      outcome     text NOT NULL CHECK (outcome IN ('ok', 'not_found', 'revoked', 'expired', 'reply_stored', 'reply_refused')),
      ip_hash     bytea,
      user_agent  text,
      at          timestamptz NOT NULL DEFAULT now()
    );
    ALTER TABLE doctor_link_access_log ENABLE ROW LEVEL SECURITY;
    CREATE POLICY p_member ON doctor_link_access_log FOR SELECT USING (patient_id IS NOT NULL AND app_can_access_patient(patient_id));
    GRANT SELECT ON doctor_link_access_log TO caresaathi_app, caresaathi_worker, caresaathi_readonly;
    """)

    op.execute("""
    CREATE FUNCTION app_resolve_doctor_link(p_hash bytea, p_ip bytea, p_ua text)
    RETURNS TABLE (r_link_id uuid, r_patient_id uuid, r_doctor_name text, r_expires_at timestamptz, r_outcome text)
    LANGUAGE plpgsql SECURITY DEFINER SET search_path = public AS $$
    DECLARE l doctor_links%ROWTYPE; o text;
    BEGIN
      SELECT * INTO l FROM doctor_links WHERE token_hash = p_hash;
      IF NOT FOUND THEN o := 'not_found';
      ELSIF l.revoked_at IS NOT NULL THEN o := 'revoked';
      ELSIF l.expires_at <= now() THEN o := 'expired';
      ELSE o := 'ok';
      END IF;
      INSERT INTO doctor_link_access_log (patient_id, link_id, outcome, ip_hash, user_agent)
      VALUES (l.patient_id, l.id, o, p_ip, left(p_ua, 200));
      IF o = 'ok' THEN
        RETURN QUERY SELECT l.id, l.patient_id, l.doctor_name, l.expires_at, o;
      ELSE
        RETURN QUERY SELECT NULL::uuid, NULL::uuid, NULL::text, NULL::timestamptz, o;
      END IF;
    END $$;

    CREATE FUNCTION app_doctor_thread(p_hash bytea)
    RETURNS TABLE (r_id uuid, r_direction text, r_body text, r_at timestamptz)
    LANGUAGE sql SECURITY DEFINER SET search_path = public AS $$
      SELECT m.id, m.direction, m.body, m.created_at
        FROM doctor_messages m JOIN doctor_links l ON l.id = m.link_id
       WHERE l.token_hash = p_hash AND l.revoked_at IS NULL AND l.expires_at > now()
       ORDER BY m.created_at
    $$;

    CREATE FUNCTION app_doctor_reply(p_hash bytea, p_body text, p_ip bytea, p_ua text)
    RETURNS text
    LANGUAGE plpgsql SECURITY DEFINER SET search_path = public AS $$
    DECLARE l doctor_links%ROWTYPE;
    BEGIN
      SELECT * INTO l FROM doctor_links WHERE token_hash = p_hash AND revoked_at IS NULL AND expires_at > now();
      IF NOT FOUND THEN
        INSERT INTO doctor_link_access_log (outcome, ip_hash, user_agent) VALUES ('reply_refused', p_ip, left(p_ua, 200));
        RETURN 'unavailable';
      END IF;
      -- A doctor can only reply while there is a question to answer, and at most 20 times per link.
      IF NOT EXISTS (SELECT 1 FROM doctor_messages WHERE link_id = l.id AND direction = 'to_doctor')
         OR (SELECT count(*) FROM doctor_messages WHERE link_id = l.id AND direction = 'from_doctor') >= 20
         OR length(btrim(coalesce(p_body, ''))) NOT BETWEEN 1 AND 4000 THEN
        INSERT INTO doctor_link_access_log (patient_id, link_id, outcome, ip_hash, user_agent) VALUES (l.patient_id, l.id, 'reply_refused', p_ip, left(p_ua, 200));
        RETURN 'refused';
      END IF;
      INSERT INTO doctor_messages (patient_id, link_id, direction, body) VALUES (l.patient_id, l.id, 'from_doctor', btrim(p_body));
      INSERT INTO doctor_link_access_log (patient_id, link_id, outcome, ip_hash, user_agent) VALUES (l.patient_id, l.id, 'reply_stored', p_ip, left(p_ua, 200));
      RETURN 'stored';
    END $$;

    REVOKE ALL ON FUNCTION app_resolve_doctor_link(bytea, bytea, text), app_doctor_thread(bytea), app_doctor_reply(bytea, text, bytea, text) FROM PUBLIC;
    GRANT EXECUTE ON FUNCTION app_resolve_doctor_link(bytea, bytea, text), app_doctor_thread(bytea), app_doctor_reply(bytea, text, bytea, text)
      TO caresaathi_app, caresaathi_worker;
    """)


def downgrade() -> None:
    op.execute("""
    DROP FUNCTION app_doctor_reply(bytea, text, bytea, text);
    DROP FUNCTION app_doctor_thread(bytea);
    DROP FUNCTION app_resolve_doctor_link(bytea, bytea, text);
    DROP TABLE doctor_link_access_log;
    DROP TABLE doctor_messages;
    DROP TABLE doctor_links;
    """)
