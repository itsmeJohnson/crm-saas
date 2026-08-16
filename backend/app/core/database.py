import logging
from typing import AsyncGenerator
from sqlalchemy import text
from sqlalchemy.pool import NullPool
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from app.core.config import settings

logger = logging.getLogger("app.db")

# Create async engine — the FastAPI runtime + background jobs connect through this.
# WP-03A: uses settings.runtime_database_uri (the unprivileged crm_runtime role when
# RUNTIME_DATABASE_URL is configured; otherwise the legacy single URL).
engine = create_async_engine(
    settings.runtime_database_uri,
    echo=False,
    future=True,
    pool_pre_ping=True
)

# Async session maker
async_session_maker = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False
)

async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """Dependency for obtaining database sessions."""
    async with async_session_maker() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


# ── WP-03A: runtime database identity / privilege self-check ──────────────────
async def runtime_role_problems(database_url: str | None = None) -> list[str]:
    """Return a list of forbidden privileges held by the connecting DB role.

    Fail-closed intent: the FastAPI runtime must connect as an unprivileged role
    (crm_runtime) that is NOT a superuser, cannot create roles, cannot bypass RLS,
    and cannot issue DDL (no CREATE on the public schema). This uses catalog lookups
    only — it never creates or drops objects. Non-PostgreSQL URLs (e.g. the SQLite
    test database) return an empty list (nothing to check).
    """
    url = database_url or settings.runtime_database_uri
    if not url.startswith("postgresql"):
        return []
    eng = create_async_engine(url, poolclass=NullPool)
    try:
        async with eng.connect() as conn:
            row = (await conn.execute(text(
                "SELECT rolsuper, rolcreaterole, rolbypassrls "
                "FROM pg_roles WHERE rolname = current_user"
            ))).first()
            if row is None:
                return ["role-not-found-in-pg_roles"]
            rolsuper, rolcreaterole, rolbypassrls = row
            can_create = (await conn.execute(text(
                "SELECT has_schema_privilege(current_user, 'public', 'CREATE')"
            ))).scalar()
            problems: list[str] = []
            if rolsuper:
                problems.append("SUPERUSER")
            if rolcreaterole:
                problems.append("CREATEROLE")
            if rolbypassrls:
                problems.append("BYPASSRLS")
            if can_create:
                problems.append("CREATE-on-schema-public(DDL-capable)")
            return problems
    finally:
        await eng.dispose()


async def verify_runtime_privileges(database_url: str | None = None,
                                    enforce: bool | None = None) -> list[str]:
    """Assert the runtime DB role is unprivileged.

    Behaviour is gated so that documented single-superuser LOCAL development still
    boots: when problems are found it raises (fail-closed) in production, and only
    logs a warning outside production. `enforce` overrides the gate for tests.
    """
    if enforce is None:
        enforce = settings.is_production
    problems = await runtime_role_problems(database_url)
    if problems:
        msg = (
            "WP-03A runtime DB privilege self-check FAILED — the application is "
            "connected with a role holding forbidden privileges: "
            + ", ".join(problems)
            + ". The runtime must connect as the unprivileged crm_runtime role, not "
            "the migrator/owner/superuser. See ops/roles/README.md."
        )
        if enforce:
            raise RuntimeError(msg)
        logger.warning(msg + " (not enforced outside production)")
    return problems
