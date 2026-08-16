# WP-03A — Database Role Separation (Runbook)

Separates three PostgreSQL roles as a prerequisite for future RLS. **WP-03A introduces no RLS.**

| Role | Login | Attributes | Purpose |
|---|---|---|---|
| `crm_migrator` | LOGIN | NOSUPERUSER, NOCREATEROLE, NOBYPASSRLS, **owns schema objects** | Alembic migrations / DDL |
| `crm_runtime` | LOGIN | NOSUPERUSER, NOCREATEROLE, NOBYPASSRLS, **owns nothing** | FastAPI + background jobs; CRUD only |
| `crm_platform` | **NOLOGIN** | NOSUPERUSER, NOCREATEROLE, **BYPASSRLS (reserved)** | Reserved placeholder for the future SuperAdmin/RLS cutover. **No password, no DATABASE_URL, no application wiring in WP-03A.** |

`crm_runtime` is **not** a member of `crm_migrator` or `crm_platform` (blocks `SET ROLE` escalation). `crm_platform` is inert — nothing connects as it.

---

## ⚠️ Prerequisite — disable `RUN_CREATE_ALL` in production

The application must not issue DDL. Ensure `RUN_CREATE_ALL` is **unset or `false`** in the production `.env`. With `ENVIRONMENT=production`, `RUN_CREATE_ALL=true` now **fails startup** (`Settings.validate_production_config`). Alembic is the sole schema authority.

> If you cannot verify the live env yet, treat "disable `RUN_CREATE_ALL` in prod" as an **external prerequisite** to complete before restricting runtime privileges. WP-03A does not modify the live environment.

---

## Connection URLs

The app reads two optional URLs (see `backend/app/core/config.py`):

- `RUNTIME_DATABASE_URL` → FastAPI runtime engine (`crm_runtime`)
- `MIGRATOR_DATABASE_URL` → Alembic (`crm_migrator`)

Both **fall back to `SQLALCHEMY_DATABASE_URI`** (built from `POSTGRES_*`) when unset, so single-role local dev is unchanged. Format:
`postgresql+asyncpg://crm_runtime:<pw>@<host>/<db>`

---

## Provisioning order (staging first, then production)

1. **Back up the database** (managed-DB snapshot + the existing `ops/backup.sh`).
2. **Create roles** (superuser, out-of-band — never via Alembic):
   ```bash
   psql "$SUPERUSER_URL" \
     -v crm_migrator_password="<secret>" \
     -v crm_runtime_password="<secret>" \
     -f ops/roles/00-create-roles.sql
   ```
3. **Confirm the current owner** of existing objects:
   ```sql
   SELECT tableowner, count(*) FROM pg_tables WHERE schemaname='public' GROUP BY 1;
   ```
4. **Transfer ownership** to `crm_migrator` (maintenance window, after backup):
   ```bash
   psql "$SUPERUSER_URL" -v current_owner="<current_owner>" -f ops/roles/20-transfer-ownership.sql
   ```
5. **Apply grants / default privileges**:
   ```bash
   psql "$SUPERUSER_URL" -f ops/roles/10-grants.sql
   ```
6. **Set split URLs** in `.env` (`RUNTIME_DATABASE_URL`, `MIGRATOR_DATABASE_URL`) and redeploy.
7. **Verify** (see below).

---

## Deployment model

Migrations no longer run inside the app container's startup. `backend/entrypoint.sh` starts uvicorn only.

- **Compose:** a one-shot `migrate` service (`docker-compose.prod.yml`) runs `alembic upgrade head` as `crm_migrator`; `backend` `depends_on` it with `condition: service_completed_successfully` and runs as `crm_runtime`.
- **`ops/deploy.sh`:** runs the migration step as `crm_migrator` before starting/refreshing the app (see that script).

---

## Runtime self-check

On startup the app calls `verify_runtime_privileges()` (`backend/app/core/database.py`): it reads `pg_roles`/`has_schema_privilege` for the connected role and asserts **no** SUPERUSER / CREATEROLE / BYPASSRLS / CREATE-on-`public`. It **fails closed in production** and **warns only outside production** (so a single-superuser local setup still boots). Catalog-only — creates no objects. Skipped for non-PostgreSQL (SQLite tests).

---

## Local development

Two supported modes:
- **Simple (default):** keep the single `postgres` superuser — nothing changes; the self-check warns (does not block) outside production.
- **Role-mode (CI + parity):** provision the three roles and set `RUNTIME_DATABASE_URL` / `MIGRATOR_DATABASE_URL`. This is what the PostgreSQL CI lane exercises.

---

## Verification

```sql
-- runtime is unprivileged
SELECT rolsuper, rolcreaterole, rolbypassrls FROM pg_roles WHERE rolname='crm_runtime';  -- f f f
-- runtime owns nothing
SELECT count(*) FROM pg_tables WHERE schemaname='public' AND tableowner='crm_runtime';    -- 0
-- migrator owns the tables
SELECT count(*) FROM pg_tables WHERE schemaname='public' AND tableowner='crm_migrator';   -- all
-- platform is inert
SELECT rolcanlogin, rolbypassrls FROM pg_roles WHERE rolname='crm_platform';              -- f t
```
Automated equivalents live in `backend/app/tests/test_wp03a_role_separation.py` (PostgreSQL lane).

---

## Rollback

Role separation is credentials + grants + ownership — **no schema/data change**, fully reversible:

1. Repoint `RUNTIME_DATABASE_URL` / `MIGRATOR_DATABASE_URL` back to the original single-role URL (or unset them) and redeploy — the app is immediately back to prior behaviour.
2. If ownership was transferred: `REASSIGN OWNED BY crm_migrator TO <original_owner>;`
3. To restore migrate-on-startup, revert `entrypoint.sh` and the compose `migrate` service.

Take a backup before step 4/ownership work. Rehearse in staging before production.
