import pytest
import re
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.core.security import create_access_token, get_password_hash
from app.repositories.organization import OrganizationRepository
from app.repositories.user_repository import UserRepository
from app.models.pipeline import PipelineStage
from app.models.lead import Lead

@pytest.fixture
async def setup_masking_data(db: AsyncSession):
    org_repo = OrganizationRepository(db)
    user_repo = UserRepository(db)

    # 1. Create Organization
    org = await org_repo.create({"name": "Masking Org", "slug": "masking-org"})
    await db.commit()

    # Get the default stage
    res = await db.execute(
        select(PipelineStage.id).filter(
            PipelineStage.organization_id == org.id,
            PipelineStage.is_system_default == True
        )
    )
    default_stage_id = res.scalar()

    # 2. Create OrgAdmin (Super Admin) - reports to None
    super_admin = await user_repo.create_user(org.id, {
        "email": "super_admin@mask.com",
        "hashed_password": get_password_hash("password123"),
        "first_name": "Super",
        "last_name": "Admin",
        "role": "OrgAdmin",
        "is_active": True,
        "reporting_to_id": None
    })
    await db.commit()

    # 3. Create Manager - reports to Super Admin
    manager = await user_repo.create_user(org.id, {
        "email": "manager@mask.com",
        "hashed_password": get_password_hash("password123"),
        "first_name": "Manager",
        "last_name": "One",
        "role": "Manager",
        "is_active": True,
        "reporting_to_id": super_admin.id
    })
    await db.commit()

    # 4. Create Team Leader (TL) - Employee reporting to Manager
    team_leader = await user_repo.create_user(org.id, {
        "email": "tl@mask.com",
        "hashed_password": get_password_hash("password123"),
        "first_name": "TL",
        "last_name": "One",
        "role": "Employee",
        "is_active": True,
        "reporting_to_id": manager.id
    })
    await db.commit()

    # 5. Create Telecaller (Agent) - Employee reporting to TL
    telecaller = await user_repo.create_user(org.id, {
        "email": "agent@mask.com",
        "hashed_password": get_password_hash("password123"),
        "first_name": "Agent",
        "last_name": "One",
        "role": "Employee",
        "is_active": True,
        "reporting_to_id": team_leader.id
    })
    await db.commit()

    # Create Lead
    lead = Lead(
        organization_id=org.id,
        first_name="Masked",
        last_name="Test",
        email="masked_lead@test.com",
        phone="+919876543210",
        title="Opportunity",
        created_by=super_admin.id,
        assigned_user_id=telecaller.id,
        stage_id=default_stage_id
    )
    db.add(lead)
    await db.commit()

    token_super = create_access_token(super_admin.id)
    token_manager = create_access_token(manager.id)
    token_tl = create_access_token(team_leader.id)
    token_agent = create_access_token(telecaller.id)

    return {
        "org": org,
        "lead": lead,
        "headers_super": {"Authorization": f"Bearer {token_super}"},
        "headers_manager": {"Authorization": f"Bearer {token_manager}"},
        "headers_tl": {"Authorization": f"Bearer {token_tl}"},
        "headers_agent": {"Authorization": f"Bearer {token_agent}"}
    }

@pytest.mark.asyncio
async def test_role_based_phone_masking(client: AsyncClient, setup_masking_data: dict):
    data = setup_masking_data
    lead_id = str(data["lead"].id)

    # 1. Access as OrgAdmin -> full number
    resp_super = await client.get(f"/api/v1/leads/{lead_id}", headers=data["headers_super"])
    assert resp_super.status_code == 200
    assert resp_super.json()["phone"] == "+919876543210"

    # 2. Access as Manager -> full number
    resp_mgr = await client.get(f"/api/v1/leads/{lead_id}", headers=data["headers_manager"])
    assert resp_mgr.status_code == 200
    assert resp_mgr.json()["phone"] == "+919876543210"

    # 3. Access as Team Leader (TL) -> full number
    resp_tl = await client.get(f"/api/v1/leads/{lead_id}", headers=data["headers_tl"])
    assert resp_tl.status_code == 200
    assert resp_tl.json()["phone"] == "+919876543210"

    # 4. Access as Telecaller (Agent) -> masked number matching "+91******10"
    resp_agent = await client.get(f"/api/v1/leads/{lead_id}", headers=data["headers_agent"])
    assert resp_agent.status_code == 200
    masked_phone = resp_agent.json()["phone"]
    assert masked_phone is not None
    assert masked_phone == "+91********10"

@pytest.mark.asyncio
async def test_role_based_phone_masking_list_endpoint(client: AsyncClient, setup_masking_data: dict):
    data = setup_masking_data

    # Access leads list as Telecaller (Agent) -> phone must be masked in list response
    resp_agent = await client.get("/api/v1/leads/", headers=data["headers_agent"])
    assert resp_agent.status_code == 200
    leads = resp_agent.json()
    assert len(leads) > 0
    masked_phone = leads[0]["phone"]
    assert masked_phone == "+91********10"

    # Access leads list as TL -> phone must not be masked
    resp_tl = await client.get("/api/v1/leads/", headers=data["headers_tl"])
    assert resp_tl.status_code == 200
    leads_tl = resp_tl.json()
    assert len(leads_tl) > 0
    assert leads_tl[0]["phone"] == "+919876543210"
