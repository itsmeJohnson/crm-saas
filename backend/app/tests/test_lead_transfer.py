import pytest
import uuid
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.core.security import create_access_token, get_password_hash
from app.repositories.organization import OrganizationRepository
from app.repositories.user_repository import UserRepository
from app.models.user import User
from app.models.lead import Lead
from app.models.pipeline import PipelineStage

@pytest.fixture
async def setup_transfer_data(db: AsyncSession):
    org_repo = OrganizationRepository(db)
    user_repo = UserRepository(db)

    # 1. Create Organization
    org = await org_repo.create({"name": "Transfer Org", "slug": "transfer-org"})
    await db.commit()

    # 2. Super Admin (OrgAdmin)
    super_admin = await user_repo.create_user(org.id, {
        "email": "sa@t.com",
        "hashed_password": get_password_hash("password123"),
        "first_name": "Super",
        "last_name": "Admin",
        "role": "OrgAdmin",
        "is_active": True
    })

    # 3. Manager
    manager = await user_repo.create_user(org.id, {
        "email": "mgr@t.com",
        "hashed_password": get_password_hash("password123"),
        "first_name": "Manager",
        "last_name": "One",
        "role": "Manager",
        "is_active": True,
        "reporting_to_id": super_admin.id
    })

    # 4. Team Leader (TL) - Employee reporting to Manager
    tl = await user_repo.create_user(org.id, {
        "email": "tl@t.com",
        "hashed_password": get_password_hash("password123"),
        "first_name": "TL",
        "last_name": "One",
        "role": "Employee",
        "is_active": True,
        "reporting_to_id": manager.id
    })

    # 5. Telecaller 1 (reporting to TL)
    tc1 = await user_repo.create_user(org.id, {
        "email": "tc1@t.com",
        "hashed_password": get_password_hash("password123"),
        "first_name": "TC1",
        "last_name": "One",
        "role": "Employee",
        "is_active": True,
        "reporting_to_id": tl.id
    })

    # 6. Telecaller 2 (reporting to TL)
    tc2 = await user_repo.create_user(org.id, {
        "email": "tc2@t.com",
        "hashed_password": get_password_hash("password123"),
        "first_name": "TC2",
        "last_name": "One",
        "role": "Employee",
        "is_active": True,
        "reporting_to_id": tl.id
    })

    await db.commit()

    # Get default pipeline stage
    res_stage = await db.execute(
        select(PipelineStage.id).filter(
            PipelineStage.organization_id == org.id,
            PipelineStage.is_system_default == True
        )
    )
    default_stage_id = res_stage.scalar()

    # Create leads assigned to tl
    leads = []
    for i in range(5):
        lead = Lead(
            organization_id=org.id,
            first_name=f"Lead_{i}",
            last_name="Test",
            email=f"lead_{i}@test.com",
            phone=f"+12345678{i}",
            title=f"Opportunity {i}",
            assigned_user_id=tl.id,
            created_by=super_admin.id,
            stage_id=default_stage_id
        )
        db.add(lead)
        leads.append(lead)
    await db.commit()

    # Create tokens
    token_sa = create_access_token(super_admin.id)
    token_mgr = create_access_token(manager.id)
    token_tl = create_access_token(tl.id)
    token_tc1 = create_access_token(tc1.id)

    return {
        "org": org,
        "super_admin": super_admin,
        "manager": manager,
        "tl": tl,
        "tc1": tc1,
        "tc2": tc2,
        "leads": leads,
        "headers_sa": {"Authorization": f"Bearer {token_sa}"},
        "headers_mgr": {"Authorization": f"Bearer {token_mgr}"},
        "headers_tl": {"Authorization": f"Bearer {token_tl}"},
        "headers_tc1": {"Authorization": f"Bearer {token_tc1}"}
    }

@pytest.mark.asyncio
async def test_transfer_leads_by_quantity(client: AsyncClient, db: AsyncSession, setup_transfer_data: dict):
    data = setup_transfer_data
    payload = {
        "source_user_id": str(data["tl"].id),
        "destination_user_ids": [str(data["tc1"].id), str(data["tc2"].id)],
        "quantity": 4
    }

    # Run transfer as TL
    res = await client.post("/api/v1/leads/transfer", json=payload, headers=data["headers_tl"])
    assert res.status_code == 200
    res_data = res.json()
    assert res_data["transferred_count"] == 4
    assert len(res_data["lead_ids"]) == 4

    # Verify database updates
    # The 4 leads should be split equally (2 to tc1, 2 to tc2)
    # Refetch leads from database
    stmt = select(Lead).filter(Lead.id.in_([uuid.UUID(lid) for lid in res_data["lead_ids"]]))
    db_res = await db.execute(stmt)
    updated_leads = db_res.scalars().all()
    
    tc1_count = sum(1 for l in updated_leads if l.assigned_user_id == data["tc1"].id)
    tc2_count = sum(1 for l in updated_leads if l.assigned_user_id == data["tc2"].id)
    assert tc1_count == 2
    assert tc2_count == 2

@pytest.mark.asyncio
async def test_transfer_leads_by_ids(client: AsyncClient, db: AsyncSession, setup_transfer_data: dict):
    data = setup_transfer_data
    target_lead_ids = [str(data["leads"][0].id), str(data["leads"][1].id), str(data["leads"][2].id)]
    
    payload = {
        "source_user_id": str(data["tl"].id),
        "destination_user_ids": [str(data["tc1"].id)],
        "lead_ids": target_lead_ids
    }

    # Run transfer as Manager (Manager can transfer TL's leads down)
    res = await client.post("/api/v1/leads/transfer", json=payload, headers=data["headers_mgr"])
    assert res.status_code == 200
    res_data = res.json()
    assert res_data["transferred_count"] == 3

    # Refetch and check assignment
    stmt = select(Lead).filter(Lead.id.in_([uuid.UUID(lid) for lid in target_lead_ids]))
    db_res = await db.execute(stmt)
    updated_leads = db_res.scalars().all()
    for l in updated_leads:
        assert l.assigned_user_id == data["tc1"].id

@pytest.mark.asyncio
async def test_transfer_leads_unauthorized_actor(client: AsyncClient, setup_transfer_data: dict):
    data = setup_transfer_data
    payload = {
        "source_user_id": str(data["tl"].id),
        "destination_user_ids": [str(data["tc2"].id)],
        "quantity": 2
    }

    # TC1 (Telecaller) is not allowed to transfer leads (require_tl_or_above)
    res = await client.post("/api/v1/leads/transfer", json=payload, headers=data["headers_tc1"])
    assert res.status_code == 403

@pytest.mark.asyncio
async def test_transfer_leads_invalid_source_or_dest(client: AsyncClient, setup_transfer_data: dict):
    data = setup_transfer_data
    
    # TL trying to transfer leads of Manager (Manager is not TL's downline)
    payload = {
        "source_user_id": str(data["manager"].id),
        "destination_user_ids": [str(data["tc1"].id)],
        "quantity": 1
    }
    res = await client.post("/api/v1/leads/transfer", json=payload, headers=data["headers_tl"])
    assert res.status_code == 403


# --- Regression: admin with an EMPTY downline + team-leader-to-self (real demo shape) ---

@pytest.fixture
async def setup_empty_downline(db: AsyncSession):
    """Reproduces the real demo reporting shape where the OrgAdmin has NO direct
    reports (the Manager reports to nobody), so the admin's reporting-chain
    downline is empty. Previously this blocked the admin from assigning any lead."""
    org = await OrganizationRepository(db).create({"name": "EmptyDL Org", "slug": "emptydl-org"})
    await db.commit()
    ur = UserRepository(db)

    async def mk(email, role, reports_to=None):
        return await ur.create_user(org.id, {
            "email": email, "hashed_password": get_password_hash("password123"),
            "first_name": email.split("@")[0], "last_name": "X", "role": role,
            "is_active": True, "reporting_to_id": reports_to})

    admin = await mk("adm@edl.com", "OrgAdmin")            # no one reports to admin
    manager = await mk("mgr@edl.com", "Manager")           # reports to nobody
    tl = await mk("tl@edl.com", "Employee", manager.id)    # team leader
    tc1 = await mk("tc1@edl.com", "Employee", tl.id)       # telecaller under TL
    tc2 = await mk("tc2@edl.com", "Employee", tl.id)
    await db.commit()

    stage = (await db.execute(select(PipelineStage.id).filter(
        PipelineStage.organization_id == org.id, PipelineStage.is_system_default == True))).scalar()

    # a lead assigned to the TL, and one to a telecaller
    l_tl = Lead(organization_id=org.id, last_name="A", title="T", assigned_user_id=tl.id,
                created_by=admin.id, stage_id=stage)
    l_tc = Lead(organization_id=org.id, last_name="B", title="T", assigned_user_id=tc1.id,
                created_by=admin.id, stage_id=stage)
    db.add_all([l_tl, l_tc])
    await db.commit()

    def h(u): return {"Authorization": f"Bearer {create_access_token(u.id)}"}
    return {"org": org, "admin": admin, "manager": manager, "tl": tl, "tc1": tc1, "tc2": tc2,
            "l_tl": str(l_tl.id), "l_tc": str(l_tc.id),
            "h_admin": h(admin), "h_tl": h(tl), "h_tc": h(tc1)}


@pytest.mark.asyncio
async def test_admin_with_empty_downline_can_transfer(client: AsyncClient, setup_empty_downline: dict):
    d = setup_empty_downline
    # OrgAdmin transfers a lead assigned to the team leader -> a telecaller
    r = await client.post("/api/v1/leads/transfer", headers=d["h_admin"], json={
        "source_user_id": str(d["tl"].id), "destination_user_ids": [str(d["tc2"].id)],
        "lead_ids": [d["l_tl"]]})
    assert r.status_code == 200, r.text


@pytest.mark.asyncio
async def test_team_leader_can_assign_to_self(client: AsyncClient, setup_empty_downline: dict):
    d = setup_empty_downline
    # TL transfers a team member's lead back to themselves
    r = await client.post("/api/v1/leads/transfer", headers=d["h_tl"], json={
        "source_user_id": str(d["tc1"].id), "destination_user_ids": [str(d["tl"].id)],
        "lead_ids": [d["l_tc"]]})
    assert r.status_code == 200, r.text
    # ...and bulk-assign including themselves
    r2 = await client.post("/api/v1/leads/assign-bulk", headers=d["h_tl"], json={
        "assignee_ids": [str(d["tl"].id), str(d["tc2"].id)], "lead_ids": [d["l_tc"]],
        "strategy": "SPLIT"})
    assert r2.status_code == 200, r2.text


@pytest.mark.asyncio
async def test_assignable_users_by_role(client: AsyncClient, setup_empty_downline: dict):
    d = setup_empty_downline
    # OrgAdmin: org-wide (all 5 users, all roles)
    admin_list = (await client.get("/api/v1/users/assignable", headers=d["h_admin"])).json()
    assert len(admin_list) == 5
    # Team leader: downline + self (tl, tc1, tc2) — NOT the manager/admin
    tl_list = (await client.get("/api/v1/users/assignable", headers=d["h_tl"])).json()
    tl_ids = {u["id"] for u in tl_list}
    assert str(d["tl"].id) in tl_ids and str(d["tc1"].id) in tl_ids and str(d["tc2"].id) in tl_ids
    assert str(d["manager"].id) not in tl_ids and str(d["admin"].id) not in tl_ids
    # Plain telecaller cannot list assignable users (not a team leader)
    assert (await client.get("/api/v1/users/assignable", headers=d["h_tc"])).status_code == 403


@pytest.mark.asyncio
async def test_team_leader_cannot_assign_outside_team(client: AsyncClient, setup_empty_downline: dict):
    d = setup_empty_downline
    # TL cannot transfer to the Manager (upline, outside the team)
    r = await client.post("/api/v1/leads/transfer", headers=d["h_tl"], json={
        "source_user_id": str(d["tc1"].id), "destination_user_ids": [str(d["manager"].id)],
        "lead_ids": [d["l_tc"]]})
    assert r.status_code == 403
