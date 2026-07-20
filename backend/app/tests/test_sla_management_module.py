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
from app.models.automation import SLABreach
from app.models.sla import SLATracker, SLAPause
from app.models.event import Event
from app.services.sla_service import SLAService
from app.services import business_time as bt
from app.core.redis import redis_client


# ---------------- pure business-time unit tests (no DB) ----------------
def _days():
    return {d: {"enabled": i < 5, "start": "09:00", "end": "17:00"}
            for i, d in enumerate(["mon", "tue", "wed", "thu", "fri", "sat", "sun"])}


def test_business_time_skips_weekend_and_holiday():
    days = _days()
    # Fri 16:00 + 4 business hours → Mon 12:00 (weekend skipped)
    assert bt.add_business_hours(datetime(2026, 7, 3, 16, 0), 4, days) == datetime(2026, 7, 6, 12, 0)
    # elapsed Fri 16:00 → Mon 10:00 = 1h (Fri) + 1h (Mon) = 2h
    assert bt.business_elapsed(datetime(2026, 7, 3, 16, 0), datetime(2026, 7, 6, 10, 0), days) == 2.0
    # a holiday on Monday pushes the deadline to Tuesday
    hols = [(datetime(2026, 7, 6).date(), False)]
    assert bt.add_business_hours(datetime(2026, 7, 3, 16, 0), 4, days, hols) == datetime(2026, 7, 7, 12, 0)


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
    org = await OrganizationRepository(db).create({"name": "SLA Org", "slug": "sla-org"})
    await db.commit()
    ur = UserRepository(db)
    admin = await ur.create_user(org.id, {"email": "admin@sla.com", "hashed_password": get_password_hash("password123"),
        "first_name": "Ad", "last_name": "Min", "role": "OrgAdmin", "is_active": True})
    await db.commit()
    emp = await ur.create_user(org.id, {"email": "emp@sla.com", "hashed_password": get_password_hash("password123"),
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


async def _lead(db, d, **kw):
    lead = Lead(organization_id=d["org"].id, last_name="L", title="Deal", status="New",
                created_by=d["admin"].id, stage_id=d["stage"].id, assigned_user_id=d["emp"].id, **kw)
    db.add(lead); await db.commit()
    return lead


@pytest.mark.asyncio
async def test_catalog_policy_crud_priority_tiers_perms(client: AsyncClient, setup: dict):
    d = setup
    cat = (await client.get("/api/v1/sla/catalog", headers=d["h_admin"])).json()
    assert "first_response" in cat["metrics"] and "escalate" in cat["breach_actions"]
    # employee cannot create
    assert (await client.post("/api/v1/sla/policies", json={"name": "x"}, headers=d["h_emp"])).status_code == 403
    # invalid on_breach rejected
    assert (await client.post("/api/v1/sla/policies", json={"name": "x", "on_breach": "bogus"}, headers=d["h_admin"])).status_code == 400
    # create with priority tiers
    p = (await client.post("/api/v1/sla/policies", json={
        "name": "Support SLA", "response_hours": 8, "resolution_hours": 48,
        "priorities": [{"level": "High", "response_hours": 1, "resolution_hours": 8},
                       {"level": "Low", "response_hours": 24, "resolution_hours": 72}]}, headers=d["h_admin"])).json()
    assert p["response_hours"] == 8 and len(p["priorities"]) == 2


@pytest.mark.asyncio
async def test_start_tracking_priority_threshold_and_due(client: AsyncClient, setup: dict, db: AsyncSession):
    d = setup
    await client.post("/api/v1/sla/policies", json={
        "name": "Wall clock", "response_hours": 4, "resolution_hours": 24,
        "priorities": [{"level": "High", "response_hours": 1, "resolution_hours": 2}]}, headers=d["h_admin"])
    svc = SLAService(db)
    # a High-priority lead → uses the 1h response tier
    hi = await _lead(db, d, priority="High")
    await svc.start_tracking(hi, "lead", d["org"].id)
    t = (await db.execute(select(SLATracker).filter(SLATracker.entity_id == hi.id))).scalars().first()
    assert t is not None and t.priority_level == "High" and t.response_hours == 1 and t.resolution_hours == 2
    assert t.response_due_at is not None and t.resolution_due_at is not None
    # a default lead → falls back to the policy defaults (4h/24h)
    lo = await _lead(db, d, priority="Medium")
    await svc.start_tracking(lo, "lead", d["org"].id)
    t2 = (await db.execute(select(SLATracker).filter(SLATracker.entity_id == lo.id))).scalars().first()
    assert t2.response_hours == 4 and t2.resolution_hours == 24
    # idempotent: re-tracking does not duplicate
    assert await svc.start_tracking(hi, "lead", d["org"].id) == 0


@pytest.mark.asyncio
async def test_response_resolution_met_vs_late(client: AsyncClient, setup: dict, db: AsyncSession):
    d = setup
    await client.post("/api/v1/sla/policies", json={"name": "P", "response_hours": 4, "resolution_hours": 24}, headers=d["h_admin"])
    svc = SLAService(db)
    lead = await _lead(db, d)
    await svc.start_tracking(lead, "lead", d["org"].id)
    # respond in time → not breached
    await svc.record_response("lead", lead.id, d["org"].id)
    t = (await db.execute(select(SLATracker).filter(SLATracker.entity_id == lead.id))).scalars().first()
    assert t.first_response_at is not None and t.response_breached is False
    # resolve in time → met
    await svc.record_resolution("lead", lead.id, d["org"].id)
    await db.refresh(t)
    assert t.status == "met" and t.resolved_at is not None

    # a second lead whose resolution deadline is already in the past → late resolution
    late = await _lead(db, d)
    await svc.start_tracking(late, "lead", d["org"].id)
    t2 = (await db.execute(select(SLATracker).filter(SLATracker.entity_id == late.id))).scalars().first()
    t2.resolution_due_at = datetime.now(timezone.utc) - timedelta(hours=1); db.add(t2); await db.commit()
    await svc.record_resolution("lead", late.id, d["org"].id)
    await db.refresh(t2)
    assert t2.status == "breached" and t2.resolution_breached is True


@pytest.mark.asyncio
async def test_pause_and_resume_extends_deadline(client: AsyncClient, setup: dict, db: AsyncSession):
    d = setup
    await client.post("/api/v1/sla/policies", json={"name": "P", "response_hours": 4, "resolution_hours": 24}, headers=d["h_admin"])
    svc = SLAService(db)
    lead = await _lead(db, d)
    await svc.start_tracking(lead, "lead", d["org"].id)
    t = (await db.execute(select(SLATracker).filter(SLATracker.entity_id == lead.id))).scalars().first()
    before = t.resolution_due_at
    # pause via API then backdate the pause so resume adds measurable time
    paused = (await client.post(f"/api/v1/sla/trackers/{t.id}/pause", json={"reason": "waiting"}, headers=d["h_admin"])).json()
    assert paused["status"] == "paused"
    row = (await db.execute(select(SLATracker).filter(SLATracker.id == t.id))).scalars().first()
    row.paused_at = datetime.now(timezone.utc) - timedelta(hours=2); db.add(row); await db.commit()
    resumed = (await client.post(f"/api/v1/sla/trackers/{t.id}/resume", headers=d["h_admin"])).json()
    assert resumed["status"] == "running" and resumed["paused_seconds"] >= 7000  # ~2h
    await db.refresh(row)
    assert row.resolution_due_at > before  # deadline pushed out by the pause
    # a pause row was recorded and closed
    pauses = (await db.execute(select(SLAPause).filter(SLAPause.tracker_id == t.id))).scalars().all()
    assert len(pauses) == 1 and pauses[0].resumed_at is not None


@pytest.mark.asyncio
async def test_scan_breaches_records_and_emits_event(client: AsyncClient, setup: dict, db: AsyncSession):
    d = setup
    p = (await client.post("/api/v1/sla/policies", json={
        "name": "Fast", "response_hours": 1, "resolution_hours": 2, "on_breach": "notify_manager"}, headers=d["h_admin"])).json()
    svc = SLAService(db)
    lead = await _lead(db, d)
    await svc.start_tracking(lead, "lead", d["org"].id)
    # force both deadlines into the past
    t = (await db.execute(select(SLATracker).filter(SLATracker.entity_id == lead.id))).scalars().first()
    past = datetime.now(timezone.utc) - timedelta(hours=3)
    t.response_due_at = past; t.resolution_due_at = past; db.add(t); await db.commit()
    # scan → response + resolution breaches
    breaches = await svc.scan(d["org"].id)
    assert breaches == 2
    await db.refresh(t)
    assert t.status == "breached" and t.response_breached and t.resolution_breached
    # SLABreach rows recorded (shared table)
    rows = (await db.execute(select(SLABreach).filter(SLABreach.entity_id == lead.id))).scalars().all()
    assert len(rows) == 2
    # sla.breached events emitted (→ workflows + notification rules)
    evs = (await db.execute(select(Event).filter(
        Event.organization_id == d["org"].id, Event.event_type == "sla.breached"))).scalars().all()
    assert len(evs) >= 1
    # the manager (admin) was notified
    from app.models.notification import Notification
    notifs = (await db.execute(select(Notification).filter(
        Notification.organization_id == d["org"].id, Notification.user_id == d["admin"].id))).scalars().all()
    assert any("SLA breach" in n.title for n in notifs)
    # idempotent-ish: re-scan doesn't add more breaches (already flagged)
    assert await svc.scan(d["org"].id) == 0


@pytest.mark.asyncio
async def test_lead_create_auto_starts_tracking(client: AsyncClient, setup: dict, db: AsyncSession):
    d = setup
    await client.post("/api/v1/sla/policies", json={"name": "Auto", "response_hours": 4}, headers=d["h_admin"])
    # creating a lead through the API opens an SLA tracker
    lead = (await client.post("/api/v1/leads/", json={"last_name": "Auto", "title": "Deal"}, headers=d["h_admin"])).json()
    trackers = (await client.get("/api/v1/sla/trackers", headers=d["h_admin"])).json()
    assert any(t["entity_id"] == lead["id"] for t in trackers)


@pytest.mark.asyncio
async def test_dashboard_and_report(client: AsyncClient, setup: dict, db: AsyncSession):
    d = setup
    await client.post("/api/v1/sla/policies", json={"name": "P", "response_hours": 4, "resolution_hours": 24}, headers=d["h_admin"])
    svc = SLAService(db)
    lead = await _lead(db, d)
    await svc.start_tracking(lead, "lead", d["org"].id)
    await svc.record_response("lead", lead.id, d["org"].id)
    await svc.record_resolution("lead", lead.id, d["org"].id)
    await db.commit()
    rep = (await client.get("/api/v1/sla/report", headers=d["h_admin"])).json()
    assert rep["policies"] >= 1 and "compliance_rate" in rep and rep["met"] >= 1
    dash = (await client.get("/api/v1/sla/dashboard", headers=d["h_admin"])).json()
    assert "compliance_rate" in dash and "at_risk" in dash and "open_breaches" in dash
