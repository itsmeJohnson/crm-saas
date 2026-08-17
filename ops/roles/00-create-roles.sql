-- ===========================================================================
-- WP-03A — PostgreSQL role provisioning (idempotent)
-- ===========================================================================
-- Roles are CLUSTER-LEVEL objects and are provisioned OUT-OF-BAND by a superuser
-- / DBA. They are NOT created by the application or by Alembic migrations.
--
-- Run once, passing secrets at runtime (never commit real passwords):
--
--   psql "$SUPERUSER_URL" \
--     -v crm_migrator_password="<STRONG_SECRET>" \
--     -v crm_runtime_password="<STRONG_SECRET>" \
--     -f ops/roles/00-create-roles.sql
--
-- Role model:
--   crm_migrator  LOGIN  — owns schema objects, runs Alembic/DDL. No SUPERUSER,
--                          no CREATEROLE, no BYPASSRLS (BYPASSRLS is added later,
--                          only when PostgreSQL RLS is introduced in WP-03C+).
--   crm_runtime   LOGIN  — FastAPI + background jobs. CRUD only. Owns nothing.
--                          No SUPERUSER, no CREATEROLE, no BYPASSRLS, no DDL.
--   crm_platform  NOLOGIN— RESERVED placeholder for the future SuperAdmin/RLS
--                          cutover. BYPASSRLS reserved; no password, no wiring.
-- ===========================================================================
\set ON_ERROR_STOP on

-- crm_migrator ---------------------------------------------------------------
DO $$
BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'crm_migrator') THEN
    CREATE ROLE crm_migrator LOGIN NOSUPERUSER NOCREATEROLE NOCREATEDB NOBYPASSRLS;
  END IF;
END$$;
ALTER ROLE crm_migrator NOSUPERUSER NOCREATEROLE NOCREATEDB NOBYPASSRLS;
ALTER ROLE crm_migrator WITH PASSWORD :'crm_migrator_password';

-- crm_runtime ----------------------------------------------------------------
DO $$
BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'crm_runtime') THEN
    CREATE ROLE crm_runtime LOGIN NOSUPERUSER NOCREATEROLE NOCREATEDB NOBYPASSRLS;
  END IF;
END$$;
ALTER ROLE crm_runtime NOSUPERUSER NOCREATEROLE NOCREATEDB NOBYPASSRLS;
ALTER ROLE crm_runtime WITH PASSWORD :'crm_runtime_password';

-- crm_platform (RESERVED placeholder — NOLOGIN, no usable credential) ---------
DO $$
BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'crm_platform') THEN
    CREATE ROLE crm_platform NOLOGIN NOSUPERUSER NOCREATEROLE NOCREATEDB BYPASSRLS;
  END IF;
END$$;
ALTER ROLE crm_platform NOLOGIN NOSUPERUSER NOCREATEROLE NOCREATEDB BYPASSRLS;

-- Anti-escalation: runtime must NOT be able to SET ROLE to migrator/platform.
-- (No-op with a notice if the membership never existed.)
REVOKE crm_migrator FROM crm_runtime;
REVOKE crm_platform  FROM crm_runtime;
