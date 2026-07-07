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
from app.models.task import Task
from app.models.pipeline import PipelineStage
from app.models.department import Department
from app.models.escalation import EscalationRule, EscalationEvent
from app.models.event import Event
from app.models.notification import Notification
from app.services.escalation_engine_service import EscalationEngineService
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
    org = await OrganizationRepository(db).create({"name": "Esc Org", "slug": "esc-org"})
    await db.commit()
    ur = UserRepository(db)
    admin = await ur.create_user(org.id, {"email": "admin@esc.com", "hashed_password": get_password_hash("password123"),
        "first_name": "Ad", "last_name": "Min", "role": "OrgAdmin", "is_active": True})
    await db.commit()
    mgr = await ur.create_user(org.id, {"email": "mgr@esc.com", "hashed_password": get_password_hash("password123"),
        "first_name": "Man", "last_name": "Ager", "role": "Manager", "is_active": True, "reporting_to_id": admin.id})
    await db.commit()
    emp = await ur.create_user(org.id, {"email": "emp@esc.com", "hashed_password": get_password_hash("password123"),
        "first_name": "Em", "last_name": "P", "role": "Employee", "is_active": True, "reporting_to_id": mgr.id})
    await db.commit()
    stage = (await db.execute(select(PipelineStage).filter(
        PipelineStage.organization_id == org.id, PipelineStage.is_system_default == True))).scalars().first()
    if not stage:
        stage = PipelineStage(organization_id=org.id, name="New", order_position=1, is_system_default=True)
        db.add(stage); await db.commit()
    return {"org": org, "admin": admin, "mgr": mgr, "emp": emp, "stage": stage,
            "h_admin": {"Authorization": f"Bearer {create_access_token(admin.id)}"},
            "h_emp": {"Authorization": f"Bearer {create_access_token(emp.id)}"}}


async def _old_lead(db, d, hours_old, **kw):
    lead = Lead(organization_id=d["org"].id, last_name="L", title="Deal", status="New",
                created_by=d["admin"].id, stage_id=d["stage"].id, assigned_user_id=d["emp"].id,
                created_at=datetime.now(timezone.utc) - timedelta(hours=hours_old), **kw)
    db.add(lead); await db.commit()
    return lead


@pytest.mark.asyncio
async def test_catalog_crud_and_permissions(client: AsyncClient, setup: dict):
    d = setup
    cat = (await client.get("/api/v1/escalation/catalog", headers=d["h_admin"])).json()
    assert "lead" in cat["entity_types"] and "department_head" in cat["escalate_targets"] and "no_activity" in cat["trigger_conditions"]
    # employee cannot create
    assert (await client.post("/api/v1/escalation/rules", json={"name": "x", "levels": []}, headers=d["h_emp"])).status_code == 403
    # invalid escalate_to rejected
    assert (await client.post("/api/v1/escalation/rules", json={
        "name": "x", "levels": [{"after_hours": 1, "escalate_to": "bogus"}]}, headers=d["h_admin"])).status_code == 400
    # valid multi-level (stored sorted by after_hours)
    r = (await client.post("/api/v1/escalation/rules", json={
        "name": "Idle lead", "entity_type": "lead", "trigger_condition": "no_activity",
        "levels": [{"after_hours": 72, "escalate_to": "department_head"}, {"after_hours": 24, "escalate_to": "manager"}]},
        headers=d["h_admin"])).json()
    assert r["levels"][0]["after_hours"] == 24 and r["levels"][1]["after_hours"] == 72


@pytest.mark.asyncio
async def test_scan_lead_no_activity_escalates_to_manager(client: AsyncClient, setup: dict, db: AsyncSession):
    d = setup
    await client.post("/api/v1/escalation/rules", json={
        "name": "Idle", "entity_type": "lead", "trigger_condition": "no_activity",
        "levels": [{"after_hours": 24, "escalate_to": "manager"}]}, headers=d["h_admin"])
    lead = await _old_lead(db, d, 30)  # 30h old, no activity, owner=emp whose manager=mgr
    fired = await EscalationEngineService(db).scan(d["org"].id)
    assert fired == 1
    ev = (await db.execute(select(EscalationEvent).filter(EscalationEvent.entity_id == lead.id))).scalars().first()
    assert ev is not None and ev.level == 0 and ev.escalated_to_user_id == d["mgr"].id
    # the manager was notified + a domain event emitted
    notifs = (await db.execute(select(Notification).filter(Notification.user_id == d["mgr"].id))).scalars().all()
    assert any("Escalation" in n.title for n in notifs)
    evs = (await db.execute(select(Event).filter(Event.event_type == "escalation.triggered"))).scalars().all()
    assert len(evs) >= 1
    # re-scan does not duplicate the same level
    assert await EscalationEngineService(db).scan(d["org"].id) == 0


@pytest.mark.asyncio
async def test_multi_level_progression_over_time(client: AsyncClient, setup: dict, db: AsyncSession):
    d = setup
    # dept with the admin as head; emp belongs to it
    dept = Department(organization_id=d["org"].id, name="Sales", head_user_id=d["admin"].id, created_by=d["admin"].id)
    db.add(dept); await db.commit()
    d["emp"].department_id = dept.id; db.add(d["emp"]); await db.commit()
    await client.post("/api/v1/escalation/rules", json={
        "name": "Two level", "entity_type": "lead", "trigger_condition": "no_activity",
        "levels": [{"after_hours": 24, "escalate_to": "manager"}, {"after_hours": 48, "escalate_to": "department_head"}]},
        headers=d["h_admin"])
    lead = await _old_lead(db, d, 30)  # 30h → only level 0 (manager) due
    svc = EscalationEngineService(db)
    await svc.scan(d["org"].id)
    evs = (await db.execute(select(EscalationEvent).filter(EscalationEvent.entity_id == lead.id).order_by(EscalationEvent.level))).scalars().all()
    assert len(evs) == 1 and evs[0].level == 0
    # age the lead to 50h → level 1 (department head) now also fires
    lead.created_at = datetime.now(timezone.utc) - timedelta(hours=50); db.add(lead); await db.commit()
    await svc.scan(d["org"].id)
    evs = (await db.execute(select(EscalationEvent).filter(EscalationEvent.entity_id == lead.id).order_by(EscalationEvent.level))).scalars().all()
    assert len(evs) == 2 and evs[1].level == 1 and evs[1].escalated_to_user_id == d["admin"].id  # dept head


@pytest.mark.asyncio
async def test_task_overdue_escalation(client: AsyncClient, setup: dict, db: AsyncSession):
    d = setup
    await client.post("/api/v1/escalation/rules", json={
        "name": "Overdue tasks", "entity_type": "task", "trigger_condition": "overdue",
        "levels": [{"after_hours": 2, "escalate_to": "manager"}]}, headers=d["h_admin"])
    task = Task(organization_id=d["org"].id, title="Do it", status="Todo", assigned_user_id=d["emp"].id,
                created_by=d["admin"].id, due_date=datetime.now(timezone.utc) - timedelta(hours=5))
    db.add(task); await db.commit()
    fired = await EscalationEngineService(db).scan(d["org"].id)
    assert fired == 1
    ev = (await db.execute(select(EscalationEvent).filter(EscalationEvent.entity_id == task.id))).scalars().first()
    assert ev is not None and ev.entity_type == "task" and ev.escalated_to_user_id == d["mgr"].id


@pytest.mark.asyncio
async def test_conditions_gate_escalation(client: AsyncClient, setup: dict, db: AsyncSession):
    d = setup
    # only escalate high-value idle leads
    await client.post("/api/v1/escalation/rules", json={
        "name": "VIP idle", "entity_type": "lead", "trigger_condition": "no_activity",
        "levels": [{"after_hours": 24, "escalate_to": "manager"}],
        "conditions": {"type": "group", "logic": "and", "children": [
            {"type": "condition", "field": "value", "op": "gte", "value": 10000}]}}, headers=d["h_admin"])
    cheap = await _old_lead(db, d, 30, value=100)
    rich = await _old_lead(db, d, 30, value=50000)
    await EscalationEngineService(db).scan(d["org"].id)
    ids = {str(e.entity_id) for e in (await db.execute(select(EscalationEvent))).scalars().all()}
    assert str(rich.id) in ids and str(cheap.id) not in ids


@pytest.mark.asyncio
async def test_scan_endpoint_dashboard_report(client: AsyncClient, setup: dict, db: AsyncSession):
    d = setup
    await client.post("/api/v1/escalation/rules", json={
        "name": "Idle", "entity_type": "lead", "trigger_condition": "no_activity",
        "levels": [{"after_hours": 24, "escalate_to": "manager"}]}, headers=d["h_admin"])
    await _old_lead(db, d, 30)
    out = (await client.post("/api/v1/escalation/scan", headers=d["h_admin"])).json()
    assert out["escalations"] == 1
    events = (await client.get("/api/v1/escalation/events", headers=d["h_admin"])).json()
    assert len(events) >= 1 and events[0]["level"] == 1  # displayed 1-based
    dash = (await client.get("/api/v1/escalation/dashboard", headers=d["h_admin"])).json()
    assert dash["escalations"] >= 1 and "by_entity" in dash and "last_7_days" in dash
    rep = (await client.get("/api/v1/escalation/report", headers=d["h_admin"])).json()
    assert rep["escalations"] >= 1 and "by_level" in rep
