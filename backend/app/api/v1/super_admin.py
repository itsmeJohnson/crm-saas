import uuid
import secrets
from datetime import datetime, timezone
from typing import Annotated, List, Literal
from fastapi import APIRouter, Depends, HTTPException, Query, status, UploadFile, File, Request
from app.schemas.invoice_config import InvoiceConfigResponse, InvoiceConfigUpdate
from app.services.invoice_config_service import InvoiceConfigService
from app.schemas.commercial_settings import CommercialSettingsResponse, CommercialSettingsUpdate
from app.services.commercial_settings_service import CommercialSettingsService
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, delete, update

from app.core.database import get_db
from app.core.security import get_password_hash
from app.models.organization import Organization
from app.models.user import User
from app.models.invoice import Invoice
from app.models.plan import Plan
from app.models.feature import Feature
from app.models.plan_feature import PlanFeature
from app.models.system_setting import SystemSetting
from app.models.tenant_subscription import TenantSubscription
from app.models.payment import Payment
from app.dependencies.auth import get_current_active_user, RoleChecker
from app.schemas.super_admin import (
    SubscriptionUpdateRequest, TenantResponse, TenantUserResponse,
    TenantInvoiceResponse, InvoiceCreateRequest,
    PlanCreate, PlanUpdate, PlanResponse, FeatureResponse, PlanFeatureResponse,
    PlanFeatureToggle, PlanFeatureClone, SystemSettingRequest, SystemSettingResponse,
    TenantUsageUpdateRequest
)
from app.services.auth_service import AuthService
from app.schemas.auth import RegisterTenantRequest
from app.schemas.trial_request import TrialRequestResponse

router = APIRouter()
require_super_admin = RoleChecker(["SuperAdmin"])

@router.get("/tenants", response_model=List[TenantResponse])
async def list_tenants(
    actor: Annotated[User, Depends(require_super_admin)],
    db: Annotated[AsyncSession, Depends(get_db)]
):
    """List all tenant organizations in the system with user and invoice counts."""
    from sqlalchemy.orm import selectinload
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
    ).where(Organization.is_deleted == False).options(selectinload(Organization.subscription))

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
                invoice_count=i_cnt,
                call_recording_usage=org.subscription.call_recording_usage if org.subscription else 0,
                currency=org.currency,
                timezone=org.timezone
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
    from sqlalchemy.orm import selectinload
    stmt = select(Organization).where(Organization.id == org_id, Organization.is_deleted == False).options(selectinload(Organization.subscription))
    res = await db.execute(stmt)
    org = res.scalar_one_or_none()
    if not org:
        raise HTTPException(status_code=404, detail="Tenant organization not found")
    
    # Look up the plan by name (case-insensitive) to get plan ID
    plan_stmt = select(Plan).where(Plan.name.ilike(payload.subscription_plan), Plan.is_deleted == False)
    plan_res = await db.execute(plan_stmt)
    plan = plan_res.scalar_one_or_none()
    
    # subscription_expires_at is a naive TIMESTAMP column; normalize any
    # tz-aware input to UTC then drop tzinfo (asyncpg rejects writing an
    # offset-aware datetime to a naive column).
    expires_at = payload.subscription_expires_at
    if expires_at and expires_at.tzinfo is not None:
        expires_at = expires_at.astimezone(timezone.utc).replace(tzinfo=None)
    org.subscription_expires_at = expires_at

    if plan:
        org.plan_id = plan.id
        # Update or create the TenantSubscription row to keep it in sync
        if org.subscription:
            org.subscription.plan_id = plan.id
            org.subscription.status = payload.subscription_status
            org.subscription.users_purchased = payload.max_users
            if expires_at:
                org.subscription.end_date = expires_at
        else:
            from datetime import timedelta
            now = datetime.now(timezone.utc)
            subscription = TenantSubscription(
                organization_id=org.id,
                plan_id=plan.id,
                status=payload.subscription_status,
                start_date=now.replace(tzinfo=None),
                end_date=expires_at or (now + timedelta(days=365)).replace(tzinfo=None),
                auto_renew=True,
                billing_cycle="monthly",
                users_purchased=payload.max_users,
                users_active=0
            )
            db.add(subscription)
            org.subscription = subscription

    org.subscription_plan = payload.subscription_plan
    org.subscription_status = payload.subscription_status
    org.max_users = payload.max_users

    # Optional tenant profile fields.
    if payload.name is not None and payload.name.strip():
        org.name = payload.name.strip()
    if payload.currency is not None and payload.currency.strip():
        org.currency = payload.currency.strip().upper()
    if payload.timezone is not None and payload.timezone.strip():
        org.timezone = payload.timezone.strip()
    
    await db.commit()

    # Invalidate features cache
    from app.dependencies.feature_guard import invalidate_tenant_features
    await invalidate_tenant_features(org_id)
    
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
        invoice_count=i_res.scalar() or 0,
        call_recording_usage=org.subscription.call_recording_usage if org.subscription else 0,
        currency=org.currency,
        timezone=org.timezone
    )

@router.put("/tenants/{org_id}/usage", response_model=TenantResponse)
async def update_tenant_usage(
    org_id: uuid.UUID,
    payload: TenantUsageUpdateRequest,
    actor: Annotated[User, Depends(require_super_admin)],
    db: Annotated[AsyncSession, Depends(get_db)]
):
    """Update a tenant's logged calling usage minutes."""
    from sqlalchemy.orm import selectinload
    stmt = select(Organization).where(Organization.id == org_id, Organization.is_deleted == False).options(selectinload(Organization.subscription))
    res = await db.execute(stmt)
    org = res.scalar_one_or_none()
    if not org:
        raise HTTPException(status_code=404, detail="Tenant organization not found")
        
    if not org.subscription:
        raise HTTPException(status_code=400, detail="Tenant has no active subscription record")
        
    org.subscription.call_recording_usage = payload.call_recording_usage
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
        invoice_count=i_res.scalar() or 0,
        call_recording_usage=org.subscription.call_recording_usage
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
    
    # due_date column is a naive TIMESTAMP; normalize to UTC then drop tzinfo
    due_date = payload.due_date
    if due_date.tzinfo is not None:
        due_date = due_date.astimezone(timezone.utc).replace(tzinfo=None)

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
    actor: Annotated[User, Depends(require_super_admin)],
    db: Annotated[AsyncSession, Depends(get_db)],
    status_val: Literal["paid", "pending", "overdue", "void", "waived"] = Query(..., description="New invoice status"),
):
    """Change the status of an invoice. Accepts only valid status values."""
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

    # Invalidate features cache
    from app.dependencies.feature_guard import invalidate_tenant_features
    await invalidate_tenant_features(org_id)
    
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
    """Soft-delete a tenant organization: mark it deleted, deactivate it and its
    users so no one can log in, and remove it from the tenant list.

    A hard delete is intentionally avoided — 148 tables carry organization_id,
    so a manual cascade is unmaintainable and would fail on foreign keys. The
    tenant list (and all tenant queries) filter is_deleted == False, so a
    soft-deleted tenant disappears immediately and its data can still be purged
    out-of-band if ever required.
    """
    org = await db.get(Organization, org_id)
    if not org or org.is_deleted:
        raise HTTPException(status_code=404, detail="Tenant organization not found")

    org.is_deleted = True
    org.is_active = False
    org.subscription_status = "cancelled"

    # Deactivate every user so the tenant can no longer authenticate.
    await db.execute(
        update(User).filter(User.organization_id == org_id).values(is_active=False)
    )

    # Invalidate any live sessions for those users.
    from app.models.session import UserSession
    user_ids = (await db.execute(select(User.id).filter(User.organization_id == org_id))).scalars().all()
    if user_ids:
        await db.execute(delete(UserSession).filter(UserSession.user_id.in_(user_ids)))

    await db.commit()

    # Invalidate features cache
    from app.dependencies.feature_guard import invalidate_tenant_features
    await invalidate_tenant_features(org_id)

    return {"detail": "Tenant organization deleted successfully"}


# ==========================================
# PLANS CRUD
# ==========================================

@router.get("/plans", response_model=List[PlanResponse])
async def list_plans(
    actor: Annotated[User, Depends(require_super_admin)],
    db: Annotated[AsyncSession, Depends(get_db)]
):
    """List all available subscription plans, ordered by display_order."""
    stmt = select(Plan).where(Plan.is_deleted == False).order_by(Plan.display_order.asc(), Plan.created_at.desc())
    res = await db.execute(stmt)
    return res.scalars().all()

@router.post("/plans", response_model=PlanResponse, status_code=status.HTTP_201_CREATED)
async def create_plan(
    payload: PlanCreate,
    actor: Annotated[User, Depends(require_super_admin)],
    db: Annotated[AsyncSession, Depends(get_db)]
):
    """Create a new plan."""
    plan = Plan(
        name=payload.name,
        display_name=payload.display_name,
        description=payload.description,
        monthly_price=payload.monthly_price,
        quarterly_price=payload.quarterly_price,
        annual_price=payload.annual_price,
        currency=payload.currency,
        max_users=payload.max_users,
        max_admins=payload.max_admins,
        max_managers=payload.max_managers,
        max_team_leads=payload.max_team_leads,
        max_employees=payload.max_employees,
        storage_limit_gb=payload.storage_limit_gb,
        recording_retention_days=payload.recording_retention_days,
        priority_support=payload.priority_support,
        api_access=payload.api_access,
        display_order=payload.display_order,
        setup_charges=payload.setup_charges,
        minimum_users=payload.minimum_users,
        maximum_users=payload.maximum_users,
        minimum_contract_months=payload.minimum_contract_months,
        price_inr=payload.monthly_price,  # Backwards compatibility
        trial_days=payload.trial_days,
        extra_user_price=payload.extra_user_price,
        discount_percentage=payload.discount_percentage,
        gst_percentage=payload.gst_percentage,
        plan_color=payload.plan_color,
        plan_badge=payload.plan_badge,
        popular_plan=payload.popular_plan,
        recommended_plan=payload.recommended_plan,
        allow_upgrade=payload.allow_upgrade,
        allow_downgrade=payload.allow_downgrade,
        allow_trial=payload.allow_trial,
        allow_additional_seats=payload.allow_additional_seats,
        auto_renew=payload.auto_renew,
        plan_active=payload.plan_active,
        is_active=payload.plan_active
    )
    db.add(plan)
    await db.commit()
    await db.refresh(plan)

    from app.services.audit_service import AuditService
    audit_service = AuditService(db)
    await audit_service.log_event(
        organization_id=actor.organization_id,
        actor_user_id=actor.id,
        action="PLAN_CREATED",
        resource_type="Plan",
        resource_id=str(plan.id),
        action_metadata={"plan_name": plan.name}
    )

    return plan

@router.patch("/plans/{plan_id}", response_model=PlanResponse)
async def update_plan(
    plan_id: uuid.UUID,
    payload: PlanUpdate,
    actor: Annotated[User, Depends(require_super_admin)],
    db: Annotated[AsyncSession, Depends(get_db)]
):
    """Partially update a plan."""
    plan = await db.get(Plan, plan_id)
    if not plan or plan.is_deleted:
        raise HTTPException(status_code=404, detail="Plan not found")

    old_val = {}
    new_val = {}
    update_data = payload.model_dump(exclude_unset=True)

    for key, val in update_data.items():
        if hasattr(plan, key):
            current_value = getattr(plan, key)
            if current_value != val:
                old_val[key] = str(current_value) if current_value is not None else ""
                new_val[key] = str(val) if val is not None else ""
                setattr(plan, key, val)

    # Keep price_inr in sync with monthly_price
    if "monthly_price" in update_data:
        plan.price_inr = update_data["monthly_price"]

    # Keep is_active in sync with plan_active if updated
    if "plan_active" in update_data:
        plan.is_active = update_data["plan_active"]

    await db.commit()
    await db.refresh(plan)

    # Invalidate all features cache
    from app.dependencies.feature_guard import invalidate_all_tenant_features
    await invalidate_all_tenant_features()

    if old_val:
        from app.services.audit_service import AuditService
        audit_service = AuditService(db)
        await audit_service.log_event(
            organization_id=actor.organization_id,
            actor_user_id=actor.id,
            action="PLAN_UPDATED",
            resource_type="Plan",
            resource_id=str(plan.id),
            action_metadata={
                "plan_name": plan.name,
                "old": old_val,
                "new": new_val
            }
        )

    return plan

@router.delete("/plans/{plan_id}", status_code=status.HTTP_200_OK)
async def delete_plan(
    plan_id: uuid.UUID,
    actor: Annotated[User, Depends(require_super_admin)],
    db: Annotated[AsyncSession, Depends(get_db)]
):
    """Soft delete a plan."""
    plan = await db.get(Plan, plan_id)
    if not plan or plan.is_deleted:
        raise HTTPException(status_code=404, detail="Plan not found")
    plan.is_deleted = True
    await db.commit()

    # Invalidate all features cache
    from app.dependencies.feature_guard import invalidate_all_tenant_features
    await invalidate_all_tenant_features()

    return {"detail": "Plan deleted successfully"}

@router.post("/plans/reorder", status_code=status.HTTP_200_OK)
async def reorder_plans(
    plan_ids: List[uuid.UUID],
    actor: Annotated[User, Depends(require_super_admin)],
    db: Annotated[AsyncSession, Depends(get_db)]
):
    """Reorder plans by updating display_order based on order of IDs provided."""
    for idx, pid in enumerate(plan_ids):
        plan = await db.get(Plan, pid)
        if plan:
            plan.display_order = idx
    await db.commit()
    return {"detail": "Plans order updated successfully"}


# ==========================================
# FEATURES MASTER
# ==========================================

@router.get("/features", response_model=List[FeatureResponse])
async def list_features(
    actor: Annotated[User, Depends(require_super_admin)],
    db: Annotated[AsyncSession, Depends(get_db)]
):
    """List all features in the master registry."""
    stmt = select(Feature).where(Feature.is_deleted == False).order_by(Feature.category.asc(), Feature.code.asc())
    res = await db.execute(stmt)
    return res.scalars().all()

@router.patch("/features/{feature_id}", response_model=FeatureResponse)
async def update_feature(
    feature_id: uuid.UUID,
    payload: dict,
    actor: Annotated[User, Depends(require_super_admin)],
    db: Annotated[AsyncSession, Depends(get_db)]
):
    """Update a feature's display or active status."""
    feature = await db.get(Feature, feature_id)
    if not feature or feature.is_deleted:
        raise HTTPException(status_code=404, detail="Feature not found")
    for key, val in payload.items():
        if hasattr(feature, key):
            setattr(feature, key, val)
    await db.commit()
    await db.refresh(feature)

    # Invalidate all features cache
    from app.dependencies.feature_guard import invalidate_all_tenant_features
    await invalidate_all_tenant_features()

    return feature


# ==========================================
# PLAN FEATURE MAPPINGS
# ==========================================

@router.get("/plan-features", response_model=List[PlanFeatureResponse])
async def list_plan_features(
    actor: Annotated[User, Depends(require_super_admin)],
    db: Annotated[AsyncSession, Depends(get_db)]
):
    """Get all plan to feature mappings."""
    from sqlalchemy.orm import selectinload
    stmt = select(PlanFeature).where(PlanFeature.is_deleted == False).options(selectinload(PlanFeature.feature))
    res = await db.execute(stmt)
    return res.scalars().all()

@router.post("/plan-features/toggle", response_model=PlanFeatureResponse)
async def toggle_plan_feature(
    payload: PlanFeatureToggle,
    actor: Annotated[User, Depends(require_super_admin)],
    db: Annotated[AsyncSession, Depends(get_db)]
):
    """Toggle a feature mapping for a plan."""
    # Check if plan and feature exist
    plan = await db.get(Plan, payload.plan_id)
    feature = await db.get(Feature, payload.feature_id)
    if not plan or plan.is_deleted or not feature or feature.is_deleted:
        raise HTTPException(status_code=404, detail="Plan or Feature not found")

    stmt = select(PlanFeature).where(
        PlanFeature.plan_id == payload.plan_id,
        PlanFeature.feature_id == payload.feature_id
    )
    res = await db.execute(stmt)
    mapping = res.scalar_one_or_none()

    if mapping:
        mapping.enabled = payload.enabled
    else:
        mapping = PlanFeature(
            plan_id=payload.plan_id,
            feature_id=payload.feature_id,
            enabled=payload.enabled
        )
        db.add(mapping)

    await db.commit()
    from sqlalchemy.orm import selectinload
    stmt2 = select(PlanFeature).where(PlanFeature.id == mapping.id).options(selectinload(PlanFeature.feature))
    mapping = (await db.execute(stmt2)).scalar_one()

    # Invalidate all features cache
    from app.dependencies.feature_guard import invalidate_all_tenant_features
    await invalidate_all_tenant_features()

    return mapping

@router.post("/plan-features/clone", status_code=status.HTTP_200_OK)
async def clone_plan_features(
    payload: PlanFeatureClone,
    actor: Annotated[User, Depends(require_super_admin)],
    db: Annotated[AsyncSession, Depends(get_db)]
):
    """Clone all feature mappings from one plan to another."""
    from_plan = await db.get(Plan, payload.from_plan_id)
    to_plan = await db.get(Plan, payload.to_plan_id)
    if not from_plan or not to_plan:
        raise HTTPException(status_code=404, detail="Source or target plan not found")

    # Clear target mappings first
    await db.execute(delete(PlanFeature).filter(PlanFeature.plan_id == payload.to_plan_id))

    # Fetch source mappings
    stmt = select(PlanFeature).where(PlanFeature.plan_id == payload.from_plan_id, PlanFeature.enabled == True)
    res = await db.execute(stmt)
    source_mappings = res.scalars().all()

    for mapping in source_mappings:
        new_mapping = PlanFeature(
            plan_id=payload.to_plan_id,
            feature_id=mapping.feature_id,
            enabled=True
        )
        db.add(new_mapping)

    await db.commit()

    # Invalidate all features cache
    from app.dependencies.feature_guard import invalidate_all_tenant_features
    await invalidate_all_tenant_features()

    return {"detail": f"Cloned {len(source_mappings)} features successfully"}


# ==========================================
# SYSTEM SETTINGS
# ==========================================

@router.get("/system-settings", response_model=List[SystemSettingResponse])
async def list_system_settings(
    actor: Annotated[User, Depends(require_super_admin)],
    db: Annotated[AsyncSession, Depends(get_db)]
):
    """Get all key-value settings."""
    stmt = select(SystemSetting)
    res = await db.execute(stmt)
    return res.scalars().all()

@router.post("/system-settings", response_model=SystemSettingResponse)
async def upsert_system_setting(
    payload: SystemSettingRequest,
    actor: Annotated[User, Depends(require_super_admin)],
    db: Annotated[AsyncSession, Depends(get_db)]
):
    """Create or update a system setting key/value pair."""
    setting = await db.get(SystemSetting, payload.key)
    if setting:
        setting.value = payload.value
    else:
        setting = SystemSetting(key=payload.key, value=payload.value)
        db.add(setting)

    await db.commit()
    await db.refresh(setting)
    return setting


# ==========================================
# TENANT / ORG CONTROLS OVERRIDES
# ==========================================

@router.post("/tenants/{org_id}/suspend", response_model=TenantResponse)
async def suspend_tenant(
    org_id: uuid.UUID,
    actor: Annotated[User, Depends(require_super_admin)],
    db: Annotated[AsyncSession, Depends(get_db)]
):
    """Suspend or reactivate a tenant organization."""
    return await toggle_tenant_subscription_status(org_id=org_id, actor=actor, db=db, status_val=None)

@router.post("/tenants/{org_id}/reset-password")
async def reset_tenant_owner_password(
    org_id: uuid.UUID,
    new_password: str,
    actor: Annotated[User, Depends(require_super_admin)],
    db: Annotated[AsyncSession, Depends(get_db)]
):
    """Reset the password of the OrgAdmin for the tenant."""
    stmt = select(User).where(
        User.organization_id == org_id,
        User.role == "OrgAdmin",
        User.is_deleted == False
    )
    res = await db.execute(stmt)
    admin_user = res.scalar_one_or_none()
    if not admin_user:
        raise HTTPException(status_code=404, detail="OrgAdmin not found for this tenant")

    admin_user.hashed_password = get_password_hash(new_password)
    admin_user.token_version += 1 # Invalidate existing sessions/tokens
    await db.commit()
    return {"detail": f"Password reset successfully for {admin_user.email}"}

@router.post("/tenants/{org_id}/invoices/manual", response_model=TenantInvoiceResponse)
async def create_manual_invoice(
    org_id: uuid.UUID,
    payload: InvoiceCreateRequest,
    actor: Annotated[User, Depends(require_super_admin)],
    db: Annotated[AsyncSession, Depends(get_db)]
):
    """Generate a manual invoice for a tenant."""
    return await create_tenant_invoice(org_id=org_id, payload=payload, actor=actor, db=db)

@router.get("/invoice-config", response_model=InvoiceConfigResponse)
async def get_invoice_config(
    actor: Annotated[User, Depends(require_super_admin)],
    db: Annotated[AsyncSession, Depends(get_db)]
):
    """Retrieve global billing/invoice configuration."""
    service = InvoiceConfigService(db)
    return await service.get_config()

@router.put("/invoice-config", response_model=InvoiceConfigResponse)
async def update_invoice_config(
    payload: InvoiceConfigUpdate,
    request: Request,
    actor: Annotated[User, Depends(require_super_admin)],
    db: Annotated[AsyncSession, Depends(get_db)]
):
    """Update global invoice/billing configuration text fields and settings."""
    service = InvoiceConfigService(db)
    ip_address = request.client.host if request.client else None
    user_agent = request.headers.get("user-agent")
    return await service.update_config(
        payload=payload,
        organization_id=actor.organization_id,
        actor_user_id=actor.id,
        ip_address=ip_address,
        user_agent=user_agent
    )

@router.post("/invoice-config/upload-logo", response_model=InvoiceConfigResponse)
async def upload_company_logo(
    request: Request,
    actor: Annotated[User, Depends(require_super_admin)],
    db: Annotated[AsyncSession, Depends(get_db)],
    file: UploadFile = File(...)
):
    """Upload company logo file for branding invoices."""
    service = InvoiceConfigService(db)
    ip_address = request.client.host if request.client else None
    user_agent = request.headers.get("user-agent")
    
    file_bytes = await file.read()
    try:
        await service.upload_logo(
            file_bytes=file_bytes,
            original_filename=file.filename or "logo.png",
            organization_id=actor.organization_id,
            actor_user_id=actor.id,
            ip_address=ip_address,
            user_agent=user_agent
        )
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    return await service.get_config()

@router.post("/invoice-config/upload-qr", response_model=InvoiceConfigResponse)
async def upload_payment_qr(
    request: Request,
    actor: Annotated[User, Depends(require_super_admin)],
    db: Annotated[AsyncSession, Depends(get_db)],
    file: UploadFile = File(...)
):
    """Upload payment QR code image for invoicing."""
    service = InvoiceConfigService(db)
    ip_address = request.client.host if request.client else None
    user_agent = request.headers.get("user-agent")
    
    file_bytes = await file.read()
    try:
        await service.upload_qr_code(
            file_bytes=file_bytes,
            original_filename=file.filename or "qr.png",
            organization_id=actor.organization_id,
            actor_user_id=actor.id,
            ip_address=ip_address,
            user_agent=user_agent
        )
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    return await service.get_config()

@router.delete("/invoice-config/logo", response_model=InvoiceConfigResponse)
async def delete_company_logo(
    request: Request,
    actor: Annotated[User, Depends(require_super_admin)],
    db: Annotated[AsyncSession, Depends(get_db)]
):
    """Delete currently saved company branding logo."""
    service = InvoiceConfigService(db)
    ip_address = request.client.host if request.client else None
    user_agent = request.headers.get("user-agent")
    
    await service.delete_logo(
        organization_id=actor.organization_id,
        actor_user_id=actor.id,
        ip_address=ip_address,
        user_agent=user_agent
    )
    return await service.get_config()

@router.delete("/invoice-config/qr", response_model=InvoiceConfigResponse)
async def delete_payment_qr(
    request: Request,
    actor: Annotated[User, Depends(require_super_admin)],
    db: Annotated[AsyncSession, Depends(get_db)]
):
    """Delete currently saved payment QR code."""
    service = InvoiceConfigService(db)
    ip_address = request.client.host if request.client else None
    user_agent = request.headers.get("user-agent")
    
    await service.delete_qr_code(
        organization_id=actor.organization_id,
        actor_user_id=actor.id,
        ip_address=ip_address,
        user_agent=user_agent
    )
    return await service.get_config()


@router.get("/commercial-settings", response_model=CommercialSettingsResponse)
async def get_commercial_settings(
    actor: Annotated[User, Depends(require_super_admin)],
    db: Annotated[AsyncSession, Depends(get_db)]
):
    """Retrieve global commercial configuration settings."""
    service = CommercialSettingsService(db)
    return await service.get_settings()


@router.put("/commercial-settings", response_model=CommercialSettingsResponse)
async def update_commercial_settings(
    payload: CommercialSettingsUpdate,
    request: Request,
    actor: Annotated[User, Depends(require_super_admin)],
    db: Annotated[AsyncSession, Depends(get_db)]
):
    """Update global commercial/business rules configuration."""
    service = CommercialSettingsService(db)
    ip_address = request.client.host if request.client else None
    user_agent = request.headers.get("user-agent")
    return await service.update_settings(
        payload=payload,
        organization_id=actor.organization_id,
        actor_user_id=actor.id,
        ip_address=ip_address,
        user_agent=user_agent
    )



# ==========================================
# PHASE 1: SUPER ADMIN EXECUTIVE DASHBOARD
# ==========================================

from app.schemas.dashboard import SuperAdminDashboardResponse, OrgMetrics, RevenueMetrics, LicensingMetrics, InfraMetrics, ActivityMetrics

@router.get("/dashboard", response_model=SuperAdminDashboardResponse)
async def get_super_admin_dashboard(
    actor: Annotated[User, Depends(require_super_admin)],
    db: Annotated[AsyncSession, Depends(get_db)],
    period: str = "month"
):
    """Executive dashboard with business overview, revenue, licensing and infra metrics."""
    from datetime import date, timedelta
    now = datetime.now(timezone.utc)
    today_start = datetime(now.year, now.month, now.day, tzinfo=timezone.utc)
    next_7_days = now + timedelta(days=7)

    # Period start for toggle (day / week / month)
    if period == "day":
        period_start = today_start
    elif period == "week":
        period_start = today_start - timedelta(days=today_start.weekday())
    else:
        period_start = datetime(now.year, now.month, 1, tzinfo=timezone.utc)

    # ── Org Metrics ──
    total_orgs = (await db.execute(select(func.count(Organization.id)).where(Organization.is_deleted == False))).scalar() or 0
    active_orgs = (await db.execute(select(func.count(Organization.id)).where(Organization.is_deleted == False, Organization.subscription_status == "active"))).scalar() or 0
    trial_orgs = (await db.execute(select(func.count(Organization.id)).where(Organization.is_deleted == False, Organization.subscription_status == "trial"))).scalar() or 0
    expired_orgs = (await db.execute(select(func.count(Organization.id)).where(Organization.is_deleted == False, Organization.subscription_status == "expired"))).scalar() or 0
    suspended_orgs = (await db.execute(select(func.count(Organization.id)).where(Organization.is_deleted == False, Organization.subscription_status == "suspended"))).scalar() or 0
    new_today = (await db.execute(select(func.count(Organization.id)).where(Organization.is_deleted == False, Organization.created_at >= today_start))).scalar() or 0

    # ── Revenue Metrics ──
    mrr_result = await db.execute(
        select(func.coalesce(func.sum(Plan.monthly_price * TenantSubscription.users_purchased), 0.0))
        .join(Plan, TenantSubscription.plan_id == Plan.id)
        .where(TenantSubscription.status.in_(["active", "trial"]), TenantSubscription.is_deleted == False)
    )
    mrr = float(mrr_result.scalar() or 0.0)

    total_collected = float((await db.execute(
        select(func.coalesce(func.sum(Invoice.total_amount), 0.0))
        .where(Invoice.payment_status == "paid", Invoice.is_deleted == False)
    )).scalar() or 0.0)

    pending = float((await db.execute(
        select(func.coalesce(func.sum(Invoice.total_amount), 0.0))
        .where(Invoice.payment_status == "unpaid", Invoice.is_deleted == False)
    )).scalar() or 0.0)

    failed_count = (await db.execute(
        select(func.count(Invoice.id))
        .where(Invoice.payment_status == "failed", Invoice.is_deleted == False)
    )).scalar() or 0

    overdue_count = (await db.execute(
        select(func.count(Invoice.id))
        .where(Invoice.payment_status == "unpaid", Invoice.due_date < now, Invoice.is_deleted == False)
    )).scalar() or 0

    # ── Licensing Metrics ──
    total_licensed = (await db.execute(
        select(func.coalesce(func.sum(TenantSubscription.users_purchased), 0))
        .where(TenantSubscription.status.in_(["active", "trial"]), TenantSubscription.is_deleted == False)
    )).scalar() or 0

    active_seats = (await db.execute(
        select(func.coalesce(func.sum(TenantSubscription.users_active), 0))
        .where(TenantSubscription.is_deleted == False)
    )).scalar() or 0

    utilization = round((active_seats / total_licensed * 100) if total_licensed > 0 else 0.0, 1)

    # ── Storage Metrics ──
    total_storage = float((await db.execute(
        select(func.coalesce(func.sum(TenantSubscription.storage_used), 0.0))
        .where(TenantSubscription.is_deleted == False)
    )).scalar() or 0.0)

    call_storage = float((await db.execute(
        select(func.coalesce(func.sum(TenantSubscription.call_recording_usage), 0.0))
        .where(TenantSubscription.is_deleted == False)
    )).scalar() or 0.0)

    # ── DB & Redis health ──
    db_status = "healthy"
    try:
        await db.execute(select(func.now()))
    except Exception:
        db_status = "unhealthy"

    redis_status = "healthy"
    try:
        from app.core.redis import redis_client
        await redis_client.ping()
    except Exception:
        redis_status = "unavailable"

    # ── Activity Metrics ──
    renewals_due = (await db.execute(
        select(func.count(TenantSubscription.id))
        .where(
            TenantSubscription.end_date.between(now, next_7_days),
            TenantSubscription.status == "active",
            TenantSubscription.is_deleted == False
        )
    )).scalar() or 0

    trials_expiring = (await db.execute(
        select(func.count(TenantSubscription.id))
        .where(
            TenantSubscription.trial_end_date != None,
            TenantSubscription.trial_end_date.between(now, next_7_days),
            TenantSubscription.status == "trial",
            TenantSubscription.is_deleted == False
        )
    )).scalar() or 0

    new_invoices = (await db.execute(
        select(func.count(Invoice.id))
        .where(Invoice.created_at >= today_start, Invoice.is_deleted == False)
    )).scalar() or 0

    new_payments = (await db.execute(
        select(func.count(Payment.id))
        .where(Payment.created_at >= today_start)
    )).scalar() or 0

    # Period-scoped metrics
    period_collected = float((await db.execute(
        select(func.coalesce(func.sum(Invoice.total_amount), 0.0))
        .where(Invoice.payment_status == "paid", Invoice.is_deleted == False,
               Invoice.updated_at >= period_start)
    )).scalar() or 0.0)

    period_onboarded = (await db.execute(
        select(func.count(Organization.id))
        .where(Organization.is_deleted == False, Organization.created_at >= period_start)
    )).scalar() or 0

    return SuperAdminDashboardResponse(
        orgs=OrgMetrics(total=total_orgs, active=active_orgs, trial=trial_orgs,
                        expired=expired_orgs, suspended=suspended_orgs, new_today=new_today),
        revenue=RevenueMetrics(mrr=mrr, arr=mrr * 12, total_collected=total_collected,
                               pending=pending, failed_count=failed_count, overdue_count=overdue_count,
                               period_collected=period_collected, period_onboarded=period_onboarded,
                               period=period),
        licensing=LicensingMetrics(total_licensed_seats=total_licensed, active_seats=active_seats,
                                   available_seats=max(0, total_licensed - active_seats),
                                   utilization_percent=utilization),
        infra=InfraMetrics(total_storage_gb=round(total_storage, 2),
                           call_recording_gb=round(call_storage / 1024, 2) if call_storage > 0 else 0.0,
                           db_status=db_status, redis_status=redis_status),
        activity=ActivityMetrics(new_orgs_today=new_today, renewals_due_7days=renewals_due,
                                  trials_expiring_7days=trials_expiring, new_invoices_today=new_invoices,
                                  payments_today=new_payments),
        generated_at=now
    )


# ==========================================
# PHASE 2: ENHANCED TENANT ACTIONS
# ==========================================

from app.core.security import create_access_token

@router.post("/tenants/{org_id}/extend-trial", response_model=TenantResponse)
async def extend_tenant_trial(
    org_id: uuid.UUID,
    days: int = 7,
    actor: Annotated[User, Depends(require_super_admin)] = None,
    db: Annotated[AsyncSession, Depends(get_db)] = None
):
    """Extend trial period for a tenant by N days."""
    org = await db.get(Organization, org_id)
    if not org or org.is_deleted:
        raise HTTPException(status_code=404, detail="Tenant not found")

    sub = (await db.execute(
        select(TenantSubscription).where(TenantSubscription.organization_id == org_id, TenantSubscription.is_deleted == False)
    )).scalar_one_or_none()

    if sub:
        from datetime import timedelta
        current_end = sub.trial_end_date or sub.end_date
        sub.trial_end_date = (current_end or datetime.now(timezone.utc)) + timedelta(days=days)
        sub.end_date = sub.trial_end_date

    from datetime import timedelta
    org.subscription_expires_at = (org.subscription_expires_at or datetime.now(timezone.utc)) + timedelta(days=days)

    await db.commit()
    await db.refresh(org)

    from app.services.audit_service import AuditService
    audit = AuditService(db)
    await audit.log_event(organization_id=actor.organization_id, actor_user_id=actor.id,
        action="TRIAL_EXTENDED", resource_type="Organization", resource_id=str(org_id),
        action_metadata={"days_extended": days, "tenant_name": org.name})

    u_cnt = (await db.execute(select(func.count(User.id)).where(User.organization_id == org_id, User.is_deleted == False))).scalar() or 0
    i_cnt = (await db.execute(select(func.count(Invoice.id)).where(Invoice.organization_id == org_id, Invoice.is_deleted == False))).scalar() or 0
    return TenantResponse(id=org.id, name=org.name, slug=org.slug, is_active=org.is_active,
                          subscription_plan=org.subscription_plan, subscription_expires_at=org.subscription_expires_at,
                          subscription_status=org.subscription_status, max_users=org.max_users,
                          user_count=u_cnt, invoice_count=i_cnt)


@router.post("/tenants/{org_id}/activate")
async def activate_tenant(
    org_id: uuid.UUID,
    actor: Annotated[User, Depends(require_super_admin)],
    db: Annotated[AsyncSession, Depends(get_db)]
):
    """Activate a suspended tenant."""
    org = await db.get(Organization, org_id)
    if not org or org.is_deleted:
        raise HTTPException(status_code=404, detail="Tenant not found")

    org.is_active = True
    org.subscription_status = "active"
    await db.commit()

    from app.services.audit_service import AuditService
    audit = AuditService(db)
    await audit.log_event(organization_id=actor.organization_id, actor_user_id=actor.id,
        action="TENANT_ACTIVATED", resource_type="Organization", resource_id=str(org_id),
        action_metadata={"tenant_name": org.name})

    return {"detail": "Tenant activated successfully"}


@router.post("/tenants/{org_id}/impersonate")
async def impersonate_tenant_admin(
    org_id: uuid.UUID,
    actor: Annotated[User, Depends(require_super_admin)],
    db: Annotated[AsyncSession, Depends(get_db)]
):
    """Generate a short-lived token to log in as the OrgAdmin of this tenant."""
    org = await db.get(Organization, org_id)
    if not org or org.is_deleted:
        raise HTTPException(status_code=404, detail="Tenant not found")

    admin = (await db.execute(
        select(User).where(User.organization_id == org_id, User.role == "OrgAdmin", User.is_deleted == False)
    )).scalar_one_or_none()
    if not admin:
        raise HTTPException(status_code=404, detail="No OrgAdmin found for this tenant")

    from datetime import timedelta
    impersonation_token = create_access_token(
        subject=str(admin.id),
        token_version=admin.token_version,
        expires_delta=timedelta(minutes=15)
    )

    from app.services.audit_service import AuditService
    audit = AuditService(db)
    await audit.log_event(organization_id=actor.organization_id, actor_user_id=actor.id,
        action="IMPERSONATION", resource_type="Organization", resource_id=str(org_id),
        action_metadata={"tenant_name": org.name, "impersonated_user": str(admin.id), "target_email": admin.email})

    return {
        "access_token": impersonation_token,
        "token_type": "bearer",
        "expires_in": 900,
        "impersonating": {"org_id": str(org_id), "org_name": org.name, "admin_email": admin.email}
    }


@router.get("/tenants/{org_id}/audit-logs")
async def get_tenant_audit_logs(
    org_id: uuid.UUID,
    actor: Annotated[User, Depends(require_super_admin)],
    db: Annotated[AsyncSession, Depends(get_db)],
    limit: int = Query(50, le=500),
    offset: int = Query(0, ge=0)
):
    """Get audit logs for a specific tenant."""
    from app.models.audit_log import AuditLog
    stmt = select(AuditLog).where(
        AuditLog.organization_id == org_id
    ).order_by(AuditLog.created_at.desc()).limit(limit).offset(offset)
    res = await db.execute(stmt)
    logs = res.scalars().all()
    total = (await db.execute(select(func.count(AuditLog.id)).where(AuditLog.organization_id == org_id))).scalar() or 0
    return {"total": total, "data": [{"id": str(l.id), "action": l.action, "resource_type": l.resource_type,
             "resource_id": l.resource_id, "metadata": l.action_metadata, "created_at": l.created_at.isoformat()} for l in logs]}


# ==========================================
# PHASE 13: GLOBAL AUDIT CENTER
# ==========================================

@router.get("/audit-logs")
async def get_all_audit_logs(
    actor: Annotated[User, Depends(require_super_admin)],
    db: Annotated[AsyncSession, Depends(get_db)],
    org_id: uuid.UUID | None = Query(None),
    action: str | None = Query(None),
    resource_type: str | None = Query(None),
    start_date: datetime | None = Query(None),
    end_date: datetime | None = Query(None),
    limit: int = Query(100, le=1000),
    offset: int = Query(0, ge=0)
):
    """Global audit log search with filters."""
    from app.models.audit_log import AuditLog
    stmt = select(AuditLog)
    if org_id:
        stmt = stmt.where(AuditLog.organization_id == org_id)
    if action:
        stmt = stmt.where(AuditLog.action.ilike(f"%{action}%"))
    if resource_type:
        stmt = stmt.where(AuditLog.resource_type == resource_type)
    if start_date:
        stmt = stmt.where(AuditLog.created_at >= start_date)
    if end_date:
        stmt = stmt.where(AuditLog.created_at <= end_date)

    total_stmt = select(func.count()).select_from(stmt.subquery())
    total = (await db.execute(total_stmt)).scalar() or 0

    stmt = stmt.order_by(AuditLog.created_at.desc()).limit(limit).offset(offset)
    res = await db.execute(stmt)
    logs = res.scalars().all()

    return {
        "total": total,
        "limit": limit,
        "offset": offset,
        "data": [{"id": str(l.id), "organization_id": str(l.organization_id),
                  "actor_user_id": str(l.actor_user_id) if l.actor_user_id else None,
                  "action": l.action, "resource_type": l.resource_type, "resource_id": l.resource_id,
                  "metadata": l.action_metadata, "created_at": l.created_at.isoformat()} for l in logs]
    }


# ==========================================
# PHASE 4: FEATURE MANAGEMENT (Create/Delete)
# ==========================================

from pydantic import BaseModel as PydanticBaseModel

class FeatureCreate(PydanticBaseModel):
    code: str
    display_name: str
    description: str | None = None
    category: str
    icon: str | None = None
    active: bool = True


@router.post("/features", response_model=FeatureResponse, status_code=status.HTTP_201_CREATED)
async def create_feature(
    payload: FeatureCreate,
    actor: Annotated[User, Depends(require_super_admin)],
    db: Annotated[AsyncSession, Depends(get_db)]
):
    """Create a new feature in the feature registry."""
    existing = (await db.execute(select(Feature).where(Feature.code == payload.code))).scalar_one_or_none()
    if existing:
        raise HTTPException(status_code=409, detail=f"Feature with code '{payload.code}' already exists")

    feature = Feature(
        code=payload.code, display_name=payload.display_name,
        description=payload.description, category=payload.category,
        icon=payload.icon, active=payload.active
    )
    db.add(feature)
    await db.commit()
    await db.refresh(feature)

    from app.dependencies.feature_guard import invalidate_all_tenant_features
    await invalidate_all_tenant_features()
    return feature


@router.delete("/features/{feature_id}")
async def delete_feature(
    feature_id: uuid.UUID,
    actor: Annotated[User, Depends(require_super_admin)],
    db: Annotated[AsyncSession, Depends(get_db)]
):
    """Soft delete a feature from the registry."""
    feature = await db.get(Feature, feature_id)
    if not feature or feature.is_deleted:
        raise HTTPException(status_code=404, detail="Feature not found")
    feature.is_deleted = True
    await db.commit()
    from app.dependencies.feature_guard import invalidate_all_tenant_features
    await invalidate_all_tenant_features()
    return {"detail": "Feature deleted"}


# ==========================================
# PHASE 5: COUPON MANAGEMENT
# ==========================================

from app.schemas.coupon import CouponCreate, CouponUpdate, CouponResponse

@router.get("/coupons", response_model=list[CouponResponse])
async def list_coupons(
    actor: Annotated[User, Depends(require_super_admin)],
    db: Annotated[AsyncSession, Depends(get_db)]
):
    from app.models.coupon import Coupon
    res = await db.execute(select(Coupon).where(Coupon.is_deleted == False).order_by(Coupon.created_at.desc()))
    return res.scalars().all()


@router.post("/coupons", response_model=CouponResponse, status_code=status.HTTP_201_CREATED)
async def create_coupon(
    payload: CouponCreate,
    actor: Annotated[User, Depends(require_super_admin)],
    db: Annotated[AsyncSession, Depends(get_db)]
):
    from app.models.coupon import Coupon
    existing = (await db.execute(select(Coupon).where(Coupon.code == payload.code.upper(), Coupon.is_deleted == False))).scalar_one_or_none()
    if existing:
        raise HTTPException(status_code=409, detail="Coupon code already exists")

    data = payload.model_dump()
    data["code"] = payload.code.upper()
    coupon = Coupon(**data, created_by=actor.id)
    db.add(coupon)
    await db.commit()
    await db.refresh(coupon)
    return coupon


@router.patch("/coupons/{coupon_id}", response_model=CouponResponse)
async def update_coupon(
    coupon_id: uuid.UUID,
    payload: CouponUpdate,
    actor: Annotated[User, Depends(require_super_admin)],
    db: Annotated[AsyncSession, Depends(get_db)]
):
    from app.models.coupon import Coupon
    coupon = await db.get(Coupon, coupon_id)
    if not coupon or coupon.is_deleted:
        raise HTTPException(status_code=404, detail="Coupon not found")
    for k, v in payload.model_dump(exclude_unset=True).items():
        setattr(coupon, k, v)
    await db.commit()
    await db.refresh(coupon)
    return coupon


@router.delete("/coupons/{coupon_id}")
async def delete_coupon(
    coupon_id: uuid.UUID,
    actor: Annotated[User, Depends(require_super_admin)],
    db: Annotated[AsyncSession, Depends(get_db)]
):
    from app.models.coupon import Coupon
    coupon = await db.get(Coupon, coupon_id)
    if not coupon or coupon.is_deleted:
        raise HTTPException(status_code=404, detail="Coupon not found")
    coupon.is_deleted = True
    await db.commit()
    return {"detail": "Coupon deleted"}


# ==========================================
# PHASE 6: MULTI-CURRENCY ENGINE
# ==========================================

from app.schemas.currency import CurrencyCreate, CurrencyUpdate, CurrencyResponse

@router.get("/currencies", response_model=list[CurrencyResponse])
async def list_currencies(
    actor: Annotated[User, Depends(require_super_admin)],
    db: Annotated[AsyncSession, Depends(get_db)]
):
    from app.models.currency import Currency
    res = await db.execute(select(Currency).where(Currency.is_active == True).order_by(Currency.code))
    return res.scalars().all()


@router.post("/currencies", response_model=CurrencyResponse, status_code=status.HTTP_201_CREATED)
async def create_currency(
    payload: CurrencyCreate,
    actor: Annotated[User, Depends(require_super_admin)],
    db: Annotated[AsyncSession, Depends(get_db)]
):
    from app.models.currency import Currency
    existing = await db.get(Currency, payload.code.upper())
    if existing:
        raise HTTPException(status_code=409, detail="Currency already exists")

    if payload.is_base:
        await db.execute(Currency.__table__.update().values(is_base=False))

    data = payload.model_dump()
    data["code"] = payload.code.upper()
    currency = Currency(**data)
    db.add(currency)
    await db.commit()
    await db.refresh(currency)
    return currency


@router.patch("/currencies/{code}", response_model=CurrencyResponse)
async def update_currency(
    code: str,
    payload: CurrencyUpdate,
    actor: Annotated[User, Depends(require_super_admin)],
    db: Annotated[AsyncSession, Depends(get_db)]
):
    from app.models.currency import Currency
    currency = await db.get(Currency, code.upper())
    if not currency:
        raise HTTPException(status_code=404, detail="Currency not found")

    for k, v in payload.model_dump(exclude_unset=True).items():
        setattr(currency, k, v)
    currency.last_updated = datetime.now(timezone.utc)
    await db.commit()
    await db.refresh(currency)
    return currency


@router.delete("/currencies/{code}")
async def delete_currency(
    code: str,
    actor: Annotated[User, Depends(require_super_admin)],
    db: Annotated[AsyncSession, Depends(get_db)]
):
    from app.models.currency import Currency
    currency = await db.get(Currency, code.upper())
    if not currency:
        raise HTTPException(status_code=404, detail="Currency not found")
    if currency.is_base:
        raise HTTPException(status_code=400, detail="Cannot delete the base currency")
    currency.is_active = False
    await db.commit()
    return {"detail": "Currency deactivated"}


# ==========================================
# PHASE 7: TAX ENGINE
# ==========================================

from app.schemas.tax_config import TaxConfigCreate, TaxConfigUpdate, TaxConfigResponse

@router.get("/tax-configs", response_model=list[TaxConfigResponse])
async def list_tax_configs(
    actor: Annotated[User, Depends(require_super_admin)],
    db: Annotated[AsyncSession, Depends(get_db)]
):
    from app.models.tax_config import TaxConfig
    res = await db.execute(select(TaxConfig).where(TaxConfig.is_deleted == False).order_by(TaxConfig.country_name))
    return res.scalars().all()


@router.post("/tax-configs", response_model=TaxConfigResponse, status_code=status.HTTP_201_CREATED)
async def create_tax_config(
    payload: TaxConfigCreate,
    actor: Annotated[User, Depends(require_super_admin)],
    db: Annotated[AsyncSession, Depends(get_db)]
):
    from app.models.tax_config import TaxConfig
    tax = TaxConfig(**payload.model_dump())
    db.add(tax)
    await db.commit()
    await db.refresh(tax)
    return tax


@router.patch("/tax-configs/{config_id}", response_model=TaxConfigResponse)
async def update_tax_config(
    config_id: uuid.UUID,
    payload: TaxConfigUpdate,
    actor: Annotated[User, Depends(require_super_admin)],
    db: Annotated[AsyncSession, Depends(get_db)]
):
    from app.models.tax_config import TaxConfig
    config = await db.get(TaxConfig, config_id)
    if not config or config.is_deleted:
        raise HTTPException(status_code=404, detail="Tax config not found")
    for k, v in payload.model_dump(exclude_unset=True).items():
        setattr(config, k, v)
    await db.commit()
    await db.refresh(config)
    return config


@router.delete("/tax-configs/{config_id}")
async def delete_tax_config(
    config_id: uuid.UUID,
    actor: Annotated[User, Depends(require_super_admin)],
    db: Annotated[AsyncSession, Depends(get_db)]
):
    from app.models.tax_config import TaxConfig
    config = await db.get(TaxConfig, config_id)
    if not config or config.is_deleted:
        raise HTTPException(status_code=404, detail="Tax config not found")
    config.is_deleted = True
    await db.commit()
    return {"detail": "Tax config deleted"}


# ==========================================
# PHASE 9: PAYMENT GATEWAY MANAGEMENT
# ==========================================

from app.schemas.payment_gateway import PaymentGatewayCreate, PaymentGatewayUpdate, PaymentGatewayResponse

@router.get("/payment-gateways", response_model=list[PaymentGatewayResponse])
async def list_payment_gateways(
    actor: Annotated[User, Depends(require_super_admin)],
    db: Annotated[AsyncSession, Depends(get_db)]
):
    from app.models.payment_gateway import PaymentGateway
    res = await db.execute(select(PaymentGateway).where(PaymentGateway.is_deleted == False).order_by(PaymentGateway.sort_order))
    gateways = res.scalars().all()
    return [PaymentGatewayResponse.from_model(gw) for gw in gateways]


@router.post("/payment-gateways", response_model=PaymentGatewayResponse, status_code=status.HTTP_201_CREATED)
async def create_payment_gateway(
    payload: PaymentGatewayCreate,
    actor: Annotated[User, Depends(require_super_admin)],
    db: Annotated[AsyncSession, Depends(get_db)]
):
    from app.models.payment_gateway import PaymentGateway
    existing = (await db.execute(select(PaymentGateway).where(PaymentGateway.name == payload.name))).scalar_one_or_none()
    if existing:
        raise HTTPException(status_code=409, detail="Gateway already configured")
    gw = PaymentGateway(**payload.model_dump())
    db.add(gw)
    await db.commit()
    await db.refresh(gw)
    return PaymentGatewayResponse.from_model(gw)


@router.patch("/payment-gateways/{gw_id}", response_model=PaymentGatewayResponse)
async def update_payment_gateway(
    gw_id: uuid.UUID,
    payload: PaymentGatewayUpdate,
    actor: Annotated[User, Depends(require_super_admin)],
    db: Annotated[AsyncSession, Depends(get_db)]
):
    from app.models.payment_gateway import PaymentGateway
    gw = await db.get(PaymentGateway, gw_id)
    if not gw or gw.is_deleted:
        raise HTTPException(status_code=404, detail="Gateway not found")
    for k, v in payload.model_dump(exclude_unset=True).items():
        if v is not None or k in ("api_key", "api_secret", "webhook_secret"):
            setattr(gw, k, v)
    await db.commit()
    await db.refresh(gw)
    return PaymentGatewayResponse.from_model(gw)


@router.post("/payment-gateways/{gw_id}/toggle")
async def toggle_payment_gateway(
    gw_id: uuid.UUID,
    actor: Annotated[User, Depends(require_super_admin)],
    db: Annotated[AsyncSession, Depends(get_db)]
):
    from app.models.payment_gateway import PaymentGateway
    gw = await db.get(PaymentGateway, gw_id)
    if not gw or gw.is_deleted:
        raise HTTPException(status_code=404, detail="Gateway not found")
    gw.is_enabled = not gw.is_enabled
    await db.commit()
    return {"detail": f"Gateway {'enabled' if gw.is_enabled else 'disabled'}", "is_enabled": gw.is_enabled}


# ==========================================
# PHASE 12: NOTIFICATION TEMPLATES
# ==========================================

from app.schemas.notification_template import NotificationTemplateCreate, NotificationTemplateUpdate, NotificationTemplateResponse

@router.get("/notification-templates", response_model=list[NotificationTemplateResponse])
async def list_notification_templates(
    actor: Annotated[User, Depends(require_super_admin)],
    db: Annotated[AsyncSession, Depends(get_db)]
):
    from app.models.notification_template import NotificationTemplate
    res = await db.execute(
        select(NotificationTemplate)
        .where(NotificationTemplate.is_deleted == False)
        .order_by(NotificationTemplate.category, NotificationTemplate.template_key)
    )
    return res.scalars().all()


@router.post("/notification-templates", response_model=NotificationTemplateResponse, status_code=status.HTTP_201_CREATED)
async def create_notification_template(
    payload: NotificationTemplateCreate,
    actor: Annotated[User, Depends(require_super_admin)],
    db: Annotated[AsyncSession, Depends(get_db)]
):
    from app.models.notification_template import NotificationTemplate
    existing = (await db.execute(
        select(NotificationTemplate).where(
            NotificationTemplate.template_key == payload.template_key,
            NotificationTemplate.is_deleted == False
        )
    )).scalar_one_or_none()
    if existing:
        raise HTTPException(status_code=409, detail="Template key already exists")
    tmpl = NotificationTemplate(**payload.model_dump())
    db.add(tmpl)
    await db.commit()
    await db.refresh(tmpl)
    return tmpl


@router.patch("/notification-templates/{tmpl_id}", response_model=NotificationTemplateResponse)
async def update_notification_template(
    tmpl_id: uuid.UUID,
    payload: NotificationTemplateUpdate,
    actor: Annotated[User, Depends(require_super_admin)],
    db: Annotated[AsyncSession, Depends(get_db)]
):
    from app.models.notification_template import NotificationTemplate
    tmpl = await db.get(NotificationTemplate, tmpl_id)
    if not tmpl or tmpl.is_deleted:
        raise HTTPException(status_code=404, detail="Template not found")
    for k, v in payload.model_dump(exclude_unset=True).items():
        setattr(tmpl, k, v)
    await db.commit()
    await db.refresh(tmpl)
    return tmpl


@router.delete("/notification-templates/{tmpl_id}")
async def delete_notification_template(
    tmpl_id: uuid.UUID,
    actor: Annotated[User, Depends(require_super_admin)],
    db: Annotated[AsyncSession, Depends(get_db)]
):
    from app.models.notification_template import NotificationTemplate
    tmpl = await db.get(NotificationTemplate, tmpl_id)
    if not tmpl or tmpl.is_deleted:
        raise HTTPException(status_code=404, detail="Template not found")
    tmpl.is_deleted = True
    await db.commit()
    return {"detail": "Template deleted"}


# ==========================================
# PHASE 15: REPORTS
# ==========================================

@router.get("/reports/revenue")
async def revenue_report(
    actor: Annotated[User, Depends(require_super_admin)],
    db: Annotated[AsyncSession, Depends(get_db)],
    start_date: datetime | None = Query(None),
    end_date: datetime | None = Query(None),
    currency: str = Query("INR")
):
    """Revenue report with MRR/ARR breakdown."""
    if not start_date:
        start_date = datetime.now(timezone.utc).replace(day=1, hour=0, minute=0, second=0)
    if not end_date:
        end_date = datetime.now(timezone.utc)

    total_collected = float((await db.execute(
        select(func.coalesce(func.sum(Invoice.total_amount), 0.0))
        .where(Invoice.payment_status == "paid", Invoice.is_deleted == False,
               Invoice.created_at.between(start_date, end_date))
    )).scalar() or 0.0)

    pending = float((await db.execute(
        select(func.coalesce(func.sum(Invoice.total_amount), 0.0))
        .where(Invoice.payment_status == "unpaid", Invoice.is_deleted == False)
    )).scalar() or 0.0)

    mrr = float((await db.execute(
        select(func.coalesce(func.sum(Plan.monthly_price * TenantSubscription.users_purchased), 0.0))
        .join(Plan, TenantSubscription.plan_id == Plan.id)
        .where(TenantSubscription.status.in_(["active"]), TenantSubscription.is_deleted == False)
    )).scalar() or 0.0)

    plan_dist = (await db.execute(
        select(Plan.display_name, Plan.name, func.count(TenantSubscription.id).label("count"))
        .join(TenantSubscription, TenantSubscription.plan_id == Plan.id)
        .where(TenantSubscription.is_deleted == False, TenantSubscription.status == "active")
        .group_by(Plan.id, Plan.display_name, Plan.name)
        .order_by(func.count(TenantSubscription.id).desc())
    )).all()

    # Monthly breakdown: group paid invoices by month in the date range
    from sqlalchemy import extract, cast, Integer
    monthly_rows = (await db.execute(
        select(
            extract('year', Invoice.created_at).label('year'),
            extract('month', Invoice.created_at).label('month'),
            func.coalesce(func.sum(Invoice.total_amount), 0.0).label('collections'),
            func.count(Invoice.id).label('invoice_count')
        )
        .where(
            Invoice.payment_status == "paid",
            Invoice.is_deleted == False,
            Invoice.created_at.between(start_date, end_date)
        )
        .group_by('year', 'month')
        .order_by('year', 'month')
    )).all()

    monthly_breakdown = [
        {
            "month": f"{int(r.year)}-{int(r.month):02d}",
            "collections": round(float(r.collections), 2),
            "invoice_count": r.invoice_count,
        }
        for r in monthly_rows
    ]

    return {
        "period_start": start_date.date().isoformat(),
        "period_end": end_date.date().isoformat(),
        "currency": currency,
        "mrr": round(mrr, 2),
        "arr": round(mrr * 12, 2),
        "total_collected": round(total_collected, 2),
        "pending": round(pending, 2),
        "monthly_breakdown": monthly_breakdown,
        "top_plans": [{"name": p.display_name or p.name, "active_subscriptions": p.count} for p in plan_dist],
    }


@router.get("/reports/tenants")
async def tenant_report(
    actor: Annotated[User, Depends(require_super_admin)],
    db: Annotated[AsyncSession, Depends(get_db)]
):
    """Tenant distribution summary."""
    total = (await db.execute(select(func.count(Organization.id)).where(Organization.is_deleted == False))).scalar() or 0
    active = (await db.execute(select(func.count(Organization.id)).where(Organization.is_deleted == False, Organization.subscription_status == "active"))).scalar() or 0
    trial = (await db.execute(select(func.count(Organization.id)).where(Organization.is_deleted == False, Organization.subscription_status == "trial"))).scalar() or 0
    expired = (await db.execute(select(func.count(Organization.id)).where(Organization.is_deleted == False, Organization.subscription_status == "expired"))).scalar() or 0
    suspended = (await db.execute(select(func.count(Organization.id)).where(Organization.is_deleted == False, Organization.subscription_status == "suspended"))).scalar() or 0

    plan_dist = (await db.execute(
        select(Organization.subscription_plan, func.count(Organization.id).label("count"))
        .where(Organization.is_deleted == False)
        .group_by(Organization.subscription_plan)
    )).all()

    return {
        "total": total, "active": active, "trial": trial,
        "expired": expired, "suspended": suspended,
        "by_plan": [{"plan": p.subscription_plan, "count": p.count} for p in plan_dist]
    }


@router.get("/reports/seat-utilization")
async def seat_utilization_report(
    actor: Annotated[User, Depends(require_super_admin)],
    db: Annotated[AsyncSession, Depends(get_db)]
):
    """Seat utilization across all tenants."""
    total_licensed = (await db.execute(
        select(func.coalesce(func.sum(TenantSubscription.users_purchased), 0))
        .where(TenantSubscription.is_deleted == False)
    )).scalar() or 0

    total_active = (await db.execute(
        select(func.coalesce(func.sum(TenantSubscription.users_active), 0))
        .where(TenantSubscription.is_deleted == False)
    )).scalar() or 0

    by_org = (await db.execute(
        select(Organization.name, TenantSubscription.users_purchased, TenantSubscription.users_active)
        .join(TenantSubscription, TenantSubscription.organization_id == Organization.id)
        .where(Organization.is_deleted == False, TenantSubscription.is_deleted == False)
        .order_by(TenantSubscription.users_purchased.desc())
        .limit(50)
    )).all()

    return {
        "total_licensed": total_licensed,
        "total_active": total_active,
        "utilization_pct": round(total_active / total_licensed * 100, 1) if total_licensed > 0 else 0.0,
        "by_organization": [
            {
                "name": r.name,
                "licensed": r.users_purchased,
                "active": r.users_active,
                "utilization_pct": round(r.users_active / r.users_purchased * 100, 1) if r.users_purchased > 0 else 0.0
            }
            for r in by_org
        ]
    }


@router.get("/reports/invoices")
async def invoice_report(
    actor: Annotated[User, Depends(require_super_admin)],
    db: Annotated[AsyncSession, Depends(get_db)],
    start_date: datetime | None = Query(None),
    end_date: datetime | None = Query(None)
):
    """Invoice summary report."""
    if not start_date:
        from datetime import timedelta
        start_date = datetime.now(timezone.utc) - timedelta(days=30)
    if not end_date:
        end_date = datetime.now(timezone.utc)

    total_invoices = (await db.execute(
        select(func.count(Invoice.id))
        .where(Invoice.is_deleted == False, Invoice.created_at.between(start_date, end_date))
    )).scalar() or 0

    paid = (await db.execute(
        select(func.count(Invoice.id), func.coalesce(func.sum(Invoice.total_amount), 0.0))
        .where(Invoice.payment_status == "paid", Invoice.is_deleted == False,
               Invoice.created_at.between(start_date, end_date))
    )).one()

    unpaid = (await db.execute(
        select(func.count(Invoice.id), func.coalesce(func.sum(Invoice.total_amount), 0.0))
        .where(Invoice.payment_status == "unpaid", Invoice.is_deleted == False,
               Invoice.created_at.between(start_date, end_date))
    )).one()

    return {
        "period_start": start_date.date().isoformat(),
        "period_end": end_date.date().isoformat(),
        "total_invoices": total_invoices,
        "paid_count": paid[0], "paid_amount": float(paid[1]),
        "unpaid_count": unpaid[0], "unpaid_amount": float(unpaid[1]),
    }


@router.get("/reports/churn")
async def churn_report(
    actor: Annotated[User, Depends(require_super_admin)],
    db: Annotated[AsyncSession, Depends(get_db)]
):
    """
    Churn rate: subscriptions that expired or were cancelled in the last 30 days
    vs total active subscriptions at the start of that period.
    """
    from datetime import timedelta
    now = datetime.now(timezone.utc)
    thirty_days_ago = now - timedelta(days=30)

    churned = (await db.execute(
        select(func.count(TenantSubscription.id))
        .where(
            TenantSubscription.is_deleted == False,
            TenantSubscription.status.in_(["expired", "suspended"]),
            TenantSubscription.end_date.between(thirty_days_ago, now)
        )
    )).scalar() or 0

    active_start = (await db.execute(
        select(func.count(TenantSubscription.id))
        .where(
            TenantSubscription.is_deleted == False,
            TenantSubscription.status == "active",
            TenantSubscription.start_date <= thirty_days_ago
        )
    )).scalar() or 0

    churn_rate = round((churned / active_start * 100), 2) if active_start > 0 else 0.0

    return {
        "period": "last_30_days",
        "churned_subscriptions": churned,
        "active_at_period_start": active_start,
        "churn_rate_pct": churn_rate,
        "healthy": churn_rate < 5.0,
        "benchmark": "< 5% monthly churn is healthy for B2B SaaS"
    }


@router.get("/trial-requests", response_model=List[TrialRequestResponse])
async def list_trial_requests(
    actor: Annotated[User, Depends(require_super_admin)],
    db: Annotated[AsyncSession, Depends(get_db)]
):
    """List all trial requests."""
    from app.models.trial_request import TrialRequest
    stmt = select(TrialRequest).where(TrialRequest.is_deleted == False).order_by(TrialRequest.created_at.desc())
    res = await db.execute(stmt)
    return res.scalars().all()


@router.post("/trial-requests/{id}/approve", response_model=TrialRequestResponse)
async def approve_trial_request(
    id: uuid.UUID,
    actor: Annotated[User, Depends(require_super_admin)],
    db: Annotated[AsyncSession, Depends(get_db)]
):
    """
    Approve a pending trial request, provisioning the Organization,
    User (Owner), 14-day trial subscription, default team, default pipeline,
    and sending a password setup welcome email.
    """
    from datetime import datetime, timezone, timedelta
    from app.models.trial_request import TrialRequest
    from app.models.organization import Organization
    from app.models.user import User
    from app.models.tenant_subscription import TenantSubscription
    from app.models.seat_history import SeatAssignmentHistory
    from app.models.team import Team, TeamMember
    from app.models.plan import Plan
    from app.core.security import generate_random_token, hash_token, get_password_hash
    from app.services.email_service import send_email
    from app.services.audit_service import AuditService
    from app.repositories.organization import OrganizationRepository
    from app.repositories.user import UserRepository
    from app.core.config import settings

    # 1. Fetch Trial Request
    stmt = select(TrialRequest).where(TrialRequest.id == id, TrialRequest.is_deleted == False)
    res = await db.execute(stmt)
    trial_req = res.scalar_one_or_none()
    if not trial_req:
        raise HTTPException(status_code=404, detail="Trial request not found")
    if trial_req.status != "PENDING":
        raise HTTPException(status_code=400, detail=f"Trial request is already {trial_req.status}")

    # 2. Check if a user with that email already exists
    user_stmt = select(User).where(User.email == trial_req.email, User.is_deleted == False)
    user_res = await db.execute(user_stmt)
    if user_res.scalars().first():
        raise HTTPException(status_code=400, detail="A user with this email is already registered")

    # 3. Generate Unique Slug
    base_slug = trial_req.company_name.lower().strip()
    import re
    base_slug = re.sub(r"[^a-z0-9\s-]", "", base_slug)
    base_slug = re.sub(r"\s+", "-", base_slug)
    slug = base_slug
    
    # Ensure uniqueness
    org_repo = OrganizationRepository(db)
    collision_count = 0
    while True:
        existing_org = await org_repo.get_by_slug(slug)
        if not existing_org:
            break
        collision_count += 1
        slug = f"{base_slug}-{collision_count}"

    # 4. Create Organization
    org = await org_repo.create({
        "name": trial_req.company_name,
        "slug": slug
    })

    # 5. Fetch default Trial Plan (Professional)
    plan_stmt = select(Plan).where(
        func.lower(Plan.name) == "professional",
        Plan.is_deleted == False
    )
    plan_res = await db.execute(plan_stmt)
    plan = plan_res.scalars().first()
    if not plan:
        plan_stmt = select(Plan).where(Plan.is_deleted == False)
        plan_res = await db.execute(plan_stmt)
        plan = plan_res.scalars().first()
        if not plan:
            plan = Plan(
                name="Professional",
                display_name="Professional",
                price_inr=1999.0,
                monthly_price=1999.0,
                max_users=1000,
                minimum_users=5,
                maximum_users=1000,
                minimum_contract_months=3,
                extra_user_price=1999.0,
                allow_additional_seats=True,
                storage_limit_gb=10,
                recording_retention_days=90,
                priority_support=True,
                api_access=False,
                is_active=True,
                plan_active=True,
                is_trial=True,
                trial_days=7,
                features={}
            )
            db.add(plan)
            await db.flush()

    # 6. Activate 14-day Trial Subscription
    now_utc = datetime.now(timezone.utc)
    trial_end = now_utc + timedelta(days=14)
    
    sub = TenantSubscription(
        organization_id=org.id,
        plan_id=plan.id,
        status="trial",
        start_date=now_utc,
        end_date=trial_end,
        trial_end_date=trial_end,
        auto_renew=True,
        billing_cycle="monthly",
        users_purchased=10,
        users_active=1
    )
    db.add(sub)
    await db.flush()

    org.subscription_plan = plan.name
    org.max_users = 10
    org.subscription_expires_at = trial_end.replace(tzinfo=None)
    org.subscription_status = "trial"
    db.add(org)

    # 7. Create Organization Owner User
    parts = trial_req.full_name.strip().split(" ", 1)
    first_name = parts[0]
    last_name = parts[1] if len(parts) > 1 else ""

    temp_pwd = secrets.token_urlsafe(32)
    hashed_password = get_password_hash(temp_pwd)

    user_repo = UserRepository(db)
    user = await user_repo.create({
        "organization_id": org.id,
        "email": trial_req.email,
        "hashed_password": hashed_password,
        "first_name": first_name,
        "last_name": last_name,
        "role": "OrgAdmin",
        "is_verified": True,
        "is_active": True,
        "phone": trial_req.phone
    })

    user.seat_number = "Seat-001"
    db.add(user)

    history = SeatAssignmentHistory(
        organization_id=org.id,
        seat_number="Seat-001",
        user_id=user.id,
        action="Assigned",
        performed_by_id=actor.id,
        remarks="Initial trial admin seat assignment"
    )
    db.add(history)

    # 8. Create Default Team
    team = Team(
        organization_id=org.id,
        name="Sales Team",
        code="SLS",
        description="Default sales working group",
        team_leader_id=user.id,
        status="active",
        created_by=user.id
    )
    db.add(team)
    await db.flush()

    team_member = TeamMember(
        organization_id=org.id,
        team_id=team.id,
        user_id=user.id,
        role_in_team="leader"
    )
    db.add(team_member)

    # 9. Generate Password Setup Token
    token = generate_random_token()
    hashed_token = hash_token(token)
    user.reset_token = hashed_token
    user.reset_token_expires = datetime.now(timezone.utc) + timedelta(hours=24)
    db.add(user)

    trial_req.status = "APPROVED"
    db.add(trial_req)

    await db.commit()

    # 10. Send Password Setup Email
    frontend_url = (
        settings.FRONTEND_URL
        or (settings.BACKEND_CORS_ORIGINS[0] if settings.BACKEND_CORS_ORIGINS else None)
        or "http://localhost:5173"
    ).rstrip("/")
    reset_url = f"{frontend_url}/login?token={token}"

    send_email(
        to_email=user.email,
        subject="Welcome to Johnson Softwares CRM - Setup Your Password",
        template_name="trial_approved.html",
        context={
            "reset_url": reset_url,
            "full_name": trial_req.full_name,
            "company_name": trial_req.company_name
        }
    )

    await AuditService(db).log_event(
        actor_id=actor.id,
        organization_id=org.id,
        event_type="TRIAL_REQUEST_APPROVED",
        description=f"Trial request for '{trial_req.company_name}' was approved, tenant created ({slug})"
    )

    return trial_req


@router.post("/trial-requests/{id}/reject", response_model=TrialRequestResponse)
async def reject_trial_request(
    id: uuid.UUID,
    actor: Annotated[User, Depends(require_super_admin)],
    db: Annotated[AsyncSession, Depends(get_db)]
):
    """Reject a pending trial request."""
    from app.models.trial_request import TrialRequest
    from app.services.audit_service import AuditService

    stmt = select(TrialRequest).where(TrialRequest.id == id, TrialRequest.is_deleted == False)
    res = await db.execute(stmt)
    trial_req = res.scalar_one_or_none()
    if not trial_req:
        raise HTTPException(status_code=404, detail="Trial request not found")
    if trial_req.status != "PENDING":
        raise HTTPException(status_code=400, detail=f"Trial request is already {trial_req.status}")

    trial_req.status = "REJECTED"
    db.add(trial_req)
    await db.commit()

    await AuditService(db).log_event(
        actor_id=actor.id,
        organization_id=None,
        event_type="TRIAL_REQUEST_REJECTED",
        description=f"Trial request for '{trial_req.company_name}' ({trial_req.email}) was rejected"
    )

    return trial_req
