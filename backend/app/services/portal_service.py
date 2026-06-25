import uuid
from datetime import datetime, timedelta, timezone
from typing import List, Optional
from sqlalchemy import select, func, desc
from sqlalchemy.ext.asyncio import AsyncSession
from fastapi import HTTPException, status

from app.models.organization import Organization
from app.models.tenant_subscription import TenantSubscription
from app.models.plan import Plan
from app.models.invoice import Invoice
from app.models.payment import Payment
from app.models.audit_log import AuditLog
from app.models.user import User
from app.models.activity import Activity
from app.models.commercial_settings import CommercialSettings
from app.models.invoice_config import InvoiceConfig
from app.services.audit_service import AuditService

class PortalService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.audit_service = AuditService(db)

    async def get_dashboard_stats(self, organization_id: uuid.UUID) -> dict:
        # 1. Fetch Organization & Active Subscription
        org_stmt = select(Organization).where(Organization.id == organization_id)
        org_res = await self.db.execute(org_stmt)
        org = org_res.scalar_one_or_none()
        if not org:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Organization not found.")

        sub_stmt = select(TenantSubscription).where(
            TenantSubscription.organization_id == organization_id,
            TenantSubscription.is_deleted == False
        )
        sub_res = await self.db.execute(sub_stmt)
        sub = sub_res.scalar_one_or_none()

        plan = None
        if sub:
            plan_stmt = select(Plan).where(Plan.id == sub.plan_id)
            plan_res = await self.db.execute(plan_stmt)
            plan = plan_res.scalar_one_or_none()

        # 2. Compute Active User Count
        user_count_stmt = select(func.count(User.id)).where(
            User.organization_id == organization_id,
            User.is_deleted == False
        )
        user_count_res = await self.db.execute(user_count_stmt)
        users_active = user_count_res.scalar() or 0

        # Limits
        max_users = plan.max_users if plan else org.max_users
        storage_limit_gb = (plan.storage_limit_gb if plan else 50) + (org.extra_storage_gb or 0)
        
        # 3. Compute Storage Used
        storage_used = float(sub.storage_used) if sub else 0.0

        # 4. Count Call Recordings
        recording_count_stmt = select(func.count(Activity.id)).where(
            Activity.organization_id == organization_id,
            Activity.recording_url.is_not(None),
            Activity.is_deleted == False
        )
        recording_count_res = await self.db.execute(recording_count_stmt)
        recording_count = recording_count_res.scalar() or 0

        # 5. Pending Invoice Amount
        pending_invoices_stmt = select(func.sum(Invoice.amount)).where(
            Invoice.organization_id == organization_id,
            Invoice.payment_status == "unpaid",
            Invoice.is_deleted == False
        )
        pending_invoices_res = await self.db.execute(pending_invoices_stmt)
        pending_amount = float(pending_invoices_res.scalar() or 0.0)

        # 6. Last Payment Amount
        last_payment_stmt = select(Invoice.amount).where(
            Invoice.organization_id == organization_id,
            Invoice.payment_status == "paid",
            Invoice.is_deleted == False
        ).order_by(desc(Invoice.issue_date)).limit(1)
        last_payment_res = await self.db.execute(last_payment_stmt)
        last_payment_amount = float(last_payment_res.scalar() or 0.0)

        # 7. Days Remaining / Upcoming Renewal
        days_remaining = 0
        upcoming_renewal = None
        subscription_status = "inactive"

        if sub:
            now = datetime.now(timezone.utc)
            upcoming_renewal = sub.end_date
            subscription_status = sub.status
            end_date = sub.end_date
            if end_date.tzinfo is None:
                end_date = end_date.replace(tzinfo=timezone.utc)
            if end_date > now:
                days_remaining = (end_date - now).days
            else:
                days_remaining = 0

        # 8. Recent Activities (Fetch last 5 Audit Logs)
        audit_stmt = select(AuditLog).where(
            AuditLog.organization_id == organization_id
        ).order_by(desc(AuditLog.created_at)).limit(5)
        audit_res = await self.db.execute(audit_stmt)
        audit_logs = audit_res.scalars().all()
        
        recent_activities = []
        for log in audit_logs:
            recent_activities.append({
                "id": str(log.id),
                "action": log.action,
                "resource_type": log.resource_type,
                "created_at": log.created_at.isoformat(),
                "metadata": log.action_metadata or {}
            })

        return {
            "plan_name": plan.display_name or plan.name if plan else org.subscription_plan,
            "subscription_status": subscription_status,
            "days_remaining": days_remaining,
            "users": {
                "current": users_active,
                "limit": max_users,
                "percent": round((users_active / max_users) * 100, 2) if max_users > 0 else 0.0
            },
            "storage": {
                "used_gb": storage_used,
                "limit_gb": storage_limit_gb,
                "percent": round((storage_used / storage_limit_gb) * 100, 2) if storage_limit_gb > 0 else 0.0
            },
            "recording_count": recording_count,
            "pending_invoice_amount": pending_amount,
            "last_payment_amount": last_payment_amount,
            "upcoming_renewal_date": upcoming_renewal,
            "recent_activities": recent_activities
        }

    async def buy_extra_seats(
        self, organization_id: uuid.UUID, actor_user_id: uuid.UUID, actor_name: str, user_count: int, gateway: str
    ) -> Invoice:
        if user_count < 1:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Seat count must be at least 1.")

        # Load configurations
        comm_stmt = select(CommercialSettings).where(CommercialSettings.id == "default")
        comm_res = await self.db.execute(comm_stmt)
        comm_settings = comm_res.scalar_one_or_none()
        if not comm_settings:
            comm_settings = CommercialSettings(id="default")
            self.db.add(comm_settings)
            await self.db.flush()

        sub_stmt = select(TenantSubscription).where(
            TenantSubscription.organization_id == organization_id,
            TenantSubscription.is_deleted == False
        )
        sub_res = await self.db.execute(sub_stmt)
        sub = sub_res.scalar_one_or_none()

        plan = None
        if sub:
            plan_stmt = select(Plan).where(Plan.id == sub.plan_id)
            plan_res = await self.db.execute(plan_stmt)
            plan = plan_res.scalar_one_or_none()

        # Seat unit price
        unit_price = 150.0
        if plan and plan.extra_user_price:
            unit_price = float(plan.extra_user_price)
        elif comm_settings.default_extra_user_price:
            unit_price = float(comm_settings.default_extra_user_price)

        base_amount = unit_price * user_count
        gst_rate = float(comm_settings.default_gst)

        if comm_settings.gst_inclusive:
            # Base amount includes GST
            gst_amount = base_amount * (gst_rate / (100.0 + gst_rate))
            taxable_amount = base_amount - gst_amount
            total_amount = base_amount
        else:
            # Base amount does not include GST
            taxable_amount = base_amount
            gst_amount = taxable_amount * (gst_rate / 100.0)
            total_amount = taxable_amount + gst_amount

        # Load invoice numbering
        config_stmt = select(InvoiceConfig).where(InvoiceConfig.id == "default")
        config_res = await self.db.execute(config_stmt)
        invoice_config = config_res.scalar_one_or_none()
        if not invoice_config:
            invoice_config = InvoiceConfig(id="default")
            self.db.add(invoice_config)
            await self.db.flush()

        prefix = invoice_config.invoice_prefix or "INV"
        now = datetime.now(timezone.utc)
        invoice_num = f"{prefix}-SEATS-{uuid.uuid4().hex[:6].upper()}-{int(now.timestamp())}"

        invoice = Invoice(
            organization_id=organization_id,
            invoice_number=invoice_num,
            amount=total_amount,
            status="Pending",
            due_date=now + timedelta(days=comm_settings.grace_period_days),
            plan_name=plan.name if plan else "Standard",
            amount_inr=total_amount if comm_settings.default_currency == "INR" else 0.0,
            currency=comm_settings.default_currency,
            issue_date=now,
            payment_status="unpaid",
            subscription_id=sub.id if sub else None,
            setup_charges=0.0,
            extra_users_amount=total_amount,
            discount_amount=0.0,
            gst_amount=gst_amount,
            total_amount=total_amount,
            pdf_file_path=None
        )
        # Store metadata to execute action when invoice is paid
        invoice.action_metadata = {
            "action_type": "buy_extra_seats",
            "user_count": user_count,
            "gateway": gateway
        }
        self.db.add(invoice)
        await self.db.commit()
        await self.db.refresh(invoice)

        await self.audit_service.log_event(
            organization_id=organization_id,
            actor_user_id=actor_user_id,
            action="GENERATE_EXTRA_SEATS_INVOICE",
            resource_type="INVOICE",
            resource_id=str(invoice.id),
            action_metadata={"user_count": user_count, "amount": total_amount}
        )
        return invoice

    async def buy_extra_storage(
        self, organization_id: uuid.UUID, actor_user_id: uuid.UUID, actor_name: str, storage_gb: int, gateway: str
    ) -> Invoice:
        if storage_gb < 1:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Storage count must be at least 1 GB.")

        comm_stmt = select(CommercialSettings).where(CommercialSettings.id == "default")
        comm_res = await self.db.execute(comm_stmt)
        comm_settings = comm_res.scalar_one_or_none()
        if not comm_settings:
            comm_settings = CommercialSettings(id="default")
            self.db.add(comm_settings)
            await self.db.flush()

        sub_stmt = select(TenantSubscription).where(
            TenantSubscription.organization_id == organization_id,
            TenantSubscription.is_deleted == False
        )
        sub_res = await self.db.execute(sub_stmt)
        sub = sub_res.scalar_one_or_none()

        plan = None
        if sub:
            plan_stmt = select(Plan).where(Plan.id == sub.plan_id)
            plan_res = await self.db.execute(plan_stmt)
            plan = plan_res.scalar_one_or_none()

        # Let's charge flat 10.0 INR per GB
        unit_price = 10.0
        base_amount = unit_price * storage_gb
        gst_rate = float(comm_settings.default_gst)

        if comm_settings.gst_inclusive:
            gst_amount = base_amount * (gst_rate / (100.0 + gst_rate))
            taxable_amount = base_amount - gst_amount
            total_amount = base_amount
        else:
            taxable_amount = base_amount
            gst_amount = taxable_amount * (gst_rate / 100.0)
            total_amount = taxable_amount + gst_amount

        config_stmt = select(InvoiceConfig).where(InvoiceConfig.id == "default")
        config_res = await self.db.execute(config_stmt)
        invoice_config = config_res.scalar_one_or_none()
        if not invoice_config:
            invoice_config = InvoiceConfig(id="default")
            self.db.add(invoice_config)
            await self.db.flush()

        prefix = invoice_config.invoice_prefix or "INV"
        now = datetime.now(timezone.utc)
        invoice_num = f"{prefix}-STOR-{uuid.uuid4().hex[:6].upper()}-{int(now.timestamp())}"

        invoice = Invoice(
            organization_id=organization_id,
            invoice_number=invoice_num,
            amount=total_amount,
            status="Pending",
            due_date=now + timedelta(days=comm_settings.grace_period_days),
            plan_name=plan.name if plan else "Standard",
            amount_inr=total_amount if comm_settings.default_currency == "INR" else 0.0,
            currency=comm_settings.default_currency,
            issue_date=now,
            payment_status="unpaid",
            subscription_id=sub.id if sub else None,
            setup_charges=0.0,
            extra_users_amount=0.0,
            discount_amount=0.0,
            gst_amount=gst_amount,
            total_amount=total_amount,
            pdf_file_path=None
        )
        invoice.action_metadata = {
            "action_type": "buy_extra_storage",
            "storage_gb": storage_gb,
            "gateway": gateway
        }
        self.db.add(invoice)
        await self.db.commit()
        await self.db.refresh(invoice)

        await self.audit_service.log_event(
            organization_id=organization_id,
            actor_user_id=actor_user_id,
            action="GENERATE_EXTRA_STORAGE_INVOICE",
            resource_type="INVOICE",
            resource_id=str(invoice.id),
            action_metadata={"storage_gb": storage_gb, "amount": total_amount}
        )
        return invoice

    async def pay_invoice(
        self, organization_id: uuid.UUID, invoice_id: uuid.UUID, gateway: str, transaction_id: Optional[str], actor_user_id: uuid.UUID, actor_name: str
    ) -> Invoice:
        stmt = select(Invoice).where(
            Invoice.id == invoice_id,
            Invoice.organization_id == organization_id,
            Invoice.is_deleted == False
        )
        res = await self.db.execute(stmt)
        invoice = res.scalar_one_or_none()
        if not invoice:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Invoice not found.")

        if invoice.payment_status == "paid":
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invoice is already paid.")

        now = datetime.now(timezone.utc)
        
        # 1. Update Invoice status
        invoice.status = "Paid"
        invoice.payment_status = "paid"
        
        # 2. Register Payment record
        payment = Payment(
            invoice_id=invoice.id,
            payment_reference=f"REF-{uuid.uuid4().hex[:8].upper()}",
            gateway=gateway,
            status="Paid",
            transaction_id=transaction_id or f"TXN-{uuid.uuid4().hex[:12].upper()}",
            paid_date=now,
            remarks=f"Self-service payment via {gateway}"
        )
        self.db.add(payment)

        # 3. Apply Side Effects
        metadata = invoice.action_metadata or {}
        action_type = metadata.get("action_type")

        # Fetch Organization
        org_stmt = select(Organization).where(Organization.id == organization_id)
        org_res = await self.db.execute(org_stmt)
        org = org_res.scalar_one_or_none()

        # Fetch TenantSubscription
        sub_stmt = select(TenantSubscription).where(
            TenantSubscription.organization_id == organization_id,
            TenantSubscription.is_deleted == False
        )
        sub_res = await self.db.execute(sub_stmt)
        sub = sub_res.scalar_one_or_none()

        if action_type == "buy_extra_seats":
            user_count = metadata.get("user_count", 0)
            if org:
                org.max_users += user_count
            if sub:
                sub.users_purchased += user_count
            
        elif action_type == "buy_extra_storage":
            storage_gb = metadata.get("storage_gb", 0)
            if org:
                org.extra_storage_gb += storage_gb

        elif action_type == "upgrade_plan":
            plan_id = uuid.UUID(metadata.get("plan_id"))
            billing_cycle = metadata.get("billing_cycle", "monthly")
            licensed_seats = metadata.get("licensed_seats")
            plan_stmt = select(Plan).where(Plan.id == plan_id)
            plan_res = await self.db.execute(plan_stmt)
            plan = plan_res.scalar_one_or_none()
            if plan and sub:
                sub.plan_id = plan.id
                sub.billing_cycle = billing_cycle
                if licensed_seats:
                    sub.users_purchased = int(licensed_seats)
                else:
                    sub.users_purchased = max(sub.users_purchased, plan.minimum_users)
                days_to_add = 30
                if billing_cycle == "quarterly":
                    days_to_add = 90
                elif billing_cycle == "annual":
                    days_to_add = 365
                start_date = now
                sub.start_date = start_date
                sub.end_date = start_date + timedelta(days=days_to_add)
                sub.status = "active"
                sub.updated_at = now
                
                if org:
                    org.subscription_plan = plan.name
                    org.max_users = sub.users_purchased
                    org.subscription_expires_at = sub.end_date
                    org.subscription_status = "active"

        else:
            # Default fallback: it's a plan renewal or standard subscription invoice
            if sub:
                plan_stmt = select(Plan).where(Plan.id == sub.plan_id)
                plan_res = await self.db.execute(plan_stmt)
                plan = plan_res.scalar_one_or_none()
                days_to_add = plan.billing_cycle_days if plan else 30
                sub_end_date = sub.end_date
                if sub_end_date.tzinfo is None:
                    sub_end_date = sub_end_date.replace(tzinfo=timezone.utc)
                start_date = sub.end_date if sub_end_date > now else now
                sub.start_date = start_date
                sub.end_date = start_date + timedelta(days=days_to_add)
                sub.status = "active"
                sub.updated_at = now

                if org:
                    org.subscription_expires_at = sub.end_date
                    org.subscription_status = "active"

        await self.db.commit()

        # Invalidate features cache
        from app.dependencies.feature_guard import invalidate_tenant_features
        await invalidate_tenant_features(organization_id)

        await self.db.refresh(invoice)

        # 4. Log audit log
        await self.audit_service.log_event(
            organization_id=organization_id,
            actor_user_id=actor_user_id,
            action="PAY_INVOICE_SUCCESS",
            resource_type="INVOICE",
            resource_id=str(invoice.id),
            action_metadata={"gateway": gateway, "transaction_id": transaction_id, "amount": float(invoice.amount)}
        )

        return invoice

    async def upgrade_subscription(
        self, organization_id: uuid.UUID, actor_user_id: uuid.UUID, actor_name: str, plan_id: uuid.UUID, billing_cycle: str, gateway: str
    ) -> Invoice:
        # Load configurations
        comm_stmt = select(CommercialSettings).where(CommercialSettings.id == "default")
        comm_res = await self.db.execute(comm_stmt)
        comm_settings = comm_res.scalar_one_or_none()
        if not comm_settings:
            comm_settings = CommercialSettings(id="default")
            self.db.add(comm_settings)
            await self.db.flush()

        plan_stmt = select(Plan).where(Plan.id == plan_id, Plan.plan_active == True, Plan.is_deleted == False)
        plan_res = await self.db.execute(plan_stmt)
        plan = plan_res.scalar_one_or_none()
        if not plan:
            # try fallback to is_active filter just in case
            plan_stmt = select(Plan).where(Plan.id == plan_id, Plan.is_active == True, Plan.is_deleted == False)
            plan_res = await self.db.execute(plan_stmt)
            plan = plan_res.scalar_one_or_none()
            if not plan:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Plan not found.")

        # Fetch active sub if any
        sub_stmt = select(TenantSubscription).where(
            TenantSubscription.organization_id == organization_id,
            TenantSubscription.is_deleted == False
        )
        sub_res = await self.db.execute(sub_stmt)
        sub = sub_res.scalar_one_or_none()

        licensed_seats = max(sub.users_purchased, plan.minimum_users) if sub else max(plan.minimum_users, 10)

        # Determine price per seat based on cycle
        if billing_cycle == "annual":
            price_per_seat = float(plan.annual_price) if plan.annual_price > 0 else float(plan.monthly_price) * 12
        elif billing_cycle == "quarterly":
            price_per_seat = float(plan.quarterly_price) if plan.quarterly_price > 0 else float(plan.monthly_price) * 3
        else:
            price_per_seat = float(plan.monthly_price) if plan.monthly_price > 0 else float(plan.price_inr)

        base_amount = price_per_seat * licensed_seats

        gst_rate = float(comm_settings.default_gst)
        if comm_settings.gst_inclusive:
            gst_amount = base_amount * (gst_rate / (100.0 + gst_rate))
            taxable_amount = base_amount - gst_amount
            total_amount = base_amount
        else:
            taxable_amount = base_amount
            gst_amount = taxable_amount * (gst_rate / 100.0)
            total_amount = taxable_amount + gst_amount

        # Load invoice numbering
        config_stmt = select(InvoiceConfig).where(InvoiceConfig.id == "default")
        config_res = await self.db.execute(config_stmt)
        invoice_config = config_res.scalar_one_or_none()
        if not invoice_config:
            invoice_config = InvoiceConfig(id="default")
            self.db.add(invoice_config)
            await self.db.flush()

        prefix = invoice_config.invoice_prefix or "INV"
        now = datetime.now(timezone.utc)
        invoice_num = f"{prefix}-UPGR-{uuid.uuid4().hex[:6].upper()}-{int(now.timestamp())}"

        invoice = Invoice(
            organization_id=organization_id,
            invoice_number=invoice_num,
            amount=total_amount,
            status="Pending",
            due_date=now + timedelta(days=comm_settings.grace_period_days),
            plan_name=plan.name,
            amount_inr=total_amount if comm_settings.default_currency == "INR" else 0.0,
            currency=comm_settings.default_currency,
            issue_date=now,
            payment_status="unpaid",
            subscription_id=sub.id if sub else None,
            setup_charges=float(plan.setup_charges or 0.0),
            extra_users_amount=0.0,
            discount_amount=0.0,
            gst_amount=gst_amount,
            total_amount=total_amount + float(plan.setup_charges or 0.0),
            pdf_file_path=None
        )
        invoice.action_metadata = {
            "action_type": "upgrade_plan",
            "plan_id": str(plan_id),
            "billing_cycle": billing_cycle,
            "gateway": gateway,
            "licensed_seats": licensed_seats
        }
        self.db.add(invoice)
        await self.db.commit()
        await self.db.refresh(invoice)

        await self.audit_service.log_event(
            organization_id=organization_id,
            actor_user_id=actor_user_id,
            action="GENERATE_UPGRADE_INVOICE",
            resource_type="INVOICE",
            resource_id=str(invoice.id),
            action_metadata={"plan_name": plan.name, "billing_cycle": billing_cycle, "amount": total_amount}
        )
        return invoice

    async def reduce_licensed_seats(
        self, organization_id: uuid.UUID, actor_user_id: uuid.UUID, new_seat_count: int
    ) -> TenantSubscription:
        sub_stmt = select(TenantSubscription).where(
            TenantSubscription.organization_id == organization_id,
            TenantSubscription.is_deleted == False
        )
        sub_res = await self.db.execute(sub_stmt)
        sub = sub_res.scalar_one_or_none()
        if not sub:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Subscription not found.")

        # Validation checks
        if new_seat_count >= sub.users_purchased:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="New seat count must be less than current purchased seats."
            )
        if new_seat_count < 10:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Cannot reduce below the minimum initial purchase of 10 Licensed Seats."
            )

        # Count active users currently assigned seats
        from app.models.user import User
        from sqlalchemy import func
        stmt = select(func.count(User.id)).where(
            User.organization_id == organization_id,
            User.is_active == True,
            User.seat_number.isnot(None),
            User.is_deleted == False
        )
        res = await self.db.execute(stmt)
        active_count = res.scalar() or 0

        if new_seat_count < active_count:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Cannot reduce seats below the number of currently active users ({active_count}). Please deactivate some users first."
            )

        # Schedule the reduction
        sub.users_purchased_next = new_seat_count
        await self.db.commit()
        await self.db.refresh(sub)

        # Log audit event
        await self.audit_service.log_event(
            organization_id=organization_id,
            actor_user_id=actor_user_id,
            action="SCHEDULE_SEAT_REDUCTION",
            resource_type="SUBSCRIPTION",
            resource_id=str(sub.id),
            action_metadata={"from_seats": sub.users_purchased, "to_seats": new_seat_count}
        )

        return sub
