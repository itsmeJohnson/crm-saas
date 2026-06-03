import pytest
from httpx import AsyncClient

@pytest.mark.asyncio
async def test_register_and_login(client: AsyncClient):
    # Register tenant
    reg_payload = {
        "company_name": "Acme Corp",
        "slug": "acme",
        "admin_email": "admin@acme.com",
        "admin_password": "supersecurepassword123",
        "first_name": "John",
        "last_name": "Doe"
    }
    response = await client.post("/api/v1/auth/register", json=reg_payload)
    assert response.status_code == 200
    data = response.json()
    assert data["organization"]["slug"] == "acme"
    assert data["user"]["email"] == "admin@acme.com"
    assert data["user"]["role"] == "OrgAdmin"

    # Login
    login_payload = {
        "email": "admin@acme.com",
        "password": "supersecurepassword123"
    }
    response = await client.post("/api/v1/auth/login", json=login_payload)
    assert response.status_code == 200
    tokens = response.json()
    assert "access_token" in tokens
    assert "refresh_token" in tokens

    # Access Protected Route /me
    headers = {"Authorization": f"Bearer {tokens['access_token']}"}
    response = await client.get("/api/v1/auth/me", headers=headers)
    assert response.status_code == 200
    me_data = response.json()
    assert me_data["user"]["email"] == "admin@acme.com"
    assert me_data["organization"]["name"] == "Acme Corp"

    # Refresh token
    refresh_payload = {
        "refresh_token": tokens["refresh_token"]
    }
    response = await client.post("/api/v1/auth/refresh", json=refresh_payload)
    assert response.status_code == 200
    new_tokens = response.json()
    assert "access_token" in new_tokens
    assert "refresh_token" in new_tokens

    # Access Protected Route with new access token
    new_headers = {"Authorization": f"Bearer {new_tokens['access_token']}"}
    response = await client.get("/api/v1/auth/me", headers=new_headers)
    assert response.status_code == 200

    # Logout
    logout_payload = {
        "refresh_token": new_tokens["refresh_token"]
    }
    response = await client.post("/api/v1/auth/logout", json=logout_payload)
    assert response.status_code == 200

    # Try to reuse the logged out refresh token (should fail)
    response = await client.post("/api/v1/auth/refresh", json=logout_payload)
    assert response.status_code == 401
