"""SMS module service.

SMS messages are Activity rows (activity_type='SMS') so they flow through the
Communication Center feed, conversation view, and customer timeline unchanged.
This service owns the send/receive/delivery lifecycle on top of that: provider
transmission, per-org daily cap, delivery-status + inbound webhooks, retries,
and reporting. Provider config lives in SmsSettings (one row per org).
"""
import secrets
import uuid
from datetime import datetime, timezone, timedelta
from fastapi import HTTPException, status
from sqlalchemy import select, func, or_
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User
from app.models.lead import Lead
from app.models.contact import Contact
from app.models.company import Company
from app.models.activity import Activity
from app.models.communication import CommunicationFlag
from app.models.sms_settings import SmsSettings
from app.services.audit_service import AuditService
from app.services.notification_service import NotificationService
from app.services.sms_providers import get_provider, segment_count

MAX_AUTO_RETRIES = 3
# statuses that count as a successful delivery for delivery-rate reporting
DELIVERED_STATUSES = {"delivered", "sent"}
FAILED_STATUSES = {"failed", "undelivered"}


class SmsService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.audit = AuditService(db)
        self.notifier = NotificationService(db)

    def _privileged(self, actor: User) -> bool:
        return actor.role in ("SuperAdmin", "OrgAdmin", "Manager")

    # ---------- Settings ----------
    async def get_settings(self, actor: User, create: bool = True) -> SmsSettings | None:
        res = await self.db.execute(select(SmsSettings).filter(
            SmsSettings.organization_id == actor.organization_id, SmsSettings.is_deleted == False))
        s = res.scalars().first()
        if not s and create:
            s = SmsSettings(organization_id=actor.organization_id, provider="mock",
                            webhook_token=secrets.token_urlsafe(24))
            self.db.add(s)
            await self.db.flush()
            await self.db.refresh(s)
        return s

    async def update_settings(self, actor: User, data: dict) -> SmsSettings:
        if actor.role not in ("SuperAdmin", "OrgAdmin"):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only an OrgAdmin can change SMS settings.")
        s = await self.get_settings(actor, create=True)
        for k in ("provider", "account_sid", "auth_token", "sender_id", "sms_priority",
                  "sms_type", "default_template_id", "daily_limit", "is_active"):
            if k in data and data[k] is not None:
                setattr(s, k, data[k])
        if data.get("regenerate_webhook_token") or not s.webhook_token:
            s.webhook_token = secrets.token_urlsafe(24)
        self.db.add(s)
        await self.db.flush()
        await self.db.refresh(s)
        return s

    # ---------- Sending ----------
    async def _daily_sent_count(self, org_id: uuid.UUID) -> int:
        start = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
        res = await self.db.execute(select(func.count(Activity.id)).filter(
            Activity.organization_id == org_id, Activity.activity_type == "SMS",
            Activity.call_direction == "OUTBOUND", Activity.created_at >= start))
        return res.scalar() or 0

    async def _resolve_recipient(self, actor: User, data: dict) -> tuple[str, dict]:
        """Return (to_number, {lead_id/contact_id/company_id}). Prefers an explicit
        to_number, else derives it from the linked lead/contact phone."""
        links = {"lead_id": data.get("lead_id"), "contact_id": data.get("contact_id"),
                 "company_id": data.get("company_id")}
        to_number = (data.get("to_number") or "").strip()
        if not to_number and data.get("lead_id"):
            lead = (await self.db.execute(select(Lead).filter(
                Lead.id == data["lead_id"], Lead.organization_id == actor.organization_id))).scalars().first()
            if lead:
                to_number = (lead.phone or "").strip()
        if not to_number and data.get("contact_id"):
            c = (await self.db.execute(select(Contact).filter(
                Contact.id == data["contact_id"], Contact.organization_id == actor.organization_id))).scalars().first()
            if c:
                to_number = (c.phone or "").strip()
        if not to_number:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST,
                                detail="No destination number: provide to_number or a lead/contact with a phone.")
        return to_number, links

    async def send(self, actor: User, data: dict, *, _settings: SmsSettings | None = None,
                   _skip_cap: bool = False) -> Activity:
        body = (data.get("body") or "").strip()
        if not body:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Message body is required.")
        settings_row = _settings if _settings is not None else await self.get_settings(actor, create=True)

        if not _skip_cap:
            sent_today = await self._daily_sent_count(actor.organization_id)
            if settings_row and sent_today >= settings_row.daily_limit:
                raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                                    detail=f"Daily SMS limit reached ({settings_row.daily_limit}).")

        to_number, links = await self._resolve_recipient(actor, data)
        from_number = (settings_row.sender_id if settings_row else None) or ""

        act = Activity(
            organization_id=actor.organization_id, activity_type="SMS",
            subject=data.get("subject") or f"SMS to {to_number}",
            description=body, status="Planned", call_direction="OUTBOUND",
            assigned_user_id=actor.id, created_by=actor.id,
            lead_id=links["lead_id"], contact_id=links["contact_id"], company_id=links["company_id"],
            to_number=to_number, from_number=from_number, sms_segments=segment_count(body),
        )
        self.db.add(act)
        await self.db.flush()

        provider = get_provider(settings_row)
        result = await provider.send(to_number=to_number, from_number=from_number, body=body)
        act.sms_status = result.status
        act.sms_provider_id = result.provider_id
        act.sms_error = result.error
        act.sms_segments = result.segments
        act.status = "Completed" if result.status != "failed" else "Failed"

        # Outbound is inherently 'read' for the sender (matches Comm Center semantics)
        self.db.add(CommunicationFlag(organization_id=actor.organization_id, user_id=actor.id,
                                      activity_id=act.id, is_read=True, read_at=datetime.now(timezone.utc)))
        self.db.add(act)
        await self.db.flush()

        await self.audit.log_event(organization_id=actor.organization_id, actor_user_id=actor.id,
                                   action="SMS_SENT", resource_type="communication", resource_id=str(act.id),
                                   action_metadata={"to": to_number, "status": result.status,
                                                    "provider": provider.name, "segments": result.segments})
        return act

    async def send_bulk(self, actor: User, data: dict) -> dict:
        recipients = data.get("recipients") or []
        if not recipients:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="No recipients provided.")
        if len(recipients) > 500:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Bulk send is limited to 500 recipients per request.")
        body = (data.get("body") or "").strip()
        if not body:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Message body is required.")

        settings_row = await self.get_settings(actor, create=True)
        sent_today = await self._daily_sent_count(actor.organization_id)
        remaining = max(0, (settings_row.daily_limit if settings_row else 0) - sent_today)
        if len(recipients) > remaining:
            raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                                detail=f"Bulk request ({len(recipients)}) exceeds remaining daily quota ({remaining}).")

        results = {"total": len(recipients), "queued": 0, "failed": 0, "activity_ids": []}
        for r in recipients:
            payload = {"body": body, "subject": data.get("subject"),
                       "to_number": r.get("to_number"), "lead_id": r.get("lead_id"),
                       "contact_id": r.get("contact_id"), "company_id": r.get("company_id")}
            try:
                act = await self.send(actor, payload, _settings=settings_row, _skip_cap=True)
                results["activity_ids"].append(str(act.id))
                if act.sms_status in FAILED_STATUSES or act.sms_status == "failed":
                    results["failed"] += 1
                else:
                    results["queued"] += 1
            except HTTPException:
                results["failed"] += 1
        return results

    async def retry(self, actor: User, activity_id: uuid.UUID) -> Activity:
        act = await self._get_sms(actor, activity_id)
        if act.call_direction != "OUTBOUND":
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Only outbound SMS can be retried.")
        if act.sms_status not in ({"failed"} | FAILED_STATUSES):
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST,
                                detail=f"Only failed messages can be retried (status={act.sms_status}).")
        settings_row = await self.get_settings(actor, create=True)
        provider = get_provider(settings_row)
        result = await provider.send(to_number=act.to_number or "", from_number=act.from_number or "", body=act.description or "")
        act.sms_status = result.status
        act.sms_provider_id = result.provider_id or act.sms_provider_id
        act.sms_error = result.error
        act.sms_retry_count = (act.sms_retry_count or 0) + 1
        act.status = "Completed" if result.status != "failed" else "Failed"
        self.db.add(act)
        await self.db.flush()
        return act

    async def retry_failed_batch(self, organization_id: uuid.UUID | None = None) -> int:
        """Cron: re-send failed outbound SMS that haven't exhausted retries."""
        q = select(Activity).filter(
            Activity.is_deleted == False, Activity.activity_type == "SMS",
            Activity.call_direction == "OUTBOUND", Activity.sms_status == "failed",
            Activity.sms_retry_count < MAX_AUTO_RETRIES)
        if organization_id:
            q = q.filter(Activity.organization_id == organization_id)
        acts = list((await self.db.execute(q)).scalars().all())
        # cache settings per org to avoid re-querying
        settings_cache: dict = {}
        retried = 0
        for act in acts:
            oid = act.organization_id
            if oid not in settings_cache:
                res = await self.db.execute(select(SmsSettings).filter(
                    SmsSettings.organization_id == oid, SmsSettings.is_deleted == False))
                settings_cache[oid] = res.scalars().first()
            provider = get_provider(settings_cache[oid])
            result = await provider.send(to_number=act.to_number or "", from_number=act.from_number or "", body=act.description or "")
            act.sms_status = result.status
            act.sms_provider_id = result.provider_id or act.sms_provider_id
            act.sms_error = result.error
            act.sms_retry_count = (act.sms_retry_count or 0) + 1
            act.status = "Completed" if result.status != "failed" else "Failed"
            self.db.add(act)
            retried += 1
        await self.db.flush()
        return retried

    # ---------- Webhooks (token-secured, no auth actor) ----------
    async def _org_by_token(self, token: str) -> SmsSettings:
        if not token:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing webhook token.")
        res = await self.db.execute(select(SmsSettings).filter(
            SmsSettings.webhook_token == token, SmsSettings.is_deleted == False))
        s = res.scalars().first()
        if not s:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid webhook token.")
        return s

    async def handle_status(self, token: str, provider_id: str, new_status: str, error: str | None) -> dict:
        s = await self._org_by_token(token)
        if not provider_id:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Missing provider message id.")
        res = await self.db.execute(select(Activity).filter(
            Activity.organization_id == s.organization_id, Activity.activity_type == "SMS",
            Activity.sms_provider_id == provider_id))
        act = res.scalars().first()
        if not act:
            return {"status": "ignored", "reason": "unknown provider id"}
        act.sms_status = new_status
        if error:
            act.sms_error = error[:500]
        if new_status in FAILED_STATUSES:
            act.status = "Failed"
        elif new_status in DELIVERED_STATUSES:
            act.status = "Completed"
        self.db.add(act)
        await self.db.flush()
        return {"status": "updated", "activity_id": str(act.id)}

    async def handle_inbound(self, token: str, from_number: str, to_number: str, body: str,
                             provider_id: str | None) -> dict:
        s = await self._org_by_token(token)
        org_id = s.organization_id
        caller = (from_number or "").strip()
        last10 = caller[-10:] if len(caller) >= 10 else caller

        # Match a lead or contact by trailing-10-digit phone
        lead = None
        contact = None
        if last10:
            lead = (await self.db.execute(select(Lead).filter(
                Lead.organization_id == org_id, Lead.is_deleted == False,
                Lead.phone.like(f"%{last10}%")))).scalars().first()
            if not lead:
                contact = (await self.db.execute(select(Contact).filter(
                    Contact.organization_id == org_id, Contact.is_deleted == False,
                    Contact.phone.like(f"%{last10}%")))).scalars().first()

        target_user = None
        if lead:
            target_user = lead.assigned_user_id or lead.created_by
        elif contact:
            target_user = contact.assigned_user_id or contact.created_by

        act = Activity(
            organization_id=org_id, activity_type="SMS",
            subject=f"SMS from {from_number}", description=body or "", status="Completed",
            call_direction="INBOUND", sms_status="received", sms_provider_id=provider_id,
            assigned_user_id=target_user, created_by=target_user,
            lead_id=lead.id if lead else None, contact_id=contact.id if contact else None,
            to_number=(to_number or "").strip(), from_number=caller,
            sms_segments=segment_count(body),
        )
        self.db.add(act)
        await self.db.flush()

        # Notify the owner of an inbound message
        if target_user:
            who = None
            if lead:
                who = lead.title
            elif contact:
                who = f"{contact.first_name or ''} {contact.last_name or ''}".strip()
            await self.notifier.create_notification(
                organization_id=org_id, user_id=target_user, category="sms",
                title="New SMS received",
                body=f"SMS from {who or from_number}: {(body or '')[:80]}",
                link_url="/communications",
                action_metadata={"activity_id": str(act.id), "from": from_number})

        # Fire sms_received workflow rules against a matched lead
        if lead and target_user:
            owner = await self.db.get(User, target_user)
            if owner:
                from app.services.workflow_service import WorkflowService
                await WorkflowService(self.db).run("sms_received", lead, owner)

        return {"status": "received", "activity_id": str(act.id),
                "lead_id": str(lead.id) if lead else None,
                "contact_id": str(contact.id) if contact else None}

    # ---------- Delivery reports (poll-based providers, e.g. BulkSMSPlans) ----------
    # Non-terminal outbound statuses worth re-polling from the gateway.
    POLL_STATUSES = {"sent", "queued", "pending", "submitted"}

    async def _poll_one(self, provider, act: Activity) -> bool:
        """Poll one activity's delivery report if the provider supports polling.
        Returns True when the row was changed."""
        if not hasattr(provider, "delivery_report") or not act.sms_provider_id:
            return False
        rep = await provider.delivery_report(act.sms_provider_id)
        if not rep.get("found"):
            return False
        changed = False
        mapped = rep.get("status")
        if mapped and mapped != act.sms_status:
            act.sms_status = mapped
            if mapped in DELIVERED_STATUSES:
                act.status = "Completed"
            elif mapped in (FAILED_STATUSES | {"failed"}):
                act.status = "Failed"
            changed = True
        err = rep.get("error")
        if err and str(err) != (act.sms_error or ""):
            act.sms_error = str(err)[:500]
            changed = True
        return changed

    async def refresh_status(self, actor: User, activity_id: uuid.UUID) -> Activity:
        """Manually re-poll a single outbound SMS's delivery status from the provider."""
        act = await self._get_sms(actor, activity_id)
        provider = get_provider(await self.get_settings(actor, create=True))
        if await self._poll_one(provider, act):
            self.db.add(act)
            await self.db.flush()
        return act

    async def poll_delivery_reports(self, organization_id: uuid.UUID | None = None,
                                    lookback_hours: int = 72) -> int:
        """Cron: poll DLR for outbound SMS still in a non-terminal state, for orgs
        whose provider supports polling (e.g. BulkSMSPlans). Returns count updated."""
        since = datetime.now(timezone.utc) - timedelta(hours=lookback_hours)
        q = select(Activity).filter(
            Activity.is_deleted == False, Activity.activity_type == "SMS",
            Activity.call_direction == "OUTBOUND", Activity.sms_provider_id.isnot(None),
            Activity.sms_status.in_(list(self.POLL_STATUSES)), Activity.created_at >= since)
        if organization_id:
            q = q.filter(Activity.organization_id == organization_id)
        acts = list((await self.db.execute(q)).scalars().all())
        provider_cache: dict = {}
        updated = 0
        for act in acts:
            oid = act.organization_id
            if oid not in provider_cache:
                res = await self.db.execute(select(SmsSettings).filter(
                    SmsSettings.organization_id == oid, SmsSettings.is_deleted == False))
                provider_cache[oid] = get_provider(res.scalars().first())
            provider = provider_cache[oid]
            if not hasattr(provider, "delivery_report"):
                continue
            try:
                if await self._poll_one(provider, act):
                    self.db.add(act)
                    updated += 1
            except Exception:
                continue
        await self.db.flush()
        return updated

    # ---------- Provider account info (BulkSMSPlans etc.) ----------
    async def check_balance(self, actor: User) -> dict:
        provider = get_provider(await self.get_settings(actor, create=True))
        if not hasattr(provider, "check_balance"):
            return {"success": False, "message": f"Balance check not supported by provider '{provider.name}'."}
        return await provider.check_balance()

    async def list_sender_ids(self, actor: User) -> dict:
        provider = get_provider(await self.get_settings(actor, create=True))
        if not hasattr(provider, "list_sender_ids"):
            return {"success": False, "items": [],
                    "message": f"Sender-ID management not supported by provider '{provider.name}'."}
        return await provider.list_sender_ids()

    async def request_sender_id(self, actor: User, sender: str, country: str, remarks: str | None) -> dict:
        if actor.role not in ("SuperAdmin", "OrgAdmin"):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only an OrgAdmin can request sender IDs.")
        provider = get_provider(await self.get_settings(actor, create=True))
        if not hasattr(provider, "request_sender_id"):
            return {"success": False, "message": f"Sender-ID management not supported by provider '{provider.name}'."}
        return await provider.request_sender_id(sender, country=country, remarks=remarks)

    # ---------- History / reports ----------
    def _scope(self, q, actor: User):
        if not self._privileged(actor):
            q = q.filter(or_(Activity.assigned_user_id == actor.id, Activity.created_by == actor.id))
        return q

    async def _get_sms(self, actor: User, activity_id: uuid.UUID) -> Activity:
        q = select(Activity).filter(
            Activity.id == activity_id, Activity.organization_id == actor.organization_id,
            Activity.is_deleted == False, Activity.activity_type == "SMS")
        act = (await self.db.execute(self._scope(q, actor))).scalars().first()
        if not act:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="SMS not found")
        return act

    async def messages(self, actor: User, direction=None, sms_status=None, search=None,
                       date_from=None, date_to=None, skip=0, limit=50) -> dict:
        q = select(Activity).filter(
            Activity.organization_id == actor.organization_id, Activity.is_deleted == False,
            Activity.activity_type == "SMS")
        q = self._scope(q, actor)
        if direction:
            q = q.filter(Activity.call_direction == direction)
        if sms_status:
            q = q.filter(Activity.sms_status == sms_status)
        if date_from is not None:
            q = q.filter(Activity.created_at >= date_from)
        if date_to is not None:
            q = q.filter(Activity.created_at <= date_to)
        if search:
            s = f"%{search}%"
            q = q.filter(or_(Activity.subject.ilike(s), Activity.description.ilike(s),
                             Activity.to_number.ilike(s), Activity.from_number.ilike(s)))
        acts = list((await self.db.execute(q.order_by(Activity.created_at.desc()))).scalars().all())
        total = len(acts)
        acts = acts[skip:skip + limit]
        names = await self._names({a.assigned_user_id or a.created_by for a in acts})
        return {"items": [self._item(a, names) for a in acts], "total": total}

    def _item(self, a: Activity, names: dict) -> dict:
        uid = a.assigned_user_id or a.created_by
        return {
            "id": str(a.id), "direction": a.call_direction, "body": a.description,
            "sms_status": a.sms_status, "error": a.sms_error, "retry_count": a.sms_retry_count or 0,
            "segments": a.sms_segments, "to_number": a.to_number, "from_number": a.from_number,
            "timestamp": a.created_at, "agent_id": str(uid) if uid else None, "agent_name": names.get(uid),
            "lead_id": str(a.lead_id) if a.lead_id else None,
            "contact_id": str(a.contact_id) if a.contact_id else None,
            "company_id": str(a.company_id) if a.company_id else None,
        }

    async def reports(self, actor: User, date_from=None, date_to=None) -> dict:
        q = select(Activity).filter(
            Activity.organization_id == actor.organization_id, Activity.is_deleted == False,
            Activity.activity_type == "SMS")
        q = self._scope(q, actor)
        if date_from is not None:
            q = q.filter(Activity.created_at >= date_from)
        if date_to is not None:
            q = q.filter(Activity.created_at <= date_to)
        acts = list((await self.db.execute(q)).scalars().all())

        by_status: dict = {}
        by_direction: dict = {}
        by_day: dict = {}
        outbound = 0
        delivered = 0
        failed = 0
        segments = 0
        for a in acts:
            st = a.sms_status or "unknown"
            by_status[st] = by_status.get(st, 0) + 1
            d = a.call_direction or "OUTBOUND"
            by_direction[d] = by_direction.get(d, 0) + 1
            by_day[a.created_at.date().isoformat()] = by_day.get(a.created_at.date().isoformat(), 0) + 1
            segments += a.sms_segments or 1
            if d == "OUTBOUND":
                outbound += 1
                if st in DELIVERED_STATUSES:
                    delivered += 1
                elif st in FAILED_STATUSES or st == "failed":
                    failed += 1
        return {
            "total": len(acts),
            "outbound": outbound,
            "inbound": by_direction.get("INBOUND", 0),
            "delivered": delivered,
            "failed": failed,
            "segments": segments,
            "delivery_rate": round(delivered * 100 / outbound, 1) if outbound else 0.0,
            "by_status": [{"label": k, "count": v} for k, v in sorted(by_status.items(), key=lambda kv: -kv[1])],
            "by_direction": [{"label": k, "count": v} for k, v in by_direction.items()],
            "by_day": [{"label": day, "count": c} for day, c in sorted(by_day.items())],
        }

    async def _names(self, ids) -> dict:
        ids = {i for i in ids if i}
        if not ids:
            return {}
        res = await self.db.execute(select(User.id, User.first_name, User.last_name, User.email).filter(User.id.in_(ids)))
        return {uid: (f"{fn or ''} {ln or ''}".strip() or em) for uid, fn, ln, em in res.all()}
