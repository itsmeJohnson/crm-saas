"""Security regression tests — unseeded-Feature-table fallback must be TEST-ONLY.

Hardening (fix/security-test-feature-gate): the fallback that grants ALL features
when the Feature catalog is empty is gated on the POSITIVE settings.is_testing
(ENVIRONMENT == "testing"), never on a raw/negative env check. It must be impossible
to activate in staging/production even when TESTING=true is present.

Covers both hardened resolvers:
  - app.middleware.permissions.resolve_feature_codes
  - app.dependencies.feature_guard.get_active_features
"""
import os
import uuid
from datetime import datetime, timezone, timedelta

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.organization import Organization
from app.models.user import User
from app.models.plan import Plan
from app.models.feature import Feature
from app.models.plan_feature import PlanFeature
from app.models.tenant_subscription import TenantSubscription
from app.middleware.permissions import resolve_feature_codes
from app.dependencies.feature_guard import get_active_features

pytestmark = pytest.mark.asyncio

# A gated feature that a no-subscription tenant can ONLY obtain via the fallback.
FALLBACK_ONLY = "BULK_IMPORT"


@pytest.fixture
async def user_no_sub(db: AsyncSession):
    org = Organization(name="Sec Org", slug=f"secorg-{uuid.uuid4().hex[:8]}")
    db.add(org)
    await db.flush()
    u = User(
        organization_id=org.id,
        email=f"sec-{uuid.uuid4().hex[:8]}@example.com",
        hashed_password="x",
        first_name="Sec",
        last_name="User",
        role="Employee",
        is_active=True,
        is_verified=True,
    )
    db.add(u)
    await db.flush()
    return u, org


def _set_env(monkeypatch, env: str):
    monkeypatch.setattr(settings, "ENVIRONMENT", env)


# ── A: explicit testing env + empty Feature table → fallback ACTIVE ──────────
async def test_A_testing_env_empty_table_fallback_active(db, user_no_sub, monkeypatch):
    user, _ = user_no_sub
    _set_env(monkeypatch, "testing")
    codes = await resolve_feature_codes(user, db)
    assert FALLBACK_ONLY in codes
    assert "WHATSAPP_MESSAGING" in codes  # sanity: full grant


# ── B: production env + empty Feature table → fallback INACTIVE ──────────────
async def test_B_production_env_empty_table_no_fallback(db, user_no_sub, monkeypatch):
    user, _ = user_no_sub
    _set_env(monkeypatch, "production")
    codes = await resolve_feature_codes(user, db)
    assert FALLBACK_ONLY not in codes
    assert "WHATSAPP_MESSAGING" not in codes


# ── C: staging env + empty Feature table → fallback INACTIVE ─────────────────
async def test_C_staging_env_empty_table_no_fallback(db, user_no_sub, monkeypatch):
    user, _ = user_no_sub
    _set_env(monkeypatch, "staging")
    codes = await resolve_feature_codes(user, db)
    assert FALLBACK_ONLY not in codes


# ── E: TESTING=true env var ALONE is NOT sufficient (env is production) ──────
async def test_E_testing_envvar_alone_insufficient(db, user_no_sub, monkeypatch):
    user, _ = user_no_sub
    # conftest already exports TESTING=true; assert that precondition holds…
    monkeypatch.setenv("TESTING", "true")
    assert os.getenv("TESTING") == "true"
    # …but the application environment is production → fallback must NOT fire.
    _set_env(monkeypatch, "production")
    codes = await resolve_feature_codes(user, db)
    assert FALLBACK_ONLY not in codes


# ── D: production + POPULATED Feature table → NORMAL plan resolution ─────────
async def test_D_production_populated_table_normal_resolution(db, monkeypatch):
    org = Organization(name="Prod Org", slug=f"prodorg-{uuid.uuid4().hex[:8]}")
    db.add(org)
    await db.flush()
    granted = Feature(code="VOIP_CALLS", display_name="VoIP", category="Calling", active=True)
    other = Feature(code="BULK_IMPORT", display_name="Bulk Import", category="Leads", active=True)
    db.add_all([granted, other])
    await db.flush()
    plan = Plan(
        name="P", display_name="P", description="d",
        price_inr=1000.0, billing_cycle_days=30, max_users=5, is_active=True,
    )
    db.add(plan)
    await db.flush()
    db.add(PlanFeature(plan_id=plan.id, feature_id=granted.id, enabled=True))  # only VOIP granted
    sub = TenantSubscription(
        organization_id=org.id, plan_id=plan.id, status="active",
        users_purchased=0, billing_cycle="monthly",
        start_date=datetime.now(timezone.utc),
        end_date=datetime.now(timezone.utc) + timedelta(days=30),
    )
    db.add(sub)
    user = User(
        organization_id=org.id, email=f"o-{uuid.uuid4().hex[:8]}@example.com",
        hashed_password="x", first_name="O", last_name="A", role="Employee",
        is_active=True, is_verified=True,
    )
    db.add(user)
    await db.flush()

    _set_env(monkeypatch, "production")
    codes = await resolve_feature_codes(user, db)
    # Feature table is populated → fallback skipped entirely; real plan resolution:
    assert "VOIP_CALLS" in codes           # granted by the plan
    assert "BULK_IMPORT" not in codes      # exists but NOT granted by the plan


# ── get_active_features (feature_guard.py) — same gate, cache-backed ─────────
async def test_gaf_testing_env_empty_table_fallback_active(db, monkeypatch):
    _set_env(monkeypatch, "testing")
    feats = await get_active_features(db, uuid.uuid4())  # fresh org → no cache
    assert FALLBACK_ONLY in feats


async def test_gaf_production_env_empty_table_no_fallback(db, monkeypatch):
    _set_env(monkeypatch, "production")
    feats = await get_active_features(db, uuid.uuid4())
    assert FALLBACK_ONLY not in feats


async def test_gaf_testing_envvar_alone_insufficient(db, monkeypatch):
    monkeypatch.setenv("TESTING", "true")
    _set_env(monkeypatch, "production")  # TESTING=true present but env=production
    feats = await get_active_features(db, uuid.uuid4())
    assert FALLBACK_ONLY not in feats
