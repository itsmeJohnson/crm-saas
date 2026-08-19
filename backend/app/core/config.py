import os
from typing import List, Union
from pydantic import AnyHttpUrl, BeforeValidator, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict
from typing_extensions import Annotated

def parse_cors(v: Union[str, List[str]]) -> List[str]:
    if isinstance(v, str) and not v.startswith("["):
        return [i.strip() for i in v.split(",")]
    elif isinstance(v, (list, str)):
        return v
    raise ValueError(v)

class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_ignore_empty=True,
        extra="ignore"
    )

    API_V1_STR: str = "/api/v1"
    PROJECT_NAME: str = "CRM SaaS"
    
    # Security
    JWT_SECRET_KEY: str = "supersecretkeychangeinproduction1234567890"
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7

    # CORS
    BACKEND_CORS_ORIGINS: Annotated[
        List[str], BeforeValidator(parse_cors)
    ] = ["http://localhost:5173", "http://localhost:3000", "http://localhost"]

    # Public base URL of the frontend/SPA, used to build user-facing links such as
    # password-reset URLs (M5). Set this in production; if unset we fall back to the
    # first CORS origin, then localhost. Building links off CORS[0] alone is fragile
    # because that list can be reordered or contain non-frontend origins.
    FRONTEND_URL: str | None = None
    # When true, public trial signups are provisioned immediately (no manual
    # SuperAdmin approval). SuperAdmin retains full suspend/delete/restore control.
    TRIAL_AUTO_APPROVE: bool = True

    # Database
    POSTGRES_SERVER: str = "db"
    POSTGRES_USER: str = "postgres"
    POSTGRES_PASSWORD: str = "postgres"
    POSTGRES_DB: str = "crm"
    SQLALCHEMY_DATABASE_URI: str | None = None

    @field_validator("SQLALCHEMY_DATABASE_URI", mode="before")
    @classmethod
    def assemble_db_connection(cls, v: str | None, info) -> str:
        if isinstance(v, str) and v:
            return v
        data = info.data
        server = os.environ.get("POSTGRES_SERVER") or data.get("POSTGRES_SERVER", "localhost")
        user = os.environ.get("POSTGRES_USER") or data.get("POSTGRES_USER", "postgres")
        password = os.environ.get("POSTGRES_PASSWORD") or data.get("POSTGRES_PASSWORD", "postgres")
        db = os.environ.get("POSTGRES_DB") or data.get("POSTGRES_DB", "crm")
        return f"postgresql+asyncpg://{user}:{password}@{server}/{db}"

    # ── WP-03A: database role separation ──────────────────────────────────────
    # Optional per-role connection URLs. When provided, the application runtime
    # connects as the unprivileged `crm_runtime` role via RUNTIME_DATABASE_URL,
    # while Alembic migrations connect as the schema-owning `crm_migrator` role
    # via MIGRATOR_DATABASE_URL. When either is absent it falls back to
    # SQLALCHEMY_DATABASE_URI, so existing single-role local development keeps
    # working unchanged. See ops/roles/README.md.
    RUNTIME_DATABASE_URL: str | None = None
    MIGRATOR_DATABASE_URL: str | None = None

    # Local-dev-only schema bootstrap via Base.metadata.create_all. Alembic is the
    # sole schema authority; this escape hatch is hard-blocked in production by
    # validate_production_config so the runtime role never needs DDL privileges.
    RUN_CREATE_ALL: bool = False

    # Redis
    REDIS_HOST: str = "redis"
    REDIS_PORT: int = 6379
    REDIS_URL: str | None = None

    @field_validator("REDIS_URL", mode="before")
    @classmethod
    def assemble_redis_connection(cls, v: str | None, info) -> str:
        if isinstance(v, str) and v:
            return v
        data = info.data
        host = os.environ.get("REDIS_HOST") or data.get("REDIS_HOST", "redis")
        port = os.environ.get("REDIS_PORT") or data.get("REDIS_PORT", 6379)
        return f"redis://{host}:{port}/0"

    # SMTP / Emails
    # Hostinger config: SMTP_HOST=smtp.hostinger.com, SMTP_PORT=465, SMTP_USE_TLS=true
    # For port 465 (SMTP_SSL=True), use smtplib.SMTP_SSL
    # For port 587 (SMTP_TLS=True), use STARTTLS
    SMTP_TLS: bool = True       # STARTTLS on port 587
    SMTP_SSL: bool = False      # Direct SSL on port 465 (Hostinger)
    SMTP_USE_TLS: bool = False  # Alias: if True, sets SMTP_SSL=True and SMTP_PORT=465
    SMTP_PORT: int = 587
    SMTP_HOST: str | None = None
    SMTP_USER: str | None = None
    SMTP_PASSWORD: str | None = None
    SMTP_FROM_EMAIL: str | None = None   # Overrides EMAILS_FROM_EMAIL if set
    SMTP_FROM_NAME: str | None = None    # Overrides EMAILS_FROM_NAME if set
    EMAILS_FROM_EMAIL: str = "contact@support.johnsonsoftwares.com"
    EMAILS_FROM_NAME: str = "Johnson Softwares CRM"

    # MFA
    MFA_ISSUER: str = "Johnson Softwares CRM"

    # DigitalOcean Spaces Storage
    SPACES_KEY: str | None = None
    SPACES_SECRET: str | None = None
    SPACES_ENDPOINT: str | None = None
    SPACES_BUCKET: str | None = None

    # Razorpay Settings
    RAZORPAY_KEY_ID: str | None = None
    RAZORPAY_KEY_SECRET: str | None = None
    RAZORPAY_WEBHOOK_SECRET: str | None = None

    # Cashfree Settings
    CASHFREE_APP_ID: str | None = None
    CASHFREE_SECRET_KEY: str | None = None
    CASHFREE_WEBHOOK_SECRET: str | None = None
    CASHFREE_ENV: str = "sandbox"  # "sandbox" or "production"

    # Profile Mode
    ENVIRONMENT: str = "development"

    @property
    def is_production(self) -> bool:
        return self.ENVIRONMENT.lower() == "production"

    @property
    def is_testing(self) -> bool:
        """True only in the explicit test environment (conftest sets ENVIRONMENT=testing).
        Positive allow-list used to gate the unseeded-Feature-table fallback so it can
        never activate in staging/production, regardless of any other env vars."""
        return self.ENVIRONMENT.lower() == "testing"

    @property
    def runtime_database_uri(self) -> str:
        """DB URL the FastAPI runtime / background jobs connect with.
        Prefers the dedicated crm_runtime URL; falls back to the legacy single URL."""
        return self.RUNTIME_DATABASE_URL or self.SQLALCHEMY_DATABASE_URI

    @property
    def migrator_database_uri(self) -> str:
        """DB URL Alembic connects with. Prefers the schema-owning crm_migrator URL;
        falls back to the legacy single URL for single-role local development."""
        return self.MIGRATOR_DATABASE_URL or self.SQLALCHEMY_DATABASE_URI

    @model_validator(mode="after")
    def validate_production_config(self) -> "Settings":
        if self.ENVIRONMENT == "production":
            if self.JWT_SECRET_KEY == "supersecretkeychangeinproduction1234567890":
                raise ValueError(
                    "Default JWT_SECRET_KEY cannot be used in production environment."
                )
            if self.POSTGRES_PASSWORD == "postgres" or self.POSTGRES_USER == "postgres":
                raise ValueError(
                    "Default PostgreSQL credentials (postgres/postgres) cannot be used in production environment."
                )
            # WP-03A: Alembic is the sole schema authority in production. Never let
            # the application runtime issue DDL via create_all — that would require
            # granting CREATE to crm_runtime and defeats role separation. Fail closed.
            if self.RUN_CREATE_ALL:
                raise ValueError(
                    "RUN_CREATE_ALL must not be enabled in production. Schema is managed "
                    "exclusively by Alembic (run as the crm_migrator role in a dedicated "
                    "migration step). Unset RUN_CREATE_ALL and rely on 'alembic upgrade head'."
                )
        return self

settings = Settings()
