import pytest
from pydantic import ValidationError
from app.core.config import Settings

def test_production_profile_validation_success():
    # Correct configuration should validate successfully
    settings = Settings(
        ENVIRONMENT="production",
        JWT_SECRET_KEY="a_very_secure_custom_secret_key_12345",
        POSTGRES_USER="custom_admin",
        POSTGRES_PASSWORD="securepassword99",
        POSTGRES_SERVER="pg-prod-db",
        POSTGRES_DB="production_crm"
    )
    assert settings.ENVIRONMENT == "production"
    assert settings.JWT_SECRET_KEY == "a_very_secure_custom_secret_key_12345"
    assert settings.POSTGRES_USER == "custom_admin"

def test_production_profile_validation_default_jwt_failure():
    # Should fail if default JWT secret key is used in production profile
    with pytest.raises(ValidationError) as exc:
        Settings(
            ENVIRONMENT="production",
            JWT_SECRET_KEY="supersecretkeychangeinproduction1234567890",
            POSTGRES_USER="custom_admin",
            POSTGRES_PASSWORD="securepassword99",
            POSTGRES_SERVER="pg-prod-db"
        )
    assert "Default JWT_SECRET_KEY cannot be used" in str(exc.value)

def test_production_profile_validation_default_db_creds_failure():
    # Should fail if default db credentials are used in production profile
    with pytest.raises(ValidationError) as exc:
        Settings(
            ENVIRONMENT="production",
            JWT_SECRET_KEY="a_very_secure_custom_secret_key_12345",
            POSTGRES_USER="postgres",
            POSTGRES_PASSWORD="securepassword99",
            POSTGRES_SERVER="pg-prod-db"
        )
    assert "Default PostgreSQL credentials" in str(exc.value)

    with pytest.raises(ValidationError) as exc:
        Settings(
            ENVIRONMENT="production",
            JWT_SECRET_KEY="a_very_secure_custom_secret_key_12345",
            POSTGRES_USER="custom_admin",
            POSTGRES_PASSWORD="postgres",
            POSTGRES_SERVER="pg-prod-db"
        )
    assert "Default PostgreSQL credentials" in str(exc.value)
