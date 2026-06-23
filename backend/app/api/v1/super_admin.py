import uuid
import secrets
from datetime import datetime, timezone
from typing import Annotated, List
from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File, Request
from app.schemas.invoice_config import InvoiceConfigResponse, InvoiceConfigUpdate
from app.services.invoice_config_service import InvoiceConfigService
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, delete

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
    PlanCreate, PlanResponse, FeatureResponse, PlanFeatureResponse,
    PlanFeatureToggle, PlanFeatureClone, SystemSettingRequest, SystemSettingResponse
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
    payload: dict,  # Freeform dict to allow partial updates
    actor: Annotated[User, Depends(require_super_admin)],
    db: Annotated[AsyncSession, Depends(get_db)]
):
    """Partially update a plan."""
    plan = await db.get(Plan, plan_id)
    if not plan or plan.is_deleted:
        raise HTTPException(status_code=404, detail="Plan not found")
    
    old_val = {}
    new_val = {}
    
    for key, val in payload.items():
        if hasattr(plan, key):
            current_value = getattr(plan, key)
            if current_value != val:
                old_val[key] = str(current_value) if current_value is not None else ""
                new_val[key] = str(val) if val is not None else ""
                setattr(plan, key, val)
            
    # Keep price_inr in sync with monthly_price
    if "monthly_price" in payload:
        plan.price_inr = payload["monthly_price"]

    # Keep is_active in sync with plan_active if updated
    if "plan_active" in payload:
        plan.is_active = payload["plan_active"]

    await db.commit()
    await db.refresh(plan)

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
    stmt = select(PlanFeature).where(PlanFeature.is_deleted == False)
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
    await db.refresh(mapping)
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
    """Suspend a tenant organization."""
    return await toggle_tenant_subscription_status(org_id=org_id, actor=actor, db=db, status_val="suspended")

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
    await service.upload_logo(
        file_bytes=file_bytes,
        original_filename=file.filename or "logo.png",
        organization_id=actor.organization_id,
        actor_user_id=actor.id,
        ip_address=ip_address,
        user_agent=user_agent
    )
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
    await service.upload_qr_code(
        file_bytes=file_bytes,
        original_filename=file.filename or "qr.png",
        organization_id=actor.organization_id,
        actor_user_id=actor.id,
        ip_address=ip_address,
        user_agent=user_agent
    )
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

