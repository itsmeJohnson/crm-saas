import pytest
import uuid
from sqlalchemy.ext.asyncio import AsyncSession
from app.repositories.organization import OrganizationRepository
from app.repositories.user_repository import UserRepository
from app.repositories.company_repository import CompanyRepository
from app.repositories.contact_repository import ContactRepository
from app.repositories.lead_repository import LeadRepository
from app.repositories.activity_repository import ActivityRepository
from app.repositories.note_repository import NoteRepository

@pytest.fixture
async def setup_tenant_data(db: AsyncSession):
    org_repo = OrganizationRepository(db)
    user_repo = UserRepository(db)

    # 1. Setup two organizations (Tenant A and Tenant B)
    org_a = await org_repo.create({"name": "Tenant A", "slug": "tenant-a"})
    org_b = await org_repo.create({"name": "Tenant B", "slug": "tenant-b"})
    await db.commit()

    # 2. Create users under each organization
    user_a = await user_repo.create_user(org_a.id, {
        "email": "userA@test.com",
        "hashed_password": "hash",
        "first_name": "Alice",
        "last_name": "Smith",
        "role": "OrgAdmin",
        "is_active": True
    })
    user_b = await user_repo.create_user(org_b.id, {
        "email": "userB@test.com",
        "hashed_password": "hash",
        "first_name": "Bob",
        "last_name": "Jones",
        "role": "OrgAdmin",
        "is_active": True
    })
    await db.commit()

    return {
        "org_a_id": org_a.id,
        "org_b_id": org_b.id,
        "user_a_id": user_a.id,
        "user_b_id": user_b.id
    }

@pytest.mark.asyncio
async def test_company_repository(db: AsyncSession, setup_tenant_data: dict):
    data = setup_tenant_data
    company_repo = CompanyRepository(db)

    # Create Company in Org A
    company_a = await company_repo.create_company(
        organization_id=data["org_a_id"],
        company_data={"name": "Acme Corp", "domain": "acme.com", "industry": "Tech"},
        created_by=data["user_a_id"]
    )
    # Create Company in Org B
    company_b = await company_repo.create_company(
        organization_id=data["org_b_id"],
        company_data={"name": "Globex Corp", "domain": "globex.com", "industry": "Manufacturing"},
        created_by=data["user_b_id"]
    )
    await db.commit()

    # Get by ID - Tenant Isolation
    assert await company_repo.get_company_by_id(data["org_a_id"], company_a.id) is not None
    assert await company_repo.get_company_by_id(data["org_b_id"], company_a.id) is None

    # Paginate and Search
    records, total = await company_repo.paginate_companies(data["org_a_id"], skip=0, limit=10, search_query="Acme")
    assert total == 1
    assert records[0].id == company_a.id

    records, total = await company_repo.paginate_companies(data["org_a_id"], skip=0, limit=10, search_query="Globex")
    assert total == 0

    # Update
    updated = await company_repo.update_company(data["org_a_id"], company_a.id, {"industry": "Software"})
    assert updated.industry == "Software"
    await db.commit()

    # Soft Delete
    deleted = await company_repo.soft_delete_company(data["org_a_id"], company_a.id)
    assert deleted.is_deleted is True
    await db.commit()

    assert await company_repo.get_company_by_id(data["org_a_id"], company_a.id) is None

@pytest.mark.asyncio
async def test_contact_repository(db: AsyncSession, setup_tenant_data: dict):
    data = setup_tenant_data
    contact_repo = ContactRepository(db)

    # Create
    contact_a = await contact_repo.create_contact(
        organization_id=data["org_a_id"],
        contact_data={"first_name": "John", "last_name": "Doe", "email": "john@doe.com"},
        created_by=data["user_a_id"]
    )
    await db.commit()

    # Get by ID
    assert await contact_repo.get_contact_by_id(data["org_a_id"], contact_a.id) is not None
    assert await contact_repo.get_contact_by_id(data["org_b_id"], contact_a.id) is None

    # Paginate and Search
    records, total = await contact_repo.paginate_contacts(data["org_a_id"], skip=0, limit=10, search_query="John")
    assert total == 1
    assert records[0].id == contact_a.id

    # Update
    updated = await contact_repo.update_contact(data["org_a_id"], contact_a.id, {"first_name": "Johnny"})
    assert updated.first_name == "Johnny"
    await db.commit()

    # Soft Delete
    deleted = await contact_repo.soft_delete_contact(data["org_a_id"], contact_a.id)
    assert deleted.is_deleted is True
    await db.commit()

@pytest.mark.asyncio
async def test_lead_repository(db: AsyncSession, setup_tenant_data: dict):
    data = setup_tenant_data
    lead_repo = LeadRepository(db)

    # Create
    lead_a = await lead_repo.create_lead(
        organization_id=data["org_a_id"],
        lead_data={"title": "Acme Deal", "last_name": "Smith", "status": "New", "value": 10000.0},
        created_by=data["user_a_id"]
    )
    await db.commit()

    # Get by ID
    assert await lead_repo.get_lead_by_id(data["org_a_id"], lead_a.id) is not None
    assert await lead_repo.get_lead_by_id(data["org_b_id"], lead_a.id) is None

    # Paginate and Search/Filter
    records, total = await lead_repo.paginate_leads(data["org_a_id"], skip=0, limit=10, search_query="Acme", status="New")
    assert total == 1
    assert records[0].id == lead_a.id

    # Update
    updated = await lead_repo.update_lead(data["org_a_id"], lead_a.id, {"status": "Qualified"})
    assert updated.status == "Qualified"
    await db.commit()

    # Soft Delete
    deleted = await lead_repo.soft_delete_lead(data["org_a_id"], lead_a.id)
    assert deleted.is_deleted is True
    await db.commit()

@pytest.mark.asyncio
async def test_activity_repository(db: AsyncSession, setup_tenant_data: dict):
    data = setup_tenant_data
    activity_repo = ActivityRepository(db)

    # Create
    activity_a = await activity_repo.create_activity(
        organization_id=data["org_a_id"],
        activity_data={"activity_type": "Call", "subject": "Intro call", "status": "Planned"},
        created_by=data["user_a_id"]
    )
    await db.commit()

    # Get by ID
    assert await activity_repo.get_activity_by_id(data["org_a_id"], activity_a.id) is not None
    assert await activity_repo.get_activity_by_id(data["org_b_id"], activity_a.id) is None

    # Paginate
    records, total = await activity_repo.paginate_activities(data["org_a_id"], skip=0, limit=10, activity_type="Call")
    assert total == 1
    assert records[0].id == activity_a.id

    # Update
    updated = await activity_repo.update_activity(data["org_a_id"], activity_a.id, {"status": "Completed"})
    assert updated.status == "Completed"
    await db.commit()

    # Soft Delete
    deleted = await activity_repo.soft_delete_activity(data["org_a_id"], activity_a.id)
    assert deleted.is_deleted is True
    await db.commit()

@pytest.mark.asyncio
async def test_note_repository(db: AsyncSession, setup_tenant_data: dict):
    data = setup_tenant_data
    note_repo = NoteRepository(db)

    # Create
    note_a = await note_repo.create_note(
        organization_id=data["org_a_id"],
        note_data={"content": "This is a note"},
        created_by=data["user_a_id"]
    )
    await db.commit()

    # Get by ID
    assert await note_repo.get_note_by_id(data["org_a_id"], note_a.id) is not None
    assert await note_repo.get_note_by_id(data["org_b_id"], note_a.id) is None

    # Paginate
    records, total = await note_repo.paginate_notes(data["org_a_id"], skip=0, limit=10)
    assert total == 1
    assert records[0].id == note_a.id

    # Update
    updated = await note_repo.update_note(data["org_a_id"], note_a.id, {"content": "Updated note content"})
    assert updated.content == "Updated note content"
    await db.commit()

    # Soft Delete
    deleted = await note_repo.soft_delete_note(data["org_a_id"], note_a.id)
    assert deleted.is_deleted is True
    await db.commit()
