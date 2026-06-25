import pytest
import uuid
from datetime import datetime, timezone, timedelta
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.organization import Organization
from app.models.user import User
from app.models.audit_log import AuditLog
from app.models.commercial_settings import CommercialSettings
from app.models.plan import Plan
from app.models.tenant_subscription import TenantSubscription
from app.models.invoice import Invoice
from app.core.security import create_access_token, get_password_hash
from app.services.subscription_service import SubscriptionService
from app.cron.subscription_cron import process_subscription_transitions

@pytest.fixture
async def setup_super_admin_commercial(db: AsyncSession):
    # Create a SuperAdmin organization
    org = Organization(name="SuperAdmin Org", slug="super-admin-org-comm")
    db.add(org)
    await db.flush()

    # Create a SuperAdmin user
    pwd_hash = get_password_hash("password123")
    super_admin = User(
        organization_id=org.id,
        email="superadmin_comm@test.com",
        hashed_password=pwd_hash,
        first_name="Super",
        last_name="Admin",
        role="SuperAdmin",
        is_active=True,
        is_verified=True
    )
    db.add(super_admin)
    
    # Initialize default CommercialSettings
    config = CommercialSettings(
        id="default",
        default_currency="INR",
        currency_symbol="₹",
        default_timezone="Asia/Kolkata",
        default_gst=18.0,
        gst_inclusive=False,
        default_trial_days=14,
        trial_reminder_days=3,
        grace_period_days=7
    )
    db.add(config)
    
    # Add a mock plan
    plan = Plan(
        name="Test Starter Plan",
        price_inr=1000.0,
        billing_cycle_days=30,
        max_users=10,
        max_admins=1,
        max_managers=1,
        max_team_leads=2,
        max_employees=6,
        is_trial=False,
        is_active=True,
        display_name="Starter Plan",
        setup_charges=None,  # test fallback
        discount_percentage=None,  # test fallback
        gst_percentage=None,  # test fallback
        extra_user_price=0.0
    )
    db.add(plan)
    await db.flush()
    await db.commit()

    token = create_access_token(super_admin.id)
    return {
        "org": org,
        "super_admin": super_admin,
        "plan": plan,
        "headers": {"Authorization": f"Bearer {token}"}
    }

@pytest.mark.asyncio
async def test_get_commercial_settings(client: AsyncClient, setup_super_admin_commercial: dict):
    headers = setup_super_admin_commercial["headers"]
    response = await client.get("/api/v1/super-admin/commercial-settings", headers=headers)
    assert response.status_code == 200
    res_data = response.json()
    assert res_data["default_currency"] == "INR"
    assert res_data["currency_symbol"] == "₹"
    assert res_data["default_gst"] == 18.0
    assert res_data["default_trial_days"] == 14

@pytest.mark.asyncio
async def test_update_commercial_settings(client: AsyncClient, setup_super_admin_commercial: dict, db: AsyncSession):
    headers = setup_super_admin_commercial["headers"]
    org_id = setup_super_admin_commercial["org"].id

    payload = {
        "default_currency": "USD",
        "currency_symbol": "$",
        "default_gst": 5.0,
        "gst_inclusive": True,
        "default_trial_days": 7,
        "trial_reminder_days": 2,
        "grace_period_days": 5,
        "reason": "Testing commercial settings update and audit logs diff calculation"
    }
    response = await client.put("/api/v1/super-admin/commercial-settings", json=payload, headers=headers)
    assert response.status_code == 200
    res_data = response.json()
    assert res_data["default_currency"] == "USD"
    assert res_data["currency_symbol"] == "$"
    assert res_data["default_gst"] == 5.0
    assert res_data["gst_inclusive"] is True
    assert res_data["default_trial_days"] == 7

    # Verify audit logs created
    query = select(AuditLog).where(
        AuditLog.organization_id == org_id,
        AuditLog.action == "COMMERCIAL_SETTINGS_UPDATED"
    )
    res = await db.execute(query)
    logs = res.scalars().all()
    assert len(logs) > 0
    audit_meta = logs[0].action_metadata
    assert audit_meta["new"]["default_currency"] == "USD"
    assert audit_meta["old"]["default_currency"] == "INR"
    assert audit_meta["reason"] == "Testing commercial settings update and audit logs diff calculation"

@pytest.mark.asyncio
async def test_update_commercial_settings_validation_rejections(client: AsyncClient, setup_super_admin_commercial: dict):
    headers = setup_super_admin_commercial["headers"]

    # Negative values validation
    payload = {
        "default_gst": -2.0,  # invalid
        "default_trial_days": -5,  # invalid
        "minimum_users": 0,  # invalid (< 1)
        "maximum_discount_percentage": -10.0  # invalid
    }
    response = await client.put("/api/v1/super-admin/commercial-settings", json=payload, headers=headers)
    assert response.status_code == 422  # validation rejection
    errors = response.json()["detail"]
    err_fields = [err["loc"][-1] for err in errors]
    assert "default_gst" in err_fields
    assert "default_trial_days" in err_fields
    assert "minimum_users" in err_fields
    assert "maximum_discount_percentage" in err_fields

@pytest.mark.asyncio
async def test_subscription_service_renewal_fallbacks(setup_super_admin_commercial: dict, db: AsyncSession):
    # Retrieve elements from fixture
    org = setup_super_admin_commercial["org"]
    plan = setup_super_admin_commercial["plan"]
    
    # Create subscription
    now = datetime.now(timezone.utc)
    sub = TenantSubscription(
        organization_id=org.id,
        plan_id=plan.id,
        start_date=now - timedelta(days=35),
        end_date=now - timedelta(days=5),  # expired
        status="expired",
        auto_renew=False,
        users_purchased=1
    )
    db.add(sub)
    await db.commit()

    service = SubscriptionService(db)
    updated_sub = await service.renew_subscription(org.id)
    assert updated_sub.status == "active"
    
    # Retrieve the renewal invoice to check fallback values from CommercialSettings
    inv_stmt = select(Invoice).where(Invoice.organization_id == org.id)
    inv_res = await db.execute(inv_stmt)
    invoices = inv_res.scalars().all()
    assert len(invoices) == 1
    invoice = invoices[0]
    
    # Plan setup_charges is None, fallback from CommercialSettings default (0.0)
    assert invoice.setup_charges == 0.0
    # Plan gst_percentage is None, fallback from CommercialSettings default (18.0)
    # Price is 1000.0, 18% GST = 180.0
    assert invoice.gst_amount == 180.0
    assert invoice.amount == 1180.0

@pytest.mark.asyncio
async def test_subscription_cron_transitions(setup_super_admin_commercial: dict, db: AsyncSession):
    org = setup_super_admin_commercial["org"]
    plan = setup_super_admin_commercial["plan"]
    
    # Create an expired subscription that is past the grace period
    # Grace period in default settings is 7 days. Let's make it expired 10 days ago.
    now = datetime.now(timezone.utc)
    sub = TenantSubscription(
        organization_id=org.id,
        plan_id=plan.id,
        start_date=now - timedelta(days=40),
        end_date=now - timedelta(days=10),
        status="expired",
        auto_renew=False
    )
    db.add(sub)
    await db.commit()

    # Trigger transitions process
    transitions = await process_subscription_transitions(db, now)
    assert transitions == 1
    
    # Check if subscription status transitioned to suspended
    stmt = select(TenantSubscription).where(TenantSubscription.id == sub.id)
    res = await db.execute(stmt)
    updated_sub = res.scalar()
    assert updated_sub.status == "suspended"
