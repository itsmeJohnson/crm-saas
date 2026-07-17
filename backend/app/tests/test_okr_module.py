import pytest
import uuid
from datetime import date, datetime, timezone
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.core.security import create_access_token, get_password_hash
from app.repositories.organization import OrganizationRepository
from app.repositories.user_repository import UserRepository
from app.models.lead import Lead
from app.models.pipeline import PipelineStage
from app.models.notification import Notification
from app.models.okr import Objective, OKRReview
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
    org = await OrganizationRepository(db).create({"name": "OKR Org", "slug": "okr-org"})
    await db.commit()
    ur = UserRepository(db)
    admin = await ur.create_user(org.id, {"email": "admin@okr.com", "hashed_password": get_password_hash("password123"),
        "first_name": "Ad", "last_name": "Min", "role": "OrgAdmin", "is_active": True})
    await db.commit()
    emp = await ur.create_user(org.id, {"email": "emp@okr.com", "hashed_password": get_password_hash("password123"),
        "first_name": "Em", "last_name": "P", "role": "Employee", "is_active": True, "reporting_to_id": admin.id})
    await db.commit()
    stage = (await db.execute(select(PipelineStage).filter(
        PipelineStage.organization_id == org.id, PipelineStage.is_system_default == True))).scalars().first()
    if not stage:
        stage = PipelineStage(organization_id=org.id, name="New", order_position=1, is_system_default=True)
        db.add(stage); await db.commit()
    now = datetime.now(timezone.utc)
    # 1 converted lead worth 1000 assigned to admin → leads_converted=1, revenue=1000
    db.add(Lead(organization_id=org.id, last_name="A", title="t", status="Converted", value=1000,
                converted_at=now, assigned_user_id=admin.id, created_by=admin.id, stage_id=stage.id))
    await db.commit()
    return {"org": org, "admin": admin, "emp": emp,
            "h_admin": {"Authorization": f"Bearer {create_access_token(admin.id)}"},
            "h_emp": {"Authorization": f"Bearer {create_access_token(emp.id)}"}}


def _q():
    return (date.today().month - 1) // 3 + 1


@pytest.mark.asyncio
async def test_meta(client: AsyncClient, setup):
    r = await client.get("/api/v1/okr/meta", headers=setup["h_admin"])
    assert r.status_code == 200
    body = r.json()
    assert "company" in body["levels"] and "quarterly" in body["cycle_types"]
    assert "leads_converted" in body["metrics"]


@pytest.mark.asyncio
async def test_create_company_objective_with_krs(client: AsyncClient, setup):
    r = await client.post("/api/v1/okr", headers=setup["h_admin"], json={
        "title": "Grow revenue", "level": "company", "cycle_type": "quarterly",
        "key_results": [
            {"title": "Close 4 deals", "kind": "metric", "metric": "leads_converted", "target_value": 4},
            {"title": "Launch pricing page", "kind": "manual", "target_value": 1},
        ]})
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["level"] == "company" and body["cycle_quarter"] == _q()
    assert len(body["key_results"]) == 2
    metric_kr = next(k for k in body["key_results"] if k["kind"] == "metric")
    assert metric_kr["current_value"] == 1  # 1 converted lead
    assert metric_kr["progress"] == 25.0
    assert body["progress"] == 12.5  # equal weights (25 + 0) / 2


@pytest.mark.asyncio
async def test_employee_cannot_create_company_objective(client: AsyncClient, setup):
    r = await client.post("/api/v1/okr", headers=setup["h_emp"], json={
        "title": "Nope", "level": "company", "key_results": []})
    assert r.status_code == 403


@pytest.mark.asyncio
async def test_individual_objective_and_checkin_completion(client: AsyncClient, setup, db: AsyncSession):
    r = await client.post("/api/v1/okr", headers=setup["h_emp"], json={
        "title": "Personal growth", "level": "individual", "cycle_type": "quarterly",
        "key_results": [{"title": "Finish 5 trainings", "kind": "manual", "target_value": 5}]})
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["user_id"] == str(setup["emp"].id) and body["owner_id"] == str(setup["emp"].id)
    kr_id = body["key_results"][0]["id"]

    r = await client.post(f"/api/v1/okr/key-results/{kr_id}/checkin", headers=setup["h_emp"],
                          json={"value": 2, "confidence": 80, "comment": "On it"})
    assert r.status_code == 200
    assert r.json()["progress"] == 40.0

    r = await client.post(f"/api/v1/okr/key-results/{kr_id}/checkin", headers=setup["h_emp"], json={"value": 5})
    assert r.status_code == 200
    done = r.json()
    assert done["progress"] == 100.0 and done["status"] == "completed" and done["status_label"] == "achieved"
    # completion notified the owner
    n = (await db.execute(select(Notification).filter(
        Notification.user_id == setup["emp"].id, Notification.category == "okr"))).scalars().all()
    assert any("completed" in (x.title or "").lower() for x in n)
    # check-ins were recorded as reviews
    reviews = (await db.execute(select(OKRReview).filter(
        OKRReview.organization_id == setup["org"].id, OKRReview.review_type == "checkin"))).scalars().all()
    assert len(reviews) == 2


@pytest.mark.asyncio
async def test_checkin_rejected_on_metric_kr(client: AsyncClient, setup):
    r = await client.post("/api/v1/okr", headers=setup["h_admin"], json={
        "title": "Pipeline", "level": "company",
        "key_results": [{"title": "Convert leads", "kind": "metric", "metric": "leads_converted", "target_value": 10}]})
    kr_id = r.json()["key_results"][0]["id"]
    r = await client.post(f"/api/v1/okr/key-results/{kr_id}/checkin", headers=setup["h_admin"], json={"value": 3})
    assert r.status_code == 400


@pytest.mark.asyncio
async def test_reviews_and_manager_feedback(client: AsyncClient, setup, db: AsyncSession):
    r = await client.post("/api/v1/okr", headers=setup["h_emp"], json={
        "title": "My OKR", "level": "individual",
        "key_results": [{"title": "Do things", "kind": "manual", "target_value": 10}]})
    oid = r.json()["id"]
    # self review
    r = await client.post(f"/api/v1/okr/{oid}/reviews", headers=setup["h_emp"],
                          json={"review_type": "review", "rating": 4, "comment": "Going well"})
    assert r.status_code == 201
    # employee cannot leave manager feedback
    r = await client.post(f"/api/v1/okr/{oid}/reviews", headers=setup["h_emp"],
                          json={"review_type": "feedback", "comment": "sneaky"})
    assert r.status_code == 403
    # manager feedback works and notifies the owner
    r = await client.post(f"/api/v1/okr/{oid}/reviews", headers=setup["h_admin"],
                          json={"review_type": "feedback", "rating": 5, "comment": "Great pace, keep going"})
    assert r.status_code == 201
    r = await client.get(f"/api/v1/okr/{oid}/reviews", headers=setup["h_emp"])
    assert r.status_code == 200
    types = [x["review_type"] for x in r.json()]
    assert "review" in types and "feedback" in types
    n = (await db.execute(select(Notification).filter(
        Notification.user_id == setup["emp"].id, Notification.category == "okr"))).scalars().all()
    assert any("feedback" in (x.title or "").lower() for x in n)


@pytest.mark.asyncio
async def test_visibility_scoping(client: AsyncClient, setup):
    # admin's individual objective is hidden from the employee; company is visible
    await client.post("/api/v1/okr", headers=setup["h_admin"], json={
        "title": "Admin private", "level": "individual", "user_id": str(setup["admin"].id),
        "key_results": [{"title": "x", "kind": "manual", "target_value": 1}]})
    await client.post("/api/v1/okr", headers=setup["h_admin"], json={
        "title": "Company wide", "level": "company",
        "key_results": [{"title": "y", "kind": "manual", "target_value": 1}]})
    r = await client.get("/api/v1/okr", headers=setup["h_emp"])
    titles = [o["title"] for o in r.json()]
    assert "Company wide" in titles and "Admin private" not in titles


@pytest.mark.asyncio
async def test_tree_alignment(client: AsyncClient, setup):
    r = await client.post("/api/v1/okr", headers=setup["h_admin"], json={
        "title": "Company north star", "level": "company",
        "key_results": [{"title": "x", "kind": "manual", "target_value": 1}]})
    parent_id = r.json()["id"]
    r = await client.post("/api/v1/okr", headers=setup["h_admin"], json={
        "title": "Aligned child", "level": "individual", "user_id": str(setup["admin"].id),
        "parent_id": parent_id, "key_results": [{"title": "y", "kind": "manual", "target_value": 1}]})
    assert r.status_code == 201
    r = await client.get("/api/v1/okr/tree", headers=setup["h_admin"])
    roots = r.json()
    node = next(x for x in roots if x["title"] == "Company north star")
    assert [c["title"] for c in node["children"]] == ["Aligned child"]


@pytest.mark.asyncio
async def test_dashboard_and_report(client: AsyncClient, setup):
    await client.post("/api/v1/okr", headers=setup["h_admin"], json={
        "title": "Dash obj", "level": "company", "cycle_type": "annual",
        "key_results": [{"title": "x", "kind": "manual", "target_value": 2, "current_value": 1}]})
    r = await client.get("/api/v1/okr/dashboard", headers=setup["h_admin"])
    assert r.status_code == 200
    d = r.json()
    assert d["total"] >= 1 and "by_level" in d and "avg_progress" in d
    r = await client.get("/api/v1/okr/report", headers=setup["h_admin"])
    assert r.status_code == 200
    rep = r.json()
    assert rep["count"] >= 1 and any(b["level"] == "company" for b in rep["by_level"])


@pytest.mark.asyncio
async def test_key_result_crud(client: AsyncClient, setup):
    r = await client.post("/api/v1/okr", headers=setup["h_admin"], json={
        "title": "KR CRUD", "level": "company", "key_results": []})
    oid = r.json()["id"]
    r = await client.post(f"/api/v1/okr/{oid}/key-results", headers=setup["h_admin"],
                          json={"title": "Added later", "kind": "manual", "target_value": 4, "weight": 2})
    assert r.status_code == 200
    kr = r.json()["key_results"][0]
    r = await client.patch(f"/api/v1/okr/key-results/{kr['id']}", headers=setup["h_admin"],
                           json={"target_value": 8, "title": "Renamed"})
    assert r.status_code == 200
    assert r.json()["key_results"][0]["title"] == "Renamed"
    r = await client.delete(f"/api/v1/okr/key-results/{kr['id']}", headers=setup["h_admin"])
    assert r.status_code == 200
    assert r.json()["key_results"] == []


@pytest.mark.asyncio
async def test_update_and_delete_objective(client: AsyncClient, setup):
    r = await client.post("/api/v1/okr", headers=setup["h_admin"], json={
        "title": "To change", "level": "company",
        "key_results": [{"title": "x", "kind": "manual", "target_value": 1}]})
    oid = r.json()["id"]
    r = await client.patch(f"/api/v1/okr/{oid}", headers=setup["h_admin"],
                           json={"title": "Changed", "status": "cancelled"})
    assert r.status_code == 200 and r.json()["title"] == "Changed" and r.json()["status"] == "cancelled"
    r = await client.delete(f"/api/v1/okr/{oid}", headers=setup["h_admin"])
    assert r.status_code == 204
    r = await client.get(f"/api/v1/okr/{oid}", headers=setup["h_admin"])
    assert r.status_code == 404


@pytest.mark.asyncio
async def test_scan_completes_achieved_objectives(client: AsyncClient, setup, db: AsyncSession):
    r = await client.post("/api/v1/okr", headers=setup["h_admin"], json={
        "title": "Already done", "level": "company",
        "key_results": [{"title": "x", "kind": "manual", "target_value": 2, "current_value": 2}]})
    oid = r.json()["id"]
    r = await client.post("/api/v1/okr/scan", headers=setup["h_admin"])
    assert r.status_code == 200
    assert r.json()["completed"] >= 1
    o = (await db.execute(select(Objective).filter(Objective.id == uuid.UUID(oid)))).scalars().first()
    assert o.status == "completed"


@pytest.mark.asyncio
async def test_scan_forbidden_for_employee(client: AsyncClient, setup):
    r = await client.post("/api/v1/okr/scan", headers=setup["h_emp"])
    assert r.status_code == 403
