"""Daily AR dunning: flag past-due customer invoices as Overdue and notify owners."""
import logging
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.customer_invoice import CustomerInvoice
from app.models.company import Company
from app.services.notification_service import NotificationService
from app.services.audit_service import AuditService

logger = logging.getLogger("app.cron.customer")


async def mark_overdue_invoices(db: AsyncSession) -> int:
    """Move Sent/PartiallyPaid invoices whose due date has passed to Overdue. Returns count."""
    now = datetime.now(timezone.utc)
    res = await db.execute(
        select(CustomerInvoice).filter(
            CustomerInvoice.is_deleted == False,
            CustomerInvoice.status.in_(["Sent", "PartiallyPaid"]),
            CustomerInvoice.due_date.isnot(None),
            CustomerInvoice.due_date < now,
        )
    )
    invoices = res.scalars().all()
    notifier = NotificationService(db)
    audit = AuditService(db)
    count = 0
    for inv in invoices:
        if float(inv.amount_paid or 0) >= float(inv.total_amount or 0):
            continue
        inv.status = "Overdue"
        db.add(inv)
        company = await db.get(Company, inv.company_id)
        if company and company.assigned_user_id:
            await notifier.create_notification(
                organization_id=inv.organization_id,
                user_id=company.assigned_user_id,
                category="invoice",
                title="Invoice overdue",
                body=f"Invoice {inv.invoice_number} for {company.name} is past due ({inv.currency} {inv.balance_due:.2f} outstanding).",
                link_url=f"/customers?companyId={inv.company_id}",
                action_metadata={"invoice_id": str(inv.id)},
            )
        await audit.log_event(
            organization_id=inv.organization_id, actor_user_id=None,
            action="CUSTOMER_INVOICE_OVERDUE", resource_type="customer_invoice", resource_id=str(inv.id),
        )
        count += 1
    await db.flush()
    return count


async def run_customer_dunning_check(session_maker) -> None:
    async with session_maker() as db:
        try:
            n = await mark_overdue_invoices(db)
            await db.commit()
            logger.info("Customer dunning: %d invoice(s) marked overdue", n)
        except Exception as e:
            await db.rollback()
            logger.error("Customer dunning check failed: %s", e)
