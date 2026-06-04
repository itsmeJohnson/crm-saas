import uuid
from datetime import datetime
from pydantic import BaseModel, ConfigDict
from typing import List, Dict, Any

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

class RowErrorDetail(BaseModel):
    row: int
    email: str | None = None
    reason: str

class LeadImportResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    organization_id: uuid.UUID
    filename: str
    status: str
    total_rows: int
    successful_rows: int
    failed_rows: int
    mapping_confidence: float
    error_summary: List[RowErrorDetail] | None = None
    created_by: uuid.UUID
    created_at: datetime
    updated_at: datetime
