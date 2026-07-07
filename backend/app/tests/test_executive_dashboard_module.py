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
from app.models.support_ticket import SupportTicket
from app.models.dashboard_view import DashboardView
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
    org = await OrganizationRepository(db).create({"name": "Exec Org", "slug": "exec-org"})
    await db.commit()
    ur = UserRepository(db)
    admin = await ur.create_user(org.id, {"email": "admin@exec.com", "hashed_password": get_password_hash("password123"),
        "first_name": "Ad", "last_name": "Min", "role": "OrgAdmin", "is_active": True})
    await db.commit()
    emp = await ur.create_user(org.id, {"email": "emp@exec.com", "hashed_password": get_password_hash("password123"),
        "first_name": "Em", "last_name": "P", "role": "Employee", "is_active": True, "reporting_to_id": admin.id})
    await db.commit()
    stage = (await db.execute(select(PipelineStage).filter(
        PipelineStage.organization_id == org.id, PipelineStage.is_system_default == True))).scalars().first()
    if not stage:
        stage = PipelineStage(organization_id=org.id, name="New", order_position=1, is_system_default=True)
        db.add(stage); await db.commit()
    # a lead with open pipeline value (drives forecast) and a resolved support ticket (drives CSAT)
    now = datetime.now(timezone.utc)
    db.add(Lead(organization_id=org.id, last_name="Whale", title="Big deal", status="New", value=100000,
                source="Website", created_by=admin.id, assigned_user_id=admin.id, stage_id=stage.id))
    db.add(SupportTicket(organization_id=org.id, created_by_id=admin.id, ticket_number="T-1",
                         subject="x", description="y", status="Resolved", priority="High",
                         resolved_at=now, created_at=now - timedelta(hours=3)))
    await db.commit()
    return {"org": org, "admin": admin, "emp": emp,
            "h_admin": {"Authorization": f"Bearer {create_access_token(admin.id)}"},
            "h_emp": {"Authorization": f"Bearer {create_access_token(emp.id)}"}}


@pytest.mark.asyncio
async def test_catalog_and_permissions(client: AsyncClient, setup: dict):
    d = setup
    cat = (await client.get("/api/v1/executive-dashboard/catalog", headers=d["h_admin"])).json()
    ids = {w["id"] for w in cat["widgets"]}
    # the four genuinely-new executive widgets exist alongside the reused ones
    assert {"forecast", "cash_flow", "customer_satisfaction", "ai_insights"} <= ids
    assert "revenue" in ids and "sla_compliance" in ids and len(ids) == 21
    assert "ceo" in cat["personas"] and "finance" in cat["personas"]
    assert cat["persona_layouts"]["finance"]  # non-empty bundle
    # employees cannot open the executive dashboard
    assert (await client.get("/api/v1/executive-dashboard/dashboard", headers=d["h_emp"])).status_code == 403


@pytest.mark.asyncio
async def test_ceo_dashboard_composes_all_blocks(client: AsyncClient, setup: dict):
    d = setup
    res = (await client.get("/api/v1/executive-dashboard/dashboard", params={"persona": "ceo"}, headers=d["h_admin"])).json()
    assert res["persona"] == "ceo" and res["scope"] == "organization" and "from" in res and "to" in res
    blocks = res["blocks"]
    # the CEO bundle includes the exec widgets, each composed without error
    for wid in ("revenue", "collections", "forecast", "cash_flow", "customer_satisfaction", "ai_insights"):
        assert wid in blocks and "error" not in blocks[wid], (wid, blocks.get(wid))
    # forecast reflects the open pipeline lead (value 100000)
    assert blocks["forecast"]["open_pipeline_value"] == 100000.0
    assert "projected_total" in blocks["forecast"]
    # CSAT proxy derives from support tickets (1 resolved → 100%)
    assert blocks["customer_satisfaction"]["resolution_rate"] == 100.0
    # AI insights is flagged ready and returns a non-empty list
    assert blocks["ai_insights"]["ai_ready"] is True and len(blocks["ai_insights"]["insights"]) >= 1


@pytest.mark.asyncio
async def test_persona_bundles_and_custom_widgets(client: AsyncClient, setup: dict):
    d = setup
    fin = (await client.get("/api/v1/executive-dashboard/dashboard", params={"persona": "finance"}, headers=d["h_admin"])).json()
    assert set(fin["widgets"]) == set(["revenue", "collections", "cash_flow", "forecast", "target_achievement"])
    # a custom widget selection via POST is honoured (Widget Configuration)
    custom = (await client.post("/api/v1/executive-dashboard/dashboard",
              json={"widgets": ["revenue", "sla_compliance"], "scope": "department"}, headers=d["h_admin"])).json()
    assert custom["widgets"] == ["revenue", "sla_compliance"] and custom["scope"] == "department"
    assert set(custom["blocks"].keys()) == {"revenue", "sla_compliance"}


@pytest.mark.asyncio
async def test_saved_views_crud_and_default(client: AsyncClient, setup: dict, db: AsyncSession):
    d = setup
    # employee cannot create a view
    assert (await client.post("/api/v1/executive-dashboard/views",
            json={"name": "x", "persona": "ceo"}, headers=d["h_emp"])).status_code == 403
    v = (await client.post("/api/v1/executive-dashboard/views", json={
        "name": "My Board", "persona": "sales", "scope": "organization",
        "widgets": ["revenue", "pipeline"], "is_default": True}, headers=d["h_admin"])).json()
    assert v["is_default"] is True and v["widgets"] == ["revenue", "pipeline"]
    # a second default flips the first off
    v2 = (await client.post("/api/v1/executive-dashboard/views", json={
        "name": "Board 2", "persona": "finance", "is_default": True}, headers=d["h_admin"])).json()
    views = (await client.get("/api/v1/executive-dashboard/views", headers=d["h_admin"])).json()
    defaults = [x for x in views if x["is_default"]]
    assert len(defaults) == 1 and defaults[0]["id"] == v2["id"]
    # update + delete
    await client.patch(f"/api/v1/executive-dashboard/views/{v['id']}", json={"name": "Renamed"}, headers=d["h_admin"])
    assert (await client.delete(f"/api/v1/executive-dashboard/views/{v['id']}", headers=d["h_admin"])).status_code == 204
    views2 = (await client.get("/api/v1/executive-dashboard/views", headers=d["h_admin"])).json()
    assert all(x["id"] != v["id"] for x in views2)


@pytest.mark.asyncio
async def test_export_and_date_filter(client: AsyncClient, setup: dict):
    d = setup
    exp = await client.get("/api/v1/executive-dashboard/export", params={"persona": "finance"}, headers=d["h_admin"])
    assert exp.status_code == 200 and "Executive dashboard" in exp.text and "Revenue" in exp.text
    # a historical window still composes (zeroed) without error
    past = (await client.get("/api/v1/executive-dashboard/dashboard",
            params={"persona": "sales", "date_from": "2020-01-01", "date_to": "2020-01-31"}, headers=d["h_admin"])).json()
    assert past["from"] == "2020-01-01" and past["to"] == "2020-01-31"
    assert "revenue" in past["blocks"]
