"""Campaign module service.

A campaign is a bulk outreach on one channel (SMS/Email/WhatsApp/Call) to an
audience resolved from leads or contacts. It reuses the channel send services
(SmsService / EmailModuleService / WhatsAppService) so every message becomes a
tracked Activity, and derives delivery / open / click / conversion metrics from
those activities plus lead conversion state (for ROI).
"""
from __future__ import annotations
import uuid
from datetime import datetime, timezone
from decimal import Decimal
from fastapi import HTTPException, status
from sqlalchemy import select, func, or_
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User
from app.models.lead import Lead
from app.models.contact import Contact
from app.models.activity import Activity
from app.models.campaign import Campaign, CampaignRecipient, CampaignSegment
from app.models.communication import CommunicationTemplate
from app.services.audit_service import AuditService
from app.services.notification_service import NotificationService

CHANNELS = ("SMS", "Email", "WhatsApp", "Call")
BATCH_SIZE = 200
# lead statuses that count as a conversion for ROI
CONVERTED_LEAD_STATUSES = {"Won", "Converted", "Customer"}


def _now() -> datetime:
    return datetime.now(timezone.utc)


class CampaignService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.audit = AuditService(db)
        self.notifier = NotificationService(db)

    def _privileged(self, actor: User) -> bool:
        return actor.role in ("SuperAdmin", "OrgAdmin", "Manager")

    def _require_privileged(self, actor: User, what: str):
        if not self._privileged(actor):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN,
                                detail=f"Only a Manager or OrgAdmin can {what}.")

    # ---------- Audience resolution ----------
    def _apply_lead_filters(self, q, defn: dict):
        d = defn or {}
        if d.get("status"):
            q = q.filter(Lead.status == d["status"])
        if d.get("source"):
            q = q.filter(Lead.source == d["source"])
        if d.get("city"):
            q = q.filter(Lead.city == d["city"])
        if d.get("priority"):
            q = q.filter(Lead.priority == d["priority"])
        if d.get("stage_id"):
            q = q.filter(Lead.stage_id == d["stage_id"])
        if d.get("assigned_user_id"):
            q = q.filter(Lead.assigned_user_id == d["assigned_user_id"])
        if d.get("min_score") is not None:
            q = q.filter(Lead.score >= d["min_score"])
        if d.get("exclude_archived", True):
            q = q.filter(Lead.is_archived == False)
        return q

    def _apply_contact_filters(self, q, defn: dict):
        d = defn or {}
        if d.get("company_id"):
            q = q.filter(Contact.company_id == d["company_id"])
        if d.get("assigned_user_id"):
            q = q.filter(Contact.assigned_user_id == d["assigned_user_id"])
        return q

    def _needs_email(self, channel: str) -> bool:
        return channel == "Email"

    async def _resolve_entities(self, actor: User, entity_type: str, channel: str,
                                audience_type: str, definition: dict | None, segment_id=None,
                                explicit_ids: list | None = None) -> list:
        """Return a list of (entity_id, to_address) reachable on this channel."""
        if audience_type == "segment" and segment_id:
            seg = (await self.db.execute(select(CampaignSegment).filter(
                CampaignSegment.id == segment_id, CampaignSegment.organization_id == actor.organization_id,
                CampaignSegment.is_deleted == False))).scalars().first()
            if not seg:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Segment not found.")
            entity_type = seg.entity_type
            definition = seg.definition

        needs_email = self._needs_email(channel)
        results = []
        if entity_type == "contact":
            q = select(Contact).filter(Contact.organization_id == actor.organization_id, Contact.is_deleted == False)
            if audience_type == "list" and explicit_ids:
                q = q.filter(Contact.id.in_(explicit_ids))
            else:
                q = self._apply_contact_filters(q, definition or {})
            for c in (await self.db.execute(q)).scalars().all():
                addr = (c.email if needs_email else c.phone) or ""
                if addr.strip():
                    results.append((c.id, addr.strip()))
        else:
            q = select(Lead).filter(Lead.organization_id == actor.organization_id, Lead.is_deleted == False)
            if audience_type == "list" and explicit_ids:
                q = q.filter(Lead.id.in_(explicit_ids))
            else:
                q = self._apply_lead_filters(q, definition or {})
            for l in (await self.db.execute(q)).scalars().all():
                addr = (l.email if needs_email else l.phone) or ""
                if addr.strip():
                    results.append((l.id, addr.strip()))
        return results

    async def preview_audience(self, actor: User, data: dict) -> dict:
        entity_type = data.get("entity_type", "lead")
        channel = data.get("channel", "SMS")
        entities = await self._resolve_entities(
            actor, entity_type, channel, data.get("audience_type", "filter"),
            data.get("audience_definition"), data.get("segment_id"), data.get("ids"))
        sample = [str(eid) for eid, _ in entities[:5]]
        return {"count": len(entities), "sample_ids": sample, "channel": channel, "entity_type": entity_type}

    # ---------- CRUD ----------
    async def list(self, actor: User, status_filter=None, channel=None, search=None, skip=0, limit=50) -> list[Campaign]:
        q = select(Campaign).filter(Campaign.organization_id == actor.organization_id, Campaign.is_deleted == False)
        if not self._privileged(actor):
            q = q.filter(Campaign.created_by == actor.id)
        if status_filter:
            q = q.filter(Campaign.status == status_filter)
        if channel:
            q = q.filter(Campaign.channel == channel)
        if search:
            q = q.filter(Campaign.name.ilike(f"%{search}%"))
        q = q.order_by(Campaign.created_at.desc()).offset(skip).limit(limit)
        return list((await self.db.execute(q)).scalars().all())

    async def get(self, actor: User, campaign_id: uuid.UUID) -> Campaign:
        q = select(Campaign).filter(
            Campaign.id == campaign_id, Campaign.organization_id == actor.organization_id, Campaign.is_deleted == False)
        if not self._privileged(actor):
            q = q.filter(Campaign.created_by == actor.id)
        c = (await self.db.execute(q)).scalars().first()
        if not c:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Campaign not found")
        return c

    async def create(self, actor: User, data: dict) -> Campaign:
        channel = data.get("channel")
        if channel not in CHANNELS:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Invalid channel. Allowed: {list(CHANNELS)}")
        # A template or inline body is required for message channels (Call = script/queue, optional body)
        if channel != "Call" and not data.get("template_id") and not data.get("body"):
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Provide a template_id or body.")
        if data.get("template_id"):
            t = (await self.db.execute(select(CommunicationTemplate).filter(
                CommunicationTemplate.id == data["template_id"], CommunicationTemplate.organization_id == actor.organization_id,
                CommunicationTemplate.is_deleted == False))).scalars().first()
            if not t:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Template not found.")
        c = Campaign(
            organization_id=actor.organization_id, name=data["name"], description=data.get("description"),
            channel=channel, template_id=data.get("template_id"), subject=data.get("subject"), body=data.get("body"),
            status="draft", audience_type=data.get("audience_type", "filter"),
            audience_definition=data.get("audience_definition"), segment_id=data.get("segment_id"),
            entity_type=data.get("entity_type", "lead"),
            cost_per_message=Decimal(str(data.get("cost_per_message", 0) or 0)),
            max_retries=data.get("max_retries", 2), created_by=actor.id)
        self.db.add(c)
        await self.db.flush()
        await self.db.refresh(c)
        return c

    async def update(self, actor: User, campaign_id: uuid.UUID, data: dict) -> Campaign:
        c = await self.get(actor, campaign_id)
        if c.status not in ("draft", "scheduled", "paused"):
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"A {c.status} campaign cannot be edited.")
        for k in ("name", "description", "subject", "body", "template_id", "audience_type",
                  "audience_definition", "segment_id", "entity_type", "max_retries"):
            if k in data and data[k] is not None:
                setattr(c, k, data[k])
        if "cost_per_message" in data and data["cost_per_message"] is not None:
            c.cost_per_message = Decimal(str(data["cost_per_message"]))
        self.db.add(c)
        await self.db.flush()
        await self.db.refresh(c)
        return c

    async def delete(self, actor: User, campaign_id: uuid.UUID) -> None:
        c = await self.get(actor, campaign_id)
        if c.created_by != actor.id and not self._privileged(actor):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized to delete this campaign.")
        c.is_deleted = True
        self.db.add(c)
        await self.db.flush()

    # ---------- Build the queue ----------
    async def build_audience(self, actor: User, campaign_id: uuid.UUID, explicit_ids=None) -> Campaign:
        c = await self.get(actor, campaign_id)
        if c.status not in ("draft", "scheduled", "paused"):
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Audience can only be built before the campaign runs.")
        entities = await self._resolve_entities(actor, c.entity_type, c.channel, c.audience_type,
                                                c.audience_definition, c.segment_id, explicit_ids)
        # existing recipients (avoid dupes on rebuild)
        existing = set((await self.db.execute(select(
            CampaignRecipient.lead_id if c.entity_type != "contact" else CampaignRecipient.contact_id
        ).filter(CampaignRecipient.campaign_id == c.id))).scalars().all())
        added = 0
        for eid, addr in entities:
            if eid in existing:
                continue
            r = CampaignRecipient(organization_id=actor.organization_id, campaign_id=c.id, to_address=addr, status="pending")
            if c.entity_type == "contact":
                r.contact_id = eid
            else:
                r.lead_id = eid
            self.db.add(r)
            added += 1
        await self.db.flush()
        c.total_recipients = (await self.db.execute(select(func.count(CampaignRecipient.id)).filter(
            CampaignRecipient.campaign_id == c.id))).scalar() or 0
        self.db.add(c)
        await self.db.flush()
        await self.db.refresh(c)
        return c

    # ---------- Lifecycle ----------
    async def schedule(self, actor: User, campaign_id: uuid.UUID, scheduled_at: datetime) -> Campaign:
        self._require_privileged(actor, "schedule campaigns")
        c = await self.get(actor, campaign_id)
        if c.total_recipients == 0:
            await self.build_audience(actor, campaign_id)
            c = await self.get(actor, campaign_id)
        sa = scheduled_at.replace(tzinfo=None) if scheduled_at.tzinfo else scheduled_at
        c.scheduled_at = sa
        c.status = "scheduled"
        self.db.add(c)
        await self.db.flush()
        await self.db.refresh(c)
        return c

    async def launch(self, actor: User, campaign_id: uuid.UUID) -> Campaign:
        self._require_privileged(actor, "launch campaigns")
        c = await self.get(actor, campaign_id)
        if c.status not in ("draft", "scheduled", "paused"):
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"A {c.status} campaign cannot be launched.")
        if c.total_recipients == 0:
            c = await self.build_audience(actor, campaign_id)
        c.status = "running"
        if not c.started_at:
            c.started_at = _now()
        self.db.add(c)
        await self.db.flush()
        # Call campaigns are a queue for agents to work manually — no auto-send.
        if c.channel != "Call":
            await self._process(c, actor)
        else:
            await self._maybe_complete(c)
        await self.db.refresh(c)
        return c

    async def pause(self, actor: User, campaign_id: uuid.UUID) -> Campaign:
        self._require_privileged(actor, "pause campaigns")
        c = await self.get(actor, campaign_id)
        if c.status != "running":
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Only a running campaign can be paused.")
        c.status = "paused"
        self.db.add(c)
        await self.db.flush()
        await self.db.refresh(c)
        return c

    async def resume(self, actor: User, campaign_id: uuid.UUID) -> Campaign:
        self._require_privileged(actor, "resume campaigns")
        c = await self.get(actor, campaign_id)
        if c.status != "paused":
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Only a paused campaign can be resumed.")
        c.status = "running"
        self.db.add(c)
        await self.db.flush()
        if c.channel != "Call":
            await self._process(c, actor)
        await self.db.refresh(c)
        return c

    async def cancel(self, actor: User, campaign_id: uuid.UUID) -> Campaign:
        self._require_privileged(actor, "cancel campaigns")
        c = await self.get(actor, campaign_id)
        if c.status in ("completed", "cancelled"):
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Campaign already {c.status}.")
        c.status = "cancelled"
        c.completed_at = _now()
        self.db.add(c)
        await self.db.flush()
        await self.db.refresh(c)
        return c

    # ---------- Queue processing ----------
    async def _send_one(self, c: Campaign, r: CampaignRecipient, actor: User):
        """Dispatch one recipient via the channel service; update the recipient row."""
        body = c.body or ""
        subject = c.subject or c.name
        if c.template_id:
            t = (await self.db.execute(select(CommunicationTemplate).filter(
                CommunicationTemplate.id == c.template_id))).scalars().first()
            if t:
                body = body or t.body
                subject = subject or t.subject or c.name
        link = {"lead_id": r.lead_id, "contact_id": r.contact_id}
        try:
            if c.channel == "SMS":
                from app.services.sms_service import SmsService
                act = await SmsService(self.db).send(actor, {"body": body, "to_number": r.to_address, **link}, _skip_cap=True)
            elif c.channel == "Email":
                from app.services.email_service_module import EmailModuleService
                act = await EmailModuleService(self.db).send(actor, {"subject": subject, "body": body, "to": r.to_address, **link})
            elif c.channel == "WhatsApp":
                from app.services.whatsapp_service import WhatsAppService
                tname = None
                if c.template_id and t:
                    tname = t.name
                act = await WhatsAppService(self.db).send_template(actor, {
                    "template_name": tname or c.name, "to_number": r.to_address, "body": body, **link})
            else:
                return
            r.activity_id = act.id
            r.sent_at = _now()
            # failed transports set a failure status on the activity
            failed = getattr(act, "sms_status", None) == "failed" or getattr(act, "wa_status", None) == "failed" or \
                getattr(act, "email_status", None) == "failed"
            r.status = "failed" if failed else "sent"
            r.error = getattr(act, "sms_error", None) or getattr(act, "wa_error", None)
        except Exception as e:
            r.status = "failed"
            r.error = str(e)[:500]
        self.db.add(r)

    async def _process(self, c: Campaign, actor: User) -> int:
        """Send the next batch of pending recipients. Returns the number processed."""
        if c.status != "running":
            return 0
        pending = list((await self.db.execute(select(CampaignRecipient).filter(
            CampaignRecipient.campaign_id == c.id, CampaignRecipient.status == "pending").limit(BATCH_SIZE))).scalars().all())
        for r in pending:
            await self._send_one(c, r, actor)
        await self.db.flush()
        await self._recount(c)
        await self._maybe_complete(c)
        return len(pending)

    async def retry_failed(self, actor: User, campaign_id: uuid.UUID) -> Campaign:
        self._require_privileged(actor, "retry campaigns")
        c = await self.get(actor, campaign_id)
        failed = list((await self.db.execute(select(CampaignRecipient).filter(
            CampaignRecipient.campaign_id == c.id, CampaignRecipient.status == "failed",
            CampaignRecipient.retry_count < c.max_retries))).scalars().all())
        for r in failed:
            r.retry_count += 1
            await self._send_one(c, r, actor)
        await self.db.flush()
        await self._recount(c)
        await self.db.refresh(c)
        return c

    async def _recount(self, c: Campaign):
        rows = list((await self.db.execute(select(CampaignRecipient.status, func.count(CampaignRecipient.id))
                                           .filter(CampaignRecipient.campaign_id == c.id)
                                           .group_by(CampaignRecipient.status))).all())
        counts = {s: n for s, n in rows}
        c.sent_count = sum(counts.get(s, 0) for s in ("sent", "delivered", "opened", "clicked", "converted"))
        c.failed_count = counts.get("failed", 0)
        c.total_recipients = sum(counts.values())
        self.db.add(c)
        await self.db.flush()

    async def _maybe_complete(self, c: Campaign):
        pending = (await self.db.execute(select(func.count(CampaignRecipient.id)).filter(
            CampaignRecipient.campaign_id == c.id, CampaignRecipient.status.in_(["pending"])))).scalar() or 0
        if pending == 0 and c.status == "running" and c.channel != "Call":
            c.status = "completed"
            c.completed_at = _now()
            self.db.add(c)
            await self.db.flush()
            if c.created_by:
                await self.notifier.create_notification(
                    organization_id=c.organization_id, user_id=c.created_by, category="campaign",
                    title="Campaign completed",
                    body=f'Campaign "{c.name}" finished — {c.sent_count} sent, {c.failed_count} failed.',
                    link_url=f"/campaigns?campaignId={c.id}",
                    action_metadata={"campaign_id": str(c.id)})

    # ---------- Engagement sync + reports ----------
    async def sync_engagement(self, actor: User, campaign_id: uuid.UUID) -> Campaign:
        """Recompute delivery/open/click/conversion from the linked activities and
        lead conversion state, then refresh ROI figures on the campaign."""
        c = await self.get(actor, campaign_id)
        recipients = list((await self.db.execute(select(CampaignRecipient).filter(
            CampaignRecipient.campaign_id == c.id))).scalars().all())
        act_ids = [r.activity_id for r in recipients if r.activity_id]
        acts = {}
        if act_ids:
            for a in (await self.db.execute(select(Activity).filter(Activity.id.in_(act_ids)))).scalars().all():
                acts[a.id] = a
        # lead conversion state
        lead_ids = [r.lead_id for r in recipients if r.lead_id]
        converted_leads = {}
        revenue = Decimal("0")
        if lead_ids:
            for l in (await self.db.execute(select(Lead).filter(Lead.id.in_(lead_ids)))).scalars().all():
                is_conv = l.converted_contact_id is not None or l.status in CONVERTED_LEAD_STATUSES
                converted_leads[l.id] = is_conv
                if is_conv and l.value:
                    revenue += Decimal(str(l.value))

        delivered = opened = clicked = converted = 0
        for r in recipients:
            a = acts.get(r.activity_id)
            new_status = r.status
            if a is not None:
                if c.channel == "SMS":
                    if a.sms_status in ("delivered", "sent"):
                        delivered += 1
                elif c.channel == "WhatsApp":
                    if a.wa_status in ("delivered", "read", "sent"):
                        delivered += 1
                    if a.wa_status == "read":
                        opened += 1
                elif c.channel == "Email":
                    if a.email_status == "sent":
                        delivered += 1
                    if (a.email_open_count or 0) > 0:
                        opened += 1
                        new_status = "opened"
                    if (a.email_click_count or 0) > 0:
                        clicked += 1
                        new_status = "clicked"
            if r.lead_id and converted_leads.get(r.lead_id):
                converted += 1
                new_status = "converted"
            if new_status != r.status:
                r.status = new_status
                self.db.add(r)

        c.delivered_count = delivered
        c.opened_count = opened
        c.clicked_count = clicked
        c.converted_count = converted
        c.revenue = revenue
        self.db.add(c)
        await self.db.flush()
        await self.db.refresh(c)
        return c

    def _report(self, c: Campaign) -> dict:
        sent = c.sent_count or 0
        cost = (Decimal(str(c.cost_per_message or 0)) * sent)
        revenue = Decimal(str(c.revenue or 0))
        roi = revenue - cost
        roi_pct = float(round((roi / cost * 100), 1)) if cost > 0 else 0.0
        pct = lambda n: float(round(n * 100 / sent, 1)) if sent else 0.0
        return {
            "campaign_id": str(c.id), "name": c.name, "channel": c.channel, "status": c.status,
            "total_recipients": c.total_recipients, "sent": sent, "delivered": c.delivered_count,
            "failed": c.failed_count, "opened": c.opened_count, "clicked": c.clicked_count,
            "converted": c.converted_count,
            "delivery_rate": pct(c.delivered_count), "open_rate": pct(c.opened_count),
            "click_rate": pct(c.clicked_count), "conversion_rate": pct(c.converted_count),
            "cost": float(cost), "revenue": float(revenue), "roi": float(roi), "roi_pct": roi_pct,
        }

    async def reports(self, actor: User, campaign_id: uuid.UUID, sync: bool = True) -> dict:
        if sync:
            c = await self.sync_engagement(actor, campaign_id)
        else:
            c = await self.get(actor, campaign_id)
        return self._report(c)

    async def recipients(self, actor: User, campaign_id: uuid.UUID, status_filter=None, skip=0, limit=100) -> dict:
        await self.get(actor, campaign_id)  # scope check
        q = select(CampaignRecipient).filter(CampaignRecipient.campaign_id == campaign_id)
        if status_filter:
            q = q.filter(CampaignRecipient.status == status_filter)
        total = (await self.db.execute(select(func.count()).select_from(q.subquery()))).scalar() or 0
        rows = list((await self.db.execute(q.order_by(CampaignRecipient.created_at.asc()).offset(skip).limit(limit))).scalars().all())
        return {"items": [{
            "id": str(r.id), "lead_id": str(r.lead_id) if r.lead_id else None,
            "contact_id": str(r.contact_id) if r.contact_id else None, "to_address": r.to_address,
            "status": r.status, "error": r.error, "retry_count": r.retry_count,
            "activity_id": str(r.activity_id) if r.activity_id else None,
            "sent_at": r.sent_at} for r in rows], "total": total}

    async def dashboard(self, actor: User) -> dict:
        q = select(Campaign).filter(Campaign.organization_id == actor.organization_id, Campaign.is_deleted == False)
        if not self._privileged(actor):
            q = q.filter(Campaign.created_by == actor.id)
        rows = list((await self.db.execute(q)).scalars().all())
        by_status: dict = {}
        total_sent = total_converted = 0
        total_revenue = Decimal("0")
        total_cost = Decimal("0")
        for c in rows:
            by_status[c.status] = by_status.get(c.status, 0) + 1
            total_sent += c.sent_count or 0
            total_converted += c.converted_count or 0
            total_revenue += Decimal(str(c.revenue or 0))
            total_cost += Decimal(str(c.cost_per_message or 0)) * (c.sent_count or 0)
        return {
            "total": len(rows),
            "running": by_status.get("running", 0),
            "scheduled": by_status.get("scheduled", 0),
            "completed": by_status.get("completed", 0),
            "total_sent": total_sent, "total_converted": total_converted,
            "total_revenue": float(total_revenue), "total_roi": float(total_revenue - total_cost),
            "by_status": [{"label": k, "count": v} for k, v in sorted(by_status.items(), key=lambda kv: -kv[1])],
        }

    # ---------- Segments ----------
    async def list_segments(self, actor: User) -> list[CampaignSegment]:
        res = await self.db.execute(select(CampaignSegment).filter(
            CampaignSegment.organization_id == actor.organization_id, CampaignSegment.is_deleted == False)
            .order_by(CampaignSegment.name.asc()))
        return list(res.scalars().all())

    async def create_segment(self, actor: User, data: dict) -> CampaignSegment:
        seg = CampaignSegment(organization_id=actor.organization_id, name=data["name"],
                              description=data.get("description"), entity_type=data.get("entity_type", "lead"),
                              definition=data.get("definition") or {}, created_by=actor.id)
        seg.cached_count = await self._segment_count(actor, seg.entity_type, seg.definition)
        self.db.add(seg)
        await self.db.flush()
        await self.db.refresh(seg)
        return seg

    async def _segment_count(self, actor: User, entity_type: str, definition: dict) -> int:
        entities = await self._resolve_entities(actor, entity_type, "SMS" if entity_type != "contact" else "SMS",
                                                "filter", definition)
        # count entities regardless of reachability address for a segment size estimate
        if entity_type == "contact":
            q = self._apply_contact_filters(select(func.count(Contact.id)).filter(
                Contact.organization_id == actor.organization_id, Contact.is_deleted == False), definition)
        else:
            q = self._apply_lead_filters(select(func.count(Lead.id)).filter(
                Lead.organization_id == actor.organization_id, Lead.is_deleted == False), definition)
        return (await self.db.execute(q)).scalar() or 0

    async def update_segment(self, actor: User, segment_id: uuid.UUID, data: dict) -> CampaignSegment:
        seg = await self._get_segment(actor, segment_id)
        for k in ("name", "description", "entity_type", "definition"):
            if k in data and data[k] is not None:
                setattr(seg, k, data[k])
        seg.cached_count = await self._segment_count(actor, seg.entity_type, seg.definition)
        self.db.add(seg)
        await self.db.flush()
        await self.db.refresh(seg)
        return seg

    async def _get_segment(self, actor: User, segment_id: uuid.UUID) -> CampaignSegment:
        seg = (await self.db.execute(select(CampaignSegment).filter(
            CampaignSegment.id == segment_id, CampaignSegment.organization_id == actor.organization_id,
            CampaignSegment.is_deleted == False))).scalars().first()
        if not seg:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Segment not found")
        return seg

    async def delete_segment(self, actor: User, segment_id: uuid.UUID) -> None:
        seg = await self._get_segment(actor, segment_id)
        seg.is_deleted = True
        self.db.add(seg)
        await self.db.flush()

    # ---------- Workflow enrolment ----------
    async def add_lead(self, campaign_id: uuid.UUID, lead: Lead) -> bool:
        """Enrol a lead into a draft/scheduled/running campaign (workflow action).
        Returns True if newly added."""
        c = (await self.db.execute(select(Campaign).filter(
            Campaign.id == campaign_id, Campaign.organization_id == lead.organization_id,
            Campaign.is_deleted == False))).scalars().first()
        if not c or c.status in ("completed", "cancelled"):
            return False
        addr = (lead.email if c.channel == "Email" else lead.phone) or ""
        if not addr.strip():
            return False
        exists = (await self.db.execute(select(CampaignRecipient.id).filter(
            CampaignRecipient.campaign_id == c.id, CampaignRecipient.lead_id == lead.id))).scalar()
        if exists:
            return False
        self.db.add(CampaignRecipient(organization_id=c.organization_id, campaign_id=c.id,
                                      lead_id=lead.id, to_address=addr.strip(), status="pending"))
        c.total_recipients = (c.total_recipients or 0) + 1
        self.db.add(c)
        await self.db.flush()
        return True


async def process_scheduled_campaigns(db: AsyncSession) -> int:
    """Cron: launch due scheduled campaigns and advance any running queues."""
    now = _now().replace(tzinfo=None)
    svc = CampaignService(db)
    due = list((await db.execute(select(Campaign).filter(
        Campaign.is_deleted == False, Campaign.status == "scheduled",
        Campaign.scheduled_at.isnot(None), Campaign.scheduled_at <= now))).scalars().all())
    processed = 0
    for c in due:
        actor = await db.get(User, c.created_by)
        if not actor:
            continue
        c.status = "running"
        c.started_at = c.started_at or _now()
        db.add(c)
        await db.flush()
        if c.channel != "Call":
            await svc._process(c, actor)
        processed += 1
    # advance already-running message campaigns with a pending backlog
    running = list((await db.execute(select(Campaign).filter(
        Campaign.is_deleted == False, Campaign.status == "running", Campaign.channel != "Call"))).scalars().all())
    for c in running:
        actor = await db.get(User, c.created_by)
        if actor:
            await svc._process(c, actor)
    return processed
