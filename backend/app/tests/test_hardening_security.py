import pytest
from httpx import AsyncClient
from unittest.mock import patch, MagicMock
from datetime import datetime, timedelta, timezone
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.user import User
from app.core.security import hash_token

@pytest.mark.asyncio
async def test_password_reset_hardening_flow(client: AsyncClient, db: AsyncSession):
    # 1. Register a tenant
    reg_payload = {
        "company_name": "Hardening Corp",
        "slug": "hardening",
        "admin_email": "admin@hardening.com",
        "admin_password": "oldsupersecurepassword123",
        "first_name": "Security",
        "last_name": "Architect"
    }
    response = await client.post("/api/v1/auth/register", json=reg_payload)
    assert response.status_code == 200

    # 2. Trigger forgot password with SMTP send_email mocked to inspect the generated link
    forgot_payload = {
        "email": "admin@hardening.com"
    }

    with patch("app.services.email_service.send_email") as mock_send_email:
        response = await client.post("/api/v1/auth/forgot-password", json=forgot_payload)
        assert response.status_code == 200
        
        # Verify the token is NOT returned in the API response
        res_json = response.json()
        assert "token" not in res_json
        assert "Reset code" not in res_json.get("detail", "")
        
        # Verify that mock_send_email was called once
        mock_send_email.assert_called_once()
        args, kwargs = mock_send_email.call_args
        
        assert kwargs["to_email"] == "admin@hardening.com"
        assert kwargs["subject"] == "Reset your TeleCRM Password"
        assert kwargs["template_name"] == "password_reset.html"
        
        reset_url = kwargs["context"]["reset_url"]
        assert "token=" in reset_url
        
        # Extract the plain token from the query param
        plain_token = reset_url.split("token=")[1]

    # 3. Check the DB to assert that the stored token is hashed and not plaintext
    query = select(User).where(User.email == "admin@hardening.com")
    res = await db.execute(query)
    user = res.scalar_one()
    
    assert user.reset_token is not None
    assert user.reset_token != plain_token
    assert user.reset_token == hash_token(plain_token)
    expiry = user.reset_token_expires.replace(tzinfo=timezone.utc) if user.reset_token_expires.tzinfo is None else user.reset_token_expires
    assert expiry > datetime.now(timezone.utc)

    # 4. Use the plain token to reset the password
    reset_payload = {
        "token": plain_token,
        "password": "newsupersecurepassword123"
    }
    response = await client.post("/api/v1/auth/reset-password", json=reset_payload)
    assert response.status_code == 200
    assert response.json()["detail"] == "Password has been reset successfully"

    # Refresh user model from DB
    await db.refresh(user)
    # Check that reset_token and reset_token_expires are cleared (single-use guarantee)
    assert user.reset_token is None
    assert user.reset_token_expires is None

    # 5. Try using the token again (should fail because it's single use)
    response = await client.post("/api/v1/auth/reset-password", json=reset_payload)
    assert response.status_code == 400
    assert "Invalid or expired" in response.json()["detail"]

    # 6. Test login with the new password
    login_payload = {
        "email": "admin@hardening.com",
        "password": "newsupersecurepassword123"
    }
    response = await client.post("/api/v1/auth/login", json=login_payload)
    assert response.status_code == 200
    tokens = response.json()
    assert "access_token" in tokens


@pytest.mark.asyncio
async def test_password_reset_expiration(client: AsyncClient, db: AsyncSession):
    # 1. Register a tenant
    reg_payload = {
        "company_name": "Expiry Corp",
        "slug": "expiry",
        "admin_email": "admin@expiry.com",
        "admin_password": "oldsupersecurepassword123",
        "first_name": "Expiry",
        "last_name": "Tester"
    }
    response = await client.post("/api/v1/auth/register", json=reg_payload)
    assert response.status_code == 200

    # 2. Request password reset
    forgot_payload = {
        "email": "admin@expiry.com"
    }
    with patch("app.services.email_service.send_email") as mock_send_email:
        response = await client.post("/api/v1/auth/forgot-password", json=forgot_payload)
        assert response.status_code == 200
        
        args, kwargs = mock_send_email.call_args
        reset_url = kwargs["context"]["reset_url"]
        plain_token = reset_url.split("token=")[1]

    # 3. Manually expire the token in the database
    query = select(User).where(User.email == "admin@expiry.com")
    res = await db.execute(query)
    user = res.scalar_one()
    
    # Set expiration to 1 minute in the past
    user.reset_token_expires = datetime.now(timezone.utc) - timedelta(minutes=1)
    await db.commit()

    # 4. Attempt to reset with expired token (should fail)
    reset_payload = {
        "token": plain_token,
        "password": "newsupersecurepassword123"
    }
    response = await client.post("/api/v1/auth/reset-password", json=reset_payload)
    assert response.status_code == 400
    assert "Invalid or expired" in response.json()["detail"]
