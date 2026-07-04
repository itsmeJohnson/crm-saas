import logging
import os
import asyncio
from contextlib import asynccontextmanager
from datetime import datetime, timezone, timedelta

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.core.config import settings
from app.api.v1.auth import router as auth_router
from app.api.v1.organization import router as org_router
from app.api.v1.users import router as users_router
from app.api.v1.companies import router as companies_router
from app.api.v1.contacts import router as contacts_router
from app.api.v1.customers import router as customers_router
from app.api.v1.tasks import router as tasks_router
from app.api.v1.calendar import router as calendar_router
from app.api.v1.communications import router as communications_router
from app.api.v1.leads import router as leads_router
from app.api.v1.activities import router as activities_router
from app.api.v1.notes import router as notes_router
from app.api.v1.dashboard import router as dashboard_router
from app.api.v1.health import router as active_health_router
from app.api.v1.pipelines import router as pipelines_router
from app.api.v1.dialer import router as dialer_router
from app.api.v1.calling import router as calling_router
from app.api.v1.sms import router as sms_router
from app.api.v1.whatsapp import router as whatsapp_router
from app.api.v1.email import router as email_router
from app.api.v1.templates import router as templates_router
from app.api.v1.campaigns import router as campaigns_router
from app.api.v1.communication_analytics import router as comm_analytics_router
from app.api.v1.departments import router as departments_router
from app.api.v1.roles import router as roles_router
from app.api.v1.teams import router as teams_router
from app.api.v1.branches import router as branches_router
from app.api.v1.territories import router as territories_router
from app.api.v1.attendance import router as attendance_router
from app.api.v1.leaves import router as leaves_router
from app.api.v1.analytics import router as analytics_router
from app.api.v1.super_admin import router as super_admin_router
from app.api.v1.subscription import router as subscription_router
from app.api.v1.telephony import router as telephony_router
from app.api.v1.portal import router as portal_router
from app.api.v1.billing_webhook import router as billing_webhook_router
from app.api.v1.notifications import router as notifications_router
from app.api.v1.monitoring import router as monitoring_router, record_http_request
from app.middleware.correlation import correlation_id_middleware
from app.middleware.rate_limiter import RateLimiterMiddleware
from app.core.database import async_session_maker
from app.cron.subscription_cron import run_daily_subscription_check
from app.cron.lead_cron import run_lead_automation_check
from app.cron.customer_cron import run_customer_dunning_check
from app.cron.calling_cron import run_missed_call_check
from app.cron.sms_cron import run_sms_retry_check
from app.cron.email_cron import run_email_sync
from app.cron.campaign_cron import run_campaign_check

# ── JSON structured logging (production) ─────────────────────────────────────
if os.getenv("LOG_JSON", "false").lower() == "true":
    try:
        from app.core.logging import setup_logging
        setup_logging()
    except ImportError:
        logging.basicConfig(
            level=logging.INFO,
            format='{"time":"%(asctime)s","level":"%(levelname)s","name":"%(name)s","message":"%(message)s"}'
        )


# ── Cron scheduler ────────────────────────────────────────────────────────────
async def subscription_cron_scheduler():
    logger = logging.getLogger("app.cron")
    logger.info("Subscription cron scheduler loop started.")

    from app.core.redis import redis_client

    # Run immediately on startup (guarded by distributed lock)
    try:
        async with redis_client.lock("cron_lock:subscription_startup", lease_time=300, acquire_timeout=2.0) as locked:
            if locked:
                logger.info("Acquired startup cron lock. Running daily subscription check.")
                await run_daily_subscription_check(async_session_maker)
            else:
                logger.info("Another instance is already running startup subscription check.")
    except Exception as e:
        logger.error("Initial startup subscription check failed: %s", e)

    while True:
        try:
            now = datetime.now(timezone.utc)
            tomorrow = now + timedelta(days=1)
            midnight = datetime(tomorrow.year, tomorrow.month, tomorrow.day, 0, 0, 0, tzinfo=timezone.utc)
            sleep_seconds = (midnight - now).total_seconds()
            logger.info("Subscription cron sleeping %.0f seconds until %s", sleep_seconds, midnight)
            await asyncio.sleep(sleep_seconds)

            async with redis_client.lock("cron_lock:subscription_daily", lease_time=3600, acquire_timeout=5.0) as locked:
                if locked:
                    logger.info("Acquired daily cron lock. Running daily subscription check.")
                    await run_daily_subscription_check(async_session_maker)
                    await run_lead_automation_check(async_session_maker)
                    await run_customer_dunning_check(async_session_maker)
                    await run_missed_call_check(async_session_maker)
                    await run_sms_retry_check(async_session_maker)
                    await run_email_sync(async_session_maker)
                    await run_campaign_check(async_session_maker)
                else:
                    logger.info("Another instance is already running the daily subscription check.")
        except asyncio.CancelledError:
            break
        except Exception as e:
            logger.error("Error in subscription_cron_scheduler loop: %s", e)
            await asyncio.sleep(60)


# ── App lifespan ──────────────────────────────────────────────────────────────
@asynccontextmanager
async def lifespan(app: FastAPI):
    # Block startup with default JWT secret
    DEFAULT_KEY = "supersecretkeychangeinproduction1234567890"
    if settings.JWT_SECRET_KEY == DEFAULT_KEY:
        raise ValueError(
            "CRITICAL SECURITY FAILURE: Default JWT_SECRET_KEY detected. "
            "Set JWT_SECRET_KEY in your environment / .env file."
        )

    # NOTE: Schema is managed by Alembic migrations (run via entrypoint.sh).
    # Base.metadata.create_all is intentionally NOT called here in production.
    # For local dev without Alembic, set RUN_CREATE_ALL=true in your .env.
    if os.getenv("RUN_CREATE_ALL", "false").lower() == "true":
        from app.models.base import Base
        from app.core.database import engine
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

    cron_task = asyncio.create_task(subscription_cron_scheduler())
    yield
    cron_task.cancel()
    try:
        await cron_task
    except asyncio.CancelledError:
        pass


# ── FastAPI application ────────────────────────────────────────────────────────
app = FastAPI(
    title=settings.PROJECT_NAME,
    version="1.0.0",
    openapi_url=f"{settings.API_V1_STR}/openapi.json",
    lifespan=lifespan,
)

# ── CORS — explicit methods and headers only ──────────────────────────────────
if settings.BACKEND_CORS_ORIGINS:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[str(origin).strip("/") for origin in settings.BACKEND_CORS_ORIGINS],
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
        allow_headers=["Authorization", "Content-Type", "X-Correlation-ID", "Accept"],
    )

app.add_middleware(RateLimiterMiddleware, limit_per_minute=120)
app.middleware("http")(correlation_id_middleware)

@app.middleware("http")
async def prometheus_monitoring_middleware(request: Request, call_next):
    import time
    start_time = time.perf_counter()
    response = await call_next(request)
    latency = time.perf_counter() - start_time
    record_http_request(request.method, request.url.path, response.status_code, latency)
    return response

# ── Static file serving — branding uploads only ───────────────────────────────
os.makedirs("uploads/branding", exist_ok=True)
app.mount("/api/v1/uploads/branding", StaticFiles(directory="uploads/branding"), name="branding")

# ── Routers ───────────────────────────────────────────────────────────────────
# Custom-role matrix enforcement (no-op for users without a custom role). Only
# attached to routers whose routes are ALL authenticated — never to routers
# with public endpoints (users/invitations/accept, email tracking, webhooks).
from fastapi import Depends as _Depends
from app.middleware.permissions import enforce_resource as _enforce

def _rbac(resource: str):
    return [_Depends(_enforce(resource))]

app.include_router(auth_router,            prefix=f"{settings.API_V1_STR}/auth",            tags=["auth"])
app.include_router(org_router,             prefix=f"{settings.API_V1_STR}/organizations",   tags=["organizations"])
app.include_router(users_router,           prefix=f"{settings.API_V1_STR}/users",           tags=["users"])
app.include_router(companies_router,       prefix=f"{settings.API_V1_STR}/companies",       tags=["companies"], dependencies=_rbac("companies"))
app.include_router(contacts_router,        prefix=f"{settings.API_V1_STR}/contacts",        tags=["contacts"], dependencies=_rbac("contacts"))
app.include_router(customers_router,       prefix=f"{settings.API_V1_STR}/customers",       tags=["customers"], dependencies=_rbac("customers"))
app.include_router(tasks_router,           prefix=f"{settings.API_V1_STR}/tasks",           tags=["tasks"], dependencies=_rbac("tasks"))
app.include_router(calendar_router,        prefix=f"{settings.API_V1_STR}/calendar",        tags=["calendar"])
app.include_router(communications_router,  prefix=f"{settings.API_V1_STR}/communications",  tags=["communications"])
app.include_router(leads_router,           prefix=f"{settings.API_V1_STR}/leads",           tags=["leads"], dependencies=_rbac("leads"))
app.include_router(activities_router,      prefix=f"{settings.API_V1_STR}/activities",      tags=["activities"])
app.include_router(notes_router,           prefix=f"{settings.API_V1_STR}/notes",           tags=["notes"])
app.include_router(dashboard_router,       prefix=f"{settings.API_V1_STR}/dashboard",       tags=["dashboard"])
app.include_router(active_health_router,   prefix=f"{settings.API_V1_STR}/health",          tags=["health"])
app.include_router(pipelines_router,       prefix=f"{settings.API_V1_STR}/pipelines",       tags=["pipelines"])
app.include_router(dialer_router,          prefix=f"{settings.API_V1_STR}/dialer",          tags=["dialer"])
app.include_router(calling_router,         prefix=f"{settings.API_V1_STR}/calling",         tags=["calling"])
app.include_router(sms_router,             prefix=f"{settings.API_V1_STR}/sms",             tags=["sms"])
app.include_router(whatsapp_router,        prefix=f"{settings.API_V1_STR}/whatsapp",        tags=["whatsapp"])
app.include_router(email_router,           prefix=f"{settings.API_V1_STR}/email",           tags=["email"])
app.include_router(templates_router,       prefix=f"{settings.API_V1_STR}/templates",       tags=["templates"])
app.include_router(campaigns_router,       prefix=f"{settings.API_V1_STR}/campaigns",       tags=["campaigns"])
app.include_router(comm_analytics_router,  prefix=f"{settings.API_V1_STR}/comm-analytics",  tags=["comm-analytics"])
app.include_router(departments_router,     prefix=f"{settings.API_V1_STR}/departments",     tags=["departments"], dependencies=_rbac("departments"))
app.include_router(roles_router,           prefix=f"{settings.API_V1_STR}/roles",           tags=["roles"])
app.include_router(teams_router,           prefix=f"{settings.API_V1_STR}/teams",           tags=["teams"], dependencies=_rbac("teams"))
app.include_router(branches_router,        prefix=f"{settings.API_V1_STR}/branches",        tags=["branches"], dependencies=_rbac("branches"))
app.include_router(territories_router,     prefix=f"{settings.API_V1_STR}/territories",     tags=["territories"], dependencies=_rbac("territories"))
app.include_router(attendance_router,      prefix=f"{settings.API_V1_STR}/attendance",      tags=["attendance"], dependencies=_rbac("attendance"))
app.include_router(leaves_router,          prefix=f"{settings.API_V1_STR}/leaves",          tags=["leaves"], dependencies=_rbac("leave"))
app.include_router(analytics_router,       prefix=f"{settings.API_V1_STR}/analytics",       tags=["analytics"])
app.include_router(super_admin_router,     prefix=f"{settings.API_V1_STR}/super-admin",     tags=["super-admin"])
app.include_router(subscription_router,    prefix=f"{settings.API_V1_STR}/tenant",          tags=["subscription"])
app.include_router(telephony_router,       prefix=f"{settings.API_V1_STR}/telephony",       tags=["telephony"])
app.include_router(portal_router,          prefix=f"{settings.API_V1_STR}/portal",          tags=["portal"])
app.include_router(billing_webhook_router, prefix=f"{settings.API_V1_STR}/billing/webhook", tags=["billing-webhook"])
app.include_router(notifications_router,   prefix=f"{settings.API_V1_STR}/notifications",   tags=["notifications"])
app.include_router(monitoring_router)

@app.get("/health")
def health_check():
    return {"status": "ok", "project": settings.PROJECT_NAME}
