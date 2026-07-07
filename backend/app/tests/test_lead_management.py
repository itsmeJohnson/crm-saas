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
async def setup_leads(db: AsyncSession):
    org_repo = OrganizationRepository(db)
    user_repo = UserRepository(db)

    org = await org_repo.create({"name": "Lead Mgmt Org", "slug": "lead-mgmt-org"})
    await db.commit()

    admin = await user_repo.create_user(org.id, {
        "email": "admin@lm.com",
        "hashed_password": get_password_hash("password123"),
        "first_name": "Admin", "last_name": "One",
        "role": "OrgAdmin", "is_active": True,
    })
    await db.commit()

    res_stage = await db.execute(
        select(PipelineStage.id).filter(
            PipelineStage.organization_id == org.id,
            PipelineStage.is_system_default == True,
        )
    )
    stage_id = res_stage.scalar()

    leads = []
    for i in range(3):
        lead = Lead(
            organization_id=org.id,
            first_name=f"Lead{i}", last_name="Test",
            email=f"lead{i}@test.com", phone=f"+1999000{i}",
            title=f"Opp {i}", source="Website" if i < 2 else "Referral",
            city="NYC", value=1000 * (i + 1),
            assigned_user_id=admin.id, created_by=admin.id, stage_id=stage_id,
        )
        db.add(lead)
        leads.append(lead)
    await db.commit()

    token = create_access_token(admin.id)
    return {
        "org": org, "admin": admin, "leads": leads, "stage_id": stage_id,
        "headers": {"Authorization": f"Bearer {token}"},
    }


@pytest.mark.asyncio
async def test_create_lead_with_priority(client: AsyncClient, setup_leads: dict):
    data = setup_leads
    payload = {"last_name": "Prio", "title": "VIP", "priority": "Urgent"}
    res = await client.post("/api/v1/leads/", json=payload, headers=data["headers"])
    assert res.status_code == 201
    body = res.json()
    assert body["priority"] == "Urgent"
    # Urgent priority contributes to the score even with no other signals
    assert body["score"] == 20
    assert body["is_archived"] is False


@pytest.mark.asyncio
async def test_default_priority_is_medium(client: AsyncClient, setup_leads: dict):
    data = setup_leads
    res = await client.post("/api/v1/leads/", json={"last_name": "Def", "title": "T"}, headers=data["headers"])
    assert res.status_code == 201
    assert res.json()["priority"] == "Medium"


@pytest.mark.asyncio
async def test_export_leads_csv(client: AsyncClient, setup_leads: dict):
    data = setup_leads
    res = await client.get("/api/v1/leads/export?format=csv", headers=data["headers"])
    assert res.status_code == 200
    assert "text/csv" in res.headers["content-type"]
    text = res.text
    assert "first_name" in text and "priority" in text
    # 3 seeded leads + header
    assert text.strip().count("\n") == 3


@pytest.mark.asyncio
async def test_export_leads_xlsx(client: AsyncClient, setup_leads: dict):
    data = setup_leads
    res = await client.get("/api/v1/leads/export?format=xlsx", headers=data["headers"])
    assert res.status_code == 200
    assert "spreadsheetml" in res.headers["content-type"]
    assert res.content[:2] == b"PK"  # xlsx is a zip


@pytest.mark.asyncio
async def test_advanced_filter_by_source(client: AsyncClient, setup_leads: dict):
    data = setup_leads
    res = await client.get("/api/v1/leads/?source=Referral", headers=data["headers"])
    assert res.status_code == 200
    body = res.json()
    assert len(body) == 1
    assert body[0]["source"] == "Referral"


@pytest.mark.asyncio
async def test_advanced_filter_by_value_range(client: AsyncClient, setup_leads: dict):
    data = setup_leads
    res = await client.get("/api/v1/leads/?min_value=1500&max_value=2500", headers=data["headers"])
    assert res.status_code == 200
    body = res.json()
    assert len(body) == 1
    assert float(body[0]["value"]) == 2000.0


@pytest.mark.asyncio
async def test_duplicate_detection_by_email(client: AsyncClient, setup_leads: dict):
    data = setup_leads
    res = await client.get("/api/v1/leads/duplicates?email=lead0@test.com", headers=data["headers"])
    assert res.status_code == 200
    body = res.json()
    assert len(body) == 1
    assert body[0]["email"] == "lead0@test.com"


@pytest.mark.asyncio
async def test_duplicate_detection_requires_param(client: AsyncClient, setup_leads: dict):
    data = setup_leads
    res = await client.get("/api/v1/leads/duplicates", headers=data["headers"])
    assert res.status_code == 400


@pytest.mark.asyncio
async def test_archive_and_restore_lead(client: AsyncClient, setup_leads: dict):
    data = setup_leads
    lead_id = str(data["leads"][0].id)

    # Archive
    res = await client.post(f"/api/v1/leads/{lead_id}/archive", headers=data["headers"])
    assert res.status_code == 200
    assert res.json()["is_archived"] is True

    # Archived lead excluded from default listing
    res = await client.get("/api/v1/leads/", headers=data["headers"])
    ids = [l["id"] for l in res.json()]
    assert lead_id not in ids

    # But visible with include_archived
    res = await client.get("/api/v1/leads/?include_archived=true", headers=data["headers"])
    ids = [l["id"] for l in res.json()]
    assert lead_id in ids

    # Restore
    res = await client.post(f"/api/v1/leads/{lead_id}/restore", headers=data["headers"])
    assert res.status_code == 200
    assert res.json()["is_archived"] is False

    res = await client.get("/api/v1/leads/", headers=data["headers"])
    ids = [l["id"] for l in res.json()]
    assert lead_id in ids


@pytest.mark.asyncio
async def test_restore_soft_deleted_lead(client: AsyncClient, setup_leads: dict):
    data = setup_leads
    lead_id = str(data["leads"][0].id)

    res = await client.delete(f"/api/v1/leads/{lead_id}", headers=data["headers"])
    assert res.status_code == 200

    # gone from listing
    res = await client.get("/api/v1/leads/", headers=data["headers"])
    assert lead_id not in [l["id"] for l in res.json()]

    # restore undeletes
    res = await client.post(f"/api/v1/leads/{lead_id}/restore", headers=data["headers"])
    assert res.status_code == 200
    res = await client.get("/api/v1/leads/", headers=data["headers"])
    assert lead_id in [l["id"] for l in res.json()]


@pytest.mark.asyncio
async def test_bulk_update_priority_and_status(client: AsyncClient, db: AsyncSession, setup_leads: dict):
    data = setup_leads
    lead_ids = [str(l.id) for l in data["leads"]]
    payload = {"lead_ids": lead_ids, "fields": {"priority": "High", "status": "Contacted"}}
    res = await client.post("/api/v1/leads/bulk-update", json=payload, headers=data["headers"])
    assert res.status_code == 200
    assert res.json()["updated_count"] == 3

    db_res = await db.execute(select(Lead).filter(Lead.id.in_([uuid.UUID(i) for i in lead_ids])))
    for lead in db_res.scalars().all():
        assert lead.priority == "High"
        assert lead.status == "Contacted"


@pytest.mark.asyncio
async def test_bulk_update_rejects_foreign_stage(client: AsyncClient, setup_leads: dict):
    data = setup_leads
    payload = {
        "lead_ids": [str(data["leads"][0].id)],
        "fields": {"stage_id": str(uuid.uuid4())},
    }
    res = await client.post("/api/v1/leads/bulk-update", json=payload, headers=data["headers"])
    assert res.status_code == 400


# --- Tranche B ---

def test_compute_score_heuristic():
    from app.services.lead_scoring import compute_score
    # email(15)+phone(15)+company(10)+value>=100k(30)+referral(20)+urgent(20) = 100 (capped)
    high = compute_score(email="a@b.com", phone="123", company_name="Acme",
                         value=150000, source="Referral", priority="Urgent")
    assert high == 100
    # minimal lead
    low = compute_score(email=None, phone=None, company_name=None,
                        value=None, source=None, priority="Low")
    assert low == 0
    # mid: phone(15)+value>=10k(10)+website(15)+medium(5) = 45
    mid = compute_score(email=None, phone="123", company_name=None,
                       value=15000, source="Website", priority="Medium")
    assert mid == 45


@pytest.mark.asyncio
async def test_score_computed_on_create(client: AsyncClient, setup_leads: dict):
    data = setup_leads
    payload = {
        "last_name": "Scored", "title": "Big Deal", "email": "big@deal.com",
        "phone": "+15551234", "company_name": "MegaCorp", "value": 120000,
        "source": "Referral", "priority": "High",
    }
    res = await client.post("/api/v1/leads/", json=payload, headers=data["headers"])
    assert res.status_code == 201
    # 15+15+10+30+20+10 = 100
    assert res.json()["score"] == 100


@pytest.mark.asyncio
async def test_score_recomputed_on_update(client: AsyncClient, setup_leads: dict):
    data = setup_leads
    lead_id = str(data["leads"][0].id)
    res = await client.patch(f"/api/v1/leads/{lead_id}", json={"priority": "Urgent", "value": 200000}, headers=data["headers"])
    assert res.status_code == 200
    assert res.json()["score"] > 0


@pytest.mark.asyncio
async def test_recompute_score_endpoint(client: AsyncClient, setup_leads: dict):
    data = setup_leads
    lead_id = str(data["leads"][0].id)
    res = await client.post(f"/api/v1/leads/{lead_id}/recompute-score", headers=data["headers"])
    assert res.status_code == 200
    assert "score" in res.json()


@pytest.mark.asyncio
async def test_saved_filter_crud(client: AsyncClient, setup_leads: dict):
    data = setup_leads
    # create
    payload = {"name": "Hot Leads", "entity_type": "lead", "definition": {"priority": "Urgent", "status": "New"}}
    res = await client.post("/api/v1/leads/saved-filters", json=payload, headers=data["headers"])
    assert res.status_code == 201
    fid = res.json()["id"]
    assert res.json()["name"] == "Hot Leads"

    # list
    res = await client.get("/api/v1/leads/saved-filters", headers=data["headers"])
    assert res.status_code == 200
    assert any(f["id"] == fid for f in res.json())

    # update
    res = await client.patch(f"/api/v1/leads/saved-filters/{fid}", json={"name": "Very Hot"}, headers=data["headers"])
    assert res.status_code == 200
    assert res.json()["name"] == "Very Hot"

    # delete
    res = await client.delete(f"/api/v1/leads/saved-filters/{fid}", headers=data["headers"])
    assert res.status_code == 204

    res = await client.get("/api/v1/leads/saved-filters", headers=data["headers"])
    assert not any(f["id"] == fid for f in res.json())


@pytest.mark.asyncio
async def test_lead_timeline_and_audit(client: AsyncClient, setup_leads: dict):
    data = setup_leads
    lead_id = str(data["leads"][0].id)

    # generate an audit event via update
    await client.patch(f"/api/v1/leads/{lead_id}", json={"status": "Contacted"}, headers=data["headers"])
    # add a note (creates a note timeline event)
    await client.post("/api/v1/notes/", json={"content": "Called them", "lead_id": lead_id}, headers=data["headers"])

    # timeline
    res = await client.get(f"/api/v1/leads/{lead_id}/timeline", headers=data["headers"])
    assert res.status_code == 200
    events = res.json()
    types = {e["type"] for e in events}
    assert "note" in types
    assert "audit" in types

    # audit
    res = await client.get(f"/api/v1/leads/{lead_id}/audit", headers=data["headers"])
    assert res.status_code == 200
    assert len(res.json()) >= 1
    assert any(e["action"] == "LEAD_UPDATED" for e in res.json())


PNG_BYTES = b"\x89PNG\r\n\x1a\n" + b"\x00" * 64


@pytest.mark.asyncio
async def test_lead_attachment_upload_list_delete(client: AsyncClient, setup_leads: dict):
    data = setup_leads
    lead_id = str(data["leads"][0].id)

    files = {"file": ("photo.png", PNG_BYTES, "image/png")}
    res = await client.post(f"/api/v1/leads/{lead_id}/attachments", files=files, headers=data["headers"])
    assert res.status_code == 201
    body = res.json()
    assert body["filename"] == "photo.png"
    assert body["size"] == len(PNG_BYTES)

    res = await client.get(f"/api/v1/leads/{lead_id}/attachments", headers=data["headers"])
    assert res.status_code == 200
    assert len(res.json()) == 1
    stored = res.json()[0]["filename"]

    res = await client.request("DELETE", f"/api/v1/leads/{lead_id}/attachments/{stored}", headers=data["headers"])
    assert res.status_code == 200

    res = await client.get(f"/api/v1/leads/{lead_id}/attachments", headers=data["headers"])
    assert len(res.json()) == 0


@pytest.mark.asyncio
async def test_lead_attachment_rejects_bad_type(client: AsyncClient, setup_leads: dict):
    data = setup_leads
    lead_id = str(data["leads"][0].id)
    files = {"file": ("evil.exe", b"MZ\x00\x00", "application/octet-stream")}
    res = await client.post(f"/api/v1/leads/{lead_id}/attachments", files=files, headers=data["headers"])
    assert res.status_code == 400


# --- Tranche C: Reports ---

@pytest.mark.asyncio
async def test_lead_report(client: AsyncClient, setup_leads: dict):
    data = setup_leads
    res = await client.get("/api/v1/leads/reports", headers=data["headers"])
    assert res.status_code == 200
    body = res.json()
    assert body["total_leads"] == 3
    # 3 leads: values 1000, 2000, 3000 => 6000
    assert body["total_value"] == 6000.0
    # sources: 2 Website, 1 Referral
    sources = {b["label"]: b["count"] for b in body["by_source"]}
    assert sources.get("Website") == 2
    assert sources.get("Referral") == 1
    # owner breakdown present
    assert len(body["by_owner"]) == 1
    assert body["by_owner"][0]["count"] == 3
    assert "conversion_rate" in body
