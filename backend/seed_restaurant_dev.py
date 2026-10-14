"""Dev-only seed: create an org, an OrgAdmin, and a restaurant venue/offer/table
against the local SQLite dev DB, then print the public guest URL to test.

    python3 seed_restaurant_dev.py
"""
import os, asyncio, uuid
os.environ.setdefault("SQLALCHEMY_DATABASE_URI", "sqlite+aiosqlite:///./local_dev.db")
os.environ.setdefault("JWT_SECRET_KEY", "dev_secret_key_1234567890_johnson_softwares_local")
os.environ.setdefault("TELEPHONY_ENCRYPTION_KEY", "YqUFhZmtAsiakLSb4rG4VTC5qW4UhTW92BzC1B4VGsk=")
os.environ.setdefault("ENVIRONMENT", "development")

from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from app.models.base import Base
import app.models  # noqa: F401  (register all mappers)
from app.repositories.organization import OrganizationRepository
from app.repositories.user_repository import UserRepository
from app.core.security import get_password_hash
from app.services.restaurant_service import RestaurantService


async def main():
    engine = create_async_engine(os.environ["SQLALCHEMY_DATABASE_URI"], echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    Session = async_sessionmaker(bind=engine, class_=AsyncSession, expire_on_commit=False)
    async with Session() as db:
        suffix = uuid.uuid4().hex[:6]
        org = await OrganizationRepository(db).create({"name": "The Smoke Co.", "slug": f"smoke-{suffix}"})
        await db.commit()
        admin = await UserRepository(db).create_user(org.id, {
            "email": f"owner-{suffix}@smokeco.in", "hashed_password": get_password_hash("pw12345678"),
            "first_name": "Owner", "last_name": "Smoke", "role": "OrgAdmin", "is_active": True})
        await db.commit()

        svc = RestaurantService(db)
        venue = await svc.create_venue(admin, {"name": "The Smoke Co.", "slug": f"the-smoke-co-{suffix}",
                                               "brand_color": "#D97706"})
        offer = await svc.create_offer(admin, {
            "venue_id": venue.id, "title": "Complimentary Chef's Bruschetta",
            "description": "A warm welcome from our kitchen — on the house.",
            "terms": "Dine-in only · Min. order ₹800 · One per guest",
            "per_guest_limit": 1, "voucher_validity_days": 30})
        table = await svc.create_table(admin, {"venue_id": venue.id, "label": "T-04"})

        print("\n==================== SEEDED ====================")
        print("Venue slug :", venue.slug)
        print("Table token:", table.token)
        print("Owner login:", admin.email, "/ pw12345678")
        print(f"GUEST URL  : /r/{venue.slug}/t/{table.token}")
        print("===============================================\n")

asyncio.run(main())
