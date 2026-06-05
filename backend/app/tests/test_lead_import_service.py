import pytest
import uuid
import csv
import io
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User
from app.models.lead import Lead
from app.models.lead_import import LeadImport
from app.repositories.organization import OrganizationRepository
from app.repositories.user_repository import UserRepository
from app.repositories.lead_repository import LeadRepository
from app.services.lead_import_service import LeadImportService, suggest_mappings
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
    return storage

@pytest.fixture
async def import_setup(db: AsyncSession):
    org_repo = OrganizationRepository(db)
    user_repo = UserRepository(db)
    lead_repo = LeadRepository(db)

    org = await org_repo.create({"name": "Import Org", "slug": "import-org"})
    await db.commit()

    actor = await user_repo.create_user(org.id, {
        "email": "actor@importorg.com",
        "hashed_password": "hashedpassword123",
        "first_name": "Alice",
        "last_name": "Admin",
        "role": "OrgAdmin",
        "is_active": True
    })

    # Create pre-existing lead for duplicate testing
    dup_lead = await lead_repo.create_lead(org.id, {
        "first_name": "Double",
        "last_name": "Lead",
        "email": "duplicate@import.com",
        "title": "Existing Manager"
    }, actor.id)
    await db.commit()

    return {
        "org": org,
        "actor": actor,
        "dup_lead": dup_lead
    }

@pytest.mark.asyncio
async def test_suggest_mappings():
    # Test column alias detection and confidence logic
    headers = ["First Name", "lname", "Email Address", "Deal Amount", "UnrecognizedCol"]
    suggestions = suggest_mappings(headers)
    
    # "First Name" matches exactly
    assert suggestions["first_name"]["column"] == "First Name"
    assert suggestions["first_name"]["confidence"] == 1.0

    # "lname" matches last_name alias
    assert suggestions["last_name"]["column"] == "lname"
    assert suggestions["last_name"]["confidence"] == 0.8

    # "Email Address" matches email alias
    assert suggestions["email"]["column"] == "Email Address"
    assert suggestions["email"]["confidence"] == 0.8

    # "Deal Amount" matches value alias
    assert suggestions["value"]["column"] == "Deal Amount"
    assert suggestions["value"]["confidence"] == 0.8

    # "UnrecognizedCol" does not match anything
    assert suggestions["company_name"]["column"] is None
    assert suggestions["company_name"]["confidence"] == 0.0

@pytest.mark.asyncio
async def test_template_generation():
    # Test CSV template
    csv_tpl = LeadImportService.generate_csv_template()
    assert "First Name,Last Name,Email,Phone,Company,Title,Deal Value,Source" in csv_tpl

    # Test Excel template
    xlsx_tpl = LeadImportService.generate_xlsx_template()
    assert len(xlsx_tpl) > 0
    assert isinstance(xlsx_tpl, bytes)

@pytest.mark.asyncio
async def test_process_csv_import(db: AsyncSession, import_setup: dict):
    data = import_setup
    import_service = LeadImportService(db)
    lead_repo = LeadRepository(db)

    # Prepare Mock CSV content:
    # Row 1: Valid lead
    # Row 2: Invalid lead (Missing Title - required)
    # Row 3: Duplicate lead (Matches pre-existing duplicate@import.com)
    # Row 4: Valid lead
    csv_rows = [
        ["First Name", "Last Name", "Email Address", "Phone Number", "Company Name", "Job Title", "Deal Amount", "Source"],
        ["John", "Doe", "johndoe@test.com", "555-0011", "Initech", "Developer", "12000", "Web"],
        ["No", "Title", "notitle@test.com", "", "Globex", "", "", "Direct"],
        ["Dup", "Lead", "duplicate@import.com", "", "Acme", "VP Sales", "45000", "Referral"],
        ["Jane", "Smith", "janesmith@test.com", "555-0022", "Hooli", "CEO", "80000", "Google Ads"]
    ]
    
    out = io.StringIO()
    writer = csv.writer(out)
    writer.writerows(csv_rows)
    csv_text = out.getvalue()

    # Pre-cache file in Redis (mock key)
    file_token = str(uuid.uuid4())
    await redis_client.set(f"import_file:{file_token}", csv_text, ex=300)

    # Map headers to model fields
    column_mapping = {
        "first_name": "First Name",
        "last_name": "Last Name",
        "email": "Email Address",
        "phone": "Phone Number",
        "company_name": "Company Name",
        "title": "Job Title",
        "value": "Deal Amount",
        "source": "Source"
    }

    import_log = await import_service.process_import_batch(
        actor=data["actor"],
        file_token=file_token,
        source_type="file",
        column_mapping=column_mapping,
        auto_assign=False
    )

    assert import_log.status == "COMPLETED"
    assert import_log.total_rows == 4
    assert import_log.successful_rows == 2
    assert import_log.failed_rows == 2
    assert import_log.mapping_confidence > 0.0

    # Assert row validation failures summary
    assert len(import_log.error_summary) == 2
    
    # First failure on row 3 (Missing Title)
    assert import_log.error_summary[0]["row"] == 3
    assert "Job Title/Lead Title is a required field and is missing" in import_log.error_summary[0]["reason"]

    # Second failure on row 4 (Duplicate check)
    assert import_log.error_summary[1]["row"] == 4
    assert "Lead with email already exists in your organization" in import_log.error_summary[1]["reason"]

    # Assert database additions
    # Valid lead 1: johndoe@test.com
    lead1 = await lead_repo.get_lead_by_email(data["org"].id, "johndoe@test.com")
    assert lead1 is not None
    assert lead1.first_name == "John"
    assert lead1.last_name == "Doe"
    assert lead1.company_name == "Initech"
    assert lead1.title == "Developer"
    assert lead1.value == 12000.0

    # Valid lead 2: janesmith@test.com
    lead2 = await lead_repo.get_lead_by_email(data["org"].id, "janesmith@test.com")
    assert lead2 is not None
    assert lead2.value == 80000.0

    # Assert downloadable failed rows report CSV
    failed_csv_report = await import_service.get_failed_rows_report(data["org"].id, import_log.id)
    assert "Import Error Reason" in failed_csv_report
    assert "No,Title,notitle@test.com,,Globex" in failed_csv_report
    assert "Job Title/Lead Title is a required field and is missing" in failed_csv_report
