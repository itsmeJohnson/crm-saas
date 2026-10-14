"""Connect a real WhatsApp Cloud API number to a restaurant venue (go-live).

Creates/updates the tenant's WhatsAppSettings (credentials encrypted at rest) and
links it to the venue, so voucher & campaign sends switch from 'simulated' to real
WhatsApp delivery via the outbox worker.

Prereqs: TELEPHONY_ENCRYPTION_KEY and the DB env must be set (same as the backend).

Example:
    TELEPHONY_ENCRYPTION_KEY=... SQLALCHEMY_DATABASE_URI=postgresql+asyncpg://... \\
    python3.12 connect_whatsapp.py \\
      --venue-slug the-smoke-co-abc123 \\
      --phone-number-id 123456789012345 \\
      --business-account-id 987654321098765 \\
      --access-token "EAAG...long-permanent-token..." \\
      --verify-token "smoke-webhook-verify-8f2a" \\
      --app-secret "meta-app-secret-here" \\
      --sender-number "+919880893416"

Then set the Meta webhook callback URL to:
    https://<FRONTEND_URL host>/api/v1/whatsapp/webhook
with Verify Token = the --verify-token you used, and subscribe to the
'messages' field. See RESTAURANT_DEPLOYMENT.md.
"""
import os, asyncio, argparse

from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy import select
import app.models  # noqa: F401
from app.models.restaurant import RestaurantVenue
from app.models.whatsapp import WhatsAppSettings
from app.core.crypto import encrypt


async def run(a):
    engine = create_async_engine(os.environ["SQLALCHEMY_DATABASE_URI"], echo=False)
    Session = async_sessionmaker(bind=engine, class_=AsyncSession, expire_on_commit=False)
    async with Session() as db:
        venue = (await db.execute(select(RestaurantVenue).filter(
            RestaurantVenue.slug == a.venue_slug, RestaurantVenue.is_deleted == False))).scalars().first()
        if not venue:
            raise SystemExit(f"Venue slug '{a.venue_slug}' not found.")
        org_id = venue.organization_id

        s = (await db.execute(select(WhatsAppSettings).filter(
            WhatsAppSettings.organization_id == org_id,
            WhatsAppSettings.phone_number_id == a.phone_number_id,
            WhatsAppSettings.is_deleted == False))).scalars().first()
        if s is None:
            s = WhatsAppSettings(organization_id=org_id, phone_number_id=a.phone_number_id)
            db.add(s)

        s.provider = "meta"
        s.friendly_name = a.friendly_name or venue.name
        s.business_account_id = a.business_account_id
        s.access_token = encrypt(a.access_token)          # encrypted at rest
        s.sender_number = a.sender_number
        s.webhook_verify_token = a.verify_token           # matched on GET verify (plaintext)
        s.webhook_secret_enc = encrypt(a.app_secret)      # HMAC signature validation (encrypted)
        s.api_version = a.api_version
        s.is_active = True
        s.is_default = True
        s.health_status = "connected"
        await db.flush()

        venue.whatsapp_settings_id = s.id
        await db.commit()

        cb = f"{os.environ.get('FRONTEND_URL', 'https://<your-domain>')}/api/v1/whatsapp/webhook"
        print("\n==================== WHATSAPP CONNECTED ====================")
        print(f"Venue        : {venue.name} ({venue.slug})")
        print(f"Phone No. ID : {s.phone_number_id}")
        print(f"WABA ID      : {s.business_account_id}")
        print(f"Status       : {s.health_status} · default={s.is_default}")
        print("-" * 58)
        print("Set the Meta webhook in App Dashboard → WhatsApp → Configuration:")
        print(f"  Callback URL : {cb}")
        print(f"  Verify Token : {a.verify_token}")
        print("  Subscribe to : messages")
        print("Vouchers & campaigns will now send for real (channel='whatsapp').")
        print("===========================================================\n")


def main():
    p = argparse.ArgumentParser(description="Connect a WhatsApp Cloud API number to a venue.")
    p.add_argument("--venue-slug", required=True)
    p.add_argument("--phone-number-id", required=True)
    p.add_argument("--business-account-id", required=True)
    p.add_argument("--access-token", required=True, help="Meta permanent access token")
    p.add_argument("--verify-token", required=True, help="Webhook verify token you choose")
    p.add_argument("--app-secret", required=True, help="Meta App Secret (for X-Hub-Signature-256)")
    p.add_argument("--sender-number", default=None, help="Display number, e.g. +919880893416")
    p.add_argument("--friendly-name", default=None)
    p.add_argument("--api-version", default="v19.0")
    a = p.parse_args()
    for k in ("SQLALCHEMY_DATABASE_URI", "TELEPHONY_ENCRYPTION_KEY"):
        if not os.environ.get(k):
            raise SystemExit(f"Env {k} must be set (same as the backend).")
    asyncio.run(run(a))


if __name__ == "__main__":
    main()
