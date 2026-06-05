import uuid
from datetime import datetime
from enum import Enum
from pydantic import BaseModel, ConfigDict, model_validator
from typing import List, Dict, Any
from app.models.lead_import import LeadImportStatus

class AssignmentMode(str, Enum):
    AUTO = "AUTO"
    SPECIFIC_USER = "SPECIFIC_USER"
    NONE = "NONE"

class GoogleSheetsPreviewRequest(BaseModel):
    url: str

class ColumnMappingDetail(BaseModel):
    column: str | None = None
    confidence: float = 0.0

class ImportPreviewResponse(BaseModel):
    file_token: str
    headers: List[str]
    suggested_mapping: Dict[str, ColumnMappingDetail]
    preview_rows: List[Dict[str, Any]]

class LeadImportProcessRequest(BaseModel):
    file_token: str
    source_type: str  # "file" or "google_sheets"
    column_mapping: Dict[str, str]
    auto_assign: bool = True
    assignment_mode: AssignmentMode = AssignmentMode.NONE
    assigned_user_id: uuid.UUID | None = None

    @model_validator(mode='after')
    def validate_assigned_user(self) -> 'LeadImportProcessRequest':
        if 'assignment_mode' not in self.model_fields_set:
            if self.auto_assign:
                self.assignment_mode = AssignmentMode.AUTO
            else:
                self.assignment_mode = AssignmentMode.NONE

        if self.assignment_mode == AssignmentMode.SPECIFIC_USER and not self.assigned_user_id:
            raise ValueError("assigned_user_id must be provided when assignment_mode is 'SPECIFIC_USER'")
        return self

class RowErrorDetail(BaseModel):
    row: int
    email: str | None = None
    reason: str

class LeadImportResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    organization_id: uuid.UUID
    filename: str
    status: LeadImportStatus
    total_rows: int
    successful_rows: int
    failed_rows: int
    mapping_confidence: float
    error_summary: List[RowErrorDetail] | None = None
    failed_rows_file_path: str | None = None
    created_by: uuid.UUID
    created_at: datetime
    updated_at: datetime
