import pytest
import uuid
from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from app.repositories.organization import OrganizationRepository
from app.repositories.user_repository import UserRepository
from app.repositories.audit_repository import AuditRepository
from app.services.company_service import CompanyService
from app.services.contact_service import ContactService
from app.services.lead_service import LeadService
from app.services.activity_service import ActivityService
from app.services.note_service import NoteService

@pytest.fixture
async def setup_service_data(db: AsyncSession):
    org_repo = OrganizationRepository(db)
    user_repo = UserRepository(db)

    # Create Org A and Org B
    org_a = await org_repo.create({"name": "Tenant A", "slug": "tenant-a"})
    org_b = await org_repo.create({"name": "Tenant B", "slug": "tenant-b"})
    await db.commit()

    # Active User in Org A
    active_user_a = await user_repo.create_user(org_a.id, {
        "email": "activeA@test.com",
        "hashed_password": "hash",
        "first_name": "Active",
        "last_name": "A",
        "role": "OrgAdmin",
        "is_active": True
    })
    # Inactive User in Org A
    inactive_user_a = await user_repo.create_user(org_a.id, {
        "email": "inactiveA@test.com",
        "hashed_password": "hash",
        "first_name": "Inactive",
        "last_name": "A",
        "role": "Employee",
        "is_active": False
    })
    # Another Active User in Org A for assignments
    assignee_a = await user_repo.create_user(org_a.id, {
        "email": "assigneeA@test.com",
        "hashed_password": "hash",
        "first_name": "Assignee",
        "last_name": "A",
        "role": "Employee",
        "is_active": True
    })
    # Active User in Org B
    active_user_b = await user_repo.create_user(org_b.id, {
        "email": "activeB@test.com",
        "hashed_password": "hash",
        "first_name": "Active",
        "last_name": "B",
        "role": "OrgAdmin",
        "is_active": True
    })
    await db.commit()

    return {
        "org_a": org_a,
        "org_b": org_b,
        "user_a": active_user_a,
        "inactive_user_a": inactive_user_a,
        "assignee_a": assignee_a,
        "user_b": active_user_b
    }

@pytest.mark.asyncio
async def test_company_service(db: AsyncSession, setup_service_data: dict):
    data = setup_service_data
    comp_service = CompanyService(db)
    audit_repo = AuditRepository(db)

    # 1. Create company successfully
    company = await comp_service.create_company(
        actor=data["user_a"],
        company_data={"name": "Big Company", "assigned_user_id": data["assignee_a"].id}
    )
    assert company.name == "Big Company"
    assert company.assigned_user_id == data["assignee_a"].id
    await db.commit()

    # Verify audit log
    logs = await audit_repo.list_logs(data["org_a"].id)
    assert len(logs) == 1
    assert logs[0].action == "COMPANY_CREATED"

    # 2. Assign to inactive user (should fail)
    with pytest.raises(HTTPException) as exc_info:
        await comp_service.create_company(
            actor=data["user_a"],
            company_data={"name": "Fail Company", "assigned_user_id": data["inactive_user_a"].id}
        )
    assert exc_info.value.status_code == 400

    # 3. Assign to user of another tenant (should fail)
    with pytest.raises(HTTPException) as exc_info:
        await comp_service.create_company(
            actor=data["user_a"],
            company_data={"name": "Fail Company", "assigned_user_id": data["user_b"].id}
        )
    assert exc_info.value.status_code == 400

@pytest.mark.asyncio
async def test_contact_service_cross_tenant(db: AsyncSession, setup_service_data: dict):
    data = setup_service_data
    comp_service = CompanyService(db)
    contact_service = ContactService(db)

    # Create Company in Org B
    company_b = await comp_service.create_company(
        actor=data["user_b"],
        company_data={"name": "Org B Company"}
    )
    await db.commit()

    # Try to create Contact in Org A referencing Org B Company (should fail)
    with pytest.raises(HTTPException) as exc_info:
        await contact_service.create_contact(
            actor=data["user_a"],
            contact_data={
                "first_name": "Cross",
                "last_name": "Tenant",
                "company_id": company_b.id
            }
        )
    assert exc_info.value.status_code == 400

@pytest.mark.asyncio
async def test_cascading_soft_deletes(db: AsyncSession, setup_service_data: dict):
    data = setup_service_data
    lead_service = LeadService(db)
    activity_service = ActivityService(db)
    note_service = NoteService(db)

    # 1. Create a lead
    lead = await lead_service.create_lead(
        actor=data["user_a"],
        lead_data={"title": "Target Opportunity", "last_name": "Doe", "status": "New"}
    )
    await db.commit()

    # 2. Add activity and note linked to the lead
    activity = await activity_service.create_activity(
        actor=data["user_a"],
        activity_data={
            "activity_type": "Call",
            "subject": "Intro call",
            "lead_id": lead.id
        }
    )
    note = await note_service.create_note(
        actor=data["user_a"],
        note_data={
            "content": "Important info",
            "lead_id": lead.id
        }
    )
    await db.commit()

    # Verify they exist
    assert await activity_service.get_activity(data["user_a"], activity.id) is not None
    assert await note_service.get_note(data["user_a"], note.id) is not None

    # 3. Soft delete the lead
    await lead_service.soft_delete_lead(actor=data["user_a"], lead_id=lead.id)
    await db.commit()

    # 4. Verify lead is soft-deleted
    with pytest.raises(HTTPException) as exc_info:
        await lead_service.get_lead(data["user_a"], lead.id)
    assert exc_info.value.status_code == 404

    # 5. Verify activity and note are cascade soft-deleted
    with pytest.raises(HTTPException) as exc_info:
        await activity_service.get_activity(data["user_a"], activity.id)
    assert exc_info.value.status_code == 404

    with pytest.raises(HTTPException) as exc_info:
        await note_service.get_note(data["user_a"], note.id)
    assert exc_info.value.status_code == 404

@pytest.mark.asyncio
async def test_note_validation(db: AsyncSession, setup_service_data: dict):
    data = setup_service_data
    note_service = NoteService(db)

    # Try creating note with no entity linked (should fail)
    with pytest.raises(HTTPException) as exc_info:
        await note_service.create_note(
            actor=data["user_a"],
            note_data={"content": "Orphaned note"}
        )
    assert exc_info.value.status_code == 400
    assert "must be linked to at least one entity" in exc_info.value.detail
