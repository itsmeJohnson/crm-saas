"""Follow-up capture & orchestration.

The single entry point a salesperson uses after a call/interaction: it records
the outcome and the NEXT follow-up, then fans out to every existing subsystem so
nothing is manual and nothing is forgotten. It COMPOSES — it does not duplicate:

  * Activity            → the follow-up record on the lead timeline (the app's
    existing "follow-up = dated Activity" convention).
  * TaskService         → the actionable follow-up task (brings the reminder
    cron + assignee notification for free).
  * CalendarService     → an event for meeting / site-visit follow-ups.
  * NotificationService → manager visibility.
  * AuditService        → FOLLOW_UP_LOGGED audit trail.
  * WorkflowService     → fires the `follow_up_created` trigger so admins'
    automation (send WhatsApp, notify, escalate…) reacts.

No new tables — Activity/Task/CalendarEvent already carry everything needed.
"""
import uuid
from datetime import datetime, timezone, timedelta

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User
from app.models.lead import Lead
from app.models.activity import Activity
from app.services.audit_service import AuditService
from app.services.task_service import TaskService
from app.services.notification_service import NotificationService

# Unified sales+telephony outcome taxonomy (Part 2). One list, one capture.
FOLLOW_UP_OUTCOMES = (
    "Interested", "Follow-up", "Call Back Later", "No Response", "Switched Off",
    "Busy", "Wrong Number", "Invalid Lead", "Meeting Scheduled", "Site Visit Scheduled",
    "Negotiation", "Booking", "Sale Won", "Sale Lost", "Not Interested",
)
# outcome → lead.status to advance to (only when the mapping is unambiguous)
OUTCOME_STATUS = {
    "Interested": "Interested", "Negotiation": "Negotiation", "Booking": "Booking",
    "Sale Won": "Converted", "Sale Lost": "Lost", "Invalid Lead": "Lost",
    "Not Interested": "Lost",
}
FOLLOW_UP_TYPES = ("call", "whatsapp", "email", "meeting", "site_visit", "visit", "other")
_CAL_EVENT_TYPES = {"meeting": "Meeting", "site_visit": "Site Visit", "visit": "Site Visit"}


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _aware(dt):
    if dt is None:
        return None
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


class FollowUpService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.audit = AuditService(db)
        self.tasks = TaskService(db)
        self.notifier = NotificationService(db)

    async def _get_lead_scoped(self, actor: User, lead_id: uuid.UUID) -> Lead:
        # reuse LeadService's ownership/scoping + 404 semantics
        from app.services.lead_service import LeadService
        return await LeadService(self.db, actor.organization_id).get_lead(actor, lead_id)

    async def _manager_of(self, owner_id: uuid.UUID) -> uuid.UUID | None:
        row = (await self.db.execute(select(User.reporting_to_id).filter(
            User.id == owner_id, User.is_deleted == False))).scalar()
        return row

    async def create_follow_up(self, actor: User, lead_id: uuid.UUID, data: dict) -> dict:
        lead = await self._get_lead_scoped(actor, lead_id)

        outcome = (data.get("outcome") or "Follow-up").strip()
        if outcome not in FOLLOW_UP_OUTCOMES:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST,
                                detail=f"outcome must be one of {list(FOLLOW_UP_OUTCOMES)}")
        fu_type = (data.get("follow_up_type") or "call").strip()
        if fu_type not in FOLLOW_UP_TYPES:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST,
                                detail=f"follow_up_type must be one of {list(FOLLOW_UP_TYPES)}")
        priority = data.get("priority") or "Medium"
        if priority not in ("Low", "Medium", "High", "Urgent"):
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST,
                                detail="priority must be Low|Medium|High|Urgent")
        remarks = data.get("remarks")
        next_at = _aware(data.get("next_follow_up_at"))
        # a follow-up outcome REQUIRES a next date; terminal outcomes do not
        terminal = outcome in ("Sale Won", "Sale Lost", "Invalid Lead", "Not Interested", "Wrong Number")
        if not terminal and next_at is None:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST,
                                detail="next_follow_up_at is required for a non-terminal outcome")

        owner_id = lead.assigned_user_id or actor.id

        # 1) timeline Activity (the follow-up record)
        act = Activity(organization_id=actor.organization_id,
                       activity_type="Follow-up",
                       subject=f"Follow-up ({fu_type}) — {outcome}",
                       description=remarks, due_date=next_at, status="Planned",
                       assigned_user_id=owner_id, created_by=actor.id, lead_id=lead.id,
                       call_disposition=outcome)
        self.db.add(act)
        await self.db.flush()

        # 2) actionable follow-up Task (reminder cron + assignee notify come free)
        task = None
        if next_at is not None:
            reminder_min = data.get("reminder_minutes_before")
            remind_at = (next_at - timedelta(minutes=int(reminder_min))) if reminder_min else None
            task = await self.tasks.create_task(actor, {
                "title": f"Follow up: {lead.title}",
                "description": (f"[{outcome}] {remarks}" if remarks else outcome),
                "priority": priority, "due_date": next_at, "remind_at": remind_at,
                "assigned_user_id": owner_id, "lead_id": lead.id})

        # 3) calendar event for meeting / site-visit follow-ups
        cal_event = None
        if fu_type in _CAL_EVENT_TYPES or data.get("create_calendar_event"):
            if next_at is None:
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST,
                                    detail="A meeting/site-visit follow-up needs next_follow_up_at")
            from app.services.calendar_service import CalendarService
            cal_event = await CalendarService(self.db).create_event(actor, {
                "title": f"{_CAL_EVENT_TYPES.get(fu_type, 'Meeting')}: {lead.title}",
                "description": remarks, "event_type": _CAL_EVENT_TYPES.get(fu_type, "Meeting"),
                "start_at": next_at, "end_at": next_at + timedelta(hours=1),
                "assigned_user_id": owner_id, "lead_id": lead.id})

        # 4) optional lead status advance (unambiguous outcomes only)
        new_status = data.get("set_status") or OUTCOME_STATUS.get(outcome)
        status_changed = False
        if new_status and new_status != lead.status:
            lead.status = new_status
            if new_status == "Converted":
                lead.converted_at = _now()
            self.db.add(lead)
            status_changed = True

        # 5) manager visibility
        manager_id = await self._manager_of(owner_id)
        if manager_id and manager_id != actor.id:
            await self.notifier.create_notification(
                organization_id=actor.organization_id, user_id=manager_id, category="follow_up",
                title="Follow-up logged", priority=("high" if priority in ("High", "Urgent") else "normal"),
                body=f'{actor.first_name} logged "{outcome}" on {lead.title}'
                     + (f' — next {next_at.date().isoformat()}' if next_at else ""),
                link_url=f"/leads?id={lead.id}",
                action_metadata={"lead_id": str(lead.id), "outcome": outcome})

        # 6) audit
        await self.audit.log_event(organization_id=actor.organization_id, actor_user_id=actor.id,
                                   action="FOLLOW_UP_LOGGED", resource_type="lead", resource_id=str(lead.id),
                                   action_metadata={"outcome": outcome, "type": fu_type,
                                                    "next_follow_up_at": next_at.isoformat() if next_at else None,
                                                    "status_changed_to": new_status if status_changed else None})
        await self.db.flush()

        # 7) fire automation: follow_up_created (+ status trigger if advanced)
        from app.services.workflow_service import WorkflowService
        wf = WorkflowService(self.db)
        try:
            await wf.run("follow_up_created", lead, actor)
            if status_changed:
                await wf.run("lead_updated", lead, actor)
        except Exception:
            pass

        from app.services.dashboard_service import DashboardService
        await DashboardService.invalidate_cache(actor.organization_id)
        await self.db.commit()
        return {"lead_id": str(lead.id), "outcome": outcome, "follow_up_type": fu_type,
                "activity_id": str(act.id),
                "task_id": str(task.id) if task else None,
                "calendar_event_id": str(cal_event.id) if cal_event else None,
                "next_follow_up_at": next_at.isoformat() if next_at else None,
                "status": lead.status, "status_changed": status_changed,
                "manager_notified": bool(manager_id and manager_id != actor.id)}

    async def detect_missed(self, organization_id: uuid.UUID) -> int:
        """Fire the `follow_up_missed` trigger for overdue open follow-up tasks
        (idempotent-ish: only tasks past due whose lead is still open). Called by
        the daily lead cron. Returns count fired."""
        from app.models.task import Task
        from app.services.workflow_service import WorkflowService
        now = _now()
        # a system actor (org admin) for automation context
        sys_actor = (await self.db.execute(select(User).filter(
            User.organization_id == organization_id, User.is_deleted == False,
            User.is_active == True, User.role.in_(("OrgAdmin", "SuperAdmin"))).limit(1))).scalars().first()
        if sys_actor is None:
            return 0
        rows = (await self.db.execute(select(Task, Lead).join(Lead, Task.lead_id == Lead.id).filter(
            Task.organization_id == organization_id, Task.is_deleted == False,
            Task.status.in_(("Todo", "InProgress")), Task.due_date != None,
            Task.due_date < now, Lead.is_deleted == False,
            Lead.status.notin_(("Converted", "Lost", "Closed", "Dead"))))).all()
        wf = WorkflowService(self.db)
        fired = 0
        for _task, lead in rows:
            try:
                await wf.run("follow_up_missed", lead, sys_actor)
                fired += 1
            except Exception:
                pass
        return fired
