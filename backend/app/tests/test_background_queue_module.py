import pytest
import uuid
from datetime import datetime, timezone, timedelta
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.core.security import create_access_token, get_password_hash
from app.repositories.organization import OrganizationRepository
from app.repositories.user_repository import UserRepository
from app.models.pipeline import PipelineStage
from app.models.lead import Lead
from app.models.queue import QueueJob, QueueWorker
from app.services.queue_service import QueueService
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
async def setup(db: AsyncSession):
    org = await OrganizationRepository(db).create({"name": "Q Org", "slug": "q-org"})
    await db.commit()
    ur = UserRepository(db)
    admin = await ur.create_user(org.id, {"email": "admin@q.com", "hashed_password": get_password_hash("password123"),
        "first_name": "Ad", "last_name": "Min", "role": "OrgAdmin", "is_active": True})
    await db.commit()
    emp = await ur.create_user(org.id, {"email": "emp@q.com", "hashed_password": get_password_hash("password123"),
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
async def test_catalog_enqueue_and_permissions(client: AsyncClient, setup: dict):
    d = setup
    cat = (await client.get("/api/v1/queue/catalog", headers=d["h_admin"])).json()
    assert "ai" in cat["queues"] and "send_email" in cat["job_types"]
    assert cat["queue_for_type"]["ai_task"] == "ai"
    # employee cannot enqueue
    assert (await client.post("/api/v1/queue/jobs", json={"job_type": "noop"}, headers=d["h_emp"])).status_code == 403
    # invalid job_type rejected
    assert (await client.post("/api/v1/queue/jobs", json={"job_type": "bogus"}, headers=d["h_admin"])).status_code == 400
    # ai_task auto-routes to the ai queue
    job = (await client.post("/api/v1/queue/jobs", json={"job_type": "ai_task", "payload": {"prompt": "hi"}}, headers=d["h_admin"])).json()
    assert job["queue"] == "ai" and job["status"] == "queued"


@pytest.mark.asyncio
async def test_priority_ordering_and_process_success(client: AsyncClient, setup: dict, db: AsyncSession):
    d = setup
    await client.post("/api/v1/queue/jobs", json={"job_type": "noop", "priority": 1}, headers=d["h_admin"])
    hi = (await client.post("/api/v1/queue/jobs", json={"job_type": "ai_task", "priority": 9, "payload": {"prompt": "x"}}, headers=d["h_admin"])).json()
    # the worker claims the highest-priority job first
    processed = await QueueService(db).process_once(organization_id=d["org"].id, worker_id=None)
    assert processed["id"] == hi["id"] and processed["status"] == "succeeded"
    assert processed["result"]["model"] == "mock-ai"


@pytest.mark.asyncio
async def test_retry_then_dead_letter(client: AsyncClient, setup: dict, db: AsyncSession):
    d = setup
    job = (await client.post("/api/v1/queue/jobs", json={
        "job_type": "always_fail", "max_attempts": 2, "payload": {"reason": "nope"}}, headers=d["h_admin"])).json()
    svc = QueueService(db)
    # attempt 1 → fails → requeued (status queued) with backoff run_at
    r1 = await svc.process_once(organization_id=d["org"].id)
    assert r1["status"] == "queued" and r1["attempts"] == 1 and r1["error"]
    # force run_at due, attempt 2 → exhausted → dead_letter
    row = await db.get(QueueJob, uuid.UUID(job["id"]))
    row.run_at = datetime.now(timezone.utc) - timedelta(seconds=1); db.add(row); await db.flush()
    r2 = await svc.process_once(organization_id=d["org"].id)
    assert r2["status"] == "dead_letter" and r2["attempts"] == 2
    # shows up in the DLQ endpoint
    dlq = (await client.get("/api/v1/queue/dead-letter", headers=d["h_admin"])).json()
    assert any(j["id"] == job["id"] for j in dlq)
    # retry resets it to queued
    rq = (await client.post(f"/api/v1/queue/jobs/{job['id']}/retry", headers=d["h_admin"])).json()
    assert rq["status"] == "queued" and rq["attempts"] == 0


@pytest.mark.asyncio
async def test_scheduled_job_not_claimed_early(client: AsyncClient, setup: dict, db: AsyncSession):
    d = setup
    future = (datetime.now(timezone.utc) + timedelta(hours=1)).isoformat()
    job = (await client.post("/api/v1/queue/jobs", json={"job_type": "noop", "run_at": future}, headers=d["h_admin"])).json()
    # nothing due → worker returns None
    assert await QueueService(db).process_once(organization_id=d["org"].id) is None
    # it appears under scheduled
    sched = (await client.get("/api/v1/queue/jobs/scheduled", headers=d["h_admin"])).json()
    assert any(j["id"] == job["id"] for j in sched)


@pytest.mark.asyncio
async def test_cancel_queued_job(client: AsyncClient, setup: dict):
    d = setup
    future = (datetime.now(timezone.utc) + timedelta(hours=1)).isoformat()
    job = (await client.post("/api/v1/queue/jobs", json={"job_type": "noop", "run_at": future}, headers=d["h_admin"])).json()
    cancelled = (await client.post(f"/api/v1/queue/jobs/{job['id']}/cancel", headers=d["h_admin"])).json()
    assert cancelled["status"] == "cancelled"
    # cannot cancel again (not queued)
    assert (await client.post(f"/api/v1/queue/jobs/{job['id']}/cancel", headers=d["h_admin"])).status_code == 409


@pytest.mark.asyncio
async def test_report_and_export_handlers(client: AsyncClient, setup: dict, db: AsyncSession):
    d = setup
    # seed a lead so the export has a row
    db.add(Lead(organization_id=d["org"].id, last_name="Q", title="Deal", status="New", value=1000,
                created_by=d["admin"].id, stage_id=d["stage"].id))
    await db.commit()
    rep_job = (await client.post("/api/v1/queue/jobs", json={"job_type": "generate_report", "payload": {"report_type": "lead_summary"}}, headers=d["h_admin"])).json()
    exp_job = (await client.post("/api/v1/queue/jobs", json={"job_type": "generate_export", "payload": {"entity": "leads"}}, headers=d["h_admin"])).json()
    svc = QueueService(db)
    await svc.process_once(organization_id=d["org"].id)  # highest priority tie → order by run_at/created
    await svc.process_once(organization_id=d["org"].id)
    rep = await svc.get(d["admin"], uuid.UUID(rep_job["id"]))
    exp = await svc.get(d["admin"], uuid.UUID(exp_job["id"]))
    assert rep["status"] == "succeeded" and "summary" in rep["result"]
    assert exp["status"] == "succeeded" and exp["result"]["rows"] >= 1 and "csv" in exp["result"]


@pytest.mark.asyncio
async def test_worker_registration_and_monitoring(client: AsyncClient, setup: dict, db: AsyncSession):
    d = setup
    svc = QueueService(db)
    w = await svc.register_worker("test-worker", queues=["default", "ai"])
    await db.commit()
    # process a job as that worker → jobs_processed increments, worker visible
    await client.post("/api/v1/queue/jobs", json={"job_type": "noop"}, headers=d["h_admin"])
    await svc.process_once(organization_id=d["org"].id, worker_id=w.id)
    await svc.heartbeat(w.id, status_val="busy", processed_delta=1)
    await db.commit()
    workers = (await client.get("/api/v1/queue/workers", headers=d["h_admin"])).json()
    assert any(x["name"] == "test-worker" and x["jobs_processed"] >= 1 for x in workers)
    # dashboard + report
    dash = (await client.get("/api/v1/queue/dashboard", headers=d["h_admin"])).json()
    assert "pending" in dash and "dead_letter" in dash and "recent" in dash
    rep = (await client.get("/api/v1/queue/report", headers=d["h_admin"])).json()
    assert "by_queue" in rep and "success_rate" in rep and rep["total"] >= 1


@pytest.mark.asyncio
async def test_job_history_and_purge(client: AsyncClient, setup: dict, db: AsyncSession):
    d = setup
    await client.post("/api/v1/queue/jobs", json={"job_type": "noop"}, headers=d["h_admin"])
    await QueueService(db).process_once(organization_id=d["org"].id)
    # history (all jobs) + filter by status
    done = (await client.get("/api/v1/queue/jobs", params={"status": "succeeded"}, headers=d["h_admin"])).json()
    assert len(done) >= 1 and done[0]["status"] == "succeeded"
    # purge succeeded
    purged = (await client.post("/api/v1/queue/purge", json={"status": "succeeded"}, headers=d["h_admin"])).json()
    assert purged["purged"] >= 1
    assert len((await client.get("/api/v1/queue/jobs", params={"status": "succeeded"}, headers=d["h_admin"])).json()) == 0
