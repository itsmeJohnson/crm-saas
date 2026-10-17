DO $$
BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'crm_migrator') THEN
    CREATE ROLE crm_migrator LOGIN NOSUPERUSER NOCREATEROLE NOCREATEDB NOBYPASSRLS PASSWORD '94185252cba9945d989eb2a88c535b52';
  ELSE
    ALTER ROLE crm_migrator WITH PASSWORD '94185252cba9945d989eb2a88c535b52';
  END IF;
  IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'crm_runtime') THEN
    CREATE ROLE crm_runtime LOGIN NOSUPERUSER NOCREATEROLE NOCREATEDB NOBYPASSRLS PASSWORD '26f4e5f095e528e0773ec2799d3b0ceb';
  ELSE
    ALTER ROLE crm_runtime WITH PASSWORD '26f4e5f095e528e0773ec2799d3b0ceb';
  END IF;
  IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'crm_platform') THEN
    CREATE ROLE crm_platform NOLOGIN NOSUPERUSER NOCREATEROLE NOCREATEDB BYPASSRLS;
  END IF;
END$$;

ALTER SCHEMA public OWNER TO crm_migrator;
GRANT USAGE, CREATE ON SCHEMA public TO crm_migrator;

GRANT USAGE ON SCHEMA public TO crm_runtime;
GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO crm_runtime;

ALTER DEFAULT PRIVILEGES FOR ROLE crm_migrator IN SCHEMA public
  GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO crm_runtime;

REVOKE CREATE ON SCHEMA public FROM crm_runtime;
REVOKE CREATE ON SCHEMA public FROM PUBLIC;

REVOKE crm_migrator FROM crm_runtime;
REVOKE crm_platform FROM crm_runtime;

SELECT rolname, rolsuper, rolcreaterole, rolbypassrls, rolcanlogin FROM pg_roles WHERE rolname IN ('crm_migrator', 'crm_runtime', 'crm_platform');
