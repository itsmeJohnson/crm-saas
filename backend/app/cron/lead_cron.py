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


async def dispatch_task_reminders(db: AsyncSession) -> int:
    """Notify assignees of tasks whose remind_at has passed. Returns count sent."""
    from app.models.task import Task
    now = datetime.now(timezone.utc)
    res = await db.execute(
        select(Task).filter(
            Task.is_deleted == False,
            Task.reminded == False,
            Task.remind_at.isnot(None),
            Task.remind_at <= now,
            Task.status.in_(["Todo", "InProgress"]),
        )
    )
    tasks = res.scalars().all()
    notif_service = NotificationService(db)
    sent = 0
    for t in tasks:
        target = t.assigned_user_id or t.created_by
        if target:
            await notif_service.create_notification(
                organization_id=t.organization_id,
                user_id=target,
                category="task",
                title="Task reminder",
                body=f'Reminder: "{t.title}"' + (f" is due {t.due_date.date()}" if t.due_date else ""),
                link_url=f"/tasks?taskId={t.id}",
                action_metadata={"task_id": str(t.id)},
            )
            sent += 1
        t.reminded = True
        db.add(t)
    await db.flush()
    return sent


async def dispatch_event_reminders(db: AsyncSession) -> int:
    """Notify owners/attendees of calendar events whose remind_at has passed. Returns count sent."""
    from app.models.calendar_event import CalendarEvent
    now = datetime.now(timezone.utc)
    res = await db.execute(
        select(CalendarEvent).filter(
            CalendarEvent.is_deleted == False,
            CalendarEvent.reminded == False,
            CalendarEvent.remind_at.isnot(None),
            CalendarEvent.remind_at <= now,
            CalendarEvent.status == "Scheduled",
        )
    )
    events = res.scalars().all()
    notif_service = NotificationService(db)
    sent = 0
    import uuid as _uuid
    for ev in events:
        recipients = set()
        if ev.assigned_user_id:
            recipients.add(ev.assigned_user_id)
        for a in (ev.attendees or []):
            if a.get("user_id"):
                try:
                    recipients.add(_uuid.UUID(str(a["user_id"])))
                except ValueError:
                    pass
        for uid in recipients:
            await notif_service.create_notification(
                organization_id=ev.organization_id, user_id=uid, category="calendar",
                title="Event reminder", body=f'"{ev.title}" starts {ev.start_at.strftime("%b %d, %H:%M")}',
                link_url=f"/calendar?eventId={ev.id}", action_metadata={"event_id": str(ev.id)})
            sent += 1
        ev.reminded = True
        db.add(ev)
    await db.flush()
    return sent


async def dispatch_missed_follow_ups(db: AsyncSession) -> int:
    """Fire the follow_up_missed automation trigger for overdue follow-up tasks,
    per organization. Best-effort; reuses FollowUpService.detect_missed."""
    from app.services.follow_up_service import FollowUpService
    org_ids = (await db.execute(
        select(Lead.organization_id).where(Lead.is_deleted == False).distinct())).scalars().all()
    total = 0
    svc = FollowUpService(db)
    for org_id in org_ids:
        try:
            total += await svc.detect_missed(org_id)
        except Exception:
            pass
    return total


async def run_reminder_dispatch(session_maker) -> None:
    """Minute-cadence entry point: dispatch due lead/task/event reminders.

    These are time-sensitive and cheap, so they run every ~60s rather than once
    a day — a reminder set for 11:00 must notify near 11:00, not at the next
    midnight batch. Every dispatcher is guarded (LeadReminder.is_sent,
    Task.reminded, CalendarEvent.reminded) so running this frequently — alongside
    the daily catch-up in run_lead_automation_check — never double-sends.
    """
    async with session_maker() as db:
        try:
            lead_r = await dispatch_due_reminders(db)
            task_r = await dispatch_task_reminders(db)
            event_r = await dispatch_event_reminders(db)
            await db.commit()
            if lead_r or task_r or event_r:
                logger.info("Reminder dispatch: %d lead, %d task, %d event reminder(s) sent",
                            lead_r, task_r, event_r)
        except Exception as e:
            await db.rollback()
            logger.error("Reminder dispatch failed: %s", e)


async def run_lead_automation_check(session_maker) -> None:
    """Scheduler entry point: dispatch reminders then run escalation."""
    async with session_maker() as db:
        try:
            sent = await dispatch_due_reminders(db)
            escalated = await run_escalation_scan(db)
            task_reminders = await dispatch_task_reminders(db)
            event_reminders = await dispatch_event_reminders(db)
            missed_follow_ups = await dispatch_missed_follow_ups(db)
            await db.commit()
            logger.info("Lead automation: %d reminders, %d escalations, %d task reminders, "
                        "%d event reminders, %d missed follow-ups",
                        sent, escalated, task_reminders, event_reminders, missed_follow_ups)
        except Exception as e:
            await db.rollback()
            logger.error("Lead automation check failed: %s", e)
