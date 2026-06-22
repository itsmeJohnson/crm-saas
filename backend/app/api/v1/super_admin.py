import uuid
import secrets
from datetime import datetime, timezone
from typing import Annotated, List
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, delete

from app.core.database import get_db
from app.models.organization import Organization
from app.models.user import User
from app.models.invoice import Invoice
from app.dependencies.auth import get_current_active_user, RoleChecker
from app.schemas.super_admin import (
    SubscriptionUpdateRequest, TenantResponse, TenantUserResponse,
    TenantInvoiceResponse, InvoiceCreateRequest
)
from app.services.auth_service import AuthService
from app.schemas.auth import RegisterTenantRequest

router = APIRouter()
require_super_admin = RoleChecker(["SuperAdmin"])

@router.get("/tenants", response_model=List[TenantResponse])
async def list_tenants(
    actor: Annotated[User, Depends(require_super_admin)],
    db: Annotated[AsyncSession, Depends(get_db)]
):
    """List all tenant organizations in the system with user and invoice counts."""
    # Subquery for user count
    user_sub = select(
        User.organization_id, 
        func.count(User.id).label("cnt")
    ).where(User.is_deleted == False).group_by(User.organization_id).subquery()

    # Subquery for invoice count
    inv_sub = select(
        Invoice.organization_id, 
        func.count(Invoice.id).label("cnt")
    ).group_by(Invoice.organization_id).subquery()

    query = select(
        Organization,
        func.coalesce(user_sub.c.cnt, 0).label("user_count"),
        func.coalesce(inv_sub.c.cnt, 0).label("invoice_count")
    ).outerjoin(
        user_sub, Organization.id == user_sub.c.organization_id
    ).outerjoin(
        inv_sub, Organization.id == inv_sub.c.organization_id
    ).where(Organization.is_deleted == False)

    res = await db.execute(query)
    results = []
    for org, u_cnt, i_cnt in res.all():
        results.append(
            TenantResponse(
                id=org.id,
                name=org.name,
                slug=org.slug,
                is_active=org.is_active,
                subscription_plan=org.subscription_plan,
                subscription_expires_at=org.subscription_expires_at,
                subscription_status=org.subscription_status,
                max_users=org.max_users,
                user_count=u_cnt,
                invoice_count=i_cnt
            )
        )
    return results

@router.post("/tenants", response_model=TenantResponse, status_code=status.HTTP_201_CREATED)
async def create_tenant(
    payload: RegisterTenantRequest,
    actor: Annotated[User, Depends(require_super_admin)],
    db: Annotated[AsyncSession, Depends(get_db)]
):
    """Create a new tenant organization and its owner admin user."""
    auth_service = AuthService(db)
    user, org = await auth_service.register_tenant(payload)
    
    return TenantResponse(
        id=org.id,
        name=org.name,
        slug=org.slug,
        is_active=org.is_active,
        subscription_plan=org.subscription_plan,
        subscription_expires_at=org.subscription_expires_at,
        subscription_status=org.subscription_status,
        max_users=org.max_users,
        user_count=1,
        invoice_count=0
    )

@router.get("/tenants/{org_id}/users", response_model=List[TenantUserResponse])
async def list_tenant_users(
    org_id: uuid.UUID,
    actor: Annotated[User, Depends(require_super_admin)],
    db: Annotated[AsyncSession, Depends(get_db)]
):
    """Get all users registered under a specific tenant."""
    query = select(User).where(User.organization_id == org_id, User.is_deleted == False)
    res = await db.execute(query)
    users = res.scalars().all()
    return [
        TenantUserResponse(
            id=u.id,
            email=u.email,
            first_name=u.first_name,
            last_name=u.last_name,
            role=u.role,
            is_active=u.is_active
        ) for u in users
    ]

@router.put("/tenants/{org_id}/subscription", response_model=TenantResponse)
async def update_tenant_subscription(
    org_id: uuid.UUID,
    payload: SubscriptionUpdateRequest,
    actor: Annotated[User, Depends(require_super_admin)],
    db: Annotated[AsyncSession, Depends(get_db)]
):
    """Update tenant organization's plan, status, user limits, and expiration date."""
    org = await db.get(Organization, org_id)
    if not org or org.is_deleted:
        raise HTTPException(status_code=404, detail="Tenant organization not found")
    
    org.subscription_plan = payload.subscription_plan
    org.subscription_status = payload.subscription_status
    org.max_users = payload.max_users
    
    expires_at = payload.subscription_expires_at
    if expires_at and expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=timezone.utc)
    org.subscription_expires_at = expires_at
    
    await db.commit()
    
    # Get counts
    user_count_query = select(func.count(User.id)).where(User.organization_id == org_id, User.is_deleted == False)
    invoice_count_query = select(func.count(Invoice.id)).where(Invoice.organization_id == org_id)
    
    u_res = await db.execute(user_count_query)
    i_res = await db.execute(invoice_count_query)
    
    return TenantResponse(
        id=org.id,
        name=org.name,
        slug=org.slug,
        is_active=org.is_active,
        subscription_plan=org.subscription_plan,
        subscription_expires_at=org.subscription_expires_at,
        subscription_status=org.subscription_status,
        max_users=org.max_users,
        user_count=u_res.scalar() or 0,
        invoice_count=i_res.scalar() or 0
    )

@router.get("/tenants/{org_id}/invoices", response_model=List[TenantInvoiceResponse])
async def list_tenant_invoices(
    org_id: uuid.UUID,
    actor: Annotated[User, Depends(require_super_admin)],
    db: Annotated[AsyncSession, Depends(get_db)]
):
    """List billing invoices for a specific tenant organization."""
    query = select(Invoice).where(Invoice.organization_id == org_id, Invoice.is_deleted == False).order_by(Invoice.created_at.desc())
    res = await db.execute(query)
    invoices = res.scalars().all()
    return [
        TenantInvoiceResponse(
            id=i.id,
            invoice_number=i.invoice_number,
            amount=float(i.amount),
            status=i.status,
            due_date=i.due_date,
            created_at=i.created_at
        ) for i in invoices
    ]

@router.post("/tenants/{org_id}/invoices", response_model=TenantInvoiceResponse)
async def create_tenant_invoice(
    org_id: uuid.UUID,
    payload: InvoiceCreateRequest,
    actor: Annotated[User, Depends(require_super_admin)],
    db: Annotated[AsyncSession, Depends(get_db)]
):
    """Generate a new billing invoice for a specific tenant organization."""
    org = await db.get(Organization, org_id)
    if not org or org.is_deleted:
        raise HTTPException(status_code=404, detail="Tenant organization not found")
        
    # Generate invoice number
    rand_suffix = secrets.token_hex(4).upper()
    invoice_number = f"INV-{datetime.now().year}-{rand_suffix}"
    
    due_date = payload.due_date
    if due_date.tzinfo is None:
        due_date = due_date.replace(tzinfo=timezone.utc)
        
    invoice = Invoice(
        organization_id=org_id,
        invoice_number=invoice_number,
        amount=payload.amount,
        status=payload.status,
        due_date=due_date,
        created_at=datetime.now(timezone.utc)
    )
    
    db.add(invoice)
    await db.commit()
    await db.refresh(invoice)
    
    return TenantInvoiceResponse(
        id=invoice.id,
        invoice_number=invoice.invoice_number,
        amount=float(invoice.amount),
        status=invoice.status,
        due_date=invoice.due_date,
        created_at=invoice.created_at
    )

@router.patch("/invoices/{invoice_id}", response_model=TenantInvoiceResponse)
async def update_invoice_status(
    invoice_id: uuid.UUID,
    status_val: str,
    actor: Annotated[User, Depends(require_super_admin)],
    db: Annotated[AsyncSession, Depends(get_db)]
):
    """Change paid/pending/overdue status of an invoice."""
    invoice = await db.get(Invoice, invoice_id)
    if not invoice or invoice.is_deleted:
        raise HTTPException(status_code=404, detail="Invoice not found")
        
    invoice.status = status_val
    await db.commit()
    await db.refresh(invoice)
    
    return TenantInvoiceResponse(
        id=invoice.id,
        invoice_number=invoice.invoice_number,
        amount=float(invoice.amount),
        status=invoice.status,
        due_date=invoice.due_date,
        created_at=invoice.created_at
    )


@router.post("/notifications/send-renewal-alerts")
async def send_manual_renewal_alert(
    org_id: uuid.UUID,
    actor: Annotated[User, Depends(require_super_admin)],
    db: Annotated[AsyncSession, Depends(get_db)]
):
    """Sends a manual subscription renewal reminder email to the tenant owner admin."""
    org = await db.get(Organization, org_id)
    if not org or org.is_deleted:
        raise HTTPException(status_code=404, detail="Tenant organization not found")
        
    stmt_admin = select(User).where(
        User.organization_id == org_id,
        User.role == "OrgAdmin",
        User.is_deleted == False
    )
    res_admin = await db.execute(stmt_admin)
    admin_user = res_admin.scalar_one_or_none()
    
    if not admin_user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No active OrgAdmin found for this tenant."
        )

    from app.services.subscription_service import SubscriptionService
    from app.services.email_service import send_email

    service = SubscriptionService(db)
    sub = await service.get_active_subscription(org_id)
    
    amount = str(sub.plan.price_inr) if (sub and sub.plan) else "0.00"
    plan_name = sub.plan.name if (sub and sub.plan) else org.subscription_plan
    renewal_date = org.subscription_expires_at.strftime("%B %d, %Y") if org.subscription_expires_at else "N/A"

    send_email(
        to_email=admin_user.email,
        subject="Subscription Renewal Reminder",
        template_name="renewal_reminder.html",
        context={
            "org_name": org.name,
            "plan_name": plan_name,
            "renewal_date": renewal_date,
            "amount": amount
        }
    )
    return {"success": True, "message": f"Renewal alert sent to {admin_user.email}"}


@router.patch("/tenants/{org_id}/subscription", response_model=TenantResponse)
async def toggle_tenant_subscription_status(
    org_id: uuid.UUID,
    actor: Annotated[User, Depends(require_super_admin)],
    db: Annotated[AsyncSession, Depends(get_db)],
    status_val: str | None = None
):
    """Toggles or sets the subscription status (active/suspended) of a tenant organization."""
    org = await db.get(Organization, org_id)
    if not org or org.is_deleted:
        raise HTTPException(status_code=404, detail="Tenant organization not found")
        
    if status_val:
        if status_val not in ["active", "suspended"]:
            raise HTTPException(status_code=400, detail="Status must be active or suspended")
        org.subscription_status = status_val
    else:
        # Toggle
        org.subscription_status = "suspended" if org.subscription_status != "suspended" else "active"
        
    # Update TenantSubscription model as well
    stmt = select(TenantSubscription).where(TenantSubscription.organization_id == org_id)
    res = await db.execute(stmt)
    sub = res.scalar_one_or_none()
    if sub:
        sub.status = org.subscription_status
        
    await db.commit()
    
    # Send email notification if suspended or active
    stmt_admin = select(User).where(
        User.organization_id == org_id,
        User.role == "OrgAdmin",
        User.is_deleted == False
    )
    res_admin = await db.execute(stmt_admin)
    admin_user = res_admin.scalar_one_or_none()
    if admin_user:
        from app.services.email_service import send_email
        if org.subscription_status == "suspended":
            send_email(
                to_email=admin_user.email,
                subject="Account Suspended",
                template_name="account_suspended.html",
                context={
                    "org_name": org.name,
                    "support_email": "support@telecrm-saas.com"
                }
            )
        else:
            send_email(
                to_email=admin_user.email,
                subject="Account Reinstated",
                template_name="trial_started.html",
                context={
                    "org_name": org.name,
                    "trial_end_date": org.subscription_expires_at.strftime("%B %d, %Y") if org.subscription_expires_at else "N/A",
                    "max_users": org.max_users
                }
            )
            
    # Get counts
    user_count_query = select(func.count(User.id)).where(User.organization_id == org_id, User.is_deleted == False)
    invoice_count_query = select(func.count(Invoice.id)).where(Invoice.organization_id == org_id)
    
    u_res = await db.execute(user_count_query)
    i_res = await db.execute(invoice_count_query)
    
    return TenantResponse(
        id=org.id,
        name=org.name,
        slug=org.slug,
        is_active=org.is_active,
        subscription_plan=org.subscription_plan,
        subscription_expires_at=org.subscription_expires_at,
        subscription_status=org.subscription_status,
        max_users=org.max_users,
        user_count=u_res.scalar() or 0,
        invoice_count=i_res.scalar() or 0
    )


@router.delete("/tenants/{org_id}", status_code=status.HTTP_200_OK)
async def delete_tenant(
    org_id: uuid.UUID,
    actor: Annotated[User, Depends(require_super_admin)],
    db: Annotated[AsyncSession, Depends(get_db)]
):
    """Hard delete a tenant organization and all of its related data from the database."""
    # Check if organization exists
    org = await db.get(Organization, org_id)
    if not org:
        raise HTTPException(status_code=404, detail="Tenant organization not found")

    # Import related models for manual cascading deletes
    from app.models.note import Note
    from app.models.activity import Activity
    from app.models.lead import Lead
    from app.models.contact import Contact
    from app.models.company import Company
    from app.models.pipeline import PipelineStage
    from app.models.target import PerformanceTarget
    from app.models.invoice import Invoice
    from app.models.invitation import UserInvitation
    from app.models.audit_log import AuditLog
    from app.models.session import UserSession
    from app.models.tenant_subscription import TenantSubscription
    from app.models.lead_import import LeadImport
    from app.models.assignment_config import AssignmentConfig

    # 1. Delete dependent entities by organization_id
    await db.execute(delete(Note).filter(Note.organization_id == org_id))
    await db.execute(delete(Activity).filter(Activity.organization_id == org_id))
    await db.execute(delete(Lead).filter(Lead.organization_id == org_id))
    await db.execute(delete(Contact).filter(Contact.organization_id == org_id))
    await db.execute(delete(Company).filter(Company.organization_id == org_id))
    await db.execute(delete(PipelineStage).filter(PipelineStage.organization_id == org_id))
    await db.execute(delete(PerformanceTarget).filter(PerformanceTarget.organization_id == org_id))
    await db.execute(delete(Invoice).filter(Invoice.organization_id == org_id))
    await db.execute(delete(UserInvitation).filter(UserInvitation.organization_id == org_id))
    await db.execute(delete(AuditLog).filter(AuditLog.organization_id == org_id))
    await db.execute(delete(TenantSubscription).filter(TenantSubscription.organization_id == org_id))
    await db.execute(delete(LeadImport).filter(LeadImport.organization_id == org_id))
    await db.execute(delete(AssignmentConfig).filter(AssignmentConfig.organization_id == org_id))

    # 2. Get user ids to delete their sessions
    user_ids_result = await db.execute(select(User.id).filter(User.organization_id == org_id))
    user_ids = user_ids_result.scalars().all()
    if user_ids:
        await db.execute(delete(UserSession).filter(UserSession.user_id.in_(user_ids)))

    # 3. Delete all users belonging to this organization
    await db.execute(delete(User).filter(User.organization_id == org_id))

    # 4. Delete the organization itself
    await db.execute(delete(Organization).filter(Organization.id == org_id))

    await db.commit()

    return {"detail": "Tenant organization and all related data deleted successfully"}
