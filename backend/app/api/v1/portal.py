import uuid
from typing import Annotated, List
from fastapi import APIRouter, Depends, HTTPException, status, Request, Response
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc

from app.core.database import get_db
from app.dependencies.auth import RoleChecker
from app.models.user import User
from app.models.invoice import Invoice
from app.models.payment import Payment
from app.models.organization import Organization
from app.models.activity import Activity
from app.models.audit_log import AuditLog
from app.models.plan import Plan
from app.schemas.portal import (
    DashboardStatsResponse, PurchaseSeatsRequest, PurchaseStorageRequest, PayInvoiceRequest,
    OrgProfileUpdate, OrgBillingUpdate, OrgNotificationSettingsUpdate, UpgradeSubscriptionRequest
)
from app.schemas.super_admin import PlanResponse
from app.schemas.subscription import SubscriptionDetailsResponse, InvoiceResponse, ReduceSeatsRequest, TenantSubscriptionResponse
from app.schemas.support_ticket import (
    SupportTicketCreate, SupportTicketUpdate, SupportTicketCommentRequest, SupportTicketResponse
)
from app.services.portal_service import PortalService
from app.services.support_ticket_service import SupportTicketService
from app.services.subscription_service import SubscriptionService
from app.services.invoice_pdf import generate_invoice_pdf
from app.services.audit_service import AuditService

router = APIRouter()

@router.get("/stats", response_model=DashboardStatsResponse)
async def get_portal_stats(
    current_user: Annotated[User, Depends(RoleChecker(["OrgAdmin"]))],
    db: Annotated[AsyncSession, Depends(get_db)]
):
    """Retrieves Self Service Portal dashboard stats and metrics."""
    service = PortalService(db)
    stats = await service.get_dashboard_stats(current_user.organization_id)
    return stats

@router.get("/subscription", response_model=SubscriptionDetailsResponse)
async def get_portal_subscription(
    current_user: Annotated[User, Depends(RoleChecker(["OrgAdmin"]))],
    db: Annotated[AsyncSession, Depends(get_db)]
):
    """Retrieves detailed subscription limits and details."""
    service = SubscriptionService(db)
    return await service.get_subscription_details(current_user.organization_id)

@router.post("/subscription/cancel-auto-renew")
async def cancel_auto_renew(
    current_user: Annotated[User, Depends(RoleChecker(["OrgAdmin"]))],
    db: Annotated[AsyncSession, Depends(get_db)]
):
    """Cancels auto-renewal on the active organization subscription."""
    service = SubscriptionService(db)
    sub = await service.get_active_subscription(current_user.organization_id)
    if not sub:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No active subscription found.")
    sub.auto_renew = False
    await db.commit()
    
    # Audit log
    audit = AuditService(db)
    await audit.log_event(
        organization_id=current_user.organization_id,
        actor_user_id=current_user.id,
        action="CANCEL_AUTO_RENEW",
        resource_type="SUBSCRIPTION",
        resource_id=str(sub.id)
    )
    return {"success": True, "message": "Auto renewal successfully cancelled."}

@router.post("/subscription/add-users", response_model=InvoiceResponse)
async def add_user_seats(
    current_user: Annotated[User, Depends(RoleChecker(["OrgAdmin"]))],
    payload: PurchaseSeatsRequest,
    db: Annotated[AsyncSession, Depends(get_db)]
):
    """Generates a pending invoice to purchase additional user seats."""
    service = PortalService(db)
    user_name = f"{current_user.first_name or ''} {current_user.last_name or ''}".strip() or current_user.email
    invoice = await service.buy_extra_seats(
        organization_id=current_user.organization_id,
        actor_user_id=current_user.id,
        actor_name=user_name,
        user_count=payload.user_count,
        gateway=payload.gateway
    )
    return invoice

@router.post("/subscription/reduce-seats", response_model=TenantSubscriptionResponse)
async def reduce_user_seats(
    current_user: Annotated[User, Depends(RoleChecker(["OrgAdmin"]))],
    payload: ReduceSeatsRequest,
    db: Annotated[AsyncSession, Depends(get_db)]
):
    """Schedules a reduction in licensed seats to apply starting from the next billing cycle."""
    service = PortalService(db)
    return await service.reduce_licensed_seats(
        organization_id=current_user.organization_id,
        actor_user_id=current_user.id,
        new_seat_count=payload.new_seat_count
    )

@router.post("/subscription/add-storage", response_model=InvoiceResponse)
async def add_storage_limit(
    current_user: Annotated[User, Depends(RoleChecker(["OrgAdmin"]))],
    payload: PurchaseStorageRequest,
    db: Annotated[AsyncSession, Depends(get_db)]
):
    """Generates a pending invoice to purchase additional GB storage capacity."""
    service = PortalService(db)
    user_name = f"{current_user.first_name or ''} {current_user.last_name or ''}".strip() or current_user.email
    invoice = await service.buy_extra_storage(
        organization_id=current_user.organization_id,
        actor_user_id=current_user.id,
        actor_name=user_name,
        storage_gb=payload.storage_gb,
        gateway=payload.gateway
    )
    return invoice

@router.get("/plans", response_model=List[PlanResponse])
async def list_portal_plans(
    current_user: Annotated[User, Depends(RoleChecker(["OrgAdmin"]))],
    db: Annotated[AsyncSession, Depends(get_db)]
):
    """Retrieves all active plans available for upgrading."""
    stmt = select(Plan).where(
        Plan.is_deleted == False,
        Plan.plan_active == True
    ).order_by(Plan.display_order.asc())
    res = await db.execute(stmt)
    plans = res.scalars().all()
    if not plans:
        # Fallback if plan_active is not yet configured or is false for default plans
        stmt = select(Plan).where(
            Plan.is_deleted == False,
            Plan.is_active == True
        ).order_by(Plan.display_order.asc())
        res = await db.execute(stmt)
        plans = res.scalars().all()
    return plans

@router.post("/subscription/upgrade", response_model=InvoiceResponse)
async def upgrade_tenant_subscription(
    current_user: Annotated[User, Depends(RoleChecker(["OrgAdmin"]))],
    payload: UpgradeSubscriptionRequest,
    db: Annotated[AsyncSession, Depends(get_db)]
):
    """Generates an unpaid upgrade invoice. Once paid, the tenant subscription updates to the new plan."""
    service = PortalService(db)
    user_name = f"{current_user.first_name or ''} {current_user.last_name or ''}".strip() or current_user.email
    invoice = await service.upgrade_subscription(
        organization_id=current_user.organization_id,
        actor_user_id=current_user.id,
        actor_name=user_name,
        plan_id=payload.plan_id,
        billing_cycle=payload.billing_cycle,
        gateway=payload.gateway
    )
    return invoice

@router.get("/invoices", response_model=List[InvoiceResponse])
async def list_portal_invoices(
    current_user: Annotated[User, Depends(RoleChecker(["OrgAdmin"]))],
    db: Annotated[AsyncSession, Depends(get_db)]
):
    """List invoices generated for the tenant organization."""
    stmt = select(Invoice).where(
        Invoice.organization_id == current_user.organization_id,
        Invoice.is_deleted == False
    ).order_by(Invoice.issue_date.desc())
    res = await db.execute(stmt)
    return list(res.scalars().all())

@router.get("/invoices/{invoice_id}/pdf")
async def download_portal_invoice_pdf(
    invoice_id: uuid.UUID,
    current_user: Annotated[User, Depends(RoleChecker(["OrgAdmin"]))],
    db: Annotated[AsyncSession, Depends(get_db)]
):
    """Generates and downloads PDF file stream for a specific invoice."""
    stmt = select(Invoice).where(
        Invoice.id == invoice_id,
        Invoice.organization_id == current_user.organization_id,
        Invoice.is_deleted == False
    )
    res = await db.execute(stmt)
    invoice = res.scalar_one_or_none()
    if not invoice:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Invoice not found.")
    
    pdf_bytes = generate_invoice_pdf(invoice)
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={
            "Content-Disposition": f"attachment; filename=invoice_{invoice.invoice_number}.pdf"
        }
    )

@router.post("/invoices/{invoice_id}/pay", response_model=InvoiceResponse)
async def pay_portal_invoice(
    invoice_id: uuid.UUID,
    current_user: Annotated[User, Depends(RoleChecker(["OrgAdmin"]))],
    payload: PayInvoiceRequest,
    db: Annotated[AsyncSession, Depends(get_db)]
):
    """Simulates or executes invoice payment verification through chosen gateway details."""
    if payload.gateway == "Razorpay":
        if not payload.razorpay_order_id or not payload.razorpay_signature or not payload.transaction_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Missing Razorpay signature verification parameters"
            )
        from app.services.razorpay_service import RazorpayService
        rzp_service = RazorpayService(db)
        if not rzp_service.verify_payment_signature(
            order_id=payload.razorpay_order_id,
            payment_id=payload.transaction_id,
            signature=payload.razorpay_signature
        ):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid Razorpay payment signature"
            )

    service = PortalService(db)
    user_name = f"{current_user.first_name or ''} {current_user.last_name or ''}".strip() or current_user.email
    invoice = await service.pay_invoice(
        organization_id=current_user.organization_id,
        invoice_id=invoice_id,
        gateway=payload.gateway,
        transaction_id=payload.transaction_id,
        actor_user_id=current_user.id,
        actor_name=user_name
    )
    return invoice

@router.post("/invoices/{invoice_id}/checkout")
async def create_razorpay_checkout_order(
    invoice_id: uuid.UUID,
    current_user: Annotated[User, Depends(RoleChecker(["OrgAdmin"]))],
    db: Annotated[AsyncSession, Depends(get_db)]
):
    """Initiates checkout order session with Razorpay Payment Gateway."""
    from app.services.razorpay_service import RazorpayService
    
    # Verify invoice exists and belongs to organization
    stmt = select(Invoice).where(
        Invoice.id == invoice_id,
        Invoice.organization_id == current_user.organization_id,
        Invoice.is_deleted == False
    )
    res = await db.execute(stmt)
    invoice = res.scalar_one_or_none()
    
    if not invoice:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Invoice not found."
        )
        
    if invoice.payment_status == "paid":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invoice is already paid."
        )
        
    rzp_service = RazorpayService(db)
    order_data = await rzp_service.create_checkout_order(invoice)
    return order_data


@router.get("/payments")
async def list_portal_payments(
    current_user: Annotated[User, Depends(RoleChecker(["OrgAdmin"]))],
    db: Annotated[AsyncSession, Depends(get_db)]
):
    """Retrieves payment transactions history log."""
    stmt = select(Payment).join(Invoice).where(
        Invoice.organization_id == current_user.organization_id
    ).order_by(desc(Payment.paid_date))
    res = await db.execute(stmt)
    
    payments = res.scalars().all()
    return [{
        "id": str(p.id),
        "amount": float(p.invoice.amount),
        "invoice_number": p.invoice.invoice_number,
        "gateway": p.gateway,
        "status": p.status,
        "transaction_id": p.transaction_id,
        "paid_date": p.paid_date.isoformat() if p.paid_date else None,
        "remarks": p.remarks
    } for p in payments]

@router.put("/profile")
async def update_portal_profile(
    payload: OrgProfileUpdate,
    request: Request,
    current_user: Annotated[User, Depends(RoleChecker(["OrgAdmin"]))],
    db: Annotated[AsyncSession, Depends(get_db)]
):
    """Updates Organization profile parameters and saves diff change-log audits."""
    stmt = select(Organization).where(Organization.id == current_user.organization_id)
    res = await db.execute(stmt)
    org = res.scalar_one_or_none()
    if not org:
        raise HTTPException(status_code=404, detail="Organization not found.")

    diffs = {}
    ip = request.client.host if request.client else "unknown"
    ua = request.headers.get("user-agent", "unknown")

    for key, value in payload.model_dump(exclude_unset=True).items():
        old_val = getattr(org, key)
        if old_val != value:
            diffs[key] = {"old": old_val, "new": value}
            setattr(org, key, value)

    if diffs:
        await db.commit()
        await db.refresh(org)
        
        audit = AuditService(db)
        await audit.log_event(
            organization_id=current_user.organization_id,
            actor_user_id=current_user.id,
            action="UPDATE_PROFILE",
            resource_type="ORGANIZATION",
            resource_id=str(org.id),
            action_metadata={"changes": diffs, "ip": ip, "user_agent": ua}
        )

    return org

@router.put("/billing")
async def update_portal_billing(
    payload: OrgBillingUpdate,
    request: Request,
    current_user: Annotated[User, Depends(RoleChecker(["OrgAdmin"]))],
    db: Annotated[AsyncSession, Depends(get_db)]
):
    """Updates Organization billing parameters and logs change comparative details."""
    stmt = select(Organization).where(Organization.id == current_user.organization_id)
    res = await db.execute(stmt)
    org = res.scalar_one_or_none()
    if not org:
        raise HTTPException(status_code=404, detail="Organization not found.")

    diffs = {}
    ip = request.client.host if request.client else "unknown"
    ua = request.headers.get("user-agent", "unknown")

    for key, value in payload.model_dump(exclude_unset=True).items():
        old_val = getattr(org, key)
        if old_val != value:
            diffs[key] = {"old": old_val, "new": value}
            setattr(org, key, value)

    if diffs:
        await db.commit()
        await db.refresh(org)

        audit = AuditService(db)
        await audit.log_event(
            organization_id=current_user.organization_id,
            actor_user_id=current_user.id,
            action="UPDATE_BILLING",
            resource_type="ORGANIZATION",
            resource_id=str(org.id),
            action_metadata={"changes": diffs, "ip": ip, "user_agent": ua}
        )

    return org

@router.put("/settings")
async def update_portal_settings(
    payload: OrgNotificationSettingsUpdate,
    current_user: Annotated[User, Depends(RoleChecker(["OrgAdmin"]))],
    db: Annotated[AsyncSession, Depends(get_db)]
):
    """Updates Organization notification settings preferences."""
    stmt = select(Organization).where(Organization.id == current_user.organization_id)
    res = await db.execute(stmt)
    org = res.scalar_one_or_none()
    if not org:
        raise HTTPException(status_code=404, detail="Organization not found.")

    org.notification_invoice_emails = payload.notification_invoice_emails
    org.notification_renewal_emails = payload.notification_renewal_emails
    org.notification_support_emails = payload.notification_support_emails
    org.auto_renewal = payload.auto_renewal
    org.theme = payload.theme
    await db.commit()

    return {"success": True, "message": "Notification and portal settings preferences updated."}

@router.get("/usage")
async def get_portal_usage(
    current_user: Annotated[User, Depends(RoleChecker(["OrgAdmin"]))],
    db: Annotated[AsyncSession, Depends(get_db)]
):
    """Aggregates leads, calls counts, import counts, and storage metrics."""
    # Lead count
    from app.models.lead import Lead
    lead_stmt = select(func.count(Lead.id)).where(Lead.organization_id == current_user.organization_id, Lead.is_deleted == False)
    lead_res = await db.execute(lead_stmt)
    lead_count = lead_res.scalar() or 0

    # Calls count
    call_stmt = select(func.count(Activity.id)).where(
        Activity.organization_id == current_user.organization_id,
        Activity.activity_type == "Call",
        Activity.is_deleted == False
    )
    call_res = await db.execute(call_stmt)
    call_count = call_res.scalar() or 0

    # Imports count
    from app.models.lead_import import LeadImport
    import_stmt = select(func.count(LeadImport.id)).where(LeadImport.organization_id == current_user.organization_id)
    import_res = await db.execute(import_stmt)
    import_count = import_res.scalar() or 0

    # Active seats
    user_stmt = select(func.count(User.id)).where(User.organization_id == current_user.organization_id, User.is_deleted == False)
    user_res = await db.execute(user_stmt)
    active_seats = user_res.scalar() or 0

    return {
        "active_seats": active_seats,
        "total_leads": lead_count,
        "total_calls": call_count,
        "total_imports": import_count
    }

@router.get("/recordings")
async def list_portal_recordings(
    current_user: Annotated[User, Depends(RoleChecker(["OrgAdmin"]))],
    db: Annotated[AsyncSession, Depends(get_db)]
):
    """Retrieves call activity list containing active recording URLs."""
    stmt = select(Activity).where(
        Activity.organization_id == current_user.organization_id,
        Activity.recording_url.is_not(None),
        Activity.is_deleted == False
    ).order_by(desc(Activity.due_date))
    res = await db.execute(stmt)
    activities = res.scalars().all()
    
    return [{
        "id": str(act.id),
        "recording_url": act.recording_url,
        "duration": act.call_duration or 0,
        "direction": act.call_direction or "inbound",
        "subject": act.subject,
        "date": act.created_at.isoformat(),
        "assigned_user": f"{act.assigned_user_id or 'System'}"
    } for act in activities]

@router.delete("/recordings/{recording_id}")
async def delete_portal_recording(
    recording_id: uuid.UUID,
    current_user: Annotated[User, Depends(RoleChecker(["OrgAdmin"]))],
    db: Annotated[AsyncSession, Depends(get_db)]
):
    """Deletes/revokes a call recording url reference from activity."""
    stmt = select(Activity).where(
        Activity.id == recording_id,
        Activity.organization_id == current_user.organization_id,
        Activity.is_deleted == False
    )
    res = await db.execute(stmt)
    act = res.scalar_one_or_none()
    if not act:
        raise HTTPException(status_code=404, detail="Recording activity reference not found.")

    act.recording_url = None
    await db.commit()
    return {"success": True, "message": "Recording successfully deleted."}

# Support tickets API
@router.get("/support", response_model=List[SupportTicketResponse])
async def list_support_tickets(
    current_user: Annotated[User, Depends(RoleChecker(["OrgAdmin"]))],
    db: Annotated[AsyncSession, Depends(get_db)]
):
    """List support tickets for organization."""
    service = SupportTicketService(db)
    return await service.list_tickets(current_user.organization_id)

@router.post("/support", response_model=SupportTicketResponse)
async def create_support_ticket(
    payload: SupportTicketCreate,
    current_user: Annotated[User, Depends(RoleChecker(["OrgAdmin"]))],
    db: Annotated[AsyncSession, Depends(get_db)]
):
    """Create a new support ticket."""
    service = SupportTicketService(db)
    actor_name = f"{current_user.first_name or ''} {current_user.last_name or ''}".strip() or current_user.email
    return await service.create_ticket(
        organization_id=current_user.organization_id,
        user_id=current_user.id,
        actor_name=actor_name,
        payload=payload
    )

@router.get("/support/{ticket_id}", response_model=SupportTicketResponse)
async def get_support_ticket(
    ticket_id: uuid.UUID,
    current_user: Annotated[User, Depends(RoleChecker(["OrgAdmin"]))],
    db: Annotated[AsyncSession, Depends(get_db)]
):
    """Retrieve details for a single support ticket."""
    service = SupportTicketService(db)
    return await service.get_ticket(current_user.organization_id, ticket_id)

@router.post("/support/{ticket_id}/comment", response_model=SupportTicketResponse)
async def comment_on_support_ticket(
    ticket_id: uuid.UUID,
    payload: SupportTicketCommentRequest,
    current_user: Annotated[User, Depends(RoleChecker(["OrgAdmin"]))],
    db: Annotated[AsyncSession, Depends(get_db)]
):
    """Post comment reply in a ticket thread."""
    service = SupportTicketService(db)
    actor_name = f"{current_user.first_name or ''} {current_user.last_name or ''}".strip() or current_user.email
    return await service.add_comment(
        organization_id=current_user.organization_id,
        ticket_id=ticket_id,
        actor_name=actor_name,
        content=payload.content
    )

@router.get("/activity-logs")
async def list_portal_activity_logs(
    current_user: Annotated[User, Depends(RoleChecker(["OrgAdmin"]))],
    db: Annotated[AsyncSession, Depends(get_db)]
):
    """Fetch organization audit change logs trail."""
    stmt = select(AuditLog).where(
        AuditLog.organization_id == current_user.organization_id
    ).order_by(desc(AuditLog.created_at))
    res = await db.execute(stmt)
    logs = res.scalars().all()
    
    return [{
        "id": str(log.id),
        "action": log.action,
        "resource_type": log.resource_type,
        "resource_id": log.resource_id,
        "created_at": log.created_at.isoformat(),
        "metadata": log.action_metadata or {}
    } for log in logs]
