import pytest
import uuid
from datetime import datetime, timezone, timedelta
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.core.security import create_access_token, get_password_hash
from app.repositories.organization import OrganizationRepository
from app.repositories.user_repository import UserRepository
from app.models.lead import Lead
from app.models.pipeline import PipelineStage
from app.models.automation import AutomationJob, AutomationRun, SLAPolicy, SLABreach, ScheduledReport
from app.core.redis import redis_client


@pytest.fixture(autouse=True)
def mock_redis(monkeypatch):
    store = {}
    async def g(k): return store.get(k)
    async def s(k, v, ex=300): store[k] = v; return True
    async def d(k): store.pop(k, None); return True
    monkeypatch.setattr(redis_client, "get", g)
    monkeypatch.setattr(redis_client, "set", s)
    monkeypatch.setattr(redis_client, "delete", d)
    from app.dependencies import feature_guard
    async def feats(*a, **k): return ["LEAD_MANAGEMENT", "ROLE_BASED_ACCESS"]
    monkeypatch.setattr(feature_guard, "get_active_features", feats)
    return store


@pytest.fixture
async def setup(db: AsyncSession):
    org = await OrganizationRepository(db).create({"name": "Auto Org", "slug": "auto-org"})
    await db.commit()
    ur = UserRepository(db)
    admin = await ur.create_user(org.id, {"email": "admin@auto.com", "hashed_password": get_password_hash("password123"),
        "first_name": "Ad", "last_name": "Min", "role": "OrgAdmin", "is_active": True})
    await db.commit()
    emp = await ur.create_user(org.id, {"email": "emp@auto.com", "hashed_password": get_password_hash("password123"),
        "first_name": "Em", "last_name": "P", "role": "Employee", "is_active": True, "reporting_to_id": admin.id})
    await db.commit()
    stage = (await db.execute(select(PipelineStage).filter(
        PipelineStage.organization_id == org.id, PipelineStage.is_system_default == True))).scalars().first()
    if not stage:
        stage = PipelineStage(organization_id=org.id, name="New", order_position=1, is_system_default=True)
        db.add(stage); await db.commit()
    return {"org": org, "admin": admin, "emp": emp, "stage": stage,
            "h_admin": {"Authorization": f"Bearer {create_access_token(admin.id)}"},
            "h_emp": {"Authorization": f"Bearer {create_access_token(emp.id)}"}}


@pytest.mark.asyncio
async def test_catalog_jobs_registry_enable_and_permissions(client: AsyncClient, setup: dict):
    d = setup
    cat = (await client.get("/api/v1/automation/catalog", headers=d["h_admin"])).json()
    assert "sla_scan" in [j["job_key"] for j in cat["jobs"]]
    assert "first_response" in cat["sla_metrics"] and "lead_summary" in cat["report_types"]
    # list surfaces the full catalog (virtual until bootstrapped)
    jobs = (await client.get("/api/v1/automation/jobs", headers=d["h_admin"])).json()
    assert len(jobs) >= len(cat["jobs"])
    # employee cannot toggle
    assert (await client.post("/api/v1/automation/jobs/sla_scan/enable", json={"enabled": False}, headers=d["h_emp"])).status_code == 403
    # admin disables + bootstraps the job row
    off = (await client.post("/api/v1/automation/jobs/sla_scan/enable", json={"enabled": False}, headers=d["h_admin"])).json()
    assert off["is_enabled"] is False and off["id"] is not None
    # unknown job rejected
    assert (await client.post("/api/v1/automation/jobs/nope/enable", json={"enabled": True}, headers=d["h_admin"])).status_code == 400


@pytest.mark.asyncio
async def test_run_job_records_run_and_retry(client: AsyncClient, setup: dict, db: AsyncSession):
    d = setup
    # run a job manually → an AutomationRun is logged with success
    run = (await client.post("/api/v1/automation/jobs/lead_reminders/run", headers=d["h_admin"])).json()
    assert run["status"] == "success" and run["triggered_by"] == "manual"
    rows = (await db.execute(select(AutomationRun).filter(
        AutomationRun.organization_id == d["org"].id, AutomationRun.job_key == "lead_reminders"))).scalars().all()
    assert len(rows) == 1 and rows[0].finished_at is not None
    # run history endpoint
    hist = (await client.get("/api/v1/automation/runs", headers=d["h_admin"])).json()
    assert any(r["job_key"] == "lead_reminders" for r in hist)
    # retry re-runs the job under a new run
    rr = (await client.post(f"/api/v1/automation/runs/{run['id']}/retry", headers=d["h_admin"])).json()
    assert rr["triggered_by"] == "retry"


@pytest.mark.asyncio
async def test_sla_policy_crud_and_breach_scan(client: AsyncClient, setup: dict, db: AsyncSession):
    d = setup
    # a strict first-response SLA: 1 hour
    p = (await client.post("/api/v1/automation/sla", json={
        "name": "1h first response", "metric": "first_response", "threshold_hours": 1,
        "on_breach": "notify_manager"}, headers=d["h_admin"])).json()
    assert p["metric"] == "first_response" and p["threshold_hours"] == 1
    # invalid metric rejected
    assert (await client.post("/api/v1/automation/sla", json={"name": "x", "metric": "bogus"}, headers=d["h_admin"])).status_code == 400
    # an old lead with no activity and an owner → should breach
    old = Lead(organization_id=d["org"].id, last_name="Old", title="Stale deal", status="New",
               assigned_user_id=d["emp"].id, created_by=d["admin"].id, stage_id=d["stage"].id,
               created_at=datetime.now(timezone.utc) - timedelta(hours=5))
    db.add(old); await db.commit()
    # run the SLA scan job
    run = (await client.post("/api/v1/automation/jobs/sla_scan/run", headers=d["h_admin"])).json()
    assert run["status"] == "success" and run["items_processed"] >= 1
    breaches = (await client.get("/api/v1/automation/breaches", headers=d["h_admin"])).json()
    assert len(breaches) >= 1 and breaches[0]["metric"] == "first_response"
    # re-running does not duplicate the open breach (dedup)
    (await client.post("/api/v1/automation/jobs/sla_scan/run", headers=d["h_admin"])).json()
    breaches2 = (await client.get("/api/v1/automation/breaches", headers=d["h_admin"])).json()
    assert len(breaches2) == len(breaches)
    # resolve a breach
    res = (await client.post(f"/api/v1/automation/breaches/{breaches[0]['id']}/resolve", headers=d["h_admin"])).json()
    assert res["resolved"] is True


@pytest.mark.asyncio
async def test_sla_conditions_gate_breach(client: AsyncClient, setup: dict, db: AsyncSession):
    """A rule-engine condition on the SLA only breaches matching leads."""
    d = setup
    # only high-value leads are covered by this SLA
    await client.post("/api/v1/automation/sla", json={
        "name": "VIP response", "metric": "first_response", "threshold_hours": 1, "on_breach": "notify_owner",
        "conditions": {"type": "group", "logic": "and", "children": [
            {"type": "condition", "field": "value", "op": "gte", "value": 10000}]}}, headers=d["h_admin"])
    cheap = Lead(organization_id=d["org"].id, last_name="Cheap", title="Small", status="New", value=100,
                 assigned_user_id=d["emp"].id, created_by=d["admin"].id, stage_id=d["stage"].id,
                 created_at=datetime.now(timezone.utc) - timedelta(hours=5))
    rich = Lead(organization_id=d["org"].id, last_name="Rich", title="Big", status="New", value=50000,
                assigned_user_id=d["emp"].id, created_by=d["admin"].id, stage_id=d["stage"].id,
                created_at=datetime.now(timezone.utc) - timedelta(hours=5))
    db.add_all([cheap, rich]); await db.commit()
    (await client.post("/api/v1/automation/jobs/sla_scan/run", headers=d["h_admin"])).json()
    breaches = (await client.get("/api/v1/automation/breaches", headers=d["h_admin"])).json()
    breached_ids = {b["entity_id"] for b in breaches}
    assert str(rich.id) in breached_ids and str(cheap.id) not in breached_ids


@pytest.mark.asyncio
async def test_scheduled_reports_crud_and_run(client: AsyncClient, setup: dict, db: AsyncSession):
    d = setup
    r = (await client.post("/api/v1/automation/reports", json={
        "name": "Weekly leads", "report_type": "lead_summary", "frequency": "weekly",
        "recipients": [str(d["admin"].id)]}, headers=d["h_admin"])).json()
    assert r["report_type"] == "lead_summary" and r["next_run_at"] is not None
    # invalid frequency rejected
    assert (await client.post("/api/v1/automation/reports", json={"name": "x", "frequency": "annually"}, headers=d["h_admin"])).status_code == 400
    # run now → delivers a notification to the recipient
    out = (await client.post(f"/api/v1/automation/reports/{r['id']}/run", headers=d["h_admin"])).json()
    assert out["delivered"] == 1
    from app.models.notification import Notification
    notifs = (await db.execute(select(Notification).filter(
        Notification.organization_id == d["org"].id, Notification.category == "report"))).scalars().all()
    assert len(notifs) >= 1
    # send_count advanced
    updated = (await client.get("/api/v1/automation/reports", headers=d["h_admin"])).json()
    assert updated[0]["send_count"] == 1


@pytest.mark.asyncio
async def test_dashboard_and_report(client: AsyncClient, setup: dict):
    d = setup
    await client.post("/api/v1/automation/jobs/lead_reminders/run", headers=d["h_admin"])
    rep = (await client.get("/api/v1/automation/report", headers=d["h_admin"])).json()
    assert rep["total_runs"] >= 1 and "runs_by_job" in rep and "success_rate" in rep
    dash = (await client.get("/api/v1/automation/dashboard", headers=d["h_admin"])).json()
    assert dash["jobs"] >= 1 and "recent" in dash and "open_breaches" in dash


@pytest.mark.asyncio
async def test_automation_cycle_runs_tracked(setup: dict, db: AsyncSession, monkeypatch):
    """The scheduled cycle runs the new per-org jobs through the tracked runner."""
    from app.cron import automation_cron
    d = setup
    # seed an active SLA policy so the org is discovered by the cycle
    from app.services.automation_service import AutomationService
    await AutomationService(db).create_sla(d["admin"], {"name": "resp", "metric": "first_response", "threshold_hours": 1})
    await db.commit()

    # a session_maker that yields the test session (no commit/close side effects)
    from contextlib import asynccontextmanager

    class _NoOpTx:
        async def __aenter__(self): return db
        async def __aexit__(self, *a): return False

    def session_maker():
        return _NoOpTx()

    # neutralise commit within the cycle (test controls the transaction)
    async def _noop_commit(): return None
    monkeypatch.setattr(db, "commit", _noop_commit)

    await automation_cron.run_automation_cycle(session_maker)
    runs = (await db.execute(select(AutomationRun).filter(
        AutomationRun.organization_id == d["org"].id, AutomationRun.triggered_by == "schedule"))).scalars().all()
    assert any(r.job_key in ("sla_scan", "scheduled_reports") for r in runs)
