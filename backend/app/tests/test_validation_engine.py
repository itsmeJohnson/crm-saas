import pytest
from app.services.import_.validation_engine import validate_import_rows, normalize_phone

def test_normalize_phone():
    assert normalize_phone("+1 (555) 123-4567") == "+15551234567"
    assert normalize_phone("  555-1234  ") == "5551234"
    assert normalize_phone("") == ""

@pytest.mark.asyncio
async def test_validate_import_rows_success():
    rows = [
        {"First Name": "Alice", "Last Name": "Smith", "Email": "alice@test.com", "Job Title": "Sales Executive"}
    ]
    mapping = {
        "first_name": "First Name",
        "last_name": "Last Name",
        "email": "Email",
        "title": "Job Title"
    }
    
    async def mock_dup_check(email: str) -> bool:
        return False

    valid, errors = await validate_import_rows(rows, mapping, mock_dup_check)
    
    assert len(errors) == 0
    assert len(valid) == 1
    assert valid[0]["data"]["first_name"] == "Alice"
    assert valid[0]["data"]["last_name"] == "Smith"

@pytest.mark.asyncio
async def test_validate_import_rows_missing_required():
    rows = [
        {"Last Name": "", "Job Title": "Developer"},
        {"Last Name": "Jones", "Job Title": ""}
    ]
    mapping = {
        "last_name": "Last Name",
        "title": "Job Title"
    }
    
    async def mock_dup_check(email: str) -> bool:
        return False

    valid, errors = await validate_import_rows(rows, mapping, mock_dup_check)
    
    assert len(valid) == 0
    assert len(errors) == 2
    assert "Last Name is a required field" in errors[0]["reason"]
    assert "Job Title/Lead Title is a required field" in errors[1]["reason"]

@pytest.mark.asyncio
async def test_validate_import_rows_email_errors():
    rows = [
        {"Last Name": "Smith", "Job Title": "CEO", "Email": "invalidemail"},
        {"Last Name": "Jones", "Job Title": "Dev", "Email": "existing@test.com"}
    ]
    mapping = {
        "last_name": "Last Name",
        "title": "Job Title",
        "email": "Email"
    }
    
    async def mock_dup_check(email: str) -> bool:
        if email == "existing@test.com":
            return True
        return False

    valid, errors = await validate_import_rows(rows, mapping, mock_dup_check)
    
    assert len(valid) == 0
    assert len(errors) == 2
    assert "Invalid email address format" in errors[0]["reason"]
    assert "Lead with email already exists in your organization" in errors[1]["reason"]

@pytest.mark.asyncio
async def test_validate_import_rows_duplicate_in_batch():
    rows = [
        {"Last Name": "Smith", "Job Title": "CEO", "Email": "dup@test.com"},
        {"Last Name": "Jones", "Job Title": "Dev", "Email": "dup@test.com"}
    ]
    mapping = {
        "last_name": "Last Name",
        "title": "Job Title",
        "email": "Email"
    }
    
    async def mock_dup_check(email: str) -> bool:
        return False

    valid, errors = await validate_import_rows(rows, mapping, mock_dup_check)
    
    assert len(valid) == 1
    assert len(errors) == 1
    assert "Duplicate email address found within this import batch" in errors[0]["reason"]

@pytest.mark.asyncio
async def test_validate_import_rows_length_checks():
    long_name = "a" * 101
    rows = [
        {"Last Name": long_name, "Job Title": "CEO"}
    ]
    mapping = {
        "last_name": "Last Name",
        "title": "Job Title"
    }
    
    async def mock_dup_check(email: str) -> bool:
        return False

    valid, errors = await validate_import_rows(rows, mapping, mock_dup_check)
    
    assert len(valid) == 0
    assert len(errors) == 1
    assert "exceeds maximum length" in errors[0]["reason"]
