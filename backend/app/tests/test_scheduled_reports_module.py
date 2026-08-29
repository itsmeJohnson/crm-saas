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
from app.models.notification import Notification
from app.models.report_builder import ReportDefinition
from app.models.scheduled_report import ReportSchedule, ReportDeliveryLog
from app.services.scheduled_report_service import ScheduledReportService, _advance
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
    async def feats(*a, **k): return ["LEAD_MANAGEMENT","CONTACT_MANAGEMENT","FOLLOW_UP_TASKS","SALES_PIPELINE","CLICK_TO_CALL","BASIC_DASHBOARD","DASHBOARD_REPORTS","BULK_IMPORT","GOOGLE_SHEETS_IMPORT","BULK_ASSIGNMENT","ROLE_BASED_ACCESS","CUSTOM_PIPELINE","LEAD_DISTRIBUTION","KPI_DASHBOARD","TARGET_MANAGEMENT","MANAGER_DASHBOARD","TEAM_LEADER_DASHBOARD","CALL_RECORDING","INBOUND_CALLING","OUTBOUND_CALLING","SMS_MESSAGING","EMAIL_MESSAGING","WHATSAPP_MESSAGING","CAMPAIGN_MANAGEMENT","VOICE_BROADCAST","LEAD_CAPTURE","ADVANCED_PIPELINE","LEAD_TRANSFERS","BULK_TRANSFER","SMART_DISTRIBUTION","TEAM_MONITORING","CALL_DISPOSITION","AI_CALL_SUMMARY","AI_FOLLOW_UP","ADVANCED_ANALYTICS","CONVERSION_ANALYTICS","CUSTOM_REPORTS","PRIORITY_SUPPORT","WHITE_LABEL","API_ACCESS"]
    monkeypatch.setattr(feature_guard, "get_active_features", feats)
    return store


@pytest.fixture
async def setup(client: AsyncClient, db: AsyncSession):
    org = await OrganizationRepository(db).create({"name": "Sched Org", "slug": "sched-org"})
    await db.commit()
    ur = UserRepository(db)
    admin = await ur.create_user(org.id, {"email": "admin@sched.com", "hashed_password": get_password_hash("password123"),
        "first_name": "Ad", "last_name": "Min", "role": "OrgAdmin", "is_active": True, "phone": "+911234567890"})
    await db.commit()
    emp = await ur.create_user(org.id, {"email": "emp@sched.com", "hashed_password": get_password_hash("password123"),
        "first_name": "Em", "last_name": "P", "role": "Employee", "is_active": True, "reporting_to_id": admin.id})
    await db.commit()
    stage = (await db.execute(select(PipelineStage).filter(
        PipelineStage.organization_id == org.id, PipelineStage.is_system_default == True))).scalars().first()
    if not stage:
        stage = PipelineStage(organization_id=org.id, name="New", order_position=1, is_system_default=True)
        db.add(stage); await db.commit()
    for i, st in enumerate(["New", "New", "Contacted"]):
        db.add(Lead(organization_id=org.id, last_name=f"L{i}", title="t", status=st, value=100 * (i + 1),
                    assigned_user_id=admin.id, created_by=admin.id, stage_id=stage.id))
    await db.commit()
    h_admin = {"Authorization": f"Bearer {create_access_token(admin.id)}"}
    # a saved report-builder report to schedule
    r = await client.post("/api/v1/report-builder", json={
        "name": "Lead status report", "dataset": "leads",
        "columns": [{"field": "status"}, {"field": "value"}]}, headers=h_admin)
    assert r.status_code == 201, r.text
    return {"org": org, "admin": admin, "emp": emp, "report_id": r.json()["id"], "h_admin": h_admin,
            "h_emp": {"Authorization": f"Bearer {create_access_token(emp.id)}"}}


def _aw(dt):
    """SQLite returns naive datetimes — normalize to aware UTC for comparisons."""
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


def test_advance_frequencies():
    base = datetime(2026, 1, 31, 8, 0, tzinfo=timezone.utc)
    assert _advance("daily", base).day == 1
    assert _advance("weekly", base) == base + timedelta(days=7)
    assert _advance("monthly", base).month == 2 and _advance("monthly", base).day == 28
    q = _advance("quarterly", base)
    assert (q.year, q.month, q.day) == (2026, 4, 30)
    y = _advance("yearly", base)
    assert (y.year, y.month, y.day) == (2027, 1, 31)


@pytest.mark.asyncio
async def test_meta(client: AsyncClient, setup):
    r = await client.get("/api/v1/scheduled-reports/meta", headers=setup["h_admin"])
    body = r.json()
    assert set(body["frequencies"]) == {"daily", "weekly", "monthly", "quarterly", "yearly"}
    assert set(body["formats"]) == {"csv", "xlsx", "pdf"}
    assert set(body["channels"]) == {"notification", "email", "whatsapp"}


@pytest.mark.asyncio
async def test_create_and_validation(client: AsyncClient, setup):
    r = await client.post("/api/v1/scheduled-reports", headers=setup["h_admin"], json={
        "report_id": setup["report_id"], "name": "Quarterly leads", "frequency": "quarterly",
        "formats": ["csv", "xlsx", "pdf"], "channels": ["notification"]})
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["frequency"] == "quarterly" and body["next_run_at"] is not None
    assert body["report_name"] == "Lead status report"

    bad = await client.post("/api/v1/scheduled-reports", headers=setup["h_admin"], json={
        "report_id": setup["report_id"], "name": "x", "frequency": "hourly"})
    assert bad.status_code == 400
    bad = await client.post("/api/v1/scheduled-reports", headers=setup["h_admin"], json={
        "report_id": setup["report_id"], "name": "x", "formats": ["docx"]})
    assert bad.status_code == 400
    bad = await client.post("/api/v1/scheduled-reports", headers=setup["h_admin"], json={
        "report_id": setup["report_id"], "name": "x", "channels": ["pigeon"]})
    assert bad.status_code == 400
    bad = await client.post("/api/v1/scheduled-reports", headers=setup["h_admin"], json={
        "report_id": str(uuid.uuid4()), "name": "x"})
    assert bad.status_code == 404


@pytest.mark.asyncio
async def test_run_now_generates_all_formats_and_notifies(client: AsyncClient, setup, db: AsyncSession):
    r = await client.post("/api/v1/scheduled-reports", headers=setup["h_admin"], json={
        "report_id": setup["report_id"], "name": "All formats", "frequency": "daily",
        "formats": ["csv", "xlsx", "pdf"], "channels": ["notification"],
        "recipients": [str(setup["admin"].id)]})
    sid = r.json()["id"]
    r = await client.post(f"/api/v1/scheduled-reports/{sid}/run", headers=setup["h_admin"])
    assert r.status_code == 200, r.text
    log = r.json()
    assert log["status"] == "success" and log["rows_count"] == 3 and log["triggered_by"] == "manual"
    arts = {a["filename"]: a["size"] for a in log["detail"]["artifacts"]}
    assert "All formats.csv" in arts and "All formats.xlsx" in arts and "All formats.pdf" in arts
    assert all(size > 0 for size in arts.values())
    n = (await db.execute(select(Notification).filter(
        Notification.user_id == setup["admin"].id, Notification.category == "report"))).scalars().all()
    assert any("All formats" in (x.title or "") for x in n)


@pytest.mark.asyncio
async def test_email_and_whatsapp_delivery_via_mocks(client: AsyncClient, setup):
    r = await client.post("/api/v1/scheduled-reports", headers=setup["h_admin"], json={
        "report_id": setup["report_id"], "name": "Multi channel", "frequency": "weekly",
        "formats": ["csv"], "channels": ["email", "whatsapp"],
        "recipients": [str(setup["admin"].id)], "extra_emails": ["boss@example.com"]})
    sid = r.json()["id"]
    r = await client.post(f"/api/v1/scheduled-reports/{sid}/run", headers=setup["h_admin"])
    log = r.json()
    assert log["status"] == "success", log
    assert log["detail"]["email"]["status"] == "sent" and log["detail"]["email"]["sent"] == 2  # admin + extra
    assert log["detail"]["whatsapp"]["status"] == "sent" and log["detail"]["whatsapp"]["sent"] == 1


@pytest.mark.asyncio
async def test_history_and_manual_retry(client: AsyncClient, setup):
    r = await client.post("/api/v1/scheduled-reports", headers=setup["h_admin"], json={
        "report_id": setup["report_id"], "name": "Hist", "channels": ["notification"]})
    sid = r.json()["id"]
    await client.post(f"/api/v1/scheduled-reports/{sid}/run", headers=setup["h_admin"])
    r = await client.get("/api/v1/scheduled-reports/history", headers=setup["h_admin"], params={"schedule_id": sid})
    rows = r.json()
    assert len(rows) == 1 and rows[0]["schedule_name"] == "Hist"
    r = await client.post(f"/api/v1/scheduled-reports/deliveries/{rows[0]['id']}/retry", headers=setup["h_admin"])
    assert r.status_code == 200
    assert r.json()["attempt"] == 2 and r.json()["triggered_by"] == "retry"
    r = await client.get("/api/v1/scheduled-reports/history", headers=setup["h_admin"], params={"schedule_id": sid})
    assert len(r.json()) == 2


@pytest.mark.asyncio
async def test_scan_delivers_due_and_advances(client: AsyncClient, setup, db: AsyncSession):
    r = await client.post("/api/v1/scheduled-reports", headers=setup["h_admin"], json={
        "report_id": setup["report_id"], "name": "Due now", "frequency": "monthly", "channels": ["notification"]})
    sid = uuid.UUID(r.json()["id"])
    s = (await db.execute(select(ReportSchedule).filter(ReportSchedule.id == sid))).scalars().first()
    s.next_run_at = datetime.now(timezone.utc) - timedelta(hours=1)
    db.add(s); await db.commit()

    out = await ScheduledReportService(db).scan(setup["org"].id)
    await db.commit()
    assert out["delivered"] == 1 and out["failed"] == 0
    await db.refresh(s)
    assert _aw(s.next_run_at) > datetime.now(timezone.utc) and s.last_status == "success" and s.run_count == 1


@pytest.mark.asyncio
async def test_scan_retries_then_notifies_owner(client: AsyncClient, setup, db: AsyncSession):
    r = await client.post("/api/v1/scheduled-reports", headers=setup["h_admin"], json={
        "report_id": setup["report_id"], "name": "Doomed", "frequency": "daily",
        "channels": ["notification"], "max_retries": 1})
    sid = uuid.UUID(r.json()["id"])
    # break the underlying report → every delivery fails
    rep = (await db.execute(select(ReportDefinition).filter(
        ReportDefinition.id == uuid.UUID(setup["report_id"])))).scalars().first()
    rep.is_deleted = True
    s = (await db.execute(select(ReportSchedule).filter(ReportSchedule.id == sid))).scalars().first()
    s.next_run_at = datetime.now(timezone.utc) - timedelta(hours=1)
    db.add_all([rep, s]); await db.commit()

    svc = ScheduledReportService(db)
    out1 = await svc.scan(setup["org"].id)  # attempt 1 fails → stays due
    await db.commit(); await db.refresh(s)
    assert out1["failed"] == 1 and s.fail_streak == 1
    assert _aw(s.next_run_at) <= datetime.now(timezone.utc)  # still due for retry

    out2 = await svc.scan(setup["org"].id)  # attempt 2 (== max_retries+1) → give up, notify, advance
    await db.commit(); await db.refresh(s)
    assert out2["failed"] == 1 and s.fail_streak == 0
    assert _aw(s.next_run_at) > datetime.now(timezone.utc)
    logs = (await db.execute(select(ReportDeliveryLog).filter(
        ReportDeliveryLog.schedule_id == sid).order_by(ReportDeliveryLog.created_at))).scalars().all()
    assert [l.attempt for l in logs] == [1, 2] and all(l.status == "failed" for l in logs)
    n = (await db.execute(select(Notification).filter(
        Notification.user_id == setup["admin"].id))).scalars().all()
    assert any("failed" in (x.title or "").lower() for x in n)


@pytest.mark.asyncio
async def test_update_pause_and_delete(client: AsyncClient, setup):
    r = await client.post("/api/v1/scheduled-reports", headers=setup["h_admin"], json={
        "report_id": setup["report_id"], "name": "Editable", "frequency": "weekly"})
    sid = r.json()["id"]
    r = await client.patch(f"/api/v1/scheduled-reports/{sid}", headers=setup["h_admin"],
                           json={"frequency": "yearly", "is_active": False, "formats": ["pdf"]})
    body = r.json()
    assert body["frequency"] == "yearly" and body["is_active"] is False and body["formats"] == ["pdf"]
    r = await client.delete(f"/api/v1/scheduled-reports/{sid}", headers=setup["h_admin"])
    assert r.status_code == 204
    r = await client.get("/api/v1/scheduled-reports", headers=setup["h_admin"])
    assert all(x["id"] != sid for x in r.json())


@pytest.mark.asyncio
async def test_dashboard(client: AsyncClient, setup):
    r = await client.post("/api/v1/scheduled-reports", headers=setup["h_admin"], json={
        "report_id": setup["report_id"], "name": "Dash", "channels": ["notification"]})
    sid = r.json()["id"]
    await client.post(f"/api/v1/scheduled-reports/{sid}/run", headers=setup["h_admin"])
    r = await client.get("/api/v1/scheduled-reports/dashboard", headers=setup["h_admin"])
    d = r.json()
    assert d["schedules"] >= 1 and d["deliveries"] >= 1
    assert d["by_status"]["success"] >= 1 and d["success_rate"] > 0
    assert len(d["upcoming"]) >= 1


@pytest.mark.asyncio
async def test_employee_forbidden(client: AsyncClient, setup):
    r = await client.get("/api/v1/scheduled-reports", headers=setup["h_emp"])
    assert r.status_code == 403
    r = await client.post("/api/v1/scheduled-reports", headers=setup["h_emp"], json={
        "report_id": setup["report_id"], "name": "x"})
    assert r.status_code == 403
