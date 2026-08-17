"""WP-03A — PostgreSQL role-separation / privilege test lane.

Requires a REAL PostgreSQL reachable as a superuser via the env var
WP03A_TEST_DB_ADMIN_URL (plain libpq/asyncpg DSN, e.g.
    postgresql://postgres:postgres@localhost:5432/postgres
). The whole module skips cleanly when that is unset, so the default SQLite unit
suite is unaffected. CI provisions a postgres service and sets the var.

These tests exercise the model in ops/roles/*.sql and the runtime self-check in
app.core.database, proving DB-level isolation — not merely application filtering.
"""
import os
import urllib.parse

import pytest

asyncpg = pytest.importorskip("asyncpg")

ADMIN_URL = os.getenv("WP03A_TEST_DB_ADMIN_URL")

pytestmark = [
    pytest.mark.skipif(not ADMIN_URL, reason="WP03A_TEST_DB_ADMIN_URL not set (no PostgreSQL lane)"),
    pytest.mark.asyncio,
]

MIG_PW = "wp03a_mig_pw"
RUN_PW = "wp03a_run_pw"
SAMPLE = "wp03a_sample"


def _role_url(admin_url: str, user: str, password: str) -> str:
    """Rewrite the userinfo of the admin DSN for a specific role."""
    p = urllib.parse.urlparse(admin_url)
    host = p.hostname or "localhost"
    port = f":{p.port}" if p.port else ""
    netloc = f"{user}:{urllib.parse.quote(password)}@{host}{port}"
    return urllib.parse.urlunparse(p._replace(netloc=netloc))


def _sqlalchemy_url(dsn: str) -> str:
    return dsn.replace("postgresql://", "postgresql+asyncpg://", 1) if dsn.startswith("postgresql://") else dsn


@pytest.fixture
async def provisioned():
    """Provision the three roles + a migrator-owned sample table with runtime grants,
    mirroring ops/roles/00 + 10. Idempotent (cleans up any prior run). Function-scoped
    to match pytest-asyncio's function-scoped loop (see pytest.ini)."""
    admin = await asyncpg.connect(ADMIN_URL)
    try:
        # Reclaim schema ownership first so a prior failed run can't leave crm_migrator
        # owning `public` (which DROP OWNED would then destroy).
        await admin.execute("ALTER SCHEMA public OWNER TO CURRENT_USER")
        # Clean slate (tolerate missing roles/objects).
        await admin.execute(
            """
            DO $$
            BEGIN
              IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname='crm_runtime') THEN
                EXECUTE 'DROP OWNED BY crm_runtime CASCADE'; EXECUTE 'DROP ROLE crm_runtime';
              END IF;
              IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname='crm_migrator') THEN
                EXECUTE 'DROP OWNED BY crm_migrator CASCADE'; EXECUTE 'DROP ROLE crm_migrator';
              END IF;
              IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname='crm_platform') THEN
                EXECUTE 'DROP OWNED BY crm_platform CASCADE'; EXECUTE 'DROP ROLE crm_platform';
              END IF;
            END$$;
            """
        )
        await admin.execute(f"CREATE ROLE crm_migrator LOGIN PASSWORD '{MIG_PW}' NOSUPERUSER NOCREATEROLE NOCREATEDB NOBYPASSRLS")
        await admin.execute(f"CREATE ROLE crm_runtime LOGIN PASSWORD '{RUN_PW}' NOSUPERUSER NOCREATEROLE NOCREATEDB NOBYPASSRLS")
        await admin.execute("CREATE ROLE crm_platform NOLOGIN NOSUPERUSER NOCREATEROLE NOCREATEDB BYPASSRLS")
        # migrator owns the schema (mirrors 20-transfer-ownership.sql) so it can DDL.
        await admin.execute("ALTER SCHEMA public OWNER TO crm_migrator")
        # migrator-owned sample table
        await admin.execute(f"DROP TABLE IF EXISTS {SAMPLE}")
        await admin.execute(f"CREATE TABLE {SAMPLE} (id int PRIMARY KEY, val text)")
        await admin.execute(f"ALTER TABLE {SAMPLE} OWNER TO crm_migrator")
        await admin.execute(f"INSERT INTO {SAMPLE} VALUES (1, 'seed')")
        # runtime grants (mirror 10-grants.sql)
        await admin.execute("GRANT USAGE ON SCHEMA public TO crm_runtime")
        await admin.execute("GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO crm_runtime")
        await admin.execute("REVOKE CREATE ON SCHEMA public FROM crm_runtime")
        await admin.execute("REVOKE CREATE ON SCHEMA public FROM PUBLIC")
        # anti-escalation: not members
        await admin.execute("REVOKE crm_migrator FROM crm_runtime")
        await admin.execute("REVOKE crm_platform FROM crm_runtime")
    finally:
        await admin.close()

    yield {
        "runtime_url": _role_url(ADMIN_URL, "crm_runtime", RUN_PW),
        "migrator_url": _role_url(ADMIN_URL, "crm_migrator", MIG_PW),
    }

    admin = await asyncpg.connect(ADMIN_URL)
    try:
        # Reclaim schema before dropping crm_migrator so DROP OWNED can't drop `public`.
        await admin.execute("ALTER SCHEMA public OWNER TO CURRENT_USER")
        await admin.execute(
            """
            DO $$
            BEGIN
              IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname='crm_runtime') THEN EXECUTE 'DROP OWNED BY crm_runtime CASCADE'; EXECUTE 'DROP ROLE crm_runtime'; END IF;
              IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname='crm_migrator') THEN EXECUTE 'DROP OWNED BY crm_migrator CASCADE'; EXECUTE 'DROP ROLE crm_migrator'; END IF;
              IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname='crm_platform') THEN EXECUTE 'DROP OWNED BY crm_platform CASCADE'; EXECUTE 'DROP ROLE crm_platform'; END IF;
            END$$;
            """
        )
    finally:
        await admin.close()


# ── Runtime role attributes ────────────────────────────────────────────────
async def test_runtime_is_unprivileged(provisioned):
    conn = await asyncpg.connect(provisioned["runtime_url"])
    try:
        row = await conn.fetchrow(
            "SELECT rolsuper, rolcreaterole, rolbypassrls FROM pg_roles WHERE rolname=current_user"
        )
        assert row["rolsuper"] is False
        assert row["rolcreaterole"] is False
        assert row["rolbypassrls"] is False
    finally:
        await conn.close()


async def test_runtime_owns_no_table(provisioned):
    conn = await asyncpg.connect(provisioned["runtime_url"])
    try:
        n = await conn.fetchval(
            "SELECT count(*) FROM pg_tables WHERE schemaname='public' AND tableowner='crm_runtime'"
        )
        assert n == 0
        owner = await conn.fetchval(
            f"SELECT tableowner FROM pg_tables WHERE tablename='{SAMPLE}'"
        )
        assert owner == "crm_migrator"
    finally:
        await conn.close()


# ── Runtime CRUD works ──────────────────────────────────────────────────────
async def test_runtime_crud(provisioned):
    conn = await asyncpg.connect(provisioned["runtime_url"])
    try:
        await conn.execute(f"INSERT INTO {SAMPLE} VALUES (2, 'a')")
        assert await conn.fetchval(f"SELECT val FROM {SAMPLE} WHERE id=2") == "a"
        await conn.execute(f"UPDATE {SAMPLE} SET val='b' WHERE id=2")
        assert await conn.fetchval(f"SELECT val FROM {SAMPLE} WHERE id=2") == "b"
        await conn.execute(f"DELETE FROM {SAMPLE} WHERE id=2")
        assert await conn.fetchval(f"SELECT count(*) FROM {SAMPLE} WHERE id=2") == 0
    finally:
        await conn.close()


# ── Runtime DDL denied ──────────────────────────────────────────────────────
@pytest.mark.parametrize("ddl", [
    "CREATE TABLE wp03a_nope (id int)",
    f"ALTER TABLE {SAMPLE} ADD COLUMN nope int",
    f"DROP TABLE {SAMPLE}",
])
async def test_runtime_cannot_ddl(provisioned, ddl):
    conn = await asyncpg.connect(provisioned["runtime_url"])
    try:
        with pytest.raises(asyncpg.exceptions.InsufficientPrivilegeError):
            await conn.execute(ddl)
    finally:
        await conn.close()


# ── Runtime cannot escalate via SET ROLE ────────────────────────────────────
@pytest.mark.parametrize("target", ["crm_migrator", "crm_platform"])
async def test_runtime_cannot_set_role(provisioned, target):
    conn = await asyncpg.connect(provisioned["runtime_url"])
    try:
        with pytest.raises(asyncpg.exceptions.InsufficientPrivilegeError):
            await conn.execute(f"SET ROLE {target}")
    finally:
        await conn.close()


async def test_runtime_not_member_of_privileged_roles(provisioned):
    conn = await asyncpg.connect(provisioned["runtime_url"])
    try:
        assert await conn.fetchval("SELECT pg_has_role(current_user, 'crm_migrator', 'MEMBER')") is False
        assert await conn.fetchval("SELECT pg_has_role(current_user, 'crm_platform', 'MEMBER')") is False
    finally:
        await conn.close()


# ── Migrator can own + DDL ──────────────────────────────────────────────────
async def test_migrator_owns_and_can_ddl(provisioned):
    conn = await asyncpg.connect(provisioned["migrator_url"])
    try:
        await conn.execute("CREATE TABLE wp03a_mig_tmp (id int)")
        owner = await conn.fetchval("SELECT tableowner FROM pg_tables WHERE tablename='wp03a_mig_tmp'")
        assert owner == "crm_migrator"
        await conn.execute("DROP TABLE wp03a_mig_tmp")
        row = await conn.fetchrow("SELECT rolsuper, rolcreaterole FROM pg_roles WHERE rolname=current_user")
        assert row["rolsuper"] is False and row["rolcreaterole"] is False
    finally:
        await conn.close()


# ── Platform is an inert reserved placeholder ───────────────────────────────
async def test_platform_role_reserved(provisioned):
    conn = await asyncpg.connect(provisioned["runtime_url"])
    try:
        row = await conn.fetchrow("SELECT rolcanlogin, rolbypassrls FROM pg_roles WHERE rolname='crm_platform'")
        assert row["rolcanlogin"] is False   # NOLOGIN — no usable credential
        assert row["rolbypassrls"] is True   # reserved for future RLS cutover
    finally:
        await conn.close()


# ── Runtime self-check (app.core.database.verify_runtime_privileges) ─────────
async def test_self_check_passes_for_runtime(provisioned):
    from app.core.database import runtime_role_problems
    problems = await runtime_role_problems(_sqlalchemy_url(provisioned["runtime_url"]))
    assert problems == [], f"runtime should be clean, got {problems}"


async def test_self_check_flags_and_raises_for_superuser(provisioned):
    from app.core.database import runtime_role_problems, verify_runtime_privileges
    problems = await runtime_role_problems(_sqlalchemy_url(ADMIN_URL))
    assert "SUPERUSER" in problems
    # Enforced (production-style) → must raise for a privileged role.
    with pytest.raises(RuntimeError):
        await verify_runtime_privileges(_sqlalchemy_url(ADMIN_URL), enforce=True)
