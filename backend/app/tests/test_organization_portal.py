import pytest
import uuid
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.organization import Organization
from app.models.tenant_subscription import TenantSubscription
from app.models.plan import Plan
from app.models.invoice import Invoice
from app.models.payment import Payment
from app.models.audit_log import AuditLog
from app.models.support_ticket import SupportTicket
from app.models.user import User
from app.core.security import create_access_token, get_password_hash

@pytest.fixture
async def setup_portal_data(db: AsyncSession):
    # 1. Create default commercial settings & invoice config if needed
    from app.models.commercial_settings import CommercialSettings
    from app.models.invoice_config import InvoiceConfig

    comm_settings = CommercialSettings(
        id="default",
        default_currency="INR",
        default_extra_user_price=150.00,
        default_gst=18.00,
        gst_inclusive=False,
        grace_period_days=7
    )
    inv_config = InvoiceConfig(
        id="default",
        invoice_prefix="INV",
        starting_invoice_number=1001
    )
    db.add_all([comm_settings, inv_config])
    await db.flush()

    # 2. Create organization
    org = Organization(
        name="Self Service Org",
        slug="self-service-org",
        subscription_plan="Starter",
        subscription_status="active",
        max_users=5,
        extra_storage_gb=0
    )
    db.add(org)
    await db.flush()

    # 3. Create plan
    plan = Plan(
        name="Starter",
        display_name="Starter Plan",
        price_inr=999.00,
        monthly_price=999.00,
        max_users=5,
        max_admins=1,
        max_managers=1,
        max_team_leads=1,
        max_employees=2,
        storage_limit_gb=10,
        recording_retention_days=15,
        is_active=True,
        plan_active=True,
        display_order=1
    )
    db.add(plan)
    await db.flush()

    # 4. Create premium plan for upgrade testing
    premium_plan = Plan(
        name="Enterprise",
        display_name="Enterprise Plan",
        price_inr=4999.00,
        monthly_price=4999.00,
        max_users=20,
        max_admins=2,
        max_managers=4,
        max_team_leads=8,
        max_employees=10,
        storage_limit_gb=100,
        recording_retention_days=90,
        is_active=True,
        plan_active=True,
        display_order=3
    )
    db.add(premium_plan)
    await db.flush()

    # 5. Create Tenant Subscription
    sub = TenantSubscription(
        organization_id=org.id,
        plan_id=plan.id,
        status="active",
        start_date=pytest.importorskip("datetime").datetime.now(pytest.importorskip("datetime").timezone.utc),
        end_date=pytest.importorskip("datetime").datetime.now(pytest.importorskip("datetime").timezone.utc) + pytest.importorskip("datetime").timedelta(days=30),
        auto_renew=True,
        users_purchased=0,
        storage_used=0.5
    )
    db.add(sub)
    await db.flush()

    # 6. Create OrgAdmin User
    pwd_hash = get_password_hash("Password123")
    user = User(
        organization_id=org.id,
        email="orgadmin@selfservice.com",
        hashed_password=pwd_hash,
        first_name="Org",
        last_name="Admin",
        role="OrgAdmin",
        is_active=True,
        is_verified=True
    )
    db.add(user)
    await db.flush()
    await db.commit()

    token = create_access_token(user.id)
    return {
        "org": org,
        "plan": plan,
        "premium_plan": premium_plan,
        "user": user,
        "headers": {"Authorization": f"Bearer {token}"}
    }

@pytest.mark.asyncio
async def test_get_dashboard_stats(client: AsyncClient, setup_portal_data: dict):
    headers = setup_portal_data["headers"]
    response = await client.get("/api/v1/portal/stats", headers=headers)
    assert response.status_code == 200
    data = response.json()
    assert data["plan_name"] == "Starter Plan"
    assert data["users"]["limit"] == 5
    assert data["storage"]["limit_gb"] == 10
    assert data["pending_invoice_amount"] == 0.0

@pytest.mark.asyncio
async def test_get_plans(client: AsyncClient, setup_portal_data: dict):
    headers = setup_portal_data["headers"]
    response = await client.get("/api/v1/portal/plans", headers=headers)
    assert response.status_code == 200
    plans = response.json()
    assert len(plans) >= 2
    names = [p["name"] for p in plans]
    assert "Starter" in names
    assert "Enterprise" in names

@pytest.mark.asyncio
async def test_purchase_users_flow(client: AsyncClient, setup_portal_data: dict, db: AsyncSession):
    headers = setup_portal_data["headers"]
    org_id = setup_portal_data["org"].id

    # 1. Purchase Seats Invoice Generation
    payload = {"user_count": 2, "gateway": "UPI"}
    response = await client.post("/api/v1/portal/subscription/add-users", json=payload, headers=headers)
    assert response.status_code == 200
    inv_data = response.json()
    assert inv_data["payment_status"] == "unpaid"
    invoice_id = uuid.UUID(inv_data["id"])

    # Verify action metadata
    invoice_stmt = select(Invoice).where(Invoice.id == invoice_id)
    res = await db.execute(invoice_stmt)
    invoice = res.scalar_one()
    assert invoice.action_metadata["action_type"] == "buy_extra_seats"
    assert invoice.action_metadata["user_count"] == 2

    # 2. Process Invoice Payment
    pay_payload = {"gateway": "UPI", "transaction_id": "TXN-123456"}
    pay_response = await client.post(f"/api/v1/portal/invoices/{invoice_id}/pay", json=pay_payload, headers=headers)
    assert pay_response.status_code == 200
    assert pay_response.json()["payment_status"] == "paid"

    # Verify side effects in DB
    await db.refresh(setup_portal_data["org"])
    assert setup_portal_data["org"].max_users == 7

    sub_stmt = select(TenantSubscription).where(TenantSubscription.organization_id == org_id)
    sub = (await db.execute(sub_stmt)).scalar_one()
    assert sub.users_purchased == 2

    # Verify audit log was created
    audit_stmt = select(AuditLog).where(AuditLog.organization_id == org_id, AuditLog.action == "PAY_INVOICE_SUCCESS")
    audit = (await db.execute(audit_stmt)).scalar_one_or_none()
    assert audit is not None

@pytest.mark.asyncio
async def test_purchase_storage_flow(client: AsyncClient, setup_portal_data: dict, db: AsyncSession):
    headers = setup_portal_data["headers"]
    org_id = setup_portal_data["org"].id

    # 1. Purchase Storage Invoice
    payload = {"storage_gb": 15, "gateway": "Stripe"}
    response = await client.post("/api/v1/portal/subscription/add-storage", json=payload, headers=headers)
    assert response.status_code == 200
    inv_data = response.json()
    invoice_id = uuid.UUID(inv_data["id"])

    # 2. Pay Invoice
    pay_payload = {"gateway": "Stripe", "transaction_id": "TXN-STRIPE-1"}
    pay_response = await client.post(f"/api/v1/portal/invoices/{invoice_id}/pay", json=pay_payload, headers=headers)
    assert pay_response.status_code == 200

    # Verify side effects in DB
    await db.refresh(setup_portal_data["org"])
    assert setup_portal_data["org"].extra_storage_gb == 15

@pytest.mark.asyncio
async def test_plan_upgrade_flow(client: AsyncClient, setup_portal_data: dict, db: AsyncSession):
    headers = setup_portal_data["headers"]
    org_id = setup_portal_data["org"].id
    premium_plan_id = setup_portal_data["premium_plan"].id

    # 1. Generate Upgrade Invoice
    payload = {
        "plan_id": str(premium_plan_id),
        "billing_cycle": "annual",
        "gateway": "Razorpay"
    }
    response = await client.post("/api/v1/portal/subscription/upgrade", json=payload, headers=headers)
    assert response.status_code == 200
    inv_data = response.json()
    invoice_id = uuid.UUID(inv_data["id"])

    # 1b. Initiate checkout session
    checkout_response = await client.post(f"/api/v1/portal/invoices/{invoice_id}/checkout", headers=headers)
    assert checkout_response.status_code == 200
    checkout_data = checkout_response.json()
    mock_order_id = checkout_data["id"]

    # 2. Pay Invoice
    pay_payload = {
        "gateway": "Razorpay",
        "transaction_id": "TXN-RAZORPAY-1",
        "razorpay_order_id": mock_order_id,
        "razorpay_signature": "mock_sig_val"
    }
    from unittest.mock import patch
    with patch("app.services.razorpay_service.RazorpayService.verify_payment_signature", return_value=True):
        pay_response = await client.post(f"/api/v1/portal/invoices/{invoice_id}/pay", json=pay_payload, headers=headers)
        assert pay_response.status_code == 200

    # Verify plan upgrade side effects
    await db.refresh(setup_portal_data["org"])
    assert setup_portal_data["org"].subscription_plan == "Enterprise"
    assert setup_portal_data["org"].max_users == 20

    sub_stmt = select(TenantSubscription).where(TenantSubscription.organization_id == org_id)
    sub = (await db.execute(sub_stmt)).scalar_one()
    assert sub.plan_id == premium_plan_id
    assert sub.billing_cycle == "annual"

@pytest.mark.asyncio
async def test_support_tickets_operations(client: AsyncClient, setup_portal_data: dict, db: AsyncSession):
    headers = setup_portal_data["headers"]
    org_id = setup_portal_data["org"].id

    # 1. Create a support ticket
    ticket_payload = {
        "subject": "Portal Loading Time",
        "priority": "High",
        "description": "The self service portal dashboard is loading slowly today."
    }
    response = await client.post("/api/v1/portal/support", json=ticket_payload, headers=headers)
    assert response.status_code == 200
    ticket_data = response.json()
    assert ticket_data["subject"] == "Portal Loading Time"
    assert ticket_data["priority"] == "High"
    assert ticket_data["status"] == "Open"
    ticket_id = uuid.UUID(ticket_data["id"])

    # 2. Fetch ticket details
    get_response = await client.get(f"/api/v1/portal/support/{ticket_id}", headers=headers)
    assert get_response.status_code == 200
    assert get_response.json()["subject"] == "Portal Loading Time"

    # 3. Post a comment reply
    comment_payload = {"content": "Checking back if there is any update on this issue."}
    comment_response = await client.post(f"/api/v1/portal/support/{ticket_id}/comment", json=comment_payload, headers=headers)
    assert comment_response.status_code == 200
    comments = comment_response.json()["comments"]
    assert len(comments) == 1
    assert comments[0]["content"] == "Checking back if there is any update on this issue."

    # 4. List all tickets
    list_response = await client.get("/api/v1/portal/support", headers=headers)
    assert list_response.status_code == 200
    assert len(list_response.json()) >= 1

@pytest.mark.asyncio
async def test_update_profile_and_billing(client: AsyncClient, setup_portal_data: dict, db: AsyncSession):
    headers = setup_portal_data["headers"]
    org_id = setup_portal_data["org"].id

    # 1. Update Profile (with change audit logging verification)
    profile_payload = {
        "website": "https://newcompanyweb.com",
        "support_email": "customsupport@selfservice.com",
        "support_phone": "+91 99000 99000"
    }
    response = await client.put("/api/v1/portal/profile", json=profile_payload, headers=headers)
    assert response.status_code == 200
    
    # Assert DB updates
    await db.refresh(setup_portal_data["org"])
    assert setup_portal_data["org"].website == "https://newcompanyweb.com"
    assert setup_portal_data["org"].support_email == "customsupport@selfservice.com"

    # Verify audit logs comparison diff
    stmt = select(AuditLog).where(AuditLog.organization_id == org_id, AuditLog.action == "UPDATE_PROFILE")
    audit = (await db.execute(stmt)).scalar_one_or_none()
    assert audit is not None
    assert "website" in audit.action_metadata["changes"]
    assert audit.action_metadata["changes"]["website"]["new"] == "https://newcompanyweb.com"

    # 2. Update Billing Configuration
    billing_payload = {
        "billing_name": "New Corp India Pvt Ltd",
        "gst_number": "27AAAAA1111A1Z5",
        "pan": "ABCDE5555F",
        "billing_address": "45 Corporate Marg, Nariman Point",
        "billing_city": "Mumbai",
        "billing_state": "Maharashtra",
        "billing_country": "India",
        "billing_pin_code": "400021"
    }
    billing_response = await client.put("/api/v1/portal/billing", json=billing_payload, headers=headers)
    assert billing_response.status_code == 200
    
    # Assert DB billing updates
    await db.refresh(setup_portal_data["org"])
    assert setup_portal_data["org"].billing_name == "New Corp India Pvt Ltd"
    assert setup_portal_data["org"].gst_number == "27AAAAA1111A1Z5"
    assert setup_portal_data["org"].billing_city == "Mumbai"

    # Verify billing audit log comparative details
    billing_stmt = select(AuditLog).where(AuditLog.organization_id == org_id, AuditLog.action == "UPDATE_BILLING")
    billing_audit = (await db.execute(billing_stmt)).scalar_one_or_none()
    assert billing_audit is not None
    assert "gst_number" in billing_audit.action_metadata["changes"]
    assert billing_audit.action_metadata["changes"]["gst_number"]["new"] == "27AAAAA1111A1Z5"


@pytest.mark.asyncio
async def test_update_portal_settings(client: AsyncClient, setup_portal_data: dict, db: AsyncSession):
    headers = setup_portal_data["headers"]
    org = setup_portal_data["org"]

    # Update settings
    settings_payload = {
        "notification_invoice_emails": False,
        "notification_renewal_emails": False,
        "notification_support_emails": False,
        "auto_renewal": False,
        "theme": "light"
    }
    response = await client.put("/api/v1/portal/settings", json=settings_payload, headers=headers)
    assert response.status_code == 200
    assert response.json()["success"] is True

    # Assert database values were updated
    await db.refresh(org)
    assert org.notification_invoice_emails is False
    assert org.notification_renewal_emails is False
    assert org.notification_support_emails is False
    assert org.auto_renewal is False
    assert org.theme == "light"

