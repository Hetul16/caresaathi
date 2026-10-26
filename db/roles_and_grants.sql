-- Run once as a superuser, after schema.sql. Replace the placeholder passwords from your secrets store.
--
-- caresaathi_app    : the API. Subject to row-level security. Cannot change or delete the audit log.
-- caresaathi_worker : scheduler, outbox sender and pipelines. Bypasses row-level security because it
--                     works across patients. Keep its credentials out of the web process.
-- caresaathi_readonly: dashboards and the evaluation harness (reads only, RLS applies).

CREATE ROLE caresaathi_app      LOGIN PASSWORD 'change-me-app'      NOSUPERUSER NOBYPASSRLS;
CREATE ROLE caresaathi_worker   LOGIN PASSWORD 'change-me-worker'   NOSUPERUSER BYPASSRLS;
CREATE ROLE caresaathi_readonly LOGIN PASSWORD 'change-me-readonly' NOSUPERUSER NOBYPASSRLS;

-- caresaathi_auth   : login, registration and invitations only. It can touch the users table and nothing else,
--                     which is why the app role cannot read other people's emails or phone numbers.
CREATE ROLE caresaathi_auth     LOGIN PASSWORD 'change-me-auth'     NOSUPERUSER NOBYPASSRLS;
GRANT USAGE ON SCHEMA public TO caresaathi_auth;
GRANT SELECT, INSERT, UPDATE ON users TO caresaathi_auth;
CREATE POLICY p_auth ON users TO caresaathi_auth USING (true) WITH CHECK (true);

GRANT USAGE ON SCHEMA public TO caresaathi_app, caresaathi_worker, caresaathi_readonly;

GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO caresaathi_app, caresaathi_worker;
GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO caresaathi_app, caresaathi_worker;
GRANT SELECT ON ALL TABLES IN SCHEMA public TO caresaathi_readonly;
GRANT EXECUTE ON ALL FUNCTIONS IN SCHEMA public TO caresaathi_app, caresaathi_worker, caresaathi_readonly;

-- The audit log can be read and appended to, never changed (a trigger also blocks it).
REVOKE UPDATE, DELETE, TRUNCATE ON audit_log FROM caresaathi_app, caresaathi_worker;
-- Emergency card access records are append-only too.
REVOKE UPDATE, DELETE, TRUNCATE ON emergency_card_access_log FROM caresaathi_app, caresaathi_worker;
-- The drug reference list is changed by migrations and reviewers only, not by the running app.
REVOKE INSERT, UPDATE, DELETE, TRUNCATE ON drug_families, drug_substances, drug_family_members
  FROM caresaathi_app, caresaathi_worker;
-- Consents are never edited; revocation is the one allowed update, so no blanket DELETE.
REVOKE DELETE, TRUNCATE ON consents FROM caresaathi_app, caresaathi_worker;

ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT SELECT ON TABLES TO caresaathi_readonly;
