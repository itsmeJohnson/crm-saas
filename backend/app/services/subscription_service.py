import uuid
from datetime import datetime, timedelta, timezone
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from fastapi import HTTPException, status

from app.models.tenant_subscription import TenantSubscription
from app.models.plan import Plan
from app.models.user import User
from app.models.organization import Organization
from app.models.invoice import Invoice

class SubscriptionService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_active_subscription(self, organization_id: uuid.UUID) -> TenantSubscription | None:
        """Fetches the active subscription for the tenant."""
        stmt = select(TenantSubscription).where(
            TenantSubscription.organization_id == organization_id,
            TenantSubscription.is_deleted == False
        )
        res = await self.db.execute(stmt)
        return res.scalar_one_or_none()

    async def get_tenant_usage(self, organization_id: uuid.UUID) -> dict:
        """
        Computes the current counts of non-deleted users by subscription role categories:
        - admins (OrgAdmin)
        - managers (Manager)
        - team_leads (Employee reporting to a Manager)
        - employees (Employee reporting to another Employee/TL, or none)
        """
        stmt = select(User).where(
            User.organization_id == organization_id,
            User.is_deleted == False
        )
        res = await self.db.execute(stmt)
        users = res.scalars().all()

        total = len(users)
        admins = sum(1 for u in users if u.role == "OrgAdmin")
        managers = sum(1 for u in users if u.role == "Manager")
        
        # Build map of user_id -> role for fast lookup of managers
        user_roles = {u.id: u.role for u in users}

        team_leads = 0
        employees = 0
        for u in users:
            if u.role == "Employee":
                if u.reporting_to_id and user_roles.get(u.reporting_to_id) == "Manager":
                    team_leads += 1
                else:
                    employees += 1

        return {
            "total_users": total,
            "admins": admins,
            "managers": managers,
            "team_leads": team_leads,
            "employees": employees
        }

    async def get_subscription_details(self, organization_id: uuid.UUID) -> dict:
        """Retrieves subscription model details, plan details, and usage counts."""
        sub = await self.get_active_subscription(organization_id)
        usage = await self.get_tenant_usage(organization_id)

        # Build usage meters
        if sub and sub.plan:
            plan = sub.plan
            usage_meters = {
                "total_users": {
                    "current": usage["total_users"],
                    "limit": plan.max_users,
                    "percent": round((usage["total_users"] / plan.max_users) * 100, 2) if plan.max_users > 0 else 0
                },
                "admins": {
                    "current": usage["admins"],
                    "limit": plan.max_admins,
                    "percent": round((usage["admins"] / plan.max_admins) * 100, 2) if plan.max_admins > 0 else 0
                },
                "managers": {
                    "current": usage["managers"],
                    "limit": plan.max_managers,
                    "percent": round((usage["managers"] / plan.max_managers) * 100, 2) if plan.max_managers > 0 else 0
                },
                "team_leads": {
                    "current": usage["team_leads"],
                    "limit": plan.max_team_leads,
                    "percent": round((usage["team_leads"] / plan.max_team_leads) * 100, 2) if plan.max_team_leads > 0 else 0
                },
                "employees": {
                    "current": usage["employees"],
                    "limit": plan.max_employees,
                    "percent": round((usage["employees"] / plan.max_employees) * 100, 2) if plan.max_employees > 0 else 0
                }
            }
        else:
            # Fallback when no subscription exists (e.g. initial setup / testing)
            org_stmt = select(Organization).where(Organization.id == organization_id)
            org_res = await self.db.execute(org_stmt)
            org = org_res.scalar_one_or_none()
            max_users = org.max_users if org else 50
            usage_meters = {
                "total_users": {
                    "current": usage["total_users"], 
                    "limit": max_users, 
                    "percent": round((usage["total_users"] / max_users) * 100, 2) if max_users > 0 else 0.0
                },
                "admins": {"current": usage["admins"], "limit": max_users, "percent": 0.0},
                "managers": {"current": usage["managers"], "limit": max_users, "percent": 0.0},
                "team_leads": {"current": usage["team_leads"], "limit": max_users, "percent": 0.0},
                "employees": {"current": usage["employees"], "limit": max_users, "percent": 0.0}
            }

        return {
            "subscription": sub,
            "usage": usage_meters
        }

    async def check_user_creation_limit(self, organization_id: uuid.UUID, role: str, reporting_to_id: uuid.UUID | None = None) -> None:
        """
        Verifies if adding a new user of specified role and reporting structure
        violates the subscription limits of the tenant.
        Raises 403 HTTP Exception if limits are exceeded or subscription is inactive.
        """
        sub = await self.get_active_subscription(organization_id)
        if not sub:
            # Fall back to Organization fields for backwards compatibility/testing
            org_stmt = select(Organization).where(Organization.id == organization_id)
            org_res = await self.db.execute(org_stmt)
            org = org_res.scalar_one_or_none()
            if not org:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="No active subscription found for your organization."
                )
            
            if org.subscription_status in ["expired", "suspended"]:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail=f"Subscription is currently {org.subscription_status}. Please renew your plan to reactivate user changes."
                )
            
            usage = await self.get_tenant_usage(organization_id)
            max_users = org.max_users or 50
            if usage["total_users"] >= max_users:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail=f"User limit reached. Your plan allows a maximum of {max_users} total users."
                )
            return


        if sub.status in ["expired", "suspended"]:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Subscription is currently {sub.status}. Please renew your plan to reactivate user changes."
            )

        # Get current usage
        usage = await self.get_tenant_usage(organization_id)
        plan = sub.plan

        # Verify overall total limit
        if usage["total_users"] >= plan.max_users:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"User limit reached. Your plan allows a maximum of {plan.max_users} total users."
            )

        # Verify role-specific limit
        if role == "OrgAdmin":
            if usage["admins"] >= plan.max_admins:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail=f"Admin limit reached. Your plan allows a maximum of {plan.max_admins} OrgAdmins."
                )
        elif role == "Manager":
            if usage["managers"] >= plan.max_managers:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail=f"Manager limit reached. Your plan allows a maximum of {plan.max_managers} Managers."
                )
        elif role == "Employee":
            # Determine if it's a Team Leader or Telecaller
            is_tl = False
            if reporting_to_id:
                # Query parent role
                parent_stmt = select(User.role).where(User.id == reporting_to_id)
                parent_res = await self.db.execute(parent_stmt)
                parent_role = parent_res.scalar()
                if parent_role == "Manager":
                    is_tl = True

            if is_tl:
                if usage["team_leads"] >= plan.max_team_leads:
                    raise HTTPException(
                        status_code=status.HTTP_403_FORBIDDEN,
                        detail=f"Team Leader limit reached. Your plan allows a maximum of {plan.max_team_leads} Team Leaders."
                    )
            else:
                if usage["employees"] >= plan.max_employees:
                    raise HTTPException(
                        status_code=status.HTTP_403_FORBIDDEN,
                        detail=f"Telecaller limit reached. Your plan allows a maximum of {plan.max_employees} Telecallers."
                    )
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid user role: {role}"
            )

    async def renew_subscription(self, organization_id: uuid.UUID) -> TenantSubscription:
        """
        Renews/extends the tenant's subscription by the plan's billing cycle.
        Creates a corresponding Invoice.
        """
        sub = await self.get_active_subscription(organization_id)
        if not sub:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Subscription record not found."
            )

        plan = sub.plan
        days_to_add = plan.billing_cycle_days
        now = datetime.now(timezone.utc)
        
        # If subscription is active, extend from current end date.
        # If it is expired, extend from now.
        start_date = sub.end_date if sub.end_date > now else now
        new_end_date = start_date + timedelta(days=days_to_add)

        sub.start_date = start_date
        sub.end_date = new_end_date
        sub.status = "active"
        sub.updated_at = now
        
        # Load Invoice Configuration dynamically
        from app.models.invoice_config import InvoiceConfig
        config_stmt = select(InvoiceConfig).where(InvoiceConfig.id == "default")
        config_res = await self.db.execute(config_stmt)
        invoice_config = config_res.scalar_one_or_none()
        if not invoice_config:
            invoice_config = InvoiceConfig(id="default")
            self.db.add(invoice_config)
            await self.db.flush()

        # Create Invoice dynamically using configuration
        prefix = invoice_config.invoice_prefix or "INV"
        currency = invoice_config.currency or "INR"
        invoice_num = f"{prefix}-{uuid.uuid4().hex[:8].upper()}-{int(now.timestamp())}"
        
        amount = float(plan.price_inr)
        setup_charges = float(plan.setup_charges) if hasattr(plan, "setup_charges") else 0.0
        discount_percentage = float(plan.discount_percentage) if hasattr(plan, "discount_percentage") else 0.0
        gst_percentage = float(plan.gst_percentage) if hasattr(plan, "gst_percentage") else 0.0
        
        discount_amount = amount * (discount_percentage / 100.0)
        taxable_amount = amount - discount_amount
        gst_amount = taxable_amount * (gst_percentage / 100.0)
        total_amount = taxable_amount + setup_charges + gst_amount

        invoice = Invoice(
            organization_id=organization_id,
            invoice_number=invoice_num,
            amount=total_amount,
            status="Paid",  # Simulating immediate paid status on renewal
            due_date=now + timedelta(days=7),
            plan_name=plan.name,
            amount_inr=total_amount if currency == "INR" else 0.0,
            currency=currency,
            issue_date=now,
            payment_status="paid",
            subscription_id=sub.id,
            setup_charges=setup_charges,
            extra_users_amount=0.0,
            discount_amount=discount_amount,
            gst_amount=gst_amount,
            total_amount=total_amount
        )
        self.db.add(invoice)
        
        # Update denormalized Organization fields for backward compatibility
        org_stmt = select(Organization).where(Organization.id == organization_id)
        org_res = await self.db.execute(org_stmt)
        org = org_res.scalar_one_or_none()
        if org:
            org.subscription_plan = plan.name
            org.subscription_expires_at = new_end_date
            org.subscription_status = "active"
            org.max_users = plan.max_users
            
        await self.db.commit()
        await self.db.refresh(sub)
        return sub
