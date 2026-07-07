import pytest
import uuid
import json
from datetime import datetime, timedelta, timezone
from fastapi import status
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.core.security import create_access_token, get_password_hash
from app.repositories.organization import OrganizationRepository
from app.repositories.user_repository import UserRepository
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
async def setup_dialer_data(db: AsyncSession):
    org_repo = OrganizationRepository(db)
    user_repo = UserRepository(db)

    # 1. Create Organization
    org = await org_repo.create({"name": "Dialer Org", "slug": "dialer-org"})
    await db.commit()

    # 2. Create Super Admin (OrgAdmin)
    super_admin = await user_repo.create_user(org.id, {
        "email": "super_admin@dialer.com",
        "hashed_password": get_password_hash("password123"),
        "first_name": "Super",
        "last_name": "Admin",
        "role": "OrgAdmin",
        "is_active": True
    })
    await db.commit()

    # 3. Create Manager
    manager = await user_repo.create_user(org.id, {
        "email": "manager@dialer.com",
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
        "email": "tl@dialer.com",
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
        "email": "agent@dialer.com",
        "hashed_password": get_password_hash("password123"),
        "first_name": "Agent",
        "last_name": "One",
        "role": "Employee",
        "is_active": True,
        "reporting_to_id": tl.id
    })
    await db.commit()

    # Access tokens
    token_super = create_access_token(super_admin.id)
    token_manager = create_access_token(manager.id)
    token_tl = create_access_token(tl.id)
    token_agent = create_access_token(agent.id)

    # Get system default pipeline stage
    res = await db.execute(
        select(PipelineStage.id).filter(
            PipelineStage.organization_id == org.id,
            PipelineStage.is_system_default == True
        )
    )
    default_stage_id = res.scalar()
    
    if not default_stage_id:
        stage = PipelineStage(
            organization_id=org.id,
            name="New",
            order_position=1,
            is_system_default=True
        )
        db.add(stage)
        await db.commit()
        default_stage_id = stage.id

    return {
        "org": org,
        "super_admin": super_admin,
        "manager": manager,
        "tl": tl,
        "agent": agent,
        "headers_super": {"Authorization": f"Bearer {token_super}"},
        "headers_manager": {"Authorization": f"Bearer {token_manager}"},
        "headers_tl": {"Authorization": f"Bearer {token_tl}"},
        "headers_agent": {"Authorization": f"Bearer {token_agent}"},
        "default_stage_id": default_stage_id
    }

@pytest.mark.asyncio
async def test_dialer_role_restriction(client: AsyncClient, setup_dialer_data: dict):
    data = setup_dialer_data
    # SuperAdmin -> 403
    resp = await client.post("/api/v1/dialer/next-lead", json={}, headers=data["headers_super"])
    assert resp.status_code == status.HTTP_403_FORBIDDEN
    
    # Manager -> 403
    resp = await client.post("/api/v1/dialer/next-lead", json={}, headers=data["headers_manager"])
    assert resp.status_code == status.HTTP_403_FORBIDDEN

    # TL -> 403
    resp = await client.post("/api/v1/dialer/next-lead", json={}, headers=data["headers_tl"])
    assert resp.status_code == status.HTTP_403_FORBIDDEN

@pytest.mark.asyncio
async def test_dialer_state_management(client: AsyncClient, setup_dialer_data: dict):
    data = setup_dialer_data
    agent_headers = data["headers_agent"]

    # 1. Get default state (should be IDLE)
    resp = await client.get("/api/v1/dialer/state", headers=agent_headers)
    assert resp.status_code == status.HTTP_200_OK
    assert resp.json()["state"] == "IDLE"

    # 2. Set state to BREAK with reason
    payload = {
        "state": "BREAK",
        "metadata": {"break_reason": "Lunch"}
    }
    resp = await client.post("/api/v1/dialer/state", json=payload, headers=agent_headers)
    assert resp.status_code == status.HTTP_200_OK
    assert resp.json()["state"] == "BREAK"
    assert resp.json()["metadata"]["break_reason"] == "Lunch"

    # 3. Get updated state
    resp = await client.get("/api/v1/dialer/state", headers=agent_headers)
    assert resp.status_code == status.HTTP_200_OK
    assert resp.json()["state"] == "BREAK"

    # 4. Set invalid state -> should return ValidationError or error
    resp = await client.post("/api/v1/dialer/state", json={"state": "INVALID"}, headers=agent_headers)
    assert resp.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY or resp.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR

@pytest.mark.asyncio
async def test_dialer_idle_guard(client: AsyncClient, setup_dialer_data: dict, db: AsyncSession):
    data = setup_dialer_data
    agent_headers = data["headers_agent"]

    # 1. Set agent state to BREAK
    await client.post("/api/v1/dialer/state", json={"state": "BREAK"}, headers=agent_headers)

    # 2. Try to fetch next-lead -> should return 400 Bad Request
    resp = await client.post("/api/v1/dialer/next-lead", json={}, headers=agent_headers)
    assert resp.status_code == status.HTTP_400_BAD_REQUEST
    assert "Agent must be IDLE" in resp.json()["detail"]

@pytest.mark.asyncio
async def test_dialer_explicit_assignment(client: AsyncClient, setup_dialer_data: dict, db: AsyncSession):
    data = setup_dialer_data
    agent = data["agent"]
    agent_headers = data["headers_agent"]
    org = data["org"]

    # Set agent to IDLE
    await client.post("/api/v1/dialer/state", json={"state": "IDLE"}, headers=agent_headers)

    # Create two leads assigned to the agent.
    lead1 = Lead(
        organization_id=org.id,
        first_name="Explicit",
        last_name="Oldest",
        phone="+919876543211",
        title="Deal 1",
        status="New",
        assigned_user_id=agent.id,
        created_by=data["super_admin"].id,
        stage_id=data["default_stage_id"]
    )
    lead2 = Lead(
        organization_id=org.id,
        first_name="Explicit",
        last_name="Newest",
        phone="+919876543212",
        title="Deal 2",
        status="New",
        assigned_user_id=agent.id,
        created_by=data["super_admin"].id,
        stage_id=data["default_stage_id"]
    )
    db.add(lead1)
    db.add(lead2)
    await db.commit()
    
    # Adjust created_at explicitly to control order
    lead1.created_at = datetime.now(timezone.utc) - timedelta(hours=2)
    lead2.created_at = datetime.now(timezone.utc) - timedelta(hours=1)
    db.add(lead1)
    db.add(lead2)
    await db.commit()

    # Call /next-lead with collective_pooling=False
    resp = await client.post("/api/v1/dialer/next-lead", json={"collective_pooling": False}, headers=agent_headers)
    assert resp.status_code == status.HTTP_200_OK
    res_json = resp.json()
    assert res_json["id"] == str(lead1.id)
    # Verify phone number masking is applied (displayed only first 2 and last 2 characters + * in the middle)
    assert res_json["phone"] == "+91********11"

    # Agent state should transition to ACTIVE_CALLING
    state_resp = await client.get("/api/v1/dialer/state", headers=agent_headers)
    assert state_resp.json()["state"] == "ACTIVE_CALLING"

@pytest.mark.asyncio
async def test_dialer_collective_pooling(client: AsyncClient, setup_dialer_data: dict, db: AsyncSession):
    data = setup_dialer_data
    agent = data["agent"]
    tl = data["tl"]
    agent_headers = data["headers_agent"]
    org = data["org"]

    # Set agent to IDLE
    await client.post("/api/v1/dialer/state", json={"state": "IDLE"}, headers=agent_headers)

    # Create unassigned lead in TL's queue
    lead_unassigned = Lead(
        organization_id=org.id,
        first_name="Pool",
        last_name="Lead",
        phone="+919876543210",
        title="Pool Deal",
        status="New",
        assigned_user_id=None,
        created_by=tl.id,
        stage_id=data["default_stage_id"]
    )
    db.add(lead_unassigned)
    await db.commit()

    # Call /next-lead with collective_pooling=True
    resp = await client.post("/api/v1/dialer/next-lead", json={"collective_pooling": True}, headers=agent_headers)
    assert resp.status_code == status.HTTP_200_OK
    res_json = resp.json()
    assert res_json["id"] == str(lead_unassigned.id)
    assert res_json["phone"] == "+91********10"

    # Check lead is assigned to agent in DB now
    await db.refresh(lead_unassigned)
    assert lead_unassigned.assigned_user_id == agent.id

    # Agent state should transition to ACTIVE_CALLING
    state_resp = await client.get("/api/v1/dialer/state", headers=agent_headers)
    assert state_resp.json()["state"] == "ACTIVE_CALLING"
