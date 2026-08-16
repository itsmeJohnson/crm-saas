"""Org-level telephony config: encryption, masking, and RBAC.

Covers the enterprise guarantees — secrets are AES-256 encrypted at rest, never
returned to any client (only ``has_*`` flags), and the settings API is reachable
only by SuperAdmin / OrgAdmin(manage_integrations)."""
import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core import crypto
from app.core.security import create_access_token, get_password_hash
from app.models.telephony_settings import TelephonySettings
from app.repositories.organization import OrganizationRepository
from app.repositories.user_repository import UserRepository
from app.schemas.telephony_settings import TelephonyConfigUpdate
from app.services.telephony_config_service import TelephonyConfigService

SECRET = "0551ba5fc3ca7ac2c067b23600899f68"


def test_crypto_roundtrip_and_nondeterminism():
    a = crypto.encrypt(SECRET)
    b = crypto.encrypt(SECRET)
    assert a != SECRET and b != SECRET          # never stored plaintext
    assert a != b                                # random nonce → different ciphertext
    assert crypto.decrypt(a) == SECRET == crypto.decrypt(b)
    assert crypto.encrypt("") is None and crypto.decrypt(None) is None


async def _make_user(db: AsyncSession, role: str, email: str):
    org = await OrganizationRepository(db).create({"name": f"Org {email}", "slug": f"org-{email}".replace("@", "-").replace(".", "-")})
    await db.commit()
    user = await UserRepository(db).create_user(org.id, {
        "email": email, "hashed_password": get_password_hash("password123"),
        "first_name": "T", "last_name": role, "role": role, "is_active": True})
    await db.commit()
    return org, user


async def test_config_service_encrypts_masks_and_decrypts(db: AsyncSession):
    _, actor = await _make_user(db, "SuperAdmin", "owner@tel.com")
    svc = TelephonyConfigService(db)

    await svc.update(actor, TelephonyConfigUpdate(
        provider="myoperator", company_id="6a675bc2efc87963", public_ivr_id="ivr123",
        x_api_key="xkey", secret_token=SECRET, authentication_token="authtok", is_active=True))
    await db.commit()

    # Stored ciphertext is NOT the plaintext.
    row = (await db.execute(select(TelephonySettings).where(
        TelephonySettings.organization_id == actor.organization_id))).scalars().first()
    assert row.secret_token_enc and row.secret_token_enc != SECRET
    assert crypto.decrypt(row.secret_token_enc) == SECRET

    # Masked response exposes presence flags but NEVER the secret values.
    masked = svc.to_masked_response(row).model_dump()
    assert masked["has_secret_token"] and masked["has_x_api_key"] and masked["has_authentication_token"]
    dumped = str(masked)
    assert SECRET not in dumped and "xkey" not in dumped and "authtok" not in dumped
    assert "secret_token" not in masked and "x_api_key" not in masked

    # Server-side decrypt path returns usable creds.
    cfg = await svc.get_decrypted_config(actor.organization_id)
    assert cfg["secret_token"] == SECRET and cfg["public_ivr_id"] == "ivr123"


async def test_employee_forbidden_with_exact_body(client: AsyncClient, db: AsyncSession):
    _, emp = await _make_user(db, "Employee", "emp@tel.com")
    r = await client.get("/api/v1/settings/calling",
                         headers={"Authorization": f"Bearer {create_access_token(emp.id)}"})
    assert r.status_code == 403
    assert r.json() == {"success": False, "message": "You are not authorized to access telephony settings."}


async def test_superadmin_gets_masked_config(client: AsyncClient, db: AsyncSession):
    _, owner = await _make_user(db, "SuperAdmin", "owner2@tel.com")
    h = {"Authorization": f"Bearer {create_access_token(owner.id)}"}

    put = await client.put("/api/v1/settings/calling", headers=h,
                           json={"provider": "myoperator", "x_api_key": "topsecretkey", "secret_token": SECRET})
    assert put.status_code == 200
    body = put.json()
    assert body["has_x_api_key"] is True and body["has_secret_token"] is True
    assert "topsecretkey" not in str(body) and SECRET not in str(body)

    get = await client.get("/api/v1/settings/calling", headers=h)
    assert get.status_code == 200
    assert "topsecretkey" not in str(get.json())
