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
from app.api.v1.shifts import router as shifts_router
from app.api.v1.performance import router as performance_router
from app.api.v1.targets import router as targets_router
from app.api.v1.approvals import router as approvals_router
from app.api.v1.announcements import router as announcements_router
from app.api.v1.org_analytics import router as org_analytics_router
from app.api.v1.automation_analytics import router as automation_analytics_router
from app.api.v1.executive_dashboard import router as executive_dashboard_router
from app.api.v1.report_builder import router as report_builder_router
from app.api.v1.sales_analytics import router as sales_analytics_router
from app.api.v1.employee_analytics import router as employee_analytics_router
from app.api.v1.financial_analytics import router as financial_analytics_router
from app.api.v1.forecasting import router as forecasting_router
from app.api.v1.kpi import router as kpi_router
from app.api.v1.okr import router as okr_router
from app.api.v1.visualizations import router as visualizations_router
from app.api.v1.scheduled_reports import router as scheduled_reports_router
from app.api.v1.bi_export import router as bi_export_router, feed_router as bi_feed_router
from app.api.v1.historical_analytics import router as historical_analytics_router
from app.api.v1.compliance import router as compliance_router
from app.api.v1.predictive import router as predictive_router
from app.api.v1.ai_platform import router as ai_platform_router
from app.api.v1.copilot import router as copilot_router
from app.api.v1.lead_intelligence import router as lead_intelligence_router
from app.api.v1.comm_intelligence import router as comm_intelligence_router
from app.api.v1.sales_intelligence import router as sales_intelligence_router
from app.api.v1.knowledge import router as knowledge_router
from app.api.v1.document_intelligence import router as document_intelligence_router
from app.api.v1.workflow_assistant import router as workflow_assistant_router
from app.api.v1.prediction_engine import router as prediction_engine_router
from app.api.v1.recommendations import router as recommendations_router
from app.api.v1.workflows import router as workflows_router
from app.api.v1.rules import router as rules_router
from app.api.v1.automation import router as automation_router
from app.api.v1.events import router as events_router
from app.api.v1.queue import router as queue_router
from app.api.v1.scheduler import router as scheduler_router
from app.api.v1.notification_automation import router as notification_automation_router
from app.api.v1.sla import router as sla_router
from app.api.v1.escalation import router as escalation_router
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
from app.cron.automation_cron import run_automation_cycle
from app.cron.sla_cron import run_sla_scan_all
from app.cron.escalation_cron import run_escalation_engine
from app.cron.approval_cron import run_approval_timeouts
from app.cron.report_cron import run_scheduled_report_builder
from app.cron.kpi_cron import run_kpi_evaluation
from app.cron.okr_cron import run_okr_scan
from app.cron.scheduled_report_cron import run_report_schedule_delivery
from app.cron.bi_sync_cron import run_bi_data_sync
from app.cron.history_cron import run_history_capture

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
                    # Automation Engine: SLA scan + scheduled reports (tracked, per-org)
                    await run_automation_cycle(async_session_maker)
                    # SLA Management: business-hours-aware tracker breach scan
                    await run_sla_scan_all(async_session_maker)
                    # Escalation Engine: multi-level rule-based escalation scan
                    await run_escalation_engine(async_session_maker)
                    # Approval Automation: chain timeout actions (escalate/auto-approve/auto-reject)
                    await run_approval_timeouts(async_session_maker)
                    # Custom Report Builder: deliver due scheduled report definitions
                    await run_scheduled_report_builder(async_session_maker)
                    # KPI Engine: evaluate KPIs, raise/resolve threshold alerts
                    await run_kpi_evaluation(async_session_maker)
                    # Goal & OKR Management: auto-complete achieved objectives, at-risk nudges
                    await run_okr_scan(async_session_maker)
                    # Scheduled Reports: deliver due report schedules (CSV/Excel/PDF, multi-channel)
                    await run_report_schedule_delivery(async_session_maker)
                    # Export & BI Integration: run due data syncs (webhook / cloud storage)
                    await run_bi_data_sync(async_session_maker)
                    # Historical Analytics: capture daily metric snapshots + apply retention
                    await run_history_capture(async_session_maker)
                else:
                    logger.info("Another instance is already running the daily subscription check.")
        except asyncio.CancelledError:
            break
        except Exception as e:
            logger.error("Error in subscription_cron_scheduler loop: %s", e)
            await asyncio.sleep(60)


# ── Background Queue worker ───────────────────────────────────────────────────
async def queue_worker_loop():
    """Drives the durable background queue. Single active drainer via a redis
    lock; if another instance holds it, this one idles and retries."""
    logger = logging.getLogger("app.cron.queue")
    from app.core.redis import redis_client
    from app.cron.queue_worker import run_queue_worker
    while True:
        try:
            async with redis_client.lock("cron_lock:queue_worker", lease_time=30, acquire_timeout=2.0) as locked:
                if locked:
                    await run_queue_worker(async_session_maker)  # long-running until cancelled
                else:
                    await asyncio.sleep(15)
        except asyncio.CancelledError:
            break
        except Exception as e:
            logger.error("queue_worker_loop error: %s", e)
            await asyncio.sleep(15)


# ── Scheduler tick ────────────────────────────────────────────────────────────
async def scheduler_tick_loop():
    """Minute-granularity driver for the configurable Scheduler. Single active
    ticker via a redis lock; runs due schedules then sleeps ~60s."""
    logger = logging.getLogger("app.cron.scheduler")
    from app.core.redis import redis_client
    from app.cron.scheduler_tick import run_scheduler_tick
    while True:
        try:
            async with redis_client.lock("cron_lock:scheduler_tick", lease_time=55, acquire_timeout=2.0) as locked:
                if locked:
                    await run_scheduler_tick(async_session_maker)
            await asyncio.sleep(60)
        except asyncio.CancelledError:
            break
        except Exception as e:
            logger.error("scheduler_tick_loop error: %s", e)
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
    queue_task = asyncio.create_task(queue_worker_loop())
    scheduler_task = asyncio.create_task(scheduler_tick_loop())
    yield
    for t in (cron_task, queue_task, scheduler_task):
        t.cancel()
    for t in (cron_task, queue_task, scheduler_task):
        try:
            await t
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
app.include_router(shifts_router,          prefix=f"{settings.API_V1_STR}/shifts",          tags=["shifts"], dependencies=_rbac("shifts"))
app.include_router(performance_router,     prefix=f"{settings.API_V1_STR}/performance",     tags=["performance"], dependencies=_rbac("performance"))
app.include_router(targets_router,         prefix=f"{settings.API_V1_STR}/targets",         tags=["targets"], dependencies=_rbac("targets"))
app.include_router(approvals_router,       prefix=f"{settings.API_V1_STR}/approvals",       tags=["approvals"], dependencies=_rbac("approvals"))
app.include_router(announcements_router,   prefix=f"{settings.API_V1_STR}/announcements",   tags=["announcements"], dependencies=_rbac("announcements"))
app.include_router(org_analytics_router,   prefix=f"{settings.API_V1_STR}/org-analytics",   tags=["org-analytics"], dependencies=_rbac("analytics"))
app.include_router(automation_analytics_router, prefix=f"{settings.API_V1_STR}/automation-analytics", tags=["automation-analytics"], dependencies=_rbac("analytics"))
app.include_router(executive_dashboard_router, prefix=f"{settings.API_V1_STR}/executive-dashboard", tags=["executive-dashboard"], dependencies=_rbac("analytics"))
app.include_router(report_builder_router,  prefix=f"{settings.API_V1_STR}/report-builder",   tags=["report-builder"], dependencies=_rbac("analytics"))
app.include_router(sales_analytics_router, prefix=f"{settings.API_V1_STR}/sales-analytics",   tags=["sales-analytics"], dependencies=_rbac("analytics"))
app.include_router(employee_analytics_router, prefix=f"{settings.API_V1_STR}/employee-analytics", tags=["employee-analytics"], dependencies=_rbac("analytics"))
app.include_router(financial_analytics_router, prefix=f"{settings.API_V1_STR}/financial-analytics", tags=["financial-analytics"], dependencies=_rbac("analytics"))
app.include_router(forecasting_router,     prefix=f"{settings.API_V1_STR}/forecasting",      tags=["forecasting"], dependencies=_rbac("analytics"))
app.include_router(kpi_router,              prefix=f"{settings.API_V1_STR}/kpi",              tags=["kpi"], dependencies=_rbac("analytics"))
app.include_router(okr_router,              prefix=f"{settings.API_V1_STR}/okr",              tags=["okr"], dependencies=_rbac("targets"))
app.include_router(visualizations_router,   prefix=f"{settings.API_V1_STR}/visualizations",   tags=["visualizations"], dependencies=_rbac("analytics"))
app.include_router(scheduled_reports_router, prefix=f"{settings.API_V1_STR}/scheduled-reports", tags=["scheduled-reports"], dependencies=_rbac("analytics"))
# BI feed is token-authenticated (external BI tools can't do the JWT flow) — mounted WITHOUT bearer RBAC, like the calendar .ics feed.
app.include_router(bi_feed_router,          prefix=f"{settings.API_V1_STR}/bi/feed",          tags=["bi-feed"])
app.include_router(bi_export_router,        prefix=f"{settings.API_V1_STR}/bi",               tags=["bi"], dependencies=_rbac("analytics"))
app.include_router(historical_analytics_router, prefix=f"{settings.API_V1_STR}/historical-analytics", tags=["historical-analytics"], dependencies=_rbac("analytics"))
app.include_router(compliance_router,       prefix=f"{settings.API_V1_STR}/compliance",       tags=["compliance"], dependencies=_rbac("analytics"))
app.include_router(predictive_router,       prefix=f"{settings.API_V1_STR}/predictive",       tags=["predictive"], dependencies=_rbac("analytics"))
app.include_router(ai_platform_router,      prefix=f"{settings.API_V1_STR}/ai",               tags=["ai"], dependencies=_rbac("ai"))
app.include_router(copilot_router,          prefix=f"{settings.API_V1_STR}/copilot",          tags=["copilot"], dependencies=_rbac("ai"))
app.include_router(lead_intelligence_router, prefix=f"{settings.API_V1_STR}/lead-intelligence", tags=["lead-intelligence"], dependencies=_rbac("leads"))
# Communication Intelligence is open to all active users (scoped internally to own comms for reps), like Communication Analytics.
app.include_router(comm_intelligence_router, prefix=f"{settings.API_V1_STR}/comm-intelligence", tags=["comm-intelligence"])
app.include_router(sales_intelligence_router, prefix=f"{settings.API_V1_STR}/sales-intelligence", tags=["sales-intelligence"], dependencies=_rbac("analytics"))
app.include_router(knowledge_router,        prefix=f"{settings.API_V1_STR}/knowledge",        tags=["knowledge"], dependencies=_rbac("ai"))
app.include_router(document_intelligence_router, prefix=f"{settings.API_V1_STR}/document-intelligence", tags=["document-intelligence"], dependencies=_rbac("ai"))
app.include_router(workflow_assistant_router,   prefix=f"{settings.API_V1_STR}/workflow-assistant", tags=["workflow-assistant"], dependencies=_rbac("workflows"))
app.include_router(prediction_engine_router,    prefix=f"{settings.API_V1_STR}/prediction-engine", tags=["prediction-engine"], dependencies=_rbac("analytics"))
app.include_router(recommendations_router,      prefix=f"{settings.API_V1_STR}/recommendations", tags=["recommendations"], dependencies=_rbac("ai"))
app.include_router(workflows_router,       prefix=f"{settings.API_V1_STR}/workflows",       tags=["workflows"], dependencies=_rbac("workflows"))
app.include_router(rules_router,           prefix=f"{settings.API_V1_STR}/rules",           tags=["rules"], dependencies=_rbac("rules"))
app.include_router(automation_router,      prefix=f"{settings.API_V1_STR}/automation",      tags=["automation"], dependencies=_rbac("automation"))
app.include_router(events_router,          prefix=f"{settings.API_V1_STR}/events",          tags=["events"], dependencies=_rbac("events"))
app.include_router(queue_router,           prefix=f"{settings.API_V1_STR}/queue",           tags=["queue"], dependencies=_rbac("queue"))
app.include_router(scheduler_router,       prefix=f"{settings.API_V1_STR}/scheduler",       tags=["scheduler"], dependencies=_rbac("scheduler"))
app.include_router(notification_automation_router, prefix=f"{settings.API_V1_STR}/notification-automation", tags=["notification-automation"], dependencies=_rbac("notifications"))
app.include_router(sla_router,             prefix=f"{settings.API_V1_STR}/sla",             tags=["sla"], dependencies=_rbac("sla"))
app.include_router(escalation_router,      prefix=f"{settings.API_V1_STR}/escalation",      tags=["escalation"], dependencies=_rbac("escalation"))
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
