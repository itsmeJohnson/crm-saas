import pytest
import uuid
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.core.security import create_access_token, get_password_hash
from app.repositories.organization import OrganizationRepository
from app.repositories.user_repository import UserRepository
from app.models.company import Company
from app.models.contact import Contact
from app.models.lead import Lead
from app.models.activity import Activity
from app.models.pipeline import PipelineStage


@pytest.fixture
async def setup(db: AsyncSession):
    org_repo = OrganizationRepository(db)
    user_repo = UserRepository(db)

    org = await org_repo.create({"name": "Co Org", "slug": "co-org"})
    await db.commit()

    admin = await user_repo.create_user(org.id, {
        "email": "admin@co.com", "hashed_password": get_password_hash("password123"),
        "first_name": "Admin", "last_name": "One", "role": "OrgAdmin", "is_active": True,
    })
    await db.commit()

    company = Company(organization_id=org.id, name="Acme Inc", industry="Software",
                      company_type="Customer", source="Referral", employee_count=200,
                      annual_revenue=5000000, tags=["strategic"], created_by=admin.id)
    other = Company(organization_id=org.id, name="Beta LLC", industry="Retail",
                    company_type="Prospect", employee_count=50, annual_revenue=1000000, created_by=admin.id)
    db.add_all([company, other])
    await db.commit()

    # contacts (people) at Acme
    for i in range(2):
        db.add(Contact(organization_id=org.id, first_name=f"Emp{i}", last_name="Acme",
                       email=f"emp{i}@acme.com", company_id=company.id, created_by=admin.id))
    await db.commit()

    # default + converted stage
    stage_res = await db.execute(select(PipelineStage.id).filter(
        PipelineStage.organization_id == org.id, PipelineStage.is_system_default == True))
    default_stage = stage_res.scalar()
    conv_res = await db.execute(select(PipelineStage.id).filter(
        PipelineStage.organization_id == org.id, PipelineStage.name == "Converted"))
    converted_stage = conv_res.scalar()
    if not converted_stage:
        cs = PipelineStage(organization_id=org.id, name="Converted", order_position=99, created_by=admin.id)
        db.add(cs)
        await db.commit()
        converted_stage = cs.id

    # leads: one linked by company_id, one by name match, one converted
    db.add(Lead(organization_id=org.id, last_name="L1", title="Deal One", company_id=company.id,
                value=10000, created_by=admin.id, stage_id=default_stage))
    db.add(Lead(organization_id=org.id, last_name="L2", title="Deal Two", company_name="acme inc",
                value=20000, created_by=admin.id, stage_id=default_stage))
    db.add(Lead(organization_id=org.id, last_name="L3", title="Won Deal", company_id=company.id,
                value=50000, created_by=admin.id, stage_id=converted_stage))
    await db.commit()

    return {
        "org": org, "admin": admin, "company": company, "other": other,
        "headers": {"Authorization": f"Bearer {create_access_token(admin.id)}"},
    }


@pytest.mark.asyncio
async def test_create_company_with_new_fields(client: AsyncClient, setup: dict):
    data = setup
    payload = {"name": "Gamma Co", "company_type": "Partner", "source": "Event",
               "employee_count": 30, "annual_revenue": 750000, "tags": ["smb"], "industry": "Fintech"}
    res = await client.post("/api/v1/companies/", json=payload, headers=data["headers"])
    assert res.status_code == 201
    body = res.json()
    assert body["company_type"] == "Partner"
    assert body["employee_count"] == 30
    assert body["tags"] == ["smb"]


@pytest.mark.asyncio
async def test_filters(client: AsyncClient, setup: dict):
    data = setup
    res = await client.get("/api/v1/companies/?company_type=Customer", headers=data["headers"])
    assert res.status_code == 200
    assert all(c["company_type"] == "Customer" for c in res.json())
    assert len(res.json()) == 1

    res = await client.get("/api/v1/companies/?tag=strategic", headers=data["headers"])
    assert len(res.json()) == 1


@pytest.mark.asyncio
async def test_company_contacts_roster(client: AsyncClient, setup: dict):
    data = setup
    res = await client.get(f"/api/v1/companies/{data['company'].id}/contacts", headers=data["headers"])
    assert res.status_code == 200
    assert len(res.json()) == 2


@pytest.mark.asyncio
async def test_company_leads_and_deals(client: AsyncClient, setup: dict):
    data = setup
    cid = data["company"].id
    # leads: id-linked + name-matched + converted = 3
    res = await client.get(f"/api/v1/companies/{cid}/leads", headers=data["headers"])
    assert res.status_code == 200
    assert len(res.json()) == 3

    deals = await client.get(f"/api/v1/companies/{cid}/deals", headers=data["headers"])
    assert deals.status_code == 200
    d = deals.json()
    assert d["total_leads"] == 3
    assert d["won_count"] == 1          # the Converted lead == associated customer
    assert d["total_value"] == 80000.0
    assert d["won_value"] == 50000.0


@pytest.mark.asyncio
async def test_lead_autolink_on_create(client: AsyncClient, db: AsyncSession, setup: dict):
    data = setup
    # create a lead via API whose company_name matches (different case)
    res = await client.post("/api/v1/leads/", json={
        "last_name": "New", "title": "Fresh", "company_name": "ACME INC"}, headers=data["headers"])
    assert res.status_code == 201
    assert res.json()["company_id"] == str(data["company"].id)


@pytest.mark.asyncio
async def test_company_timeline_and_communications(client: AsyncClient, db: AsyncSession, setup: dict):
    data = setup
    cid = data["company"].id
    db.add(Activity(organization_id=data["org"].id, activity_type="Call", subject="Kickoff",
                    status="Completed", company_id=cid, created_by=data["admin"].id, call_direction="OUTBOUND"))
    await db.commit()
    await client.patch(f"/api/v1/companies/{cid}", json={"phone": "+15551234"}, headers=data["headers"])
    await client.post("/api/v1/notes/", json={"content": "Signed NDA", "company_id": str(cid)}, headers=data["headers"])

    tl = await client.get(f"/api/v1/companies/{cid}/timeline", headers=data["headers"])
    assert tl.status_code == 200
    assert {"note", "activity", "audit"} <= {e["type"] for e in tl.json()}

    comm = await client.get(f"/api/v1/companies/{cid}/communications", headers=data["headers"])
    assert comm.status_code == 200
    assert len(comm.json()) == 1


PNG_BYTES = b"\x89PNG\r\n\x1a\n" + b"\x00" * 64


@pytest.mark.asyncio
async def test_company_attachments(client: AsyncClient, setup: dict):
    data = setup
    cid = str(data["company"].id)
    files = {"file": ("brief.png", PNG_BYTES, "image/png")}
    res = await client.post(f"/api/v1/companies/{cid}/attachments", files=files, headers=data["headers"])
    assert res.status_code == 201
    res = await client.get(f"/api/v1/companies/{cid}/attachments", headers=data["headers"])
    assert len(res.json()) == 1
    fname = res.json()[0]["filename"]
    res = await client.request("DELETE", f"/api/v1/companies/{cid}/attachments/{fname}", headers=data["headers"])
    assert res.status_code == 200


@pytest.mark.asyncio
async def test_company_report(client: AsyncClient, setup: dict):
    data = setup
    res = await client.get("/api/v1/companies/reports", headers=data["headers"])
    assert res.status_code == 200
    body = res.json()
    assert body["total_companies"] == 2
    assert body["customers"] == 1
    assert body["prospects"] == 1
    assert body["total_revenue"] == 6000000.0
    assert body["total_employees"] == 250
    assert any(b["label"] == "Software" for b in body["by_industry"])


@pytest.mark.asyncio
async def test_company_tags_list(client: AsyncClient, setup: dict):
    data = setup
    res = await client.get("/api/v1/companies/tags", headers=data["headers"])
    assert res.status_code == 200
    assert "strategic" in res.json()
