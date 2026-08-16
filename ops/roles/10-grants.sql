-- ===========================================================================
-- WP-03A — Grants & default privileges for crm_runtime (idempotent)
-- ===========================================================================
-- Run as a superuser, OR as crm_migrator AFTER ownership transfer (20-*.sql),
-- because ALTER DEFAULT PRIVILEGES FOR ROLE crm_migrator and GRANT ON ALL TABLES
-- must be issued by (or on behalf of) the object owner.
--
--   psql "$SUPERUSER_URL" -f ops/roles/10-grants.sql
--
-- Runtime gets exactly: USAGE on schema public + SELECT/INSERT/UPDATE/DELETE on
-- all current and future application tables. No CREATE/ALTER/DROP/TRUNCATE, no
-- ownership, no role attributes.
-- ===========================================================================
\set ON_ERROR_STOP on

-- Schema usage + CRUD on existing tables.
GRANT USAGE ON SCHEMA public TO crm_runtime;
GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO crm_runtime;

-- Future tables created by crm_migrator automatically grant runtime CRUD, so new
-- migrations need no per-table GRANT.
ALTER DEFAULT PRIVILEGES FOR ROLE crm_migrator IN SCHEMA public
  GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO crm_runtime;

-- Belt-and-suspenders: the runtime role must not be able to create objects.
REVOKE CREATE ON SCHEMA public FROM crm_runtime;
REVOKE CREATE ON SCHEMA public FROM PUBLIC;

-- NOTE on sequences: the application uses Python-generated UUID primary keys and
-- timestamp defaults (backend/app/models/base.py) — there are NO serial/identity
-- sequences the runtime must advance, so NO sequence privileges are granted. If a
-- future migration adds an identity/serial column, grant it explicitly here:
--   GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO crm_runtime;
--   ALTER DEFAULT PRIVILEGES FOR ROLE crm_migrator IN SCHEMA public
--     GRANT USAGE, SELECT ON SEQUENCES TO crm_runtime;
