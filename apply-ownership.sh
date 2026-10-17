#!/bin/bash
set -e

docker exec -i crm-db psql -U crm_user -d crm_production << 'EOF'
-- Set schema owner
ALTER SCHEMA public OWNER TO crm_migrator;

-- Transfer table ownership to crm_migrator
DO $$
DECLARE
    r RECORD;
BEGIN
    FOR r IN (SELECT tablename FROM pg_tables WHERE schemaname = 'public') LOOP
        EXECUTE 'ALTER TABLE public.' || quote_ident(r.tablename) || ' OWNER TO crm_migrator';
    END LOOP;
    FOR r IN (SELECT sequence_name FROM information_schema.sequences WHERE sequence_schema = 'public') LOOP
        EXECUTE 'ALTER SEQUENCE public.' || quote_ident(r.sequence_name) || ' OWNER TO crm_migrator';
    END LOOP;
END$$;

-- Privileges for crm_migrator
GRANT USAGE, CREATE ON SCHEMA public TO crm_migrator;
GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA public TO crm_migrator;
GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public TO crm_migrator;

-- Privileges for crm_runtime
GRANT USAGE ON SCHEMA public TO crm_runtime;
GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO crm_runtime;
GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO crm_runtime;

-- Default privileges for future tables
ALTER DEFAULT PRIVILEGES FOR ROLE crm_migrator IN SCHEMA public
  GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO crm_runtime;
ALTER DEFAULT PRIVILEGES FOR ROLE crm_migrator IN SCHEMA public
  GRANT USAGE, SELECT ON SEQUENCES TO crm_runtime;

-- Block runtime role from DDL
REVOKE CREATE ON SCHEMA public FROM crm_runtime;
REVOKE CREATE ON SCHEMA public FROM PUBLIC;

SELECT count(*) as total_tables FROM pg_tables WHERE schemaname = 'public';
SELECT count(*) as migrator_owned FROM pg_tables WHERE schemaname = 'public' AND tableowner = 'crm_migrator';
SELECT count(*) as runtime_owned FROM pg_tables WHERE schemaname = 'public' AND tableowner = 'crm_runtime';
EOF
