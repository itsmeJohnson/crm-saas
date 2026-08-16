"""WP-03A — configuration guards & URL split (no database required)."""
import pytest

from app.core.config import Settings

_PROD = dict(
    ENVIRONMENT="production",
    JWT_SECRET_KEY="a-real-non-default-secret-key-0123456789",
    POSTGRES_USER="crm_prod",
    POSTGRES_PASSWORD="strong-prod-password",
    POSTGRES_DB="crm",
)


def _settings(**over):
    data = dict(_PROD)
    data.update(over)
    # init kwargs take highest precedence in pydantic-settings, so CI env vars
    # cannot override these; _env_file=None avoids reading a stray .env.
    return Settings(_env_file=None, **data)


def test_run_create_all_blocked_in_production():
    with pytest.raises(Exception) as exc:
        _settings(RUN_CREATE_ALL=True)
    assert "RUN_CREATE_ALL" in str(exc.value)


def test_run_create_all_allowed_when_false_in_production():
    s = _settings(RUN_CREATE_ALL=False)
    assert s.RUN_CREATE_ALL is False


def test_run_create_all_allowed_in_development():
    s = Settings(
        _env_file=None,
        ENVIRONMENT="development",
        JWT_SECRET_KEY="dev",
        POSTGRES_USER="u",
        POSTGRES_PASSWORD="p",
        RUN_CREATE_ALL=True,
    )
    assert s.RUN_CREATE_ALL is True


def test_runtime_and_migrator_url_fallback():
    s = _settings()
    # Unset split URLs → both fall back to the legacy single URI.
    assert s.RUNTIME_DATABASE_URL is None and s.MIGRATOR_DATABASE_URL is None
    assert s.runtime_database_uri == s.SQLALCHEMY_DATABASE_URI
    assert s.migrator_database_uri == s.SQLALCHEMY_DATABASE_URI


def test_runtime_and_migrator_url_split():
    s = _settings(
        RUNTIME_DATABASE_URL="postgresql+asyncpg://crm_runtime:x@db/crm",
        MIGRATOR_DATABASE_URL="postgresql+asyncpg://crm_migrator:y@db/crm",
    )
    assert s.runtime_database_uri == "postgresql+asyncpg://crm_runtime:x@db/crm"
    assert s.migrator_database_uri == "postgresql+asyncpg://crm_migrator:y@db/crm"
    assert s.runtime_database_uri != s.migrator_database_uri
