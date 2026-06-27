import uuid
from typing import Annotated, List
from fastapi import APIRouter, Depends, HTTPException, status, Response
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.core.database import get_db
from app.dependencies.auth import RoleChecker
from app.models.user import User
from app.models.invoice import Invoice
from app.schemas.subscription import SubscriptionDetailsResponse, SubscriptionRenewResponse, InvoiceResponse
from app.services.subscription_service import SubscriptionService
from app.services.invoice_pdf import generate_invoice_pdf

router = APIRouter()

@router.get("/subscription", response_model=SubscriptionDetailsResponse)
async def get_tenant_subscription(
    current_user: Annotated[User, Depends(RoleChecker(["OrgAdmin"]))],
    db: Annotated[AsyncSession, Depends(get_db)]
):
    """Retrieves current subscription status, plan limits, and user usage meters."""
    service = SubscriptionService(db)
    return await service.get_subscription_details(current_user.organization_id)

@router.post("/subscription/renew", response_model=SubscriptionRenewResponse)
async def renew_tenant_subscription(
    current_user: Annotated[User, Depends(RoleChecker(["OrgAdmin"]))],
    db: Annotated[AsyncSession, Depends(get_db)]
):
    """Extends the current tenant subscription by plan billing cycle days and generates paid invoice."""
    service = SubscriptionService(db)
    sub = await service.renew_subscription(current_user.organization_id)
    return {
        "success": True,
        "message": "Subscription renewed successfully.",
        "new_end_date": sub.end_date
    }

@router.get("/invoices", response_model=List[InvoiceResponse])
async def list_tenant_invoices(
    current_user: Annotated[User, Depends(RoleChecker(["OrgAdmin"]))],
    db: Annotated[AsyncSession, Depends(get_db)]
):
    """Lists all billing invoices generated for the tenant organization."""
    stmt = select(Invoice).where(
        Invoice.organization_id == current_user.organization_id,
        Invoice.is_deleted == False
    ).order_by(Invoice.issue_date.desc())
    
    res = await db.execute(stmt)
    return list(res.scalars().all())

@router.get("/invoices/{invoice_id}/pdf")
async def download_invoice_pdf(
    invoice_id: uuid.UUID,
    current_user: Annotated[User, Depends(RoleChecker(["OrgAdmin"]))],
    db: Annotated[AsyncSession, Depends(get_db)]
):
    """Generates and streams the PDF file for a specific tenant invoice."""
    stmt = select(Invoice).where(
        Invoice.id == invoice_id,
        Invoice.organization_id == current_user.organization_id,
        Invoice.is_deleted == False
    ).options(selectinload(Invoice.organization))
    res = await db.execute(stmt)
    invoice = res.scalar_one_or_none()

    if not invoice:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Invoice not found."
        )
        
    pdf_bytes = generate_invoice_pdf(invoice)
    
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={
            "Content-Disposition": f"attachment; filename=invoice_{invoice.invoice_number}.pdf"
        }
    )
