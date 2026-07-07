import uuid
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.escalation_config import EscalationConfig


class EscalationService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_or_create_config(self, organization_id: uuid.UUID) -> EscalationConfig:
        res = await self.db.execute(
            select(EscalationConfig).filter(EscalationConfig.organization_id == organization_id)
        )
        config = res.scalars().first()
        if not config:
            config = EscalationConfig(organization_id=organization_id, is_active=False, idle_days=3)
            self.db.add(config)
            await self.db.flush()
            await self.db.refresh(config)
        return config

    async def update_config(self, organization_id: uuid.UUID, data: dict) -> EscalationConfig:
        config = await self.get_or_create_config(organization_id)
        for key, val in data.items():
            setattr(config, key, val)
        self.db.add(config)
        await self.db.flush()
        await self.db.refresh(config)
        return config
