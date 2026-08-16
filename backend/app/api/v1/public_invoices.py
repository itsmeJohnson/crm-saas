"""Public, no-login invoice PDF access via an unguessable HMAC signature.
Used for WhatsApp-shared invoice links: the patient opens the link and gets
the PDF without needing a CRM account. The signature (not the invoice id
alone) is what authorizes access."""
import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status, Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.services.customer_service import CustomerService, verify_invoice_sig

router = APIRouter()


@router.get("/invoices/{invoice_id}/{sig}/pdf")
async def public_invoice_pdf(
    invoice_id: uuid.UUID,
    sig: str,
    db: Annotated[AsyncSession, Depends(get_db)],
):
    if not verify_invoice_sig(invoice_id, sig):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Invalid or expired link")
    pdf = await CustomerService(db).render_invoice_pdf_by_id(invoice_id)
    return Response(
        content=pdf,
        media_type="application/pdf",
        headers={"Content-Disposition": f"inline; filename=invoice_{invoice_id}.pdf"},
    )
