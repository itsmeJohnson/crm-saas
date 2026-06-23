from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.core.config import settings
from app.api.v1.auth import router as auth_router
from app.api.v1.organization import router as org_router
from app.api.v1.users import router as users_router
from app.api.v1.companies import router as companies_router
from app.api.v1.contacts import router as contacts_router
from app.api.v1.leads import router as leads_router
from app.api.v1.activities import router as activities_router
from app.api.v1.notes import router as notes_router
from app.api.v1.dashboard import router as dashboard_router
from app.api.v1.health import router as active_health_router
from app.api.v1.pipelines import router as pipelines_router
from app.api.v1.dialer import router as dialer_router
from app.api.v1.analytics import router as analytics_router
from app.api.v1.super_admin import router as super_admin_router
from app.api.v1.subscription import router as subscription_router
from app.api.v1.telephony import router as telephony_router
from app.models.base import Base
from app.core.database import engine, async_session_maker
import os
import asyncio
import logging
from datetime import datetime, timezone, timedelta
from app.cron.subscription_cron import run_daily_subscription_check

if os.getenv("LOG_JSON", "false").lower() == "true":
    setup_logging()

async def subscription_cron_scheduler():
    logger = logging.getLogger("app.cron")
    logger.info("Subscription cron scheduler loop started.")
    # Run immediately on startup to ensure all states are fresh
    try:
        await run_daily_subscription_check(async_session_maker)
    except Exception as e:
        logger.error("Initial startup subscription check failed: %s", e)

    while True:
        try:
            # Calculate seconds until next midnight
            now = datetime.now(timezone.utc)
            tomorrow = now + timedelta(days=1)
            midnight = datetime(tomorrow.year, tomorrow.month, tomorrow.day, 0, 0, 0, tzinfo=timezone.utc)
            sleep_seconds = (midnight - now).total_seconds()
            logger.info("Subscription cron sleeping for %d seconds until next run at %s", sleep_seconds, midnight)
            await asyncio.sleep(sleep_seconds)
            
            # Execute daily check at midnight
            await run_daily_subscription_check(async_session_maker)
        except asyncio.CancelledError:
            break
        except Exception as e:
            logger.error("Error in subscription_cron_scheduler loop: %s", e)
            await asyncio.sleep(60) # Sleep 1 minute before retrying on error

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Automatically create tables in database on start
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        
    cron_task = asyncio.create_task(subscription_cron_scheduler())
    yield
    cron_task.cancel()
    try:
        await cron_task
    except asyncio.CancelledError:
        pass

app = FastAPI(
    title=settings.PROJECT_NAME,
    version="1.0.0",
    openapi_url=f"{settings.API_V1_STR}/openapi.json",
    lifespan=lifespan
)

# Set CORS enabled origins
if settings.BACKEND_CORS_ORIGINS:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[str(origin).strip("/") for origin in settings.BACKEND_CORS_ORIGINS],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

app.include_router(auth_router, prefix=f"{settings.API_V1_STR}/auth", tags=["auth"])
app.include_router(org_router, prefix=f"{settings.API_V1_STR}/organizations", tags=["organizations"])
app.include_router(users_router, prefix=f"{settings.API_V1_STR}/users", tags=["users"])
app.include_router(companies_router, prefix=f"{settings.API_V1_STR}/companies", tags=["companies"])
app.include_router(contacts_router, prefix=f"{settings.API_V1_STR}/contacts", tags=["contacts"])
app.include_router(leads_router, prefix=f"{settings.API_V1_STR}/leads", tags=["leads"])
app.include_router(activities_router, prefix=f"{settings.API_V1_STR}/activities", tags=["activities"])
app.include_router(notes_router, prefix=f"{settings.API_V1_STR}/notes", tags=["notes"])
app.include_router(dashboard_router, prefix=f"{settings.API_V1_STR}/dashboard", tags=["dashboard"])
app.include_router(active_health_router, prefix=f"{settings.API_V1_STR}/health", tags=["health"])
app.include_router(pipelines_router, prefix=f"{settings.API_V1_STR}/pipelines", tags=["pipelines"])
app.include_router(dialer_router, prefix=f"{settings.API_V1_STR}/dialer", tags=["dialer"])
app.include_router(analytics_router, prefix=f"{settings.API_V1_STR}/analytics", tags=["analytics"])
app.include_router(super_admin_router, prefix=f"{settings.API_V1_STR}/super-admin", tags=["super-admin"])
app.include_router(subscription_router, prefix=f"{settings.API_V1_STR}/tenant", tags=["subscription"])
app.include_router(telephony_router, prefix=f"{settings.API_V1_STR}/telephony", tags=["telephony"])

@app.get("/health")
def health_check():
    return {"status": "ok", "project": settings.PROJECT_NAME}
