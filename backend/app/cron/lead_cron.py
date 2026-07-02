"""Periodic lead-automation jobs: reminder dispatch and idle-lead escalation.

Both scan functions take an AsyncSession so they can be unit-tested directly;
`run_lead_automation_check` is the entry point the scheduler calls.
"""
import logging
from datetime import datetime, timezone, timedelta

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.lead import Lead
from app.models.lead_reminder import LeadReminder
from app.models.activity import Activity
from app.models.audit_log import AuditLog
from app.models.escalation_config import EscalationConfig
from app.models.user import User
from app.services.notification_service import NotificationService
from app.services.audit_service import AuditService

logger = logging.getLogger("app.cron.lead")


async def dispatch_due_reminders(db: AsyncSession) -> int:
    """Send in-app notifications for reminders whose time has arrived. Returns count sent."""
    now = datetime.now(timezone.utc)
    res = await db.execute(
        select(LeadReminder).filter(
            LeadReminder.is_sent == False,
            LeadReminder.is_deleted == False,
            LeadReminder.remind_at <= now,
        )
    )
    reminders = res.scalars().all()
    notif_service = NotificationService(db)
    sent = 0
    for r in reminders:
        lead = await db.get(Lead, r.lead_id)
        if not lead or lead.is_deleted:
            r.is_sent = True
            db.add(r)
            continue
        await notif_service.create_notification(
            organization_id=r.organization_id,
            user_id=r.user_id,
            category="lead",
            title="Lead reminder",
            body=r.note or f'Reminder for lead "{lead.title}".',
            link_url=f"/leads?leadId={lead.id}",
            action_metadata={"lead_id": str(lead.id), "reminder_id": str(r.id)},
        )
        r.is_sent = True
        db.add(r)
        sent += 1
    await db.flush()
    return sent


async def run_escalation_scan(db: AsyncSession) -> int:
    """Escalate idle leads to their owner's manager for each org with escalation enabled.

    Returns the number of leads escalated.
    """
    now = datetime.now(timezone.utc)
    res = await db.execute(
        select(EscalationConfig).filter(EscalationConfig.is_active == True)
    )
    configs = res.scalars().all()
    audit_service = AuditService(db)
    notif_service = NotificationService(db)
    total = 0

    for config in configs:
        cutoff = now - timedelta(days=config.idle_days)
        org_id = config.organization_id

        # Leads with recent activity are excluded
        recent_activity_ids = select(Activity.lead_id).filter(
            Activity.organization_id == org_id,
            Activity.created_at >= cutoff,
            Activity.lead_id.isnot(None),
        )
        # Leads already escalated within this window are excluded (dedup)
        recently_escalated = select(AuditLog.resource_id).filter(
            AuditLog.organization_id == org_id,
            AuditLog.action == "LEAD_ESCALATED",
            AuditLog.created_at >= cutoff,
        )
        recently_escalated_ids = {row for row in (await db.execute(recently_escalated)).scalars().all()}

        candidates_res = await db.execute(
            select(Lead).filter(
                Lead.organization_id == org_id,
                Lead.is_deleted == False,
                Lead.is_archived == False,
                Lead.converted_contact_id.is_(None),
                Lead.created_at < cutoff,
                Lead.id.notin_(recent_activity_ids),
            )
        )
        for lead in candidates_res.scalars().all():
            if str(lead.id) in recently_escalated_ids:
                continue
            if not lead.assigned_user_id:
                continue
            owner = await db.get(User, lead.assigned_user_id)
            if not owner or not owner.reporting_to_id:
                continue
            manager_id = owner.reporting_to_id

            await notif_service.create_notification(
                organization_id=org_id,
                user_id=manager_id,
                category="lead",
                title="Lead escalation",
                body=f'Lead "{lead.title}" has had no activity for {config.idle_days}+ days.',
                link_url=f"/leads?leadId={lead.id}",
                action_metadata={"lead_id": str(lead.id), "owner_id": str(lead.assigned_user_id)},
            )
            await audit_service.log_event(
                organization_id=org_id,
                actor_user_id=None,
                action="LEAD_ESCALATED",
                resource_type="lead",
                resource_id=str(lead.id),
                action_metadata={"idle_days": config.idle_days, "escalated_to": str(manager_id)},
            )
            total += 1

    await db.flush()
    return total


async def run_lead_automation_check(session_maker) -> None:
    """Scheduler entry point: dispatch reminders then run escalation."""
    async with session_maker() as db:
        try:
            sent = await dispatch_due_reminders(db)
            escalated = await run_escalation_scan(db)
            await db.commit()
            logger.info("Lead automation: %d reminders sent, %d leads escalated", sent, escalated)
        except Exception as e:
            await db.rollback()
            logger.error("Lead automation check failed: %s", e)
