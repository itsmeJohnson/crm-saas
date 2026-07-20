import uuid
from datetime import datetime, timezone
from typing import List, Optional
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from fastapi import HTTPException, status

from app.models.support_ticket import SupportTicket
from app.schemas.support_ticket import SupportTicketCreate, SupportTicketUpdate
from app.services.notification_service import NotificationService

class SupportTicketService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.notification_service = NotificationService(db)

    async def create_ticket(
        self, organization_id: uuid.UUID, user_id: uuid.UUID, actor_name: str, payload: SupportTicketCreate
    ) -> SupportTicket:
        now = datetime.now(timezone.utc)
        initial_history = [{
            "status": "Open",
            "by": actor_name,
            "timestamp": now.isoformat()
        }]
        
        ticket = SupportTicket(
            organization_id=organization_id,
            created_by_id=user_id,
            subject=payload.subject,
            priority=payload.priority,
            description=payload.description,
            attachments=payload.attachments or [],
            status="Open",
            comments=[],
            history=initial_history,
            created_at=now,
            updated_at=now
        )
        self.db.add(ticket)
        await self.db.commit()
        await self.db.refresh(ticket)
        return ticket

    async def list_tickets(self, organization_id: uuid.UUID) -> List[SupportTicket]:
        stmt = select(SupportTicket).where(
            SupportTicket.organization_id == organization_id,
            SupportTicket.is_deleted == False
        ).order_by(SupportTicket.created_at.desc())
        
        res = await self.db.execute(stmt)
        return list(res.scalars().all())

    async def get_ticket(self, organization_id: uuid.UUID, ticket_id: uuid.UUID) -> SupportTicket:
        stmt = select(SupportTicket).where(
            SupportTicket.id == ticket_id,
            SupportTicket.organization_id == organization_id,
            SupportTicket.is_deleted == False
        )
        res = await self.db.execute(stmt)
        ticket = res.scalar_one_or_none()
        if not ticket:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Support ticket not found."
            )
        return ticket

    async def add_comment(
        self, organization_id: uuid.UUID, ticket_id: uuid.UUID, actor_user_id: uuid.UUID, actor_name: str, content: str
    ) -> SupportTicket:
        ticket = await self.get_ticket(organization_id, ticket_id)
        now = datetime.now(timezone.utc)

        # In SQLAlchemy, modifying a mutable JSON directly might not trigger the dirty flag.
        # We make a copy and assign it back to trigger updates.
        comments = list(ticket.comments or [])
        comments.append({
            "author": actor_name,
            "content": content,
            "timestamp": now.isoformat()
        })
        ticket.comments = comments
        ticket.updated_at = now

        # Notify the ticket creator and (if different) the assignee — skip whichever
        # of the two is the person who just commented, so nobody is notified of their own comment.
        notify_user_ids = {ticket.created_by_id, ticket.assigned_to_id} - {actor_user_id, None}
        for recipient_id in notify_user_ids:
            await self.notification_service.create_notification(
                organization_id=organization_id,
                user_id=recipient_id,
                category="support",
                title=f"New reply on ticket {ticket.ticket_number}",
                body=f"{actor_name} commented: {content[:140]}",
                link_url=f"/portal/support/{ticket.id}",
                action_metadata={"ticket_id": str(ticket.id)},
            )

        await self.db.commit()
        await self.db.refresh(ticket)
        return ticket

    async def update_ticket(
        self, organization_id: uuid.UUID, ticket_id: uuid.UUID, actor_name: str, payload: SupportTicketUpdate
    ) -> SupportTicket:
        ticket = await self.get_ticket(organization_id, ticket_id)
        now = datetime.now(timezone.utc)
        
        updated = False
        if payload.status and payload.status != ticket.status:
            history = list(ticket.history or [])
            history.append({
                "status": payload.status,
                "by": actor_name,
                "timestamp": now.isoformat()
            })
            ticket.history = history
            ticket.status = payload.status
            updated = True
            
        if payload.priority and payload.priority != ticket.priority:
            ticket.priority = payload.priority
            updated = True
            
        if payload.resolution is not None and payload.resolution != ticket.resolution:
            ticket.resolution = payload.resolution
            updated = True
            
        if updated:
            ticket.updated_at = now
            await self.db.commit()
            await self.db.refresh(ticket)
            
        return ticket
