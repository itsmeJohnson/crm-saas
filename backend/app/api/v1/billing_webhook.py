import json
import logging
from fastapi import APIRouter, Request, HTTPException, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.database import get_db
from app.services.razorpay_service import RazorpayService

logger = logging.getLogger("billing_webhook")
router = APIRouter()

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
