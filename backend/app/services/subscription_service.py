import uuid
from datetime import datetime, timedelta, timezone
from sqlalchemy import select, func
from sqlalchemy.orm import selectinload
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
        """Fetches the active subscription for the tenant, with plan eagerly loaded."""
        stmt = (
            select(TenantSubscription)
            .options(selectinload(TenantSubscription.plan))
            .where(
                TenantSubscription.organization_id == organization_id,
                TenantSubscription.is_deleted == False
            )
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
            User.is_deleted == False,
            User.seat_number.isnot(None)
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
            limit = sub.users_purchased
            usage_meters = {
                "total_users": {
                    "current": usage["total_users"],
                    "limit": limit,
                    "percent": round((usage["total_users"] / limit) * 100, 2) if limit > 0 else 0
                },
                "admins": {
                    "current": usage["admins"],
                    "limit": limit,
                    "percent": round((usage["admins"] / limit) * 100, 2) if limit > 0 else 0
                },
                "managers": {
                    "current": usage["managers"],
                    "limit": limit,
                    "percent": round((usage["managers"] / limit) * 100, 2) if limit > 0 else 0
                },
                "team_leads": {
                    "current": usage["team_leads"],
                    "limit": limit,
                    "percent": round((usage["team_leads"] / limit) * 100, 2) if limit > 0 else 0
                },
                "employees": {
                    "current": usage["employees"],
                    "limit": limit,
                    "percent": round((usage["employees"] / limit) * 100, 2) if limit > 0 else 0
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

        # Verify overall total limit based on users_purchased (Licensed Seats)
        limit = sub.users_purchased
        if usage["total_users"] >= limit:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"No available seats. Your subscription has a limit of {limit} Licensed Seats. Please purchase additional seats or replace an existing inactive employee."
            )

        if role not in ["OrgAdmin", "Manager", "Employee"]:
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

        # Load CommercialSettings dynamically
        from app.models.commercial_settings import CommercialSettings
        comm_stmt = select(CommercialSettings).where(CommercialSettings.id == "default")
        comm_res = await self.db.execute(comm_stmt)
        comm_settings = comm_res.scalar_one_or_none()
        if not comm_settings:
            comm_settings = CommercialSettings(id="default")
            self.db.add(comm_settings)
            await self.db.flush()

        # Create Invoice dynamically using configurations
        prefix = invoice_config.invoice_prefix or "INV"
        currency = invoice_config.currency or comm_settings.default_currency or "INR"
        invoice_num = f"{prefix}-{uuid.uuid4().hex[:8].upper()}-{int(now.timestamp())}"
        
        # Apply seat reduction if scheduled for the next cycle
        if sub.users_purchased_next is not None:
            sub.users_purchased = sub.users_purchased_next
            sub.users_purchased_next = None

        price_per_seat = float(plan.monthly_price if plan.monthly_price > 0 else plan.price_inr)
        amount = price_per_seat * sub.users_purchased
        
        # Determine Setup Charge fallback
        setup_charges = float(plan.setup_charges) if plan.setup_charges is not None else float(comm_settings.default_setup_charge)
        if comm_settings.free_setup_on_annual and plan.billing_cycle_days >= 360:
            setup_charges = 0.0

        # Determine Discount fallback
        discount_percentage = float(plan.discount_percentage) if plan.discount_percentage is not None else float(comm_settings.default_discount_percentage)
        if not comm_settings.allow_custom_discount:
            discount_percentage = float(comm_settings.default_discount_percentage)
        if discount_percentage > float(comm_settings.maximum_discount_percentage):
            discount_percentage = float(comm_settings.maximum_discount_percentage)

        # Determine GST fallback
        gst_percentage = float(plan.gst_percentage) if plan.gst_percentage is not None else float(comm_settings.default_gst)
        if gst_percentage == 0.0:
            gst_percentage = float(comm_settings.default_gst)

        # Apply GST inclusive vs exclusive calculations
        if comm_settings.gst_inclusive:
            # Base amount includes GST: base_price = taxable + gst
            total_sub_after_discount = amount * (1.0 - (discount_percentage / 100.0))
            gst_amount = total_sub_after_discount * (gst_percentage / (100.0 + gst_percentage))
            taxable_amount = total_sub_after_discount - gst_amount
            discount_amount = amount * (discount_percentage / 100.0) / (1.0 + (gst_percentage / 100.0))
            total_amount = total_sub_after_discount + setup_charges
        else:
            # Base amount does not include GST
            discount_amount = amount * (discount_percentage / 100.0)
            taxable_amount = amount - discount_amount
            gst_amount = taxable_amount * (gst_percentage / 100.0)
            total_amount = taxable_amount + setup_charges + gst_amount

        invoice = Invoice(
            organization_id=organization_id,
            invoice_number=invoice_num,
            amount=total_amount,
            status="Paid",  # Simulating immediate paid status on renewal
            due_date=now + timedelta(days=comm_settings.grace_period_days),
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
            org.max_users = sub.users_purchased
            
        await self.db.commit()

        # Invalidate features cache
        from app.dependencies.feature_guard import invalidate_tenant_features
        await invalidate_tenant_features(organization_id)

        await self.db.refresh(sub)
        return sub

