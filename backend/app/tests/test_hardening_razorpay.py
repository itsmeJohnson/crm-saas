import pytest
import uuid
import json
import hmac
import hashlib
from httpx import AsyncClient
from unittest.mock import patch, MagicMock
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.organization import Organization
from app.models.user import User
from app.models.invoice import Invoice
from app.models.payment import Payment
from app.models.tenant_subscription import TenantSubscription
from app.core.security import create_access_token, get_password_hash

from app.models.plan import Plan

@pytest.fixture
async def setup_portal_user(db: AsyncSession):
    # Create Organization
    org = Organization(
        name="Portal SaaS Tenant", 
        slug="portaltenant",
        max_users=5,
        extra_storage_gb=0
    )
    db.add(org)
    await db.flush()

    # Create a Plan
    plan = Plan(
        name="Growth Plan",
        display_name="Growth Plan",
        description="Growth subscription plan",
        price_inr=3999.0,
        billing_cycle_days=30,
        max_users=5,
        is_active=True
    )
    db.add(plan)
    await db.flush()

    # Create User
    pwd_hash = get_password_hash("password123")
    user = User(
        organization_id=org.id,
        email="owner@portaltenant.com",
        hashed_password=pwd_hash,
        first_name="Portal",
        last_name="Owner",
        role="OrgAdmin",
        is_active=True,
        is_verified=True
    )
    db.add(user)
    await db.flush()

    # Create TenantSubscription
    sub = TenantSubscription(
        organization_id=org.id,
        plan_id=plan.id,
        status="active",
        users_purchased=0,
        billing_cycle="monthly",
        start_date=datetime_utcnow(),
        end_date=datetime_utcnow()
    )
    db.add(sub)
    await db.flush()

    # Create Unpaid Invoice
    invoice = Invoice(
        organization_id=org.id,
        invoice_number="INV-PORTAL-TEST",
        amount=150.00,
        status="Pending",
        due_date=datetime_utcnow(),
        payment_status="unpaid",
        total_amount=150.00,
        action_metadata={"action_type": "buy_extra_seats", "user_count": 3}
    )
    db.add(invoice)
    await db.flush()
    await db.commit()

    token = create_access_token(user.id)
    return {
        "org": org,
        "user": user,
        "invoice": invoice,
        "sub": sub,
        "headers": {"Authorization": f"Bearer {token}"}
    }

def datetime_utcnow():
    from datetime import datetime, timezone
    return datetime.now(timezone.utc)


@pytest.mark.asyncio
async def test_razorpay_checkout_and_pay(client: AsyncClient, setup_portal_user: dict, db: AsyncSession):
    headers = setup_portal_user["headers"]
    invoice = setup_portal_user["invoice"]
    org = setup_portal_user["org"]

    # 1. Initiate checkout session
    response = await client.post(f"/api/v1/portal/invoices/{invoice.id}/checkout", headers=headers)
    assert response.status_code == 200
    data = response.json()
    assert "id" in data
    assert "amount" in data
    assert data["amount"] == 15000  # 150.00 in paise
    mock_order_id = data["id"]
    
    # Verify order ID is stashed in invoice metadata in DB
    await db.refresh(invoice)
    assert invoice.action_metadata["razorpay_order_id"] == mock_order_id

    # 2. Pay invoice with invalid signature (should fail)
    pay_payload = {
        "gateway": "Razorpay",
        "transaction_id": "pay_test_transaction",
        "razorpay_order_id": mock_order_id,
        "razorpay_signature": "invalid_sig_value"
    }
    
    # We patch verify_payment_signature to return False specifically for invalid
    with patch("app.services.razorpay_service.RazorpayService.verify_payment_signature", return_value=False):
        response = await client.post(f"/api/v1/portal/invoices/{invoice.id}/pay", json=pay_payload, headers=headers)
        assert response.status_code == 400
        assert "Invalid Razorpay payment signature" in response.json()["detail"]

    # 3. Pay invoice with valid signature (should succeed)
    with patch("app.services.razorpay_service.RazorpayService.verify_payment_signature", return_value=True):
        response = await client.post(f"/api/v1/portal/invoices/{invoice.id}/pay", json=pay_payload, headers=headers)
        assert response.status_code == 200
        
        # Verify invoice is paid and side effects are applied (max_users increased from 5 to 8)
        invoice_res = response.json()
        assert invoice_res["payment_status"] == "paid"
        
        # Check database organization state
        org_res = await db.execute(select(Organization).where(Organization.id == org.id))
        org_db = org_res.scalar_one()
        assert org_db.max_users == 8


@pytest.mark.asyncio
async def test_razorpay_webhooks(client: AsyncClient, setup_portal_user: dict, db: AsyncSession):
    invoice = setup_portal_user["invoice"]
    org = setup_portal_user["org"]
    
    # Add a mock order id to the invoice
    mock_order_id = "order_webhook_test_123"
    invoice.action_metadata = {"razorpay_order_id": mock_order_id, "action_type": "buy_extra_seats", "user_count": 2}
    db.add(invoice)
    await db.commit()

    # Create webhook mock payload
    webhook_payload = {
        "event": "order.paid",
        "payload": {
            "payment": {
                "entity": {
                    "id": "pay_webhook_txn_789",
                    "order_id": mock_order_id,
                    "amount": 15000,
                    "status": "captured"
                }
            }
        }
    }
    
    # We serialize payload to match raw body signature verify
    raw_body = json.dumps(webhook_payload).encode("utf-8")
    
    # Mock signature verification to pass
    with patch("app.services.razorpay_service.RazorpayService.verify_webhook_signature", return_value=True):
        response = await client.post(
            "/api/v1/billing/webhook/razorpay", 
            content=raw_body, 
            headers={"X-Razorpay-Signature": "mock_sig_value"}
        )
        assert response.status_code == 200
        assert response.json()["status"] == "processed"

    # Verify database updates
    await db.refresh(invoice)
    assert invoice.payment_status == "paid"
    
    org_res = await db.execute(select(Organization).where(Organization.id == org.id))
    org_db = org_res.scalar_one()
    assert org_db.max_users == 7  # 5 + 2 extra users

    # Test refund webhook processing
    # Retrieve the payment record created by the order.paid webhook above
    stmt_pay = select(Payment).where(Payment.transaction_id == "pay_webhook_txn_789")
    res_pay = await db.execute(stmt_pay)
    payment = res_pay.scalar_one()

    refund_payload = {
        "event": "refund.processed",
        "payload": {
            "refund": {
                "entity": {
                    "id": "rfnd_test_refund_123",
                    "payment_id": "pay_webhook_txn_789",
                    "amount": 15000,
                    "status": "processed"
                }
            }
        }
    }
    raw_refund_body = json.dumps(refund_payload).encode("utf-8")

    with patch("app.services.razorpay_service.RazorpayService.verify_webhook_signature", return_value=True):
        response = await client.post(
            "/api/v1/billing/webhook/razorpay",
            content=raw_refund_body,
            headers={"X-Razorpay-Signature": "mock_sig_value"}
        )
        assert response.status_code == 200
        assert response.json()["status"] == "processed"

    # Verify database updates
    await db.refresh(invoice)
    assert invoice.status == "Refunded"
    assert invoice.payment_status == "refunded"
    
    await db.refresh(payment)
    assert payment.status == "Refunded"
