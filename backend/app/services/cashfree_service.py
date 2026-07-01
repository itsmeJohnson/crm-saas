import hmac
import hashlib
import base64
import uuid
import logging
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.config import settings
from app.models.invoice import Invoice
from app.models.user import User
from app.services.portal_service import PortalService

logger = logging.getLogger("cashfree_service")

# Cashfree PG API (2023-08-01)
_API_VERSION = "2023-08-01"


class CashfreeService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.app_id = settings.CASHFREE_APP_ID
        self.secret_key = settings.CASHFREE_SECRET_KEY
        self.webhook_secret = settings.CASHFREE_WEBHOOK_SECRET or settings.CASHFREE_SECRET_KEY

    @property
    def base_url(self) -> str:
        env = (settings.CASHFREE_ENV or "sandbox").lower()
        return "https://api.cashfree.com/pg" if env == "production" else "https://sandbox.cashfree.com/pg"

    def _headers(self) -> dict:
        return {
            "x-client-id": self.app_id or "",
            "x-client-secret": self.secret_key or "",
            "x-api-version": _API_VERSION,
            "Content-Type": "application/json",
        }

    async def create_checkout_order(self, invoice: Invoice, customer: User) -> dict:
        """Create a Cashfree order and stash cf_order_id on the invoice metadata."""
        if not self.app_id or not self.secret_key:
            raise ValueError("Cashfree is not configured. Set CASHFREE_APP_ID and CASHFREE_SECRET_KEY.")

        amount = float(invoice.total_amount or invoice.amount)
        # Unique per checkout attempt. A deterministic id would collide with a
        # previously-created order when the user retries "Pay Now" on the same
        # invoice (Cashfree rejects duplicates with order_already_exists).
        order_id = f"CF-{invoice.invoice_number}"[:40] + "-" + uuid.uuid4().hex[:6]

        import httpx
        payload = {
            "order_id": order_id,
            "order_amount": round(amount, 2),
            "order_currency": invoice.currency or "INR",
            "customer_details": {
                "customer_id": str(customer.id),
                "customer_email": customer.email,
                "customer_phone": (customer.phone or "9999999999") if hasattr(customer, "phone") else "9999999999",
            },
            "order_note": f"Invoice {invoice.invoice_number}",
        }
        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                resp = await client.post(f"{self.base_url}/orders", json=payload, headers=self._headers())
                if resp.status_code not in (200, 201):
                    logger.error("Cashfree order creation failed: %s", resp.text)
                    raise ValueError(f"Cashfree order creation failed: {resp.text}")
                data = resp.json()
        except ValueError:
            raise
        except Exception as e:
            logger.error("Failed to create Cashfree order: %s", e)
            raise ValueError(f"Failed to initiate Cashfree checkout: {e}")

        metadata = dict(invoice.action_metadata or {})
        metadata["cashfree_order_id"] = order_id
        invoice.action_metadata = metadata
        self.db.add(invoice)
        await self.db.commit()

        return {
            "cf_order_id": data.get("cf_order_id"),
            "order_id": order_id,
            "payment_session_id": data.get("payment_session_id"),
            "order_amount": amount,
            "order_currency": invoice.currency or "INR",
            "env": (settings.CASHFREE_ENV or "sandbox").lower(),
        }

    async def is_order_paid(self, order_id: str) -> bool:
        """Server-to-server verification: ask Cashfree whether the order is actually PAID.

        This does NOT trust any client-supplied flag — it queries Cashfree directly.
        """
        if not self.app_id or not self.secret_key:
            return False
        import httpx
        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                resp = await client.get(f"{self.base_url}/orders/{order_id}", headers=self._headers())
                if resp.status_code != 200:
                    logger.error("Cashfree get-order failed (%s): %s", resp.status_code, resp.text)
                    return False
                data = resp.json()
                return data.get("order_status") == "PAID"
        except Exception as e:
            logger.error("Cashfree get-order error: %s", e)
            return False

    def verify_webhook_signature(self, raw_payload: bytes, signature: str, timestamp: str) -> bool:
        """Cashfree webhook signature = base64(HMAC-SHA256(timestamp + rawBody, secret))."""
        if not self.webhook_secret or not signature or not timestamp:
            return False
        signed = (timestamp.encode("utf-8") + raw_payload)
        digest = hmac.new(self.webhook_secret.encode("utf-8"), signed, hashlib.sha256).digest()
        expected = base64.b64encode(digest).decode("utf-8")
        return hmac.compare_digest(expected, signature)

    async def process_webhook(self, event_data: dict) -> bool:
        """Handle a verified Cashfree webhook. Marks the matching invoice paid on success."""
        data = event_data.get("data", {})
        order = data.get("order", {})
        payment = data.get("payment", {})
        order_id = order.get("order_id")
        payment_status = payment.get("payment_status")

        if not order_id or payment_status != "SUCCESS":
            logger.info("Cashfree webhook ignored (order_id=%s, status=%s)", order_id, payment_status)
            return False

        # Match invoice by the order id stashed at checkout
        stmt = select(Invoice).where(Invoice.payment_status == "unpaid", Invoice.is_deleted == False)
        res = await self.db.execute(stmt)
        target = None
        for inv in res.scalars().all():
            if inv.action_metadata and inv.action_metadata.get("cashfree_order_id") == order_id:
                target = inv
                break
        if not target:
            logger.warning("No pending invoice matches Cashfree order %s", order_id)
            return False

        user_res = await self.db.execute(
            select(User).where(User.organization_id == target.organization_id, User.is_deleted == False)
        )
        actor = user_res.scalars().first()
        actor_id = actor.id if actor else uuid.UUID(int=0)

        portal_service = PortalService(self.db)
        await portal_service.pay_invoice(
            organization_id=target.organization_id,
            invoice_id=target.id,
            gateway="Cashfree",
            transaction_id=payment.get("cf_payment_id") or order_id,
            actor_user_id=actor_id,
            actor_name="System / Cashfree Webhook",
        )
        logger.info("Cashfree webhook paid invoice %s", target.invoice_number)
        return True
