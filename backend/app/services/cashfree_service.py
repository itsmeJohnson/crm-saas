"""
Cashfree Payment Gateway Service
---------------------------------
Primary payment gateway for Johnson Softwares CRM SaaS.
Cashfree is easier to get approved with UDYAM registration (no GST required).

Registration: https://merchant.cashfree.com/merchants/signup
Docs: https://docs.cashfree.com/docs/payment-gateway

Required environment variables:
  CASHFREE_APP_ID       — from Dashboard → Credentials
  CASHFREE_SECRET_KEY   — from Dashboard → Credentials
  CASHFREE_ENVIRONMENT  — "SANDBOX" for testing, "PRODUCTION" for live

Mock mode: when no credentials configured, returns mock data for local dev.
"""

import hmac
import hashlib
import uuid
import logging
from datetime import datetime, timezone
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.config import settings
from app.models.invoice import Invoice
from app.models.user import User

logger = logging.getLogger("cashfree_service")


def _get_base_url() -> str:
    env = getattr(settings, "CASHFREE_ENVIRONMENT", "SANDBOX").upper()
    if env == "PRODUCTION":
        return "https://api.cashfree.com/pg"
    return "https://sandbox.cashfree.com/pg"


def _get_api_version() -> str:
    return "2023-08-01"


class CashfreeService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.app_id = getattr(settings, "CASHFREE_APP_ID", None)
        self.secret_key = getattr(settings, "CASHFREE_SECRET_KEY", None)
        self.environment = getattr(settings, "CASHFREE_ENVIRONMENT", "SANDBOX")

    @property
    def is_configured(self) -> bool:
        return bool(self.app_id and self.secret_key)

    async def create_checkout_order(self, invoice: Invoice, customer_email: str | None = None, customer_phone: str | None = None) -> dict:
        """
        Creates a Cashfree order for a given invoice.
        Returns the payment session ID needed by the Cashfree.js frontend SDK.
        """
        amount = float(invoice.total_amount or invoice.amount)
        order_id = f"CF-{invoice.invoice_number}-{uuid.uuid4().hex[:6].upper()}"

        if not self.is_configured:
            mock_session_id = f"mock_session_{uuid.uuid4().hex[:16]}"
            metadata = dict(invoice.action_metadata or {})
            metadata["cashfree_order_id"] = order_id
            metadata["cashfree_session_id"] = mock_session_id
            invoice.action_metadata = metadata
            self.db.add(invoice)
            await self.db.commit()
            return {
                "order_id": order_id,
                "payment_session_id": mock_session_id,
                "amount": amount,
                "currency": "INR",
                "gateway": "cashfree",
                "environment": "sandbox",
                "mock": True,
                "app_id": "mock_app_id"
            }

        import httpx
        headers = {
            "x-api-version": _get_api_version(),
            "x-client-id": self.app_id,
            "x-client-secret": self.secret_key,
            "Content-Type": "application/json",
        }

        frontend_url = settings.BACKEND_CORS_ORIGINS[0] if settings.BACKEND_CORS_ORIGINS else "http://localhost:5173"
        payload = {
            "order_id": order_id,
            "order_amount": round(amount, 2),
            "order_currency": "INR",
            "customer_details": {
                "customer_id": str(invoice.organization_id),
                "customer_email": customer_email or "billing@johnsonsoftwares.com",
                "customer_phone": customer_phone or "9880893416",
                "customer_name": "Billing Contact",
            },
            "order_meta": {
                "return_url": f"{frontend_url}/portal/billing?cf_order_id={order_id}",
                "notify_url": f"{frontend_url}/api/v1/billing/cashfree/webhook",
            },
            "order_tags": {
                "invoice_id": str(invoice.id),
                "invoice_number": invoice.invoice_number,
            },
        }

        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{_get_base_url()}/orders",
                    json=payload,
                    headers=headers,
                    timeout=15.0
                )
                if response.status_code not in (200, 201):
                    raise ValueError(f"Cashfree order creation failed: {response.text}")

                res_data = response.json()
                cf_order_id = res_data.get("order_id", order_id)
                payment_session_id = res_data.get("payment_session_id", "")

                metadata = dict(invoice.action_metadata or {})
                metadata["cashfree_order_id"] = cf_order_id
                metadata["cashfree_session_id"] = payment_session_id
                invoice.action_metadata = metadata
                self.db.add(invoice)
                await self.db.commit()

                return {
                    "order_id": cf_order_id,
                    "payment_session_id": payment_session_id,
                    "amount": amount,
                    "currency": "INR",
                    "gateway": "cashfree",
                    "environment": self.environment.lower(),
                    "mock": False,
                    "app_id": self.app_id,
                }
        except Exception as e:
            logger.error(f"Failed to create Cashfree order: {e}")
            raise ValueError(f"Failed to initiate Cashfree checkout: {e}")

    def verify_webhook_signature(self, raw_payload: bytes, timestamp: str, signature: str) -> bool:
        if not self.secret_key:
            return False
        data = f"{timestamp}{raw_payload.decode('utf-8')}"
        expected = hmac.new(
            self.secret_key.encode("utf-8"),
            data.encode("utf-8"),
            hashlib.sha256
        ).hexdigest()
        return hmac.compare_digest(expected, signature)

    async def get_order_status(self, order_id: str) -> dict:
        if not self.is_configured:
            return {"order_status": "PAID", "mock": True}
        import httpx
        headers = {
            "x-api-version": _get_api_version(),
            "x-client-id": self.app_id,
            "x-client-secret": self.secret_key,
        }
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"{_get_base_url()}/orders/{order_id}",
                    headers=headers,
                    timeout=10.0
                )
                if response.status_code == 200:
                    return response.json()
                return {"order_status": "UNKNOWN", "error": response.text}
        except Exception as e:
            return {"order_status": "ERROR", "error": str(e)}

    async def process_webhook(self, event_data: dict) -> bool:
        event_type = event_data.get("type", "")
        data = event_data.get("data", {})
        order_data = data.get("order", {})
        payment_data = data.get("payment", {})

        logger.info(f"Processing Cashfree webhook: {event_type}")

        if event_type == "PAYMENT_SUCCESS":
            cf_order_id = order_data.get("order_id")
            transaction_id = payment_data.get("cf_payment_id") or payment_data.get("bank_reference")

            if not cf_order_id:
                return False

            stmt = select(Invoice).where(Invoice.payment_status == "unpaid", Invoice.is_deleted == False)
            res = await self.db.execute(stmt)
            invoices = res.scalars().all()

            target_invoice = None
            for inv in invoices:
                if inv.action_metadata and inv.action_metadata.get("cashfree_order_id") == cf_order_id:
                    target_invoice = inv
                    break

            if not target_invoice:
                logger.warning(f"No invoice matching Cashfree order {cf_order_id}")
                return False

            user_stmt = select(User).where(
                User.organization_id == target_invoice.organization_id,
                User.is_deleted == False
            )
            user_res = await self.db.execute(user_stmt)
            active_user = user_res.scalars().first()
            actor_user_id = active_user.id if active_user else uuid.UUID(int=0)

            from app.services.portal_service import PortalService
            await PortalService(self.db).pay_invoice(
                organization_id=target_invoice.organization_id,
                invoice_id=target_invoice.id,
                gateway="Cashfree",
                transaction_id=str(transaction_id),
                actor_user_id=actor_user_id,
                actor_name="System / Cashfree Webhook"
            )
            logger.info(f"Cashfree webhook paid invoice {target_invoice.invoice_number}")
            return True

        elif event_type == "PAYMENT_FAILED":
            logger.info(f"Payment failed for Cashfree order: {order_data.get('order_id')}")
            return True

        return False
