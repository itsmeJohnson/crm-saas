"""Launch Sprint 0 — Forgot/Reset password P0 fixes.

Covers:
  C1 — forgot-password surfaces the token in non-prod + SMTP-disabled (mock) mode
       so the flow is usable without a real inbox; never leaks it otherwise.
  M2 — email lookups are case-insensitive (rescues mixed-case rows; blocks
       case-variant duplicate accounts) and signup stores normalized emails.
  M5 — reset link is built from FRONTEND_URL, falling back to CORS[0].
  C3 — reset_token_expires is timezone-aware (guards against reverting to a naive
       column, which 500s the whole flow on Postgres).
"""
import app.services.email_service as email_service_mod
import pytest
from sqlalchemy import select

from app.core.config import settings
from app.core.security import get_password_hash
from app.models.user import User
from app.repositories.organization import OrganizationRepository
from app.repositories.user import UserRepository


async def _make_user(db, email: str, password: str = "OrigPass123"):
    org = await OrganizationRepository(db).create({"name": "Reset Org", "slug": f"reset-{email}"})
    await db.commit()
    user = User(
        organization_id=org.id,
        email=email,  # stored verbatim so we can exercise mixed-case rows
        hashed_password=get_password_hash(password),
        first_name="Reset",
        last_name="User",
        role="OrgAdmin",
        is_active=True,
        is_verified=True,
    )
    db.add(user)
    await db.commit()
    return user


@pytest.fixture(autouse=True)
def _capture_email(monkeypatch):
    """Capture send_email calls; the endpoint imports it fresh from the module,
    so patch it on the module object."""
    sent = {}

    def fake_send_email(to_email, subject, template_name, context):
        sent["to"] = to_email
        sent["subject"] = subject
        sent["context"] = context

    monkeypatch.setattr(email_service_mod, "send_email", fake_send_email)
    return sent


# ---------------------------------------------------------------------------
# C1 — token surfaced in mock/non-prod mode, and the full flow completes
# ---------------------------------------------------------------------------

async def test_c1_forgot_returns_token_in_mock_mode(client, db, monkeypatch):
    monkeypatch.setattr(settings, "SMTP_HOST", None)          # mock mode
    monkeypatch.setattr(settings, "ENVIRONMENT", "development")
    await _make_user(db, "founder@acme.com")

    res = await client.post("/api/v1/auth/forgot-password", json={"email": "founder@acme.com"})
    assert res.status_code == 200
    body = res.json()
    assert "detail" in body
    assert body.get("token"), "mock mode should surface the reset token for local/demo use"


async def test_c1_full_reset_flow_completes(client, db, monkeypatch):
    monkeypatch.setattr(settings, "SMTP_HOST", None)
    monkeypatch.setattr(settings, "ENVIRONMENT", "development")
    user = await _make_user(db, "flow@acme.com", password="OrigPass123")

    token = (await client.post("/api/v1/auth/forgot-password",
                               json={"email": "flow@acme.com"})).json()["token"]

    reset = await client.post("/api/v1/auth/reset-password",
                              json={"token": token, "password": "BrandNewPass1"})
    assert reset.status_code == 200

    await db.refresh(user)
    assert user.reset_token is None and user.reset_token_expires is None   # single-use, cleared
    # New password works, old does not.
    from app.core.security import verify_password
    assert verify_password("BrandNewPass1", user.hashed_password)
    assert not verify_password("OrigPass123", user.hashed_password)


async def test_c1_token_never_leaked_in_production(client, db, monkeypatch):
    monkeypatch.setattr(settings, "ENVIRONMENT", "production")
    monkeypatch.setattr(settings, "SMTP_HOST", None)   # even misconfigured prod must not leak
    await _make_user(db, "prod@acme.com")

    res = await client.post("/api/v1/auth/forgot-password", json={"email": "prod@acme.com"})
    assert res.status_code == 200
    assert "token" not in res.json(), "production must never return the reset token over the API"


async def test_c1_unknown_email_is_generic_and_tokenless(client, db, monkeypatch):
    monkeypatch.setattr(settings, "SMTP_HOST", None)
    monkeypatch.setattr(settings, "ENVIRONMENT", "development")

    res = await client.post("/api/v1/auth/forgot-password", json={"email": "nobody@acme.com"})
    assert res.status_code == 200
    assert "token" not in res.json()   # no account → nothing to hand back


# ---------------------------------------------------------------------------
# M2 — case-insensitive email handling
# ---------------------------------------------------------------------------

async def test_m2_forgot_is_case_insensitive(client, db, monkeypatch):
    monkeypatch.setattr(settings, "SMTP_HOST", None)
    monkeypatch.setattr(settings, "ENVIRONMENT", "development")
    # Pre-existing row stored in mixed case (as older signups did).
    await _make_user(db, "Mixed.Case@Acme.com")

    res = await client.post("/api/v1/auth/forgot-password",
                            json={"email": "mixed.case@acme.com"})   # different case
    assert res.status_code == 200
    assert res.json().get("token"), "case-variant address must still resolve to the account"


async def test_m2_get_by_email_case_insensitive(db):
    await _make_user(db, "Founder@Example.com")
    found = await UserRepository(db).get_by_email("founder@example.COM")
    assert found is not None
    assert found.email == "founder@example.com"   # stored normalized/lowercased


async def test_m2_signup_stores_normalized_email(db):
    """register_tenant lowercases the stored email, so later case variants dedupe."""
    from app.schemas.auth import RegisterTenantRequest
    from app.services.auth_service import AuthService

    req = RegisterTenantRequest(
        company_name="Norm Co", slug="norm-co",
        admin_email="Owner@Norm.CO", admin_password="Password123",
        first_name="O", last_name="N",
        licensed_seats=10, contract_months=3,
    )
    user, _org = await AuthService(db).register_tenant(req)
    await db.commit()
    assert user.email == "owner@norm.co"
    # A case variant is now recognized as the same account (dedup guard).
    assert await UserRepository(db).get_by_email("OWNER@NORM.CO") is not None


# ---------------------------------------------------------------------------
# M5 — reset link built from FRONTEND_URL
# ---------------------------------------------------------------------------

async def test_m5_reset_url_uses_frontend_url(client, db, monkeypatch, _capture_email):
    monkeypatch.setattr(settings, "SMTP_HOST", "smtp.example.com")   # real send path → capture
    monkeypatch.setattr(settings, "ENVIRONMENT", "production")
    monkeypatch.setattr(settings, "FRONTEND_URL", "https://app.johnsoncrm.com/")
    await _make_user(db, "linkuser@acme.com")

    await client.post("/api/v1/auth/forgot-password", json={"email": "linkuser@acme.com"})
    reset_url = _capture_email["context"]["reset_url"]
    assert reset_url.startswith("https://app.johnsoncrm.com/login?token=")
    assert "//login" not in reset_url   # trailing slash trimmed, no double slash


async def test_m5_reset_url_falls_back_to_cors_origin(client, db, monkeypatch, _capture_email):
    monkeypatch.setattr(settings, "SMTP_HOST", "smtp.example.com")
    monkeypatch.setattr(settings, "ENVIRONMENT", "production")
    monkeypatch.setattr(settings, "FRONTEND_URL", None)
    monkeypatch.setattr(settings, "BACKEND_CORS_ORIGINS", ["https://cors-first.example.com"])
    await _make_user(db, "fallback@acme.com")

    await client.post("/api/v1/auth/forgot-password", json={"email": "fallback@acme.com"})
    assert _capture_email["context"]["reset_url"].startswith("https://cors-first.example.com/login?token=")


# ---------------------------------------------------------------------------
# C3 — column stays timezone-aware
# ---------------------------------------------------------------------------

def test_c3_reset_token_expires_is_timezone_aware():
    col = User.__table__.c.reset_token_expires
    assert getattr(col.type, "timezone", False) is True, (
        "reset_token_expires must be timezone-aware; a naive column 500s the reset "
        "flow on Postgres (verified DataError on write and compare)."
    )
