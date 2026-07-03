import uuid
from typing import Sequence
from datetime import datetime, timezone
from sqlalchemy import select, func, update, or_
from sqlalchemy.ext.asyncio import AsyncSession
from fastapi import HTTPException, status

from app.models.notification import Notification, NotificationPreference, PushSubscription
from app.models.user import User

# Canonical categories surfaced in the Notification Center / preferences UI.
CATEGORIES = [
    "lead", "task", "calendar", "contact", "customer", "calling", "sms", "whatsapp",
    "email", "campaign", "billing", "invoice", "payment", "support", "system",
]
PRIORITIES = ("low", "normal", "high", "urgent")
CHANNELS = ("in_app", "email", "sms", "whatsapp", "push")


class NotificationService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def create_notification(
        self,
        organization_id: uuid.UUID,
        user_id: uuid.UUID,
        category: str,
        title: str,
        body: str,
        link_url: str | None = None,
        action_metadata: dict | None = None,
        priority: str = "normal",
        actions: list | None = None,
        channels_sent: list | None = None,
    ) -> Notification:
        """Creates an in-app notification for a single user. Callers treat this as
        fire-and-forget alongside their audit_service.log_event() call. Backward
        compatible: priority/actions/channels_sent are optional."""
        notification = Notification(
            organization_id=organization_id,
            user_id=user_id,
            category=category,
            title=title,
            body=body,
            link_url=link_url,
            action_metadata=action_metadata,
            priority=priority if priority in PRIORITIES else "normal",
            actions=actions,
            channels_sent=channels_sent or ["in_app"],
        )
        self.db.add(notification)
        await self.db.flush()
        return notification

    # ---------- Multi-channel dispatch ----------
    async def dispatch(
        self,
        organization_id: uuid.UUID,
        user_id: uuid.UUID,
        category: str,
        title: str,
        body: str,
        link_url: str | None = None,
        action_metadata: dict | None = None,
        priority: str = "normal",
        actions: list | None = None,
        fanout: bool = True,
    ) -> Notification | None:
        """Create the in-app notification (if the user allows it for this category)
        and best-effort fan out to email/SMS/WhatsApp/push per the user's prefs."""
        prefs = await self._effective_prefs(user_id, category)
        channels: list[str] = []

        if prefs["in_app"]:
            channels.append("in_app")

        if fanout:
            user = await self.db.get(User, user_id)
            if user:
                if prefs["email"] and user.email and await self._send_email(user, title, body):
                    channels.append("email")
                if prefs["sms"] and getattr(user, "phone", None) and await self._send_sms(user, title, body):
                    channels.append("sms")
                if prefs["whatsapp"] and getattr(user, "phone", None) and await self._send_whatsapp(user, title, body):
                    channels.append("whatsapp")
                if prefs["push"] and await self._send_push(organization_id, user_id, title, body, link_url):
                    channels.append("push")

        # Always persist a record for history; if in-app is muted for this category,
        # keep it out of the bell/unread by recording it pre-dismissed.
        notif = await self.create_notification(
            organization_id, user_id, category, title, body, link_url, action_metadata,
            priority=priority, actions=actions, channels_sent=channels or ["(none)"])
        if "in_app" not in channels:
            notif.is_dismissed = True
            notif.dismissed_at = datetime.now(timezone.utc)
            self.db.add(notif)
            await self.db.flush()
        return notif

    async def _send_email(self, user: User, title: str, body: str) -> bool:
        try:
            from app.services.email_service import send_email
            send_email(user.email, title, "generic_message", {"body": body})
            return True
        except Exception:
            return False

    async def _send_sms(self, user: User, title: str, body: str) -> bool:
        try:
            from app.services.sms_service import SmsService
            await SmsService(self.db).send(user, {"body": f"{title}: {body}", "to_number": user.phone}, _skip_cap=True)
            return True
        except Exception:
            return False

    async def _send_whatsapp(self, user: User, title: str, body: str) -> bool:
        try:
            from app.services.whatsapp_service import WhatsAppService
            await WhatsAppService(self.db).send_template(user, {"template_name": "notification",
                                                               "to_number": user.phone, "body": f"{title}: {body}"})
            return True
        except Exception:
            return False

    async def _send_push(self, org_id, user_id, title, body, url) -> bool:
        subs = list((await self.db.execute(select(PushSubscription).filter(
            PushSubscription.user_id == user_id, PushSubscription.is_deleted == False))).scalars().all())
        if not subs:
            return False
        from app.services.push_provider import get_push_sender
        sender = get_push_sender()
        ok = False
        for s in subs:
            if sender.send(subscription={"endpoint": s.endpoint, "p256dh": s.p256dh, "auth": s.auth},
                           title=title, body=body, url=url):
                ok = True
        return ok

    # ---------- Preferences ----------
    async def _effective_prefs(self, user_id: uuid.UUID, category: str) -> dict:
        row = (await self.db.execute(select(NotificationPreference).filter(
            NotificationPreference.user_id == user_id, NotificationPreference.category == category,
            NotificationPreference.is_deleted == False))).scalars().first()
        if row:
            return {"in_app": row.in_app, "email": row.email, "sms": row.sms, "whatsapp": row.whatsapp, "push": row.push}
        return {"in_app": True, "email": False, "sms": False, "whatsapp": False, "push": False}

    async def get_preferences(self, actor: User) -> list[dict]:
        rows = {r.category: r for r in (await self.db.execute(select(NotificationPreference).filter(
            NotificationPreference.user_id == actor.id, NotificationPreference.is_deleted == False))).scalars().all()}
        out = []
        for cat in CATEGORIES:
            r = rows.get(cat)
            out.append({"category": cat,
                        "in_app": r.in_app if r else True, "email": r.email if r else False,
                        "sms": r.sms if r else False, "whatsapp": r.whatsapp if r else False,
                        "push": r.push if r else False})
        return out

    async def update_preferences(self, actor: User, items: list[dict]) -> list[dict]:
        for item in items:
            cat = item.get("category")
            if cat not in CATEGORIES:
                continue
            row = (await self.db.execute(select(NotificationPreference).filter(
                NotificationPreference.user_id == actor.id, NotificationPreference.category == cat,
                NotificationPreference.is_deleted == False))).scalars().first()
            if not row:
                row = NotificationPreference(organization_id=actor.organization_id, user_id=actor.id, category=cat)
                self.db.add(row)
            for ch in CHANNELS:
                if ch in item and item[ch] is not None:
                    setattr(row, ch, bool(item[ch]))
        await self.db.flush()
        return await self.get_preferences(actor)

    # ---------- Push subscriptions ----------
    async def register_push(self, actor: User, data: dict) -> PushSubscription:
        endpoint = data["endpoint"]
        existing = (await self.db.execute(select(PushSubscription).filter(
            PushSubscription.user_id == actor.id, PushSubscription.endpoint == endpoint))).scalars().first()
        if existing:
            existing.p256dh = data.get("p256dh")
            existing.auth = data.get("auth")
            existing.user_agent = data.get("user_agent")
            existing.is_deleted = False
            self.db.add(existing)
            await self.db.flush()
            return existing
        sub = PushSubscription(organization_id=actor.organization_id, user_id=actor.id, endpoint=endpoint,
                               p256dh=data.get("p256dh"), auth=data.get("auth"), user_agent=data.get("user_agent"))
        self.db.add(sub)
        await self.db.flush()
        await self.db.refresh(sub)
        return sub

    async def unregister_push(self, actor: User, endpoint: str) -> None:
        sub = (await self.db.execute(select(PushSubscription).filter(
            PushSubscription.user_id == actor.id, PushSubscription.endpoint == endpoint))).scalars().first()
        if sub:
            sub.is_deleted = True
            self.db.add(sub)
            await self.db.flush()

    # ---------- Queries ----------
    async def paginate_for_user(
        self, organization_id, user_id, skip=0, limit=20, unread_only=False,
        category=None, priority=None, include_dismissed=False,
    ) -> tuple[Sequence[Notification], int]:
        filters = [
            Notification.organization_id == organization_id,
            Notification.user_id == user_id,
            Notification.is_deleted == False,
        ]
        if unread_only:
            filters.append(Notification.is_read == False)
        if not include_dismissed:
            filters.append(Notification.is_dismissed == False)
        if category:
            filters.append(Notification.category == category)
        if priority:
            filters.append(Notification.priority == priority)

        total = (await self.db.execute(select(func.count(Notification.id)).where(*filters))).scalar() or 0
        stmt = (select(Notification).where(*filters)
                .order_by(Notification.created_at.desc()).offset(skip).limit(limit))
        res = await self.db.execute(stmt)
        return list(res.scalars().all()), total

    async def get_unread_count(self, organization_id, user_id) -> int:
        return (await self.db.execute(select(func.count(Notification.id)).where(
            Notification.organization_id == organization_id, Notification.user_id == user_id,
            Notification.is_read == False, Notification.is_dismissed == False,
            Notification.is_deleted == False))).scalar() or 0

    async def unread_by_category(self, organization_id, user_id) -> list[dict]:
        rows = (await self.db.execute(select(Notification.category, func.count(Notification.id)).where(
            Notification.organization_id == organization_id, Notification.user_id == user_id,
            Notification.is_read == False, Notification.is_dismissed == False,
            Notification.is_deleted == False).group_by(Notification.category))).all()
        return [{"category": c, "count": n} for c, n in rows]

    async def mark_read(self, organization_id, user_id, notification_id) -> Notification:
        n = (await self.db.execute(select(Notification).where(
            Notification.id == notification_id, Notification.organization_id == organization_id,
            Notification.user_id == user_id, Notification.is_deleted == False))).scalar_one_or_none()
        if not n:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Notification not found.")
        if not n.is_read:
            n.is_read = True
            n.read_at = datetime.now(timezone.utc)
            await self.db.commit()
            await self.db.refresh(n)
        return n

    async def mark_all_read(self, organization_id, user_id) -> int:
        result = await self.db.execute(update(Notification).where(
            Notification.organization_id == organization_id, Notification.user_id == user_id,
            Notification.is_read == False, Notification.is_deleted == False)
            .values(is_read=True, read_at=datetime.now(timezone.utc)))
        await self.db.commit()
        return result.rowcount or 0

    async def bulk_read(self, organization_id, user_id, ids=None, category=None) -> int:
        filters = [Notification.organization_id == organization_id, Notification.user_id == user_id,
                   Notification.is_read == False, Notification.is_deleted == False]
        if ids:
            filters.append(Notification.id.in_(ids))
        if category:
            filters.append(Notification.category == category)
        if not ids and not category:
            return 0
        result = await self.db.execute(update(Notification).where(*filters)
                                       .values(is_read=True, read_at=datetime.now(timezone.utc)))
        await self.db.commit()
        return result.rowcount or 0

    async def dismiss(self, organization_id, user_id, notification_id) -> Notification:
        n = (await self.db.execute(select(Notification).where(
            Notification.id == notification_id, Notification.organization_id == organization_id,
            Notification.user_id == user_id, Notification.is_deleted == False))).scalar_one_or_none()
        if not n:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Notification not found.")
        n.is_dismissed = True
        n.dismissed_at = datetime.now(timezone.utc)
        if not n.is_read:
            n.is_read = True
            n.read_at = datetime.now(timezone.utc)
        await self.db.commit()
        await self.db.refresh(n)
        return n

    async def stats(self, organization_id, user_id) -> dict:
        base = [Notification.organization_id == organization_id, Notification.user_id == user_id,
                Notification.is_deleted == False]
        total = (await self.db.execute(select(func.count(Notification.id)).where(*base))).scalar() or 0
        unread = (await self.db.execute(select(func.count(Notification.id)).where(
            *base, Notification.is_read == False))).scalar() or 0
        by_cat = (await self.db.execute(select(Notification.category, func.count(Notification.id)).where(*base)
                                        .group_by(Notification.category))).all()
        by_pri = (await self.db.execute(select(Notification.priority, func.count(Notification.id)).where(*base)
                                        .group_by(Notification.priority))).all()
        read_rate = round((total - unread) * 100 / total, 1) if total else 0.0
        return {
            "total": total, "unread": unread, "read": total - unread, "read_rate": read_rate,
            "by_category": [{"label": c, "count": n} for c, n in sorted(by_cat, key=lambda x: -x[1])],
            "by_priority": [{"label": p, "count": n} for p, n in sorted(by_pri, key=lambda x: -x[1])],
        }

    # ---------- Broadcast (admin) ----------
    async def broadcast(self, actor: User, data: dict) -> dict:
        if actor.role not in ("SuperAdmin", "OrgAdmin", "Manager"):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only a Manager or OrgAdmin can broadcast notifications.")
        target_role = data.get("role")
        q = select(User).filter(User.organization_id == actor.organization_id, User.is_active == True,
                                User.is_deleted == False)
        if target_role:
            q = q.filter(User.role == target_role)
        users = list((await self.db.execute(q)).scalars().all())
        sent = 0
        for u in users:
            n = await self.dispatch(
                organization_id=actor.organization_id, user_id=u.id, category=data.get("category", "system"),
                title=data["title"], body=data["body"], link_url=data.get("link_url"),
                priority=data.get("priority", "normal"), actions=data.get("actions"),
                fanout=data.get("fanout", False))
            if n:
                sent += 1
        await self.db.flush()
        return {"recipients": len(users), "sent": sent}
