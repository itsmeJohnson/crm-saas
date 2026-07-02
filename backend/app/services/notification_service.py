import uuid
from typing import Sequence
from datetime import datetime, timezone
from sqlalchemy import select, func, update
from sqlalchemy.ext.asyncio import AsyncSession
from fastapi import HTTPException, status

from app.models.notification import Notification

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
    ) -> Notification:
        """Creates an in-app notification for a single user. Callers should treat
        this as fire-and-forget alongside their existing audit_service.log_event()
        call — a failure here should never block the primary action it's attached to."""
        notification = Notification(
            organization_id=organization_id,
            user_id=user_id,
            category=category,
            title=title,
            body=body,
            link_url=link_url,
            action_metadata=action_metadata,
        )
        self.db.add(notification)
        await self.db.flush()
        return notification

    async def paginate_for_user(
        self,
        organization_id: uuid.UUID,
        user_id: uuid.UUID,
        skip: int = 0,
        limit: int = 20,
        unread_only: bool = False,
    ) -> tuple[Sequence[Notification], int]:
        filters = [
            Notification.organization_id == organization_id,
            Notification.user_id == user_id,
            Notification.is_deleted == False,
        ]
        if unread_only:
            filters.append(Notification.is_read == False)

        count_stmt = select(func.count(Notification.id)).where(*filters)
        total = (await self.db.execute(count_stmt)).scalar() or 0

        stmt = (
            select(Notification)
            .where(*filters)
            .order_by(Notification.created_at.desc())
            .offset(skip)
            .limit(limit)
        )
        res = await self.db.execute(stmt)
        return list(res.scalars().all()), total

    async def get_unread_count(self, organization_id: uuid.UUID, user_id: uuid.UUID) -> int:
        stmt = select(func.count(Notification.id)).where(
            Notification.organization_id == organization_id,
            Notification.user_id == user_id,
            Notification.is_read == False,
            Notification.is_deleted == False,
        )
        return (await self.db.execute(stmt)).scalar() or 0

    async def mark_read(self, organization_id: uuid.UUID, user_id: uuid.UUID, notification_id: uuid.UUID) -> Notification:
        stmt = select(Notification).where(
            Notification.id == notification_id,
            Notification.organization_id == organization_id,
            Notification.user_id == user_id,
            Notification.is_deleted == False,
        )
        res = await self.db.execute(stmt)
        notification = res.scalar_one_or_none()
        if not notification:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Notification not found.")
        if not notification.is_read:
            notification.is_read = True
            notification.read_at = datetime.now(timezone.utc)
            await self.db.commit()
            await self.db.refresh(notification)
        return notification

    async def mark_all_read(self, organization_id: uuid.UUID, user_id: uuid.UUID) -> int:
        stmt = (
            update(Notification)
            .where(
                Notification.organization_id == organization_id,
                Notification.user_id == user_id,
                Notification.is_read == False,
                Notification.is_deleted == False,
            )
            .values(is_read=True, read_at=datetime.now(timezone.utc))
        )
        result = await self.db.execute(stmt)
        await self.db.commit()
        return result.rowcount or 0
