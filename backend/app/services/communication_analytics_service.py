"""Unified Communication Analytics.

Read-only aggregation over the Activity table — where every Call/SMS/WhatsApp/
Email lives — plus the Campaign subsystem. No new tables: this consolidates the
per-channel /reports endpoints into one cross-channel view with agent
performance, response/talk time, missed comms, conversion, engagement, and a
weekday×hour heatmap. All queries are org-scoped; non-privileged users see only
communications they sent or own.
"""
from __future__ import annotations
import csv
import io
import uuid
from datetime import datetime, timezone, timedelta
from sqlalchemy import select, func, or_, and_
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User
from app.models.lead import Lead
from app.models.contact import Contact
from app.models.activity import Activity

CHANNELS = ("Call", "SMS", "WhatsApp", "Email")
CONVERTED_LEAD_STATUSES = {"Won", "Converted", "Customer"}
CONNECTED_CALL_DISPOSITIONS = {
    "Picked", "Answered / Resolved", "Callback Requested", "Interested", "Not Interested", "Spam / Junk",
}


def _naive(dt: datetime | None) -> datetime | None:
    if dt is None:
        return None
    return dt.replace(tzinfo=None) if dt.tzinfo else dt


class CommunicationAnalyticsService:
    def __init__(self, db: AsyncSession):
        self.db = db

    def _privileged(self, actor: User) -> bool:
        return actor.role in ("SuperAdmin", "OrgAdmin", "Manager")

    def _base(self, actor: User, channel=None, direction=None, agent_id=None, date_from=None, date_to=None):
        q = select(Activity).filter(
            Activity.organization_id == actor.organization_id, Activity.is_deleted == False,
            Activity.activity_type.in_(CHANNELS))
        if not self._privileged(actor):
            q = q.filter(or_(Activity.assigned_user_id == actor.id, Activity.created_by == actor.id))
        elif agent_id:
            q = q.filter(or_(Activity.assigned_user_id == agent_id, Activity.created_by == agent_id))
        if channel:
            q = q.filter(Activity.activity_type == channel)
        if direction:
            q = q.filter(Activity.call_direction == direction)
        if date_from is not None:
            q = q.filter(Activity.created_at >= date_from)
        if date_to is not None:
            q = q.filter(Activity.created_at <= date_to)
        return q

    async def _load(self, actor, **f) -> list[Activity]:
        return list((await self.db.execute(self._base(actor, **f))).scalars().all())

    # ---------- Overview ----------
    def _delivered(self, a: Activity) -> bool:
        if a.activity_type == "SMS":
            return a.sms_status in ("delivered", "sent")
        if a.activity_type == "WhatsApp":
            return a.wa_status in ("delivered", "read", "sent")
        if a.activity_type == "Email":
            return a.email_status == "sent"
        if a.activity_type == "Call":
            return a.call_disposition in CONNECTED_CALL_DISPOSITIONS
        return False

    def _failed(self, a: Activity) -> bool:
        return (a.sms_status in ("failed", "undelivered") or a.wa_status == "failed"
                or a.email_status == "failed" or a.status == "Missed")

    async def overview(self, actor, **f) -> dict:
        acts = await self._load(actor, **f)
        by_channel: dict = {}
        by_direction: dict = {}
        outbound = inbound = delivered = failed = 0
        for a in acts:
            by_channel[a.activity_type] = by_channel.get(a.activity_type, 0) + 1
            d = a.call_direction or "OUTBOUND"
            by_direction[d] = by_direction.get(d, 0) + 1
            if d == "INBOUND":
                inbound += 1
            else:
                outbound += 1
            if self._delivered(a):
                delivered += 1
            if self._failed(a):
                failed += 1
        return {
            "total": len(acts), "outbound": outbound, "inbound": inbound,
            "delivered": delivered, "failed": failed,
            "delivery_rate": round(delivered * 100 / outbound, 1) if outbound else 0.0,
            "by_channel": [{"label": k, "count": v} for k, v in sorted(by_channel.items(), key=lambda kv: -kv[1])],
            "by_direction": [{"label": k, "count": v} for k, v in by_direction.items()],
        }

    # ---------- Per-channel breakdown ----------
    async def by_channel(self, actor, **f) -> list[dict]:
        acts = await self._load(actor, **f)
        buckets: dict = {c: {"channel": c, "total": 0, "outbound": 0, "inbound": 0, "delivered": 0,
                             "failed": 0, "opened": 0, "clicked": 0, "read": 0,
                             "talk_seconds": 0, "talk_calls": 0} for c in CHANNELS}
        for a in acts:
            b = buckets[a.activity_type]
            b["total"] += 1
            if (a.call_direction or "OUTBOUND") == "INBOUND":
                b["inbound"] += 1
            else:
                b["outbound"] += 1
            if self._delivered(a):
                b["delivered"] += 1
            if self._failed(a):
                b["failed"] += 1
            if a.activity_type == "Email":
                if (a.email_open_count or 0) > 0:
                    b["opened"] += 1
                if (a.email_click_count or 0) > 0:
                    b["clicked"] += 1
            if a.activity_type == "WhatsApp" and a.wa_status == "read":
                b["read"] += 1
            if a.activity_type == "Call" and a.call_duration:
                b["talk_seconds"] += a.call_duration
                b["talk_calls"] += 1
        out = []
        for c in CHANNELS:
            b = buckets[c]
            ob = b["outbound"]
            out.append({
                "channel": c, "total": b["total"], "outbound": ob, "inbound": b["inbound"],
                "delivered": b["delivered"], "failed": b["failed"], "opened": b["opened"],
                "clicked": b["clicked"], "read": b["read"],
                "delivery_rate": round(b["delivered"] * 100 / ob, 1) if ob else 0.0,
                "open_rate": round(b["opened"] * 100 / ob, 1) if (c == "Email" and ob) else 0.0,
                "avg_talk_time": round(b["talk_seconds"] / b["talk_calls"]) if b["talk_calls"] else 0,
            })
        return out

    # ---------- Agent performance ----------
    async def agents(self, actor, **f) -> list[dict]:
        acts = await self._load(actor, **f)
        agg: dict = {}
        for a in acts:
            uid = a.assigned_user_id or a.created_by
            if not uid:
                continue
            g = agg.setdefault(uid, {"total": 0, "outbound": 0, "inbound": 0, "calls": 0,
                                     "talk_seconds": 0, "talk_calls": 0, "failed": 0, "by_channel": {}})
            g["total"] += 1
            if (a.call_direction or "OUTBOUND") == "INBOUND":
                g["inbound"] += 1
            else:
                g["outbound"] += 1
            g["by_channel"][a.activity_type] = g["by_channel"].get(a.activity_type, 0) + 1
            if a.activity_type == "Call":
                g["calls"] += 1
                if a.call_duration:
                    g["talk_seconds"] += a.call_duration
                    g["talk_calls"] += 1
            if self._failed(a):
                g["failed"] += 1
        names = await self._names(set(agg))
        resp = await self._response_times_by_agent(actor, **f)
        out = []
        for uid, g in agg.items():
            out.append({
                "agent_id": str(uid), "agent_name": names.get(uid, "Unknown"),
                "total": g["total"], "outbound": g["outbound"], "inbound": g["inbound"],
                "calls": g["calls"], "failed": g["failed"],
                "avg_talk_time": round(g["talk_seconds"] / g["talk_calls"]) if g["talk_calls"] else 0,
                "avg_response_seconds": resp.get(uid, 0),
                "by_channel": [{"label": k, "count": v} for k, v in sorted(g["by_channel"].items(), key=lambda kv: -kv[1])],
            })
        out.sort(key=lambda x: -x["total"])
        return out

    # ---------- Response time ----------
    async def _entity_pairs(self, actor, **f) -> dict:
        """Return {entity_key: [activities sorted by time]} grouped by lead/contact."""
        acts = await self._load(actor, **f)
        groups: dict = {}
        for a in acts:
            key = ("lead", a.lead_id) if a.lead_id else (("contact", a.contact_id) if a.contact_id else None)
            if key is None:
                continue
            groups.setdefault(key, []).append(a)
        for k in groups:
            groups[k].sort(key=lambda x: x.created_at)
        return groups

    async def _response_pairs(self, actor, **f) -> list[tuple]:
        """List of (agent_id, seconds) for each inbound→first-outbound reply."""
        groups = await self._entity_pairs(actor, **f)
        pairs = []
        for acts in groups.values():
            i = 0
            while i < len(acts):
                a = acts[i]
                if (a.call_direction or "OUTBOUND") == "INBOUND":
                    # find the next outbound after this inbound
                    for b in acts[i + 1:]:
                        if (b.call_direction or "OUTBOUND") == "OUTBOUND":
                            secs = (_naive(b.created_at) - _naive(a.created_at)).total_seconds()
                            if secs >= 0:
                                pairs.append((b.assigned_user_id or b.created_by, secs))
                            break
                i += 1
        return pairs

    async def _response_times_by_agent(self, actor, **f) -> dict:
        pairs = await self._response_pairs(actor, **f)
        agg: dict = {}
        for uid, secs in pairs:
            if uid is None:
                continue
            agg.setdefault(uid, []).append(secs)
        return {uid: round(sum(v) / len(v)) for uid, v in agg.items() if v}

    async def response_time(self, actor, **f) -> dict:
        pairs = await self._response_pairs(actor, **f)
        secs = [s for _, s in pairs]
        avg = round(sum(secs) / len(secs)) if secs else 0
        return {"avg_response_seconds": avg, "sample_size": len(secs),
                "median_response_seconds": round(sorted(secs)[len(secs) // 2]) if secs else 0}

    async def talk_time(self, actor, **f) -> dict:
        acts = await self._load(actor, **{**f, "channel": "Call"})
        durs = [a.call_duration for a in acts if a.call_duration]
        return {"avg_talk_seconds": round(sum(durs) / len(durs)) if durs else 0,
                "total_talk_seconds": sum(durs), "calls_with_duration": len(durs)}

    # ---------- Missed ----------
    async def missed(self, actor, **f) -> dict:
        acts = await self._load(actor, **f)
        missed_calls = sum(1 for a in acts if a.activity_type == "Call" and a.status == "Missed")
        failed = {c: 0 for c in CHANNELS}
        for a in acts:
            if self._failed(a) and not (a.activity_type == "Call" and a.status == "Missed"):
                failed[a.activity_type] += 1
        total_failed = sum(failed.values())
        return {"missed_calls": missed_calls, "failed_messages": total_failed,
                "total_missed": missed_calls + total_failed,
                "by_channel": [{"label": c, "count": failed[c]} for c in CHANNELS if failed[c]]}

    # ---------- Conversion ----------
    async def conversion(self, actor, **f) -> dict:
        acts = await self._load(actor, **f)
        lead_ids = {a.lead_id for a in acts if a.lead_id}
        if not lead_ids:
            return {"leads_contacted": 0, "converted": 0, "conversion_rate": 0.0, "revenue": 0.0}
        leads = list((await self.db.execute(select(Lead).filter(Lead.id.in_(lead_ids)))).scalars().all())
        converted = 0
        revenue = 0.0
        for l in leads:
            if l.converted_contact_id is not None or l.status in CONVERTED_LEAD_STATUSES:
                converted += 1
                if l.value:
                    revenue += float(l.value)
        n = len(leads)
        return {"leads_contacted": n, "converted": converted,
                "conversion_rate": round(converted * 100 / n, 1) if n else 0.0, "revenue": round(revenue, 2)}

    # ---------- Engagement ----------
    async def engagement(self, actor, limit=10, **f) -> list[dict]:
        acts = await self._load(actor, **f)
        groups: dict = {}
        for a in acts:
            key = ("lead", a.lead_id) if a.lead_id else (("contact", a.contact_id) if a.contact_id else None)
            if key is None:
                continue
            g = groups.setdefault(key, {"entity_type": key[0], "entity_id": str(key[1]), "interactions": 0,
                                        "inbound": 0, "outbound": 0, "last_at": a.created_at, "channels": set()})
            g["interactions"] += 1
            if (a.call_direction or "OUTBOUND") == "INBOUND":
                g["inbound"] += 1
            else:
                g["outbound"] += 1
            g["channels"].add(a.activity_type)
            if a.created_at > g["last_at"]:
                g["last_at"] = a.created_at
        await self._resolve_names(actor, groups)
        rows = sorted(groups.values(), key=lambda g: -g["interactions"])[:limit]
        return [{"entity_type": g["entity_type"], "entity_id": g["entity_id"], "name": g.get("name", "Unknown"),
                 "interactions": g["interactions"], "inbound": g["inbound"], "outbound": g["outbound"],
                 "channels": sorted(g["channels"]), "last_at": g["last_at"]} for g in rows]

    async def _resolve_names(self, actor, groups: dict):
        lead_ids = [eid for (etype, eid) in groups if etype == "lead"]
        contact_ids = [eid for (etype, eid) in groups if etype == "contact"]
        names = {}
        if lead_ids:
            for lid, title in (await self.db.execute(select(Lead.id, Lead.title).filter(Lead.id.in_(lead_ids)))).all():
                names[("lead", lid)] = title
        if contact_ids:
            for cid, fn, ln in (await self.db.execute(select(Contact.id, Contact.first_name, Contact.last_name).filter(Contact.id.in_(contact_ids)))).all():
                names[("contact", cid)] = f"{fn or ''} {ln or ''}".strip()
        for key, g in groups.items():
            g["name"] = names.get(key, "Unknown")

    # ---------- Heatmap ----------
    async def heatmap(self, actor, **f) -> dict:
        acts = await self._load(actor, **f)
        # grid[weekday 0=Mon..6=Sun][hour 0..23]
        grid = [[0] * 24 for _ in range(7)]
        for a in acts:
            dt = _naive(a.created_at)
            grid[dt.weekday()][dt.hour] += 1
        peak = {"weekday": 0, "hour": 0, "count": 0}
        for wd in range(7):
            for hr in range(24):
                if grid[wd][hr] > peak["count"]:
                    peak = {"weekday": wd, "hour": hr, "count": grid[wd][hr]}
        return {"grid": grid, "peak": peak, "total": sum(sum(r) for r in grid)}

    # ---------- Trend (by day) ----------
    async def trend(self, actor, **f) -> list[dict]:
        acts = await self._load(actor, **f)
        by_day: dict = {}
        for a in acts:
            day = _naive(a.created_at).date().isoformat()
            by_day[day] = by_day.get(day, 0) + 1
        return [{"label": d, "count": c} for d, c in sorted(by_day.items())]

    # ---------- CSV export ----------
    async def export_csv(self, actor, **f) -> str:
        acts = await self._load(actor, **f)
        names = await self._names({a.assigned_user_id or a.created_by for a in acts})
        buf = io.StringIO()
        w = csv.writer(buf)
        w.writerow(["created_at", "channel", "direction", "status", "agent", "duration_sec",
                    "delivered", "failed", "lead_id", "contact_id"])
        for a in sorted(acts, key=lambda x: x.created_at, reverse=True):
            uid = a.assigned_user_id or a.created_by
            status = (a.sms_status or a.wa_status or a.email_status or a.call_disposition or a.status or "")
            w.writerow([_naive(a.created_at).isoformat(), a.activity_type, a.call_direction or "OUTBOUND",
                        status, names.get(uid, ""), a.call_duration or "",
                        "yes" if self._delivered(a) else "", "yes" if self._failed(a) else "",
                        str(a.lead_id) if a.lead_id else "", str(a.contact_id) if a.contact_id else ""])
        return buf.getvalue()

    # ---------- Campaign analytics passthrough ----------
    async def campaigns(self, actor) -> dict:
        from app.services.campaign_service import CampaignService
        return await CampaignService(self.db).dashboard(actor)

    async def _names(self, ids) -> dict:
        ids = {i for i in ids if i}
        if not ids:
            return {}
        res = await self.db.execute(select(User.id, User.first_name, User.last_name, User.email).filter(User.id.in_(ids)))
        return {uid: (f"{fn or ''} {ln or ''}".strip() or em) for uid, fn, ln, em in res.all()}
