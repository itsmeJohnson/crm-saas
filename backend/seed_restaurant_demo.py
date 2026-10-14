"""Polished restaurant demo seed — a realistic, presentation-ready dataset.

Creates a branded venue, several offers, a full table set, and ~12 guests with
vouchers in mixed states (redeemed / active / expired), a couple of opt-outs, and
current-month birthdays — so the owner dashboard looks alive for prospects.

    python3.12 seed_restaurant_demo.py

Works on SQLite (dev) or Postgres (prod) via SQLALCHEMY_DATABASE_URI.
Creates a fresh demo org each run and prints all the URLs + logins.
"""
import os, asyncio, uuid, secrets, random
from datetime import datetime, timezone, timedelta, date

os.environ.setdefault("SQLALCHEMY_DATABASE_URI", "sqlite+aiosqlite:///./local_dev.db")
os.environ.setdefault("JWT_SECRET_KEY", "dev_secret_key_1234567890_johnson_softwares_local")
os.environ.setdefault("TELEPHONY_ENCRYPTION_KEY", "YqUFhZmtAsiakLSb4rG4VTC5qW4UhTW92BzC1B4VGsk=")
os.environ.setdefault("ENVIRONMENT", "development")

from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from app.models.base import Base
import app.models  # noqa: F401
from app.models.restaurant import RestaurantGuest, RestaurantVoucher
from app.repositories.organization import OrganizationRepository
from app.repositories.user_repository import UserRepository
from app.core.security import get_password_hash
from app.services.restaurant_service import RestaurantService

NOW = datetime.now(timezone.utc)
MONTH = NOW.month
_ALPHA = "23456789ABCDEFGHJKMNPQRSTUVWXYZ"


def code(prefix="SMOKE"):
    return f"{prefix}-{''.join(secrets.choice(_ALPHA) for _ in range(8))}"


# (name, phone10, dob 'YYYY-MM-DD', visits, status, voucher_state)
# a few DOBs are set to the current month so "birthdays this month" > 0.
def _dob(m_day):  # helper: build a DOB in the CURRENT month for birthday demo
    return date(1993, MONTH, m_day)


GUESTS = [
    ("Vikram Malhotra", "9880194821", date(1991, 9, 18), 3, "active", "redeemed", "T-04", "Rahul (Server)"),
    ("Ananya Iyer",     "9845012399", _dob(24),          1, "active", "active",   "T-08", None),
    ("Rohan Nambiar",   "9900234188", date(1988, 10, 4), 2, "active", "active",   "T-12", None),
    ("Pooja Reddy",     "9740981122", date(1996, 3, 12), 1, "opted_out", "redeemed", "T-02", "Priya (Captain)"),
    ("Karan Johar",     "9887766554", _dob(9),           4, "active", "redeemed", "T-02", "Rahul (Server)"),
    ("Meera Nair",      "9812345678", _dob(28),          2, "active", "active",   "Rooftop 1", None),
    ("Arjun Kapoor",    "9823456712", date(1985, 11, 15),1, "active", "expired",  "T-06", None),
    ("Sneha Rao",       "9834567890", date(1998, 1, 5),  1, "active", "active",   "Bar", None),
    ("Aditya Sharma",   "9845678901", date(1992, 7, 21), 5, "active", "redeemed", "T-01", "Priya (Captain)"),
    ("Divya Menon",     "9856789012", _dob(3),           1, "active", "active",   "T-09", None),
    ("Rahul Verma",     "9867890123", date(1989, 12, 30),2, "opted_out", "redeemed", "T-03", "Rahul (Server)"),
    ("Nisha Pillai",    "9878901234", date(1997, 6, 18), 1, "active", "expired",  "Rooftop 2", None),
]

CONSENT = ("I agree to receive exclusive dining vouchers, birthday treats and offers "
           "from The Smoke Co. on WhatsApp. I can reply STOP anytime to opt out.")


async def main():
    engine = create_async_engine(os.environ["SQLALCHEMY_DATABASE_URI"], echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    Session = async_sessionmaker(bind=engine, class_=AsyncSession, expire_on_commit=False)
    async with Session() as db:
        sfx = uuid.uuid4().hex[:6]
        org = await OrganizationRepository(db).create({"name": "The Smoke Co.", "slug": f"smoke-demo-{sfx}"})
        await db.commit()
        owner = await UserRepository(db).create_user(org.id, {
            "email": f"owner-{sfx}@smokeco.in", "hashed_password": get_password_hash("pw12345678"),
            "first_name": "Aarav", "last_name": "Kapoor", "role": "OrgAdmin", "is_active": True})
        staff = await UserRepository(db).create_user(org.id, {
            "email": f"floor-{sfx}@smokeco.in", "hashed_password": get_password_hash("pw12345678"),
            "first_name": "Rahul", "last_name": "Server", "role": "Employee", "is_active": True})
        await db.commit()

        svc = RestaurantService(db)
        venue = await svc.create_venue(owner, {
            "name": "The Smoke Co.", "slug": f"the-smoke-co-{sfx}", "brand_color": "#D97706",
            "consent_text": CONSENT})

        bruschetta = await svc.create_offer(owner, {
            "venue_id": venue.id, "title": "Complimentary Chef's Bruschetta",
            "description": "A warm welcome from our kitchen — on the house.",
            "terms": "Dine-in only · Min. order ₹800 · One per guest", "voucher_validity_days": 30})
        await svc.create_offer(owner, {
            "venue_id": venue.id, "title": "Free Welcome Mocktail",
            "description": "A refreshing house mocktail to start your evening.",
            "terms": "Dine-in only · One per guest", "voucher_validity_days": 30})
        await svc.create_offer(owner, {
            "venue_id": venue.id, "title": "Birthday Dessert Platter",
            "description": "Celebrate with a complimentary dessert platter.",
            "terms": "Valid in your birthday month · One per guest", "voucher_validity_days": 45})

        # tables: T-01..T-12 + named zones
        await svc.bulk_create_tables(owner, {"venue_id": venue.id, "prefix": "T-", "start": 1, "count": 12})
        for label in ("Rooftop 1", "Rooftop 2", "Bar"):
            await svc.create_table(owner, {"venue_id": venue.id, "label": label})
        tables = await svc.list_tables(owner, venue.id)
        for t in tables:  # sprinkle some scan activity
            t.scan_count = random.randint(2, 40)
        await db.commit()

        # guests + vouchers (direct ORM for full control of statuses/timestamps)
        issued = redeemed = 0
        for (name, phone, dob, visits, gstatus, vstate, table_label, redeemer) in GUESTS:
            g = RestaurantGuest(
                organization_id=org.id, venue_id=venue.id, name=name, phone=f"91{phone}",
                email=f"{name.split(' ')[0].lower()}@example.com", dob=dob,
                marketing_consent=True, consent_text=CONSENT, consent_ip="106.51.72.19",
                consent_at=NOW - timedelta(days=random.randint(1, 40)),
                status=gstatus, opted_out_at=(NOW - timedelta(days=3)) if gstatus == "opted_out" else None,
                visit_count=visits, last_visit_at=NOW - timedelta(days=random.randint(0, 20)),
                last_table_label=table_label, rating=random.choice([None, 4, 5, 5]))
            db.add(g)
            await db.flush()

            v = RestaurantVoucher(
                organization_id=org.id, venue_id=venue.id, offer_id=bruschetta.id, guest_id=g.id,
                code=code(), offer_title=bruschetta.title, issued_table_label=table_label,
                delivery_status="sent", status="active",
                expires_at=NOW + timedelta(days=25))
            if vstate == "redeemed":
                v.status = "redeemed"
                v.redeemed_at = NOW - timedelta(days=random.randint(0, 12))
                v.redeemed_by_user_id = staff.id
                v.redeemed_table_label = table_label
                redeemed += 1
            elif vstate == "expired":
                v.status = "expired"
                v.expires_at = NOW - timedelta(days=random.randint(1, 10))
            db.add(v)
            issued += 1

        bruschetta.issued_count = issued
        bruschetta.redeemed_count = redeemed
        await db.commit()

        first_table = next((t for t in tables if t.label == "T-04"), tables[0])
        active_v = (await svc.list_vouchers(owner, status_filter="active"))[0]

        base = os.environ.get("DEMO_BASE_URL", "http://localhost:5173")
        print("\n==================== RESTAURANT DEMO SEEDED ====================")
        print(f"Owner login : {owner.email} / pw12345678   (OrgAdmin)")
        print(f"Staff login : {staff.email} / pw12345678   (Employee)")
        print(f"Guests: {len(GUESTS)}  ·  Vouchers issued: {issued}  ·  redeemed: {redeemed}  ·  redemption {round(redeemed/issued*100)}%")
        print("-" * 63)
        print(f"GUEST scan  : {base}/r/{venue.slug}/t/{first_table.token}   (table {first_table.label})")
        print(f"STAFF app   : {base}/staff/redeem   (try active code {active_v.code})")
        print(f"OWNER admin : {base}/restaurant/manage")
        print("===============================================================\n")

asyncio.run(main())
