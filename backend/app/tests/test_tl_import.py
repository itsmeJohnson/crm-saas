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
from app.models.lead_import import LeadImport
from app.core.redis import redis_client

@pytest.fixture(autouse=True)
def mock_redis_local(monkeypatch):
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
    return storage

@pytest.fixture
async def setup_tl_import_data(db: AsyncSession):
    org_repo = OrganizationRepository(db)
    user_repo = UserRepository(db)

    # 1. Create Organization
    org = await org_repo.create({"name": "Import Org", "slug": "import-org"})
    await db.commit()

    # 2. Super Admin (OrgAdmin)
    super_admin = await user_repo.create_user(org.id, {
        "email": "sa@i.com",
        "hashed_password": get_password_hash("password123"),
        "first_name": "Super",
        "last_name": "Admin",
        "role": "OrgAdmin",
        "is_active": True
    })

    # 3. Manager
    manager = await user_repo.create_user(org.id, {
        "email": "mgr@i.com",
        "hashed_password": get_password_hash("password123"),
        "first_name": "Manager",
        "last_name": "One",
        "role": "Manager",
        "is_active": True,
        "reporting_to_id": super_admin.id
    })

    # 4. Team Leader (TL) - Employee reporting to Manager
    tl = await user_repo.create_user(org.id, {
        "email": "tl@i.com",
        "hashed_password": get_password_hash("password123"),
        "first_name": "TL",
        "last_name": "One",
        "role": "Employee",
        "is_active": True,
        "reporting_to_id": manager.id
    })

    # 5. Telecaller 1 (reporting to TL)
    tc1 = await user_repo.create_user(org.id, {
        "email": "tc1@i.com",
        "hashed_password": get_password_hash("password123"),
        "first_name": "TC1",
        "last_name": "One",
        "role": "Employee",
        "is_active": True,
        "reporting_to_id": tl.id
    })

    # 6. Telecaller 2 (reporting to TL)
    tc2 = await user_repo.create_user(org.id, {
        "email": "tc2@i.com",
        "hashed_password": get_password_hash("password123"),
        "first_name": "TC2",
        "last_name": "One",
        "role": "Employee",
        "is_active": True,
        "reporting_to_id": tl.id
    })

    # 7. Other TL (outside chain)
    other_tl = await user_repo.create_user(org.id, {
        "email": "othertl@i.com",
        "hashed_password": get_password_hash("password123"),
        "first_name": "Other",
        "last_name": "TL",
        "role": "Employee",
        "is_active": True,
        "reporting_to_id": manager.id
    })

    await db.commit()

    token_tl = create_access_token(tl.id)
    token_tc1 = create_access_token(tc1.id)

    return {
        "org": org,
        "super_admin": super_admin,
        "tl": tl,
        "tc1": tc1,
        "tc2": tc2,
        "other_tl": other_tl,
        "headers_tl": {"Authorization": f"Bearer {token_tl}"},
        "headers_tc1": {"Authorization": f"Bearer {token_tc1}"}
    }

@pytest.mark.asyncio
async def test_tl_import_permissions(client: AsyncClient, setup_tl_import_data: dict, mock_redis_local):
    data = setup_tl_import_data
    
    # TL gets template - should be allowed (require_tl_or_above)
    res_template = await client.get("/api/v1/leads/import/template", headers=data["headers_tl"])
    assert res_template.status_code == 200

    # Telecaller gets template - should be forbidden
    res_template_tc = await client.get("/api/v1/leads/import/template", headers=data["headers_tc1"])
    assert res_template_tc.status_code == 403

@pytest.mark.asyncio
async def test_tl_process_import_multiple_users(client: AsyncClient, db: AsyncSession, setup_tl_import_data: dict, mock_redis_local):
    data = setup_tl_import_data
    
    # 1. Put CSV content into mock redis
    file_token = "mock_import_token"
    csv_content = "First Name,Last Name,Email,Phone,Company,Title,City,Deal Value,Source\n" \
                  "Alice,Smith,alice@example.com,+1234567890,Company A,Representative,Seattle,5000,Web\n" \
                  "Bob,Jones,bob@example.com,+1234567891,Company B,Manager,Chicago,10000,Referral\n"
    mock_redis_local[f"import_file:{file_token}"] = csv_content

    # 2. Process import with MULTIPLE_USERS assignment mode
    payload = {
        "file_token": file_token,
        "source_type": "file",
        "column_mapping": {
            "first_name": "First Name",
            "last_name": "Last Name",
            "email": "Email",
            "phone": "Phone",
            "company_name": "Company",
            "title": "Title",
            "city": "City",
            "value": "Deal Value",
            "source": "Source"
        },
        "auto_assign": False,
        "assignment_mode": "MULTIPLE_USERS",
        "assigned_user_ids": [str(data["tc1"].id), str(data["tc2"].id)]
    }

    res = await client.post("/api/v1/leads/import/process", json=payload, headers=data["headers_tl"])
    assert res.status_code == 200
    res_data = res.json()
    assert res_data["successful_rows"] == 2
    assert res_data["failed_rows"] == 0

    # 3. Refetch imported leads and check splitting
    stmt = select(Lead).filter(Lead.import_id == uuid.UUID(res_data["id"]))
    db_res = await db.execute(stmt)
    leads = db_res.scalars().all()
    assert len(leads) == 2
    
    # One lead to tc1, one to tc2
    assigned_ids = {l.assigned_user_id for l in leads}
    assert assigned_ids == {data["tc1"].id, data["tc2"].id}

@pytest.mark.asyncio
async def test_tl_process_import_invalid_assignee(client: AsyncClient, setup_tl_import_data: dict, mock_redis_local):
    data = setup_tl_import_data
    
    # 1. Put CSV content into mock redis
    file_token = "mock_import_token_invalid"
    csv_content = "First Name,Last Name,Email,Phone,Company,Title,City,Deal Value,Source\n" \
                  "Alice,Smith,alice@example.com,+1234567890,Company A,Representative,Seattle,5000,Web\n"
    mock_redis_local[f"import_file:{file_token}"] = csv_content

    # 2. Process import with other_tl (which is NOT in TL's downline reporting chain)
    payload = {
        "file_token": file_token,
        "source_type": "file",
        "column_mapping": {
            "first_name": "First Name",
            "last_name": "Last Name",
            "email": "Email",
            "phone": "Phone",
            "company_name": "Company",
            "title": "Title"
        },
        "auto_assign": False,
        "assignment_mode": "SPECIFIC_USER",
        "assigned_user_id": str(data["other_tl"].id)
    }

    res = await client.post("/api/v1/leads/import/process", json=payload, headers=data["headers_tl"])
    # Should fail with 403 forbidden because assignee is not downline
    assert res.status_code == 403
