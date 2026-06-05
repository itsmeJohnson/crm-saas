import pytest
import uuid
from datetime import datetime, timezone
from pydantic import ValidationError

from app.models.lead_import import LeadImport, LeadImportStatus
from app.models.assignment_config import AssignmentConfig, AssignmentStrategy
from app.schemas.lead_import import LeadImportResponse
from app.schemas.assignment_config import AssignmentConfigResponse

def test_lead_import_status_enum():
    assert LeadImportStatus.PENDING == "PENDING"
    assert LeadImportStatus.PREVIEW_READY == "PREVIEW_READY"
    assert LeadImportStatus.PROCESSING == "PROCESSING"
    assert LeadImportStatus.COMPLETED == "COMPLETED"
    assert LeadImportStatus.FAILED == "FAILED"
    assert LeadImportStatus.PARTIAL_SUCCESS == "PARTIAL_SUCCESS"

def test_assignment_strategy_enum():
    assert AssignmentStrategy.ROUND_ROBIN == "ROUND_ROBIN"
    assert AssignmentStrategy.MANUAL == "MANUAL"

def test_lead_import_response_schema():
    # Test valid schema mapping
    data = {
        "id": uuid.uuid4(),
        "organization_id": uuid.uuid4(),
        "filename": "test.csv",
        "status": LeadImportStatus.PENDING,
        "total_rows": 10,
        "successful_rows": 8,
        "failed_rows": 2,
        "mapping_confidence": 0.9,
        "error_summary": [{"row": 1, "email": "err@test.com", "reason": "invalid"}],
        "failed_rows_file_path": "/path/to/file.csv",
        "created_by": uuid.uuid4(),
        "created_at": datetime.now(timezone.utc),
        "updated_at": datetime.now(timezone.utc)
    }
    
    resp = LeadImportResponse(**data)
    assert resp.filename == "test.csv"
    assert resp.status == LeadImportStatus.PENDING
    assert resp.failed_rows_file_path == "/path/to/file.csv"

def test_assignment_config_response_schema():
    data = {
        "organization_id": uuid.uuid4(),
        "is_active": True,
        "last_assigned_user_id": uuid.uuid4(),
        "assignment_strategy": AssignmentStrategy.ROUND_ROBIN
    }
    
    resp = AssignmentConfigResponse(**data)
    assert resp.is_active is True
    assert resp.assignment_strategy == AssignmentStrategy.ROUND_ROBIN
