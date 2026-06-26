import json
import logging
import uuid
from fastapi import APIRouter, Request, HTTPException, Depends, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.database import get_db
from app.core.security import get_current_user
from app.models.user import User
from app.models.invoice import Invoice
from app.services.razorpay_service import RazorpayService
from app.services.cashfree_service import CashfreeService

logger = logging.getLogger("billing_webhook")
router = APIRouter()


# ─────────────────────────────────────────────────────────────────────────────
# Razorpay (kept as secondary gateway)
# ─────────────────────────────────────────────────────────────────────────────

@router.post("/razorpay")
async def razorpay_webhook(
    request: Request,
    db: AsyncSession = Depends(get_db)
):
    """
    Handle background webhook events sent by Razorpay.
    Verifies signature header and processes invoices/refunds.
    """
    body = await request.body()
    signature = request.headers.get("X-Razorpay-Signature")

    if not signature:
        logger.error("Missing X-Razorpay-Signature header")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Missing signature header"
        )

    rzp_service = RazorpayService(db)

    # Cryptographic signature validation
    if not rzp_service.verify_webhook_signature(body, signature):
        logger.error("Invalid webhook signature verification failed")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid signature"
        )

    try:
        event_data = json.loads(body.decode("utf-8"))
    except Exception as e:
        logger.error(f"Failed to parse JSON body from webhook: {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid JSON payload"
        )

    processed = await rzp_service.process_webhook(event_data)

    if not processed:
        return {"status": "skipped", "reason": "event ignored or target invoice not found"}

    return {"status": "processed"}


# ─────────────────────────────────────────────────────────────────────────────
# Cashfree (primary gateway — UDYAM-compatible, no GST required)
# ─────────────────────────────────────────────────────────────────────────────

@router.post("/cashfree/create-order/{invoice_id}")
async def cashfree_create_order(
    invoice_id: uuid.UUID,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Creates a Cashfree payment order for the given invoice.
    Called by the tenant billing UI before loading Cashfree.js checkout.
    Returns payment_session_id which Cashfree.js uses to render the payment modal.
    """
    stmt = select(Invoice).where(
        Invoice.id == invoice_id,
        Invoice.organization_id == current_user.organization_id,
        Invoice.is_deleted == False,
    )
    res = await db.execute(stmt)
    invoice = res.scalar_one_or_none()

    if not invoice:
        raise HTTPException(status_code=404, detail="Invoice not found")
    if invoice.payment_status == "paid":
        raise HTTPException(status_code=400, detail="Invoice is already paid")

    cf_service = CashfreeService(db)
    result = await cf_service.create_checkout_order(
        invoice=invoice,
        customer_email=current_user.email,
        customer_phone=getattr(current_user, "phone", None),
    )
    return result


@router.get("/cashfree/verify/{order_id}")
async def cashfree_verify_payment(
    order_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Verifies payment status after Cashfree redirect.
    Called from the return_url the frontend receives after payment.
    """
    cf_service = CashfreeService(db)
    status_data = await cf_service.get_order_status(order_id)
    order_status = status_data.get("order_status", "UNKNOWN")
    return {
        "order_id": order_id,
        "order_status": order_status,
        "paid": order_status in ("PAID", "PARTIAL"),
    }


@router.post("/cashfree/webhook")
async def cashfree_webhook(
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """
    Handles async webhook events from Cashfree.
    Configure in Cashfree Dashboard → Webhooks → Payment Events.
    URL: https://yourdomain.com/api/v1/billing/cashfree/webhook
    """
    body = await request.body()
    timestamp = request.headers.get("x-webhook-timestamp", "")
    signature = request.headers.get("x-webhook-signature", "")

    cf_service = CashfreeService(db)

    # Skip signature verification in mock/sandbox dev mode
    if cf_service.is_configured and signature:
        if not cf_service.verify_webhook_signature(body, timestamp, signature):
            logger.error("Cashfree webhook: invalid signature")
            raise HTTPException(status_code=400, detail="Invalid webhook signature")

    try:
        event_data = json.loads(body.decode("utf-8"))
    except Exception as e:
        logger.error(f"Cashfree webhook: invalid JSON — {e}")
        raise HTTPException(status_code=400, detail="Invalid JSON payload")

    processed = await cf_service.process_webhook(event_data)

    if not processed:
        return {"status": "skipped"}

    return {"status": "processed"}
