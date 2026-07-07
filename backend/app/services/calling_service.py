"""Calling Platform read/reporting layer over Call activities.

Calls are Activity rows (activity_type='Call') created by the dialer, the
telephony inbound webhook, or Communication Center logging — this service
never creates calls, it queries/annotates them: history, tags, reports,
missed-call detection, and the live queue monitor.
"""
import asyncio
import uuid
from datetime import datetime, timezone, timedelta
from fastapi import HTTPException, status
from sqlalchemy import select, func, or_
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User
from app.models.lead import Lead
from app.models.activity import Activity
from app.services.notification_service import NotificationService

# Dispositions where the customer was actually on the line (a conversation
# happened) — the numerator of connect rate. RNR/Switch Off/Busy/Not Exist/
# Out of Service are failed attempts.
CONNECTED_DISPOSITIONS = {
    "Picked", "Answered / Resolved", "Callback Requested",
    "Interested", "Not Interested", "Spam / Junk",
}

# An inbound call still 'Planned' after this long was never answered/dispositioned.
MISSED_CALL_THRESHOLD_MINUTES = 10


class CallingService:
    def __init__(self, db: AsyncSession):
        self.db = db

    def _privileged(self, actor: User) -> bool:
        return actor.role in ("SuperAdmin", "OrgAdmin", "Manager")

    def _base_query(self, actor: User):
        q = select(Activity).filter(
            Activity.organization_id == actor.organization_id,
            Activity.is_deleted == False,
            Activity.activity_type == "Call",
        )
        if not self._privileged(actor):
            q = q.filter(or_(Activity.assigned_user_id == actor.id, Activity.created_by == actor.id))
        return q

    # ---------- History ----------
    async def history(self, actor: User, direction=None, disposition=None, agent_id=None, call_status=None,
                      tag=None, has_recording=None, missed_only=False, search=None,
                      date_from=None, date_to=None, skip=0, limit=50) -> dict:
        q = self._base_query(actor)
        if direction:
            q = q.filter(Activity.call_direction == direction)
        if disposition:
            q = q.filter(Activity.call_disposition == disposition)
        if agent_id:
            q = q.filter(Activity.assigned_user_id == agent_id)
        if call_status:
            q = q.filter(Activity.status == call_status)
        if missed_only:
            q = q.filter(Activity.status == "Missed")
        if has_recording is True:
            q = q.filter(Activity.recording_url.isnot(None))
        if date_from is not None:
            q = q.filter(Activity.created_at >= date_from)
        if date_to is not None:
            q = q.filter(Activity.created_at <= date_to)
        if search:
            s = f"%{search}%"
            q = q.filter(or_(Activity.subject.ilike(s), Activity.description.ilike(s)))

        acts = list((await self.db.execute(q.order_by(Activity.created_at.desc()))).scalars().all())
        # tag filter on the JSON list is applied in Python — org call volumes are modest
        if tag:
            acts = [a for a in acts if tag in (a.call_tags or [])]
        total = len(acts)
        acts = acts[skip:skip + limit]

        names = await self._names({a.assigned_user_id or a.created_by for a in acts})
        lead_titles = await self._lead_titles({a.lead_id for a in acts if a.lead_id})
        items = [self._item(a, names, lead_titles) for a in acts]
        return {"items": items, "total": total}

    def _item(self, a: Activity, names: dict, lead_titles: dict) -> dict:
        uid = a.assigned_user_id or a.created_by
        return {
            "id": str(a.id), "subject": a.subject, "description": a.description,
            "direction": a.call_direction, "disposition": a.call_disposition, "status": a.status,
            "duration": a.call_duration, "recording_url": a.recording_url,
            "tags": list(a.call_tags or []), "timestamp": a.created_at,
            "agent_id": str(uid) if uid else None, "agent_name": names.get(uid),
            "lead_id": str(a.lead_id) if a.lead_id else None,
            "lead_title": lead_titles.get(a.lead_id),
            "contact_id": str(a.contact_id) if a.contact_id else None,
            "company_id": str(a.company_id) if a.company_id else None,
        }

    # ---------- Tags ----------
    async def set_tags(self, actor: User, activity_id: uuid.UUID, tags: list[str]) -> dict:
        act = await self._get_call(actor, activity_id)
        clean = []
        for t in tags:
            t = str(t).strip()
            if t and t not in clean:
                clean.append(t[:50])
        act.call_tags = clean
        self.db.add(act)
        await self.db.flush()
        names = await self._names({act.assigned_user_id or act.created_by})
        lead_titles = await self._lead_titles({act.lead_id} if act.lead_id else set())
        return self._item(act, names, lead_titles)

    async def list_tags(self, actor: User) -> list[str]:
        q = self._base_query(actor).filter(Activity.call_tags.isnot(None))
        acts = (await self.db.execute(q)).scalars().all()
        tags: set[str] = set()
        for a in acts:
            tags.update(a.call_tags or [])
        return sorted(tags)

    async def _get_call(self, actor: User, activity_id: uuid.UUID) -> Activity:
        q = self._base_query(actor).filter(Activity.id == activity_id)
        act = (await self.db.execute(q)).scalars().first()
        if not act:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Call not found")
        return act

    # ---------- Reports ----------
    async def reports(self, actor: User, date_from=None, date_to=None) -> dict:
        q = self._base_query(actor)
        if date_from is not None:
            q = q.filter(Activity.created_at >= date_from)
        if date_to is not None:
            q = q.filter(Activity.created_at <= date_to)
        acts = list((await self.db.execute(q)).scalars().all())

        by_direction: dict = {}
        by_disposition: dict = {}
        by_agent: dict = {}
        by_day: dict = {}
        durations: list[int] = []
        missed = 0
        connected = 0
        dispositioned = 0
        for a in acts:
            d = a.call_direction or "OUTBOUND"
            by_direction[d] = by_direction.get(d, 0) + 1
            if a.call_disposition:
                by_disposition[a.call_disposition] = by_disposition.get(a.call_disposition, 0) + 1
                dispositioned += 1
                if a.call_disposition in CONNECTED_DISPOSITIONS:
                    connected += 1
            uid = a.assigned_user_id or a.created_by
            if uid:
                by_agent[uid] = by_agent.get(uid, 0) + 1
            if a.status == "Missed":
                missed += 1
            if a.call_duration:
                durations.append(a.call_duration)
            day = a.created_at.date().isoformat()
            by_day[day] = by_day.get(day, 0) + 1

        names = await self._names(set(by_agent))
        return {
            "total": len(acts),
            "missed": missed,
            "avg_duration": round(sum(durations) / len(durations)) if durations else 0,
            "connect_rate": round(connected * 100 / dispositioned, 1) if dispositioned else 0.0,
            "connected": connected,
            "dispositioned": dispositioned,
            "by_direction": [{"label": k, "count": v} for k, v in by_direction.items()],
            "by_disposition": [{"label": k, "count": v} for k, v in sorted(by_disposition.items(), key=lambda kv: -kv[1])],
            "by_agent": [{"label": names.get(uid, "Unknown"), "count": c}
                         for uid, c in sorted(by_agent.items(), key=lambda kv: -kv[1])],
            "by_day": [{"label": day, "count": c} for day, c in sorted(by_day.items())],
        }

    # ---------- Missed-call detection ----------
    async def detect_missed_calls(self, organization_id: uuid.UUID | None = None) -> int:
        """Mark stale in-progress inbound calls as Missed and notify the assigned
        agent (or the lead creator). Runs lazily from the history endpoint (scoped
        to that org) and org-wide from the daily cron. Returns count flagged."""
        cutoff = datetime.now(timezone.utc) - timedelta(minutes=MISSED_CALL_THRESHOLD_MINUTES)
        q = select(Activity).filter(
            Activity.is_deleted == False,
            Activity.activity_type == "Call",
            Activity.call_direction == "INBOUND",
            Activity.status == "Planned",
            Activity.created_at < cutoff,
        )
        if organization_id:
            q = q.filter(Activity.organization_id == organization_id)
        acts = list((await self.db.execute(q)).scalars().all())
        notifier = NotificationService(self.db)
        lead_titles = await self._lead_titles({a.lead_id for a in acts if a.lead_id})
        for a in acts:
            a.status = "Missed"
            self.db.add(a)
            target = a.assigned_user_id or a.created_by
            if target:
                lead_label = lead_titles.get(a.lead_id) or "an unknown caller"
                await notifier.create_notification(
                    organization_id=a.organization_id, user_id=target, category="calling",
                    title="Missed call",
                    body=f"Missed inbound call from {lead_label}.",
                    link_url=f"/calling?activityId={a.id}",
                    action_metadata={"activity_id": str(a.id), "lead_id": str(a.lead_id) if a.lead_id else None},
                )
        await self.db.flush()
        return len(acts)

    # ---------- Queue / live-calls monitor ----------
    async def queue(self, actor: User) -> dict:
        from app.services.user_service import UserService
        from app.services.agent_state_service import AgentStateService
        from app.middleware.permissions import check_is_team_leader

        if actor.role not in ("SuperAdmin", "OrgAdmin", "Manager") and not await check_is_team_leader(actor, self.db):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized to view the call queue.")

        pending = (await self.db.execute(
            select(func.count(Lead.id)).filter(
                Lead.organization_id == actor.organization_id,
                Lead.is_deleted == False,
                Lead.status == "New",
            )
        )).scalar() or 0

        user_service = UserService(self.db)
        agent_state_service = AgentStateService()
        downline_ids = await user_service.get_downline_user_ids(actor)
        agents: list[dict] = []
        if downline_ids:
            res = await self.db.execute(select(User.id, User.first_name, User.last_name).where(
                User.id.in_(downline_ids),
                User.organization_id == actor.organization_id,
                User.is_active == True,
                User.is_deleted == False,
            ))
            members = res.all()
            states = await asyncio.gather(*[
                agent_state_service.get_agent_state(actor.organization_id, uid) for uid, _, _ in members
            ])
            active_ids = [uid for (uid, _, _), st in zip(members, states) if st.get("state") == "ACTIVE_CALLING"]
            current_calls: dict = {}
            if active_ids:
                cq = select(Activity).filter(
                    Activity.organization_id == actor.organization_id,
                    Activity.is_deleted == False,
                    Activity.activity_type == "Call",
                    Activity.status == "Planned",
                    Activity.assigned_user_id.in_(active_ids),
                ).order_by(Activity.created_at.desc())
                for a in (await self.db.execute(cq)).scalars().all():
                    current_calls.setdefault(a.assigned_user_id, a)
            lead_titles = await self._lead_titles({a.lead_id for a in current_calls.values() if a.lead_id})
            for (uid, fn, ln), st in zip(members, states):
                call = current_calls.get(uid) if st.get("state") == "ACTIVE_CALLING" else None
                agents.append({
                    "user_id": str(uid),
                    "user_name": f"{fn or ''} {ln or ''}".strip() or "Unnamed User",
                    "state": st.get("state", "IDLE"),
                    "since": st.get("timestamp"),
                    "current_call": ({
                        "activity_id": str(call.id), "direction": call.call_direction,
                        "lead_id": str(call.lead_id) if call.lead_id else None,
                        "lead_title": lead_titles.get(call.lead_id),
                        "started_at": call.created_at,
                    } if call else None),
                })
        agents.sort(key=lambda a: (a["state"] != "ACTIVE_CALLING", a["user_name"]))
        return {"pending_queue": pending, "agents": agents}

    # ---------- helpers ----------
    async def _names(self, ids) -> dict:
        ids = {i for i in ids if i}
        if not ids:
            return {}
        res = await self.db.execute(select(User.id, User.first_name, User.last_name, User.email).filter(User.id.in_(ids)))
        return {uid: (f"{fn or ''} {ln or ''}".strip() or em) for uid, fn, ln, em in res.all()}

    async def _lead_titles(self, ids) -> dict:
        ids = {i for i in ids if i}
        if not ids:
            return {}
        res = await self.db.execute(select(Lead.id, Lead.title).filter(Lead.id.in_(ids)))
        return {lid: title for lid, title in res.all()}
