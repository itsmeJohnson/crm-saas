from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from fastapi import HTTPException

from app.models.currency import Currency
from app.schemas.currency import CurrencyCreate, CurrencyUpdate


class CurrencyService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_all(self) -> list[Currency]:
        res = await self.db.execute(
            select(Currency).where(Currency.is_active == True).order_by(Currency.code)
        )
        return res.scalars().all()

    async def get(self, code: str) -> Currency:
        currency = await self.db.get(Currency, code.upper())
        if not currency or not currency.is_active:
            raise HTTPException(status_code=404, detail=f"Currency '{code}' not found")
        return currency

    async def create(self, payload: CurrencyCreate) -> Currency:
        existing = await self.db.get(Currency, payload.code.upper())
        if existing:
            raise HTTPException(status_code=409, detail="Currency already exists")
        if payload.is_base:
            # Unset any existing base currency
            await self.db.execute(
                Currency.__table__.update().values(is_base=False)
            )
        currency = Currency(**payload.model_dump(), code=payload.code.upper())
        self.db.add(currency)
        await self.db.commit()
        await self.db.refresh(currency)
        return currency

    async def update(self, code: str, payload: CurrencyUpdate) -> Currency:
        currency = await self.get(code)
        if payload.is_base:
            await self.db.execute(
                Currency.__table__.update().values(is_base=False)
            )
        for k, v in payload.model_dump(exclude_unset=True).items():
            setattr(currency, k, v)
        from datetime import datetime, timezone
        currency.last_updated = datetime.now(timezone.utc)
        await self.db.commit()
        await self.db.refresh(currency)
        return currency

    async def delete(self, code: str) -> None:
        currency = await self.get(code)
        if currency.is_base:
            raise HTTPException(status_code=400, detail="Cannot delete the base currency")
        currency.is_active = False
        await self.db.commit()

    async def convert(self, amount: float, from_code: str, to_code: str) -> float:
        """Convert amount between currencies using exchange rates relative to base."""
        if from_code.upper() == to_code.upper():
            return amount
        from_curr = await self.get(from_code)
        to_curr = await self.get(to_code)
        # Convert to base first, then to target
        # exchange_rate represents: 1 base = exchange_rate of this currency
        # So to get base amount: amount / from_curr.exchange_rate
        # Then to get target: base_amount * to_curr.exchange_rate
        base_amount = amount / float(from_curr.exchange_rate)
        converted = base_amount * float(to_curr.exchange_rate)
        return round(converted, 2)
