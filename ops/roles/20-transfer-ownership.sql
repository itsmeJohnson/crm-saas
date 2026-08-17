-- ===========================================================================
-- WP-03A — Transfer ownership of existing objects to crm_migrator
-- ===========================================================================
-- ⚠️  EXPLICIT OPERATIONAL STEP — never run automatically (not from app startup,
--     not from Alembic, not from Docker entrypoints). Run in a maintenance window
--     AFTER a verified database backup. See ops/roles/README.md.
--
-- Provide :current_owner = the role that currently owns the schema objects (the
-- bootstrap POSTGRES_USER on this database — e.g. "crm_prod"). Do NOT invent it;
-- confirm it first (README §Verify current owner).
--
--   psql "$SUPERUSER_URL" -v current_owner="crm_prod" -f ops/roles/20-transfer-ownership.sql
--
-- After this, run 10-grants.sql so crm_runtime retains CRUD on the reassigned tables.
-- ===========================================================================
\set ON_ERROR_STOP on

BEGIN;

-- Schema itself.
ALTER SCHEMA public OWNER TO crm_migrator;

-- All tables / sequences / functions / views currently owned by :current_owner.
REASSIGN OWNED BY :"current_owner" TO crm_migrator;

COMMIT;
