import uuid
import json
import asyncio
from datetime import datetime, date, time, timezone
from typing import Dict, Any, List, Tuple
from fastapi import HTTPException, status
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User
from app.models.lead import Lead
from app.models.contact import Contact
from app.models.company import Company
from app.models.activity import Activity
from app.models.pipeline import PipelineStage
from app.core.redis import redis_client

class DashboardService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_summary(self, actor: User) -> Dict[str, Any]:
        if not actor.is_active:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Actor is inactive")

        org_id = actor.organization_id
        cache_key = f"dashboard_summary:{org_id}"

        # Try to retrieve from cache
        cached_data = await redis_client.get(cache_key)
        if cached_data:
            try:
                return json.loads(cached_data)
            except Exception:
                pass # Fallback to database query if json load fails

        # Database queries
        total_leads_query = select(func.count(Lead.id)).filter(
            Lead.organization_id == org_id,
            Lead.is_deleted == False
        )
        contacts_count_query = select(func.count(Contact.id)).filter(
            Contact.organization_id == org_id,
            Contact.is_deleted == False
        )
        companies_count_query = select(func.count(Company.id)).filter(
            Company.organization_id == org_id,
            Company.is_deleted == False
        )
        user_count_query = select(func.count(User.id)).filter(
            User.organization_id == org_id,
            User.is_active == True,
            User.is_deleted == False
        )
        activities_count_query = select(func.count(Activity.id)).filter(
            Activity.organization_id == org_id,
            Activity.is_deleted == False
        )
        leads_by_status_query = select(
            Lead.status,
            func.count(Lead.id)
        ).filter(
            Lead.organization_id == org_id,
            Lead.is_deleted == False
        ).group_by(Lead.status)

        assigned_leads_query = (
            select(
                Lead.assigned_user_id,
                User.first_name,
                User.last_name,
                func.count(Lead.id)
            )
            .outerjoin(User, Lead.assigned_user_id == User.id)
            .filter(
                Lead.organization_id == org_id,
                Lead.is_deleted == False
            )
            .group_by(Lead.assigned_user_id, User.first_name, User.last_name)
        )

        # Lead sources — reuses the existing (already-populated) Lead.source field.
        leads_by_source_query = select(
            Lead.source,
            func.count(Lead.id)
        ).filter(
            Lead.organization_id == org_id,
            Lead.is_deleted == False
        ).group_by(Lead.source)

        # Pipeline by stage — reuses the org's actual configured pipeline stages
        # (Pipeline Settings), ordered the same way the Pipeline module orders them.
        leads_by_stage_query = (
            select(PipelineStage.id, PipelineStage.name, PipelineStage.order_position, func.count(Lead.id))
            .outerjoin(Lead, (Lead.stage_id == PipelineStage.id) & (Lead.is_deleted == False))
            .filter(PipelineStage.organization_id == org_id, PipelineStage.is_deleted == False)
            .group_by(PipelineStage.id, PipelineStage.name, PipelineStage.order_position)
            .order_by(PipelineStage.order_position)
        )

        # "Today" scoping (server timezone = UTC, matching every other date-scoped
        # query in this codebase, e.g. AnalyticsService.get_telecaller_metrics).
        today = date.today()
        today_start = datetime.combine(today, time.min).replace(tzinfo=timezone.utc)
        today_end = datetime.combine(today, time.max).replace(tzinfo=timezone.utc)
        now = datetime.now(timezone.utc)

        leads_today_query = select(func.count(Lead.id)).filter(
            Lead.organization_id == org_id,
            Lead.is_deleted == False,
            Lead.created_at >= today_start,
            Lead.created_at <= today_end
        )
        meetings_today_query = select(func.count(Activity.id)).filter(
            Activity.organization_id == org_id,
            Activity.is_deleted == False,
            Activity.activity_type == "Meeting",
            Activity.due_date >= today_start,
            Activity.due_date <= today_end
        )
        tasks_today_query = select(func.count(Activity.id)).filter(
            Activity.organization_id == org_id,
            Activity.is_deleted == False,
            Activity.activity_type == "Task",
            Activity.due_date >= today_start,
            Activity.due_date <= today_end
        )
        # Follow-ups due = anything not yet completed whose due date has arrived
        # (today or earlier) — the same "overdue-or-due-today" definition already
        # implied by Activity.status's own "Overdue" value.
        followups_due_query = select(func.count(Activity.id)).filter(
            Activity.organization_id == org_id,
            Activity.is_deleted == False,
            Activity.status.in_(["Planned", "Overdue"]),
            Activity.due_date.isnot(None),
            Activity.due_date <= today_end
        )

        # Run queries in parallel
        db_results = await asyncio.gather(
            self.db.execute(total_leads_query),
            self.db.execute(contacts_count_query),
            self.db.execute(companies_count_query),
            self.db.execute(user_count_query),
            self.db.execute(activities_count_query),
            self.db.execute(leads_by_status_query),
            self.db.execute(assigned_leads_query),
            self.db.execute(leads_by_source_query),
            self.db.execute(leads_by_stage_query),
            self.db.execute(leads_today_query),
            self.db.execute(meetings_today_query),
            self.db.execute(tasks_today_query),
            self.db.execute(followups_due_query),
        )

        total_leads = db_results[0].scalar_one()
        contacts_count = db_results[1].scalar_one()
        companies_count = db_results[2].scalar_one()
        user_count = db_results[3].scalar_one()
        activities_count = db_results[4].scalar_one()

        # Parse leads by status
        leads_by_status = {}
        for status_row in db_results[5].all():
            status_name = status_row[0] or "Unknown"
            status_count = status_row[1]
            leads_by_status[status_name] = status_count

        # Parse assigned leads breakdown
        assigned_leads_breakdown = []
        for row in db_results[6].all():
            user_id = row[0]
            first_name = row[1]
            last_name = row[2]
            count = row[3]

            if user_id is None:
                assigned_leads_breakdown.append({
                    "user_id": "unassigned",
                    "user_name": "Unassigned",
                    "lead_count": count
                })
            else:
                user_name = f"{first_name or ''} {last_name or ''}".strip() or "Unnamed User"
                assigned_leads_breakdown.append({
                    "user_id": str(user_id),
                    "user_name": user_name,
                    "lead_count": count
                })

        leads_by_source = {}
        for source_row in db_results[7].all():
            source_name = source_row[0] or "Unknown"
            leads_by_source[source_name] = leads_by_source.get(source_name, 0) + source_row[1]

        converted_stage_name = None
        leads_by_stage = []
        for stage_row in db_results[8].all():
            stage_name = stage_row[1]
            stage_count = stage_row[3]
            leads_by_stage.append({
                "stage_id": str(stage_row[0]),
                "stage_name": stage_name,
                "count": stage_count,
            })
            if stage_name == "Converted":
                converted_stage_name = stage_name

        # None (not 0.0) when the org has no stage literally named "Converted" —
        # matches AnalyticsService.get_converted_stage_id()'s existing convention
        # (already relied on by the Telecaller/Team-Leader conversion cards).
        # Distinguishing "not configured" from "configured but genuinely 0%" avoids
        # showing a misleading number for orgs whose pipeline uses different naming
        # (e.g. this demo org's stage is named "Won", not "Converted").
        conversion_rate = None
        if converted_stage_name and total_leads > 0:
            converted_count = next((s["count"] for s in leads_by_stage if s["stage_name"] == "Converted"), 0)
            conversion_rate = round((converted_count / total_leads) * 100, 1)

        summary = {
            "total_leads": total_leads,
            "contacts_count": contacts_count,
            "companies_count": companies_count,
            "user_count": user_count,
            "activities_count": activities_count,
            "leads_by_status": leads_by_status,
            "assigned_leads_breakdown": assigned_leads_breakdown,
            "leads_by_source": leads_by_source,
            "leads_by_stage": leads_by_stage,
            "conversion_rate": conversion_rate,
            "today": {
                "leads_created": db_results[9].scalar_one() or 0,
                "meetings_due": db_results[10].scalar_one() or 0,
                "tasks_due": db_results[11].scalar_one() or 0,
                "follow_ups_due": db_results[12].scalar_one() or 0,
            },
        }

        # Cache results for 5 minutes
        try:
            await redis_client.set(cache_key, json.dumps(summary), ex=300)
        except Exception:
            pass

        return summary

    async def employee_summary(self, actor: User) -> Dict[str, Any]:
        """Personal snapshot for the Employee Dashboard: my leads, today's calls
        and meetings, and my task counts. Everything is scoped to the actor."""
        from app.models.task import Task
        from app.models.calendar_event import CalendarEvent
        org = actor.organization_id
        today = date.today()
        start = datetime.combine(today, time.min).replace(tzinfo=timezone.utc)
        end = datetime.combine(today, time.max).replace(tzinfo=timezone.utc)

        # My leads (assigned to me), with a small status breakdown
        lead_rows = (await self.db.execute(select(Lead.status, func.count(Lead.id)).filter(
            Lead.organization_id == org, Lead.is_deleted == False, Lead.assigned_user_id == actor.id,
            Lead.is_archived == False).group_by(Lead.status))).all()
        by_status = {s: n for s, n in lead_rows}
        my_leads_total = sum(by_status.values())
        converted = sum(n for s, n in by_status.items() if s in ("Won", "Converted", "Customer"))

        # Today's calls (Call activities I logged/own today)
        today_calls = (await self.db.execute(select(func.count(Activity.id)).filter(
            Activity.organization_id == org, Activity.is_deleted == False,
            Activity.assigned_user_id == actor.id, Activity.activity_type == "Call",
            Activity.created_at >= start, Activity.created_at <= end))).scalar() or 0

        # Today's meetings (calendar events assigned to me overlapping today)
        meetings = list((await self.db.execute(select(CalendarEvent).filter(
            CalendarEvent.organization_id == org, CalendarEvent.is_deleted == False,
            CalendarEvent.assigned_user_id == actor.id, CalendarEvent.start_at <= end,
            CalendarEvent.end_at >= start).order_by(CalendarEvent.start_at.asc()))).scalars().all())
        today_meetings = [{"id": str(m.id), "title": m.title, "event_type": m.event_type,
                           "start_at": m.start_at.isoformat() if m.start_at else None,
                           "status": m.status} for m in meetings]

        # My tasks
        open_tasks = (await self.db.execute(select(func.count(Task.id)).filter(
            Task.organization_id == org, Task.is_deleted == False, Task.assigned_user_id == actor.id,
            Task.status.in_(["Todo", "InProgress"])))).scalar() or 0
        overdue_tasks = (await self.db.execute(select(func.count(Task.id)).filter(
            Task.organization_id == org, Task.is_deleted == False, Task.assigned_user_id == actor.id,
            Task.status.in_(["Todo", "InProgress"]), Task.due_date.isnot(None), Task.due_date < end))).scalar() or 0

        return {
            "my_leads_total": my_leads_total, "my_leads_converted": converted,
            "my_leads_by_status": [{"status": s, "count": n} for s, n in by_status.items()],
            "today_calls": today_calls, "today_meetings_count": len(today_meetings),
            "today_meetings": today_meetings, "open_tasks": open_tasks, "overdue_tasks": overdue_tasks,
        }

    async def get_team_status(self, actor: User) -> List[Dict[str, Any]]:
        """Live agent-state snapshot (IDLE / ACTIVE_CALLING / BREAK) for the
        actor's downline — Manager/TeamLeader/OrgAdmin only. Reuses the same
        Redis-backed AgentStateService the dialer console itself reads/writes,
        so this is always exactly in sync with what an agent's own console shows."""
        from app.services.user_service import UserService
        from app.services.agent_state_service import AgentStateService
        from app.middleware.permissions import check_is_team_leader

        if actor.role not in ("SuperAdmin", "OrgAdmin", "Manager") and not await check_is_team_leader(actor, self.db):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized to view team status.")

        user_service = UserService(self.db)
        agent_state_service = AgentStateService()

        downline_ids = await user_service.get_downline_user_ids(actor)
        if not downline_ids:
            return []

        users_query = select(User.id, User.first_name, User.last_name, User.role).where(
            User.id.in_(downline_ids),
            User.organization_id == actor.organization_id,
            User.is_active == True,
            User.is_deleted == False,
        )
        res = await self.db.execute(users_query)
        team_members = res.all()

        states = await asyncio.gather(*[
            agent_state_service.get_agent_state(actor.organization_id, member_id)
            for member_id, _, _, _ in team_members
        ])

        return [
            {
                "user_id": str(member_id),
                "user_name": f"{first_name or ''} {last_name or ''}".strip() or "Unnamed User",
                "role": role,
                "state": state_data.get("state", "IDLE"),
                "since": state_data.get("timestamp"),
            }
            for (member_id, first_name, last_name, role), state_data in zip(team_members, states)
        ]

    async def get_recent_activities(
        self, actor: User, page: int = 1, limit: int = 10
    ) -> Dict[str, Any]:
        if not actor.is_active:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Actor is inactive")

        if page < 1:
            page = 1
        if limit < 1:
            limit = 10

        offset = (page - 1) * limit
        org_id = actor.organization_id

        # Query recent activities
        recent_activities_query = (
            select(Activity, User.first_name, User.last_name)
            .outerjoin(User, Activity.assigned_user_id == User.id)
            .filter(
                Activity.organization_id == org_id,
                Activity.is_deleted == False
            )
            .order_by(Activity.created_at.desc())
            .offset(offset)
            .limit(limit)
        )

        total_recent_activities_query = select(func.count(Activity.id)).filter(
            Activity.organization_id == org_id,
            Activity.is_deleted == False
        )

        db_results = await asyncio.gather(
            self.db.execute(recent_activities_query),
            self.db.execute(total_recent_activities_query)
        )

        records = db_results[0].all()
        total = db_results[1].scalar_one()

        items = []
        for row in records:
            activity = row[0]
            first_name = row[1]
            last_name = row[2]
            
            assigned_user_name = "Unassigned"
            if activity.assigned_user_id:
                assigned_user_name = f"{first_name or ''} {last_name or ''}".strip() or "Unnamed User"

            items.append({
                "id": str(activity.id),
                "activity_type": activity.activity_type,
                "subject": activity.subject,
                "description": activity.description,
                "due_date": activity.due_date.isoformat() if activity.due_date else None,
                "status": activity.status,
                "assigned_user_id": str(activity.assigned_user_id) if activity.assigned_user_id else None,
                "assigned_user_name": assigned_user_name,
                "created_at": activity.created_at.isoformat()
            })

        return {
            "items": items,
            "total": total,
            "page": page,
            "limit": limit
        }

    # ================= My Work Queue (prioritized, actionable) =================
    async def _queue_scope(self, actor: User) -> set | None:
        """None = whole org (admins); else actor + direct reports (managers) or
        just the actor (individual contributors)."""
        if actor.role in ("SuperAdmin", "OrgAdmin"):
            return None
        ids = {actor.id}
        if actor.role == "Manager":
            rows = (await self.db.execute(select(User.id).filter(
                User.organization_id == actor.organization_id, User.is_deleted == False,
                User.reporting_to_id == actor.id))).scalars().all()
            ids |= set(rows)
        return ids

    async def work_queue(self, actor: User, limit_per_section: int = 25) -> Dict[str, Any]:
        """The prioritized 'what to work on next' list. Ordered exactly:
        overdue follow-ups → today's follow-ups → meetings → site visits →
        hot → interested → new → cold → closed → personal tasks.
        Follow-up tasks are lead-linked open tasks; personal tasks are the rest."""
        from app.models.task import Task
        from app.models.calendar_event import CalendarEvent
        org = actor.organization_id
        scope = await self._queue_scope(actor)
        now = datetime.now(timezone.utc)
        today = date.today()
        day_end = datetime.combine(today, time.max).replace(tzinfo=timezone.utc)
        OPEN_TASK = ("Todo", "InProgress")
        CLOSED_LEAD = ("Converted", "Lost", "Closed", "Dead")

        def uscope(q, col):
            return q if scope is None else q.filter(col.in_(list(scope)))

        # ---- follow-up tasks (lead-linked, open) ----
        ftq = uscope(select(Task).filter(
            Task.organization_id == org, Task.is_deleted == False,
            Task.status.in_(OPEN_TASK), Task.lead_id != None, Task.due_date != None),
            Task.assigned_user_id).order_by(Task.due_date.asc())
        ftasks = list((await self.db.execute(ftq)).scalars().all())
        overdue_fu, today_fu = [], []
        for t in ftasks:
            due = t.due_date if t.due_date.tzinfo else t.due_date.replace(tzinfo=timezone.utc)
            item = {"type": "follow_up", "id": str(t.id), "lead_id": str(t.lead_id),
                    "title": t.title, "priority": t.priority, "due_date": due.isoformat()}
            if due < now:
                item["overdue"] = True
                overdue_fu.append(item)
            elif due <= day_end:
                today_fu.append(item)

        # ---- meetings & site visits (upcoming calendar events) ----
        evq = uscope(select(CalendarEvent).filter(
            CalendarEvent.organization_id == org, CalendarEvent.is_deleted == False,
            CalendarEvent.end_at >= now), CalendarEvent.assigned_user_id).order_by(CalendarEvent.start_at.asc())
        events = list((await self.db.execute(evq)).scalars().all())
        meetings, site_visits = [], []
        for e in events:
            item = {"type": "event", "id": str(e.id), "lead_id": str(e.lead_id) if e.lead_id else None,
                    "title": e.title, "event_type": e.event_type,
                    "start_at": (e.start_at if e.start_at.tzinfo else e.start_at.replace(tzinfo=timezone.utc)).isoformat()}
            if (e.event_type or "").lower().replace(" ", "_") == "site_visit":
                site_visits.append(item)
            else:
                meetings.append(item)

        # ---- leads by temperature/status ----
        lq = uscope(select(Lead).filter(
            Lead.organization_id == org, Lead.is_deleted == False, Lead.is_archived == False),
            Lead.assigned_user_id)
        leads = list((await self.db.execute(lq)).scalars().all())
        hot, interested, new, cold, closed = [], [], [], [], []
        for l in leads:
            item = {"type": "lead", "id": str(l.id), "title": l.title, "status": l.status,
                    "score": l.score, "priority": l.priority, "value": float(l.value or 0)}
            st = (l.status or "").lower()
            if l.status in CLOSED_LEAD:
                closed.append(item)
            elif st == "interested":
                interested.append(item)
            elif (l.score or 0) >= 70 or l.priority in ("High", "Urgent"):
                hot.append(item)
            elif st in ("new", ""):
                new.append(item)
            else:
                cold.append(item)
        hot.sort(key=lambda x: -x["score"])

        # ---- personal tasks (not lead-linked) ----
        ptq = uscope(select(Task).filter(
            Task.organization_id == org, Task.is_deleted == False,
            Task.status.in_(OPEN_TASK), Task.lead_id == None),
            Task.assigned_user_id).order_by(Task.due_date.asc().nullslast())
        ptasks = [{"type": "task", "id": str(t.id), "title": t.title, "priority": t.priority,
                   "due_date": (t.due_date.isoformat() if t.due_date else None)}
                  for t in (await self.db.execute(ptq)).scalars().all()]

        sections = [
            ("overdue_follow_ups", overdue_fu), ("todays_follow_ups", today_fu),
            ("meetings", meetings), ("site_visits", site_visits),
            ("hot_leads", hot), ("interested_leads", interested), ("new_leads", new),
            ("cold_leads", cold), ("closed_leads", closed), ("personal_tasks", ptasks),
        ]
        out, counts = [], {}
        for i, (key, items) in enumerate(sections, 1):
            counts[key] = len(items)
            out.append({"key": key, "order": i, "label": key.replace("_", " ").title(),
                        "count": len(items), "items": items[:limit_per_section]})
        return {"generated_at": now.isoformat(), "scope": actor.role,
                "next_action": (overdue_fu or today_fu or meetings or site_visits or hot or [None])[0],
                "counts": counts, "sections": out}

    @staticmethod
    async def invalidate_cache(org_id: uuid.UUID):
        cache_key = f"dashboard_summary:{org_id}"
        await redis_client.delete(cache_key)
