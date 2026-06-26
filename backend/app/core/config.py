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
        server = data.get("POSTGRES_SERVER", "db")
        user = data.get("POSTGRES_USER", "postgres")
        password = data.get("POSTGRES_PASSWORD", "postgres")
        db = data.get("POSTGRES_DB", "crm")
        return f"postgresql+asyncpg://{user}:{password}@{server}/{db}"

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
        host = data.get("REDIS_HOST", "redis")
        port = data.get("REDIS_PORT", 6379)
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

    # Profile Mode
    ENVIRONMENT: str = "development"

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
        return self

settings = Settings()
