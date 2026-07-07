"""Announcement service — a small persistent broadcast board for dashboards.

Managers/OrgAdmins publish audience-targeted announcements; every user sees the
active, unexpired ones addressed to them (their role or 'all'). Distinct from
per-user Notifications.
"""
from __future__ import annotations
import uuid
from datetime import datetime, timezone
from fastapi import HTTPException, status
from sqlalchemy import select, or_
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User
from app.models.announcement import Announcement, ANNOUNCEMENT_AUDIENCES
from app.services.audit_service import AuditService


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _aware(dt):
    if dt is None:
        return None
    return dt.replace(tzinfo=timezone.utc) if dt.tzinfo is None else dt.astimezone(timezone.utc)


class AnnouncementService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.audit = AuditService(db)

    def _is_manager(self, actor: User) -> bool:
        return actor.role in ("SuperAdmin", "OrgAdmin", "Manager")

    def _require_manager(self, actor: User):
        if not self._is_manager(actor):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN,
                                detail="Only a manager or OrgAdmin can manage announcements.")

    async def _get(self, actor: User, announcement_id: uuid.UUID) -> Announcement:
        a = (await self.db.execute(select(Announcement).filter(
            Announcement.id == announcement_id, Announcement.organization_id == actor.organization_id,
            Announcement.is_deleted == False))).scalars().first()
        if not a:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Announcement not found")
        return a

    async def list_for_user(self, actor: User) -> list[dict]:
        """Active, unexpired announcements addressed to this user (their role or all)."""
        now = _now()
        rows = list((await self.db.execute(select(Announcement).filter(
            Announcement.organization_id == actor.organization_id, Announcement.is_deleted == False,
            Announcement.is_active == True,
            Announcement.audience.in_(["all", actor.role]),
            Announcement.published_at <= now,
            or_(Announcement.expires_at.is_(None), Announcement.expires_at >= now))
            .order_by(Announcement.is_pinned.desc(), Announcement.published_at.desc()))).scalars().all())
        return [await self._serialize(a) for a in rows]

    async def list_all(self, actor: User) -> list[dict]:
        """Full list for management (managers/admins)."""
        self._require_manager(actor)
        rows = list((await self.db.execute(select(Announcement).filter(
            Announcement.organization_id == actor.organization_id, Announcement.is_deleted == False)
            .order_by(Announcement.is_pinned.desc(), Announcement.published_at.desc()))).scalars().all())
        return [await self._serialize(a) for a in rows]

    async def create(self, actor: User, data: dict) -> dict:
        self._require_manager(actor)
        audience = data.get("audience", "all")
        if audience not in ANNOUNCEMENT_AUDIENCES:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST,
                                detail=f"audience must be one of {list(ANNOUNCEMENT_AUDIENCES)}")
        a = Announcement(organization_id=actor.organization_id, title=data["title"], body=data["body"],
                         audience=audience, is_pinned=bool(data.get("is_pinned", False)),
                         is_active=bool(data.get("is_active", True)),
                         published_at=_aware(data.get("published_at")) or _now(),
                         expires_at=_aware(data.get("expires_at")), created_by=actor.id)
        self.db.add(a)
        await self.db.flush()
        await self.db.refresh(a)
        await self.audit.log_event(organization_id=actor.organization_id, actor_user_id=actor.id,
                                   action="ANNOUNCEMENT_CREATED", resource_type="announcement", resource_id=str(a.id),
                                   action_metadata={"title": a.title, "audience": audience})
        return await self._serialize(a)

    async def update(self, actor: User, announcement_id: uuid.UUID, data: dict) -> dict:
        self._require_manager(actor)
        a = await self._get(actor, announcement_id)
        if "audience" in data and data["audience"] not in ANNOUNCEMENT_AUDIENCES:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST,
                                detail=f"audience must be one of {list(ANNOUNCEMENT_AUDIENCES)}")
        for f in ("title", "body", "audience", "is_pinned", "is_active"):
            if f in data and data[f] is not None:
                setattr(a, f, data[f])
        if "published_at" in data and data["published_at"] is not None:
            a.published_at = _aware(data["published_at"])
        if "expires_at" in data:
            a.expires_at = _aware(data["expires_at"])
        self.db.add(a)
        await self.db.flush()
        await self.db.refresh(a)
        return await self._serialize(a)

    async def delete(self, actor: User, announcement_id: uuid.UUID) -> None:
        self._require_manager(actor)
        a = await self._get(actor, announcement_id)
        a.is_deleted = True
        self.db.add(a)
        await self.db.flush()

    async def _serialize(self, a: Announcement) -> dict:
        author = (await self.db.execute(select(User.first_name, User.last_name, User.email).filter(
            User.id == a.created_by))).first()
        author_name = None
        if author:
            author_name = f"{author[0] or ''} {author[1] or ''}".strip() or author[2]
        return {"id": str(a.id), "title": a.title, "body": a.body, "audience": a.audience,
                "is_pinned": a.is_pinned, "is_active": a.is_active,
                "published_at": a.published_at.isoformat() if a.published_at else None,
                "expires_at": a.expires_at.isoformat() if a.expires_at else None,
                "author_name": author_name, "created_at": a.created_at}
