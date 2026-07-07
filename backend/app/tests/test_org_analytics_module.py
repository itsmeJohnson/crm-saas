import pytest
import uuid
from datetime import date, datetime, timezone, timedelta
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.core.security import create_access_token, get_password_hash
from app.repositories.organization import OrganizationRepository
from app.repositories.user_repository import UserRepository
from app.models.user import User
from app.models.lead import Lead
from app.models.activity import Activity
from app.models.task import Task
from app.models.attendance import AttendanceRecord
from app.models.pipeline import PipelineStage
from app.core.redis import redis_client


@pytest.fixture(autouse=True)
def mock_redis(monkeypatch):
    storage = {}

    async def mock_get(key): return storage.get(key)
    async def mock_set(key, value, ex=300): storage[key] = value; return True
    async def mock_delete(key): storage.pop(key, None); return True

    monkeypatch.setattr(redis_client, "get", mock_get)
    monkeypatch.setattr(redis_client, "set", mock_set)
    monkeypatch.setattr(redis_client, "delete", mock_delete)

    from app.dependencies import feature_guard

    async def mock_features(*a, **k):
        return ["LEAD_MANAGEMENT", "ROLE_BASED_ACCESS"]

    monkeypatch.setattr(feature_guard, "get_active_features", mock_features)
    return storage


@pytest.fixture
async def setup(db: AsyncSession):
    org_repo = OrganizationRepository(db)
    user_repo = UserRepository(db)
    org = await org_repo.create({"name": "OA Org", "slug": "oa-org"})
    await db.commit()
    admin = await user_repo.create_user(org.id, {
        "email": "admin@oa.com", "hashed_password": get_password_hash("password123"),
        "first_name": "Admin", "last_name": "One", "role": "OrgAdmin", "is_active": True})
    await db.commit()
    emp = await user_repo.create_user(org.id, {
        "email": "emp@oa.com", "hashed_password": get_password_hash("password123"),
        "first_name": "Emp", "last_name": "Two", "role": "Employee", "is_active": True, "reporting_to_id": admin.id})
    await db.commit()
    stage = (await db.execute(select(PipelineStage).filter(
        PipelineStage.organization_id == org.id, PipelineStage.is_system_default == True))).scalars().first()
    if not stage:
        stage = PipelineStage(organization_id=org.id, name="New", order_position=1, is_system_default=True)
        db.add(stage); await db.commit()
    return {
        "org": org, "admin": admin, "emp": emp, "stage": stage,
        "h_admin": {"Authorization": f"Bearer {create_access_token(admin.id)}"},
        "h_emp": {"Authorization": f"Bearer {create_access_token(emp.id)}"},
    }


@pytest.mark.asyncio
async def test_overview_and_permissions(client: AsyncClient, setup: dict, db: AsyncSession):
    data = setup
    now = datetime.now(timezone.utc)
    db.add(Lead(organization_id=data["org"].id, last_name="A", title="A", status="Won", value=1000,
                created_by=data["emp"].id, assigned_user_id=data["emp"].id, stage_id=data["stage"].id, created_at=now))
    db.add(Lead(organization_id=data["org"].id, last_name="B", title="B", status="New",
                created_by=data["emp"].id, assigned_user_id=data["emp"].id, stage_id=data["stage"].id, created_at=now))
    db.add(Activity(organization_id=data["org"].id, activity_type="Call", subject="c",
                    assigned_user_id=data["emp"].id, created_by=data["emp"].id, created_at=now))
    db.add(AttendanceRecord(organization_id=data["org"].id, user_id=data["emp"].id, work_date=date.today(),
                            status="present", clock_in_at=now))
    await db.commit()

    ov = (await client.get("/api/v1/org-analytics/overview", headers=data["h_admin"])).json()
    assert ov["leads"] == 2 and ov["converted"] == 1 and ov["conversion_rate"] == 50.0
    assert ov["revenue"] == 1000.0 and ov["calls"] == 1
    assert ov["headcount"] == 2 and ov["present_today"] == 1

    # employees cannot access org analytics
    assert (await client.get("/api/v1/org-analytics/overview", headers=data["h_emp"])).status_code == 403


@pytest.mark.asyncio
async def test_health_composite(client: AsyncClient, setup: dict, db: AsyncSession):
    data = setup
    h = (await client.get("/api/v1/org-analytics/health", headers=data["h_admin"])).json()
    assert 0 <= h["score"] <= 100
    assert h["rating"] in ("Excellent", "Good", "Fair", "Needs attention")
    names = {c["name"] for c in h["components"]}
    assert {"Attendance", "Target attainment", "Task completion", "Lead conversion"} == names


@pytest.mark.asyncio
async def test_heatmap_trend_domain_and_export(client: AsyncClient, setup: dict, db: AsyncSession):
    data = setup
    now = datetime.now(timezone.utc)
    for i in range(3):
        db.add(Activity(organization_id=data["org"].id, activity_type="Call", subject=f"c{i}",
                        assigned_user_id=data["emp"].id, created_by=data["emp"].id, created_at=now))
    await db.commit()

    hm = (await client.get("/api/v1/org-analytics/heatmap", headers=data["h_admin"])).json()
    assert len(hm["grid"]) == 7 and len(hm["grid"][0]) == 24
    assert hm["peak"]["count"] >= 3

    tr = (await client.get("/api/v1/org-analytics/trend", params={"granularity": "monthly", "count": 3}, headers=data["h_admin"])).json()
    assert tr["granularity"] == "monthly" and len(tr["series"]) == 3
    # invalid granularity rejected
    assert (await client.get("/api/v1/org-analytics/trend", params={"granularity": "hourly"}, headers=data["h_admin"])).status_code == 400

    # domain passthrough (department analytics reused)
    dep = (await client.get("/api/v1/org-analytics/domain/department", headers=data["h_admin"])).json()
    assert isinstance(dep, list)
    assert (await client.get("/api/v1/org-analytics/domain/galaxy", headers=data["h_admin"])).status_code == 400

    # export CSV
    r = await client.get("/api/v1/org-analytics/export", headers=data["h_admin"])
    assert r.status_code == 200 and "Organization Analytics" in r.text
