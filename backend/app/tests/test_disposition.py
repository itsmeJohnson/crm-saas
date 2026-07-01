import pytest
import uuid
import json
from datetime import datetime, timezone, timedelta
from fastapi import status
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.core.security import create_access_token, get_password_hash
from app.repositories.organization import OrganizationRepository
from app.repositories.user_repository import UserRepository
from app.repositories.audit_repository import AuditRepository
from app.models.user import User
from app.models.lead import Lead
from app.models.pipeline import PipelineStage
from app.core.redis import redis_client

@pytest.fixture(autouse=True)
def mock_redis(monkeypatch):
    storage = {}
    async def mock_get(key: str) -> str | None:
        return storage.get(key)
    async def mock_set(key: str, value: str, ex: int = 300) -> bool:
        storage[key] = value
        return True
    async def mock_delete(key: str) -> bool:
        storage.pop(key, None)
        return True
    
    monkeypatch.setattr(redis_client, "get", mock_get)
    monkeypatch.setattr(redis_client, "set", mock_set)
    monkeypatch.setattr(redis_client, "delete", mock_delete)

    from app.dependencies import feature_guard
    async def mock_get_active_features(*args, **kwargs) -> list[str]:
        return ["OUTBOUND_CALLING", "INBOUND_CALLING", "CLICK_TO_CALL", "CALL_RECORDING", "CALL_DISPOSITION"]
    monkeypatch.setattr(feature_guard, "get_active_features", mock_get_active_features)

    return storage

@pytest.fixture
async def setup_disposition_data(db: AsyncSession):
    org_repo = OrganizationRepository(db)
    user_repo = UserRepository(db)

    # 1. Create Organization
    org = await org_repo.create({"name": "Disp Org", "slug": "disp-org"})
    await db.commit()

    # 2. Create Super Admin (OrgAdmin)
    super_admin = await user_repo.create_user(org.id, {
        "email": "super_admin@disp.com",
        "hashed_password": get_password_hash("password123"),
        "first_name": "Super",
        "last_name": "Admin",
        "role": "OrgAdmin",
        "is_active": True
    })
    await db.commit()

    # 3. Create Manager
    manager = await user_repo.create_user(org.id, {
        "email": "manager@disp.com",
        "hashed_password": get_password_hash("password123"),
        "first_name": "Manager",
        "last_name": "One",
        "role": "Manager",
        "is_active": True,
        "reporting_to_id": super_admin.id
    })
    await db.commit()

    # 4. Create Team Leader (TL)
    tl = await user_repo.create_user(org.id, {
        "email": "tl@disp.com",
        "hashed_password": get_password_hash("password123"),
        "first_name": "TL",
        "last_name": "One",
        "role": "Employee",
        "is_active": True,
        "reporting_to_id": manager.id
    })
    await db.commit()

    # 5. Create Telecaller (Agent)
    agent = await user_repo.create_user(org.id, {
        "email": "agent@disp.com",
        "hashed_password": get_password_hash("password123"),
        "first_name": "Agent",
        "last_name": "One",
        "role": "Employee",
        "is_active": True,
        "reporting_to_id": tl.id
    })
    await db.commit()

    # Create another Telecaller (Agent 2) for scoping checks
    agent2 = await user_repo.create_user(org.id, {
        "email": "agent2@disp.com",
        "hashed_password": get_password_hash("password123"),
        "first_name": "Agent",
        "last_name": "Two",
        "role": "Employee",
        "is_active": True,
        "reporting_to_id": tl.id
    })
    await db.commit()

    # Access tokens
    token_super = create_access_token(super_admin.id)
    token_tl = create_access_token(tl.id)
    token_agent = create_access_token(agent.id)
    token_agent2 = create_access_token(agent2.id)

    # Get system stages
    res = await db.execute(
        select(PipelineStage).filter(
            PipelineStage.organization_id == org.id,
            PipelineStage.is_deleted == False
        )
    )
    stages = res.scalars().all()
    
    fresh_stage = None
    dropped_stage = None
    contacted_stage = None
    
    for s in stages:
        if s.name == "Fresh Leads" or s.is_system_default:
            fresh_stage = s
        if s.name == "Dropped":
            dropped_stage = s
        if s.name == "Contacted":
            contacted_stage = s

    # Ensure stages exist
    if not fresh_stage:
        fresh_stage = PipelineStage(organization_id=org.id, name="Fresh Leads", order_position=1, is_system_default=True)
        db.add(fresh_stage)
    if not dropped_stage:
        dropped_stage = PipelineStage(organization_id=org.id, name="Dropped", order_position=4, is_system_default=False)
        db.add(dropped_stage)
    if not contacted_stage:
        contacted_stage = PipelineStage(organization_id=org.id, name="Contacted", order_position=2, is_system_default=False)
        db.add(contacted_stage)
    await db.commit()

    return {
        "org": org,
        "super_admin": super_admin,
        "tl": tl,
        "agent": agent,
        "agent2": agent2,
        "headers_super": {"Authorization": f"Bearer {token_super}"},
        "headers_tl": {"Authorization": f"Bearer {token_tl}"},
        "headers_agent": {"Authorization": f"Bearer {token_agent}"},
        "headers_agent2": {"Authorization": f"Bearer {token_agent2}"},
        "fresh_stage_id": fresh_stage.id,
        "dropped_stage_id": dropped_stage.id,
        "contacted_stage_id": contacted_stage.id
    }

@pytest.mark.asyncio
async def test_disposition_schema_validations(client: AsyncClient, setup_disposition_data: dict, db: AsyncSession):
    data = setup_disposition_data
    agent_headers = data["headers_agent"]

    # 1. Picked without custom_pipeline_stage_id -> should fail with 422
    payload = {
        "status": "Picked",
        "remarks": "Connected successfully but missing stage ID"
    }
    resp = await client.post(f"/api/v1/dialer/leads/{uuid.uuid4()}/disposition", json=payload, headers=agent_headers)
    assert resp.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

    # 2. RNR with custom_pipeline_stage_id -> should fail with 422
    payload = {
        "status": "RNR",
        "remarks": "Not answered",
        "custom_pipeline_stage_id": str(data["contacted_stage_id"])
    }
    resp = await client.post(f"/api/v1/dialer/leads/{uuid.uuid4()}/disposition", json=payload, headers=agent_headers)
    assert resp.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

    # 3. Empty remarks -> should fail with 422
    payload = {
        "status": "Busy",
        "remarks": ""
    }
    resp = await client.post(f"/api/v1/dialer/leads/{uuid.uuid4()}/disposition", json=payload, headers=agent_headers)
    assert resp.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

@pytest.mark.asyncio
async def test_disposition_scoping_rules(client: AsyncClient, setup_disposition_data: dict, db: AsyncSession):
    data = setup_disposition_data
    org = data["org"]
    agent = data["agent"]
    agent2_headers = data["headers_agent2"]
    tl_headers = data["headers_tl"]

    # Create lead assigned to agent 1
    lead = Lead(
        organization_id=org.id,
        first_name="Scope",
        last_name="Test",
        phone="+919876543222",
        title="Scoping",
        status="New",
        assigned_user_id=agent.id,
        created_by=data["super_admin"].id,
        stage_id=data["fresh_stage_id"]
    )
    db.add(lead)
    await db.commit()

    # 1. Non-telecaller (e.g. TL) tries to disposition -> 403 Forbidden
    payload = {
        "status": "Busy",
        "remarks": "Busy call"
    }
    resp = await client.post(f"/api/v1/dialer/leads/{lead.id}/disposition", json=payload, headers=tl_headers)
    assert resp.status_code == status.HTTP_403_FORBIDDEN

    # 2. Telecaller who is NOT the assignee tries to disposition -> 403 Forbidden
    resp = await client.post(f"/api/v1/dialer/leads/{lead.id}/disposition", json=payload, headers=agent2_headers)
    assert resp.status_code == status.HTTP_403_FORBIDDEN

@pytest.mark.asyncio
async def test_disposition_system_action_busy(client: AsyncClient, setup_disposition_data: dict, db: AsyncSession, mock_redis: dict):
    data = setup_disposition_data
    org = data["org"]
    agent = data["agent"]
    agent_headers = data["headers_agent"]

    # Pre-set agent state in Redis to ACTIVE_CALLING
    redis_key = f"org:{org.id}:agent:{agent.id}:state"
    mock_redis[redis_key] = json.dumps({"state": "ACTIVE_CALLING", "timestamp": "...", "metadata": {}})

    # Create lead assigned to agent
    lead = Lead(
        organization_id=org.id,
        first_name="Busy",
        last_name="Lead",
        phone="+919876543223",
        title="Busy Deal",
        status="New",
        assigned_user_id=agent.id,
        created_by=data["super_admin"].id,
        stage_id=data["fresh_stage_id"]
    )
    db.add(lead)
    await db.commit()

    # Call /disposition
    payload = {
        "status": "Busy",
        "remarks": "User cut the call"
    }
    resp = await client.post(f"/api/v1/dialer/leads/{lead.id}/disposition", json=payload, headers=agent_headers)
    assert resp.status_code == status.HTTP_200_OK
    
    # Reload lead
    await db.refresh(lead)
    assert lead.call_attempts_count == 1
    assert lead.stage_id == data["fresh_stage_id"]  # Pipeline stage unchanged
    assert lead.status == "Busy"
    assert lead.available_at is not None
    # available_at should be ~2 hours from now
    available_naive = lead.available_at.replace(tzinfo=None) if lead.available_at.tzinfo else lead.available_at
    now_naive = datetime.now(timezone.utc).replace(tzinfo=None)
    diff = available_naive - now_naive
    assert diff > timedelta(minutes=115) and diff < timedelta(minutes=125)

    # Redis state should be reset to IDLE
    state_resp = await client.get("/api/v1/dialer/state", headers=agent_headers)
    assert state_resp.json()["state"] == "IDLE"

    # Verify audit log
    audit_repo = AuditRepository(db)
    logs = await audit_repo.list_logs(org.id)
    assert len(logs) > 0
    disposition_log = [l for l in logs if l.action == "LEAD_DISPOSITION_SUBMITTED"][0]
    assert disposition_log.resource_id == str(lead.id)
    assert disposition_log.action_metadata["status"] == "Busy"
    assert disposition_log.action_metadata["remarks"] == "User cut the call"

@pytest.mark.asyncio
async def test_disposition_threshold_auto_drop(client: AsyncClient, setup_disposition_data: dict, db: AsyncSession):
    data = setup_disposition_data
    org = data["org"]
    agent = data["agent"]
    agent_headers = data["headers_agent"]

    # Create lead with call_attempts_count = 4
    lead = Lead(
        organization_id=org.id,
        first_name="AutoDrop",
        last_name="Lead",
        phone="+919876543224",
        title="Auto Drop Deal",
        status="New",
        assigned_user_id=agent.id,
        created_by=data["super_admin"].id,
        stage_id=data["fresh_stage_id"],
        call_attempts_count=4
    )
    db.add(lead)
    await db.commit()

    # Call /disposition with RNR (attempt 5)
    payload = {
        "status": "RNR",
        "remarks": "Not picking up on 5th attempt"
    }
    resp = await client.post(f"/api/v1/dialer/leads/{lead.id}/disposition", json=payload, headers=agent_headers)
    assert resp.status_code == status.HTTP_200_OK

    await db.refresh(lead)
    assert lead.call_attempts_count == 5
    assert lead.stage_id == data["dropped_stage_id"]  # Advanced to system Dropped stage
    assert lead.status == "RNR"

@pytest.mark.asyncio
async def test_disposition_invalid_entries_immediate_drop(client: AsyncClient, setup_disposition_data: dict, db: AsyncSession):
    data = setup_disposition_data
    org = data["org"]
    agent = data["agent"]
    agent_headers = data["headers_agent"]

    # Create lead
    lead = Lead(
        organization_id=org.id,
        first_name="Invalid",
        last_name="Number",
        phone="+919876543225",
        title="Invalid Number Deal",
        status="New",
        assigned_user_id=agent.id,
        created_by=data["super_admin"].id,
        stage_id=data["fresh_stage_id"]
    )
    db.add(lead)
    await db.commit()

    # Call /disposition with Out of Service
    payload = {
        "status": "Out of Service",
        "remarks": "Number does not exist"
    }
    resp = await client.post(f"/api/v1/dialer/leads/{lead.id}/disposition", json=payload, headers=agent_headers)
    assert resp.status_code == status.HTTP_200_OK

    await db.refresh(lead)
    assert lead.call_attempts_count == 0  # Not incremented for invalid entry
    assert lead.stage_id == data["dropped_stage_id"]  # Advanced to system Dropped stage immediately
    assert lead.status == "Out of Service"

@pytest.mark.asyncio
async def test_disposition_picked_success_advancement(client: AsyncClient, setup_disposition_data: dict, db: AsyncSession):
    data = setup_disposition_data
    org = data["org"]
    agent = data["agent"]
    agent_headers = data["headers_agent"]

    # Create lead
    lead = Lead(
        organization_id=org.id,
        first_name="Success",
        last_name="Connection",
        phone="+919876543226",
        title="Picked Connection Deal",
        status="New",
        assigned_user_id=agent.id,
        created_by=data["super_admin"].id,
        stage_id=data["fresh_stage_id"]
    )
    db.add(lead)
    await db.commit()

    # Call /disposition with Picked and custom contacted stage id
    payload = {
        "status": "Picked",
        "remarks": "Discussed details, advancing to contacted",
        "custom_pipeline_stage_id": str(data["contacted_stage_id"])
    }
    resp = await client.post(f"/api/v1/dialer/leads/{lead.id}/disposition", json=payload, headers=agent_headers)
    assert resp.status_code == status.HTTP_200_OK

    await db.refresh(lead)
    assert lead.stage_id == data["contacted_stage_id"]  # Advanced to custom contacted stage
    assert lead.status == "Picked"
