import uuid
from typing import List, Literal
from pydantic import BaseModel, model_validator

class LeadBulkAssignRequest(BaseModel):
    lead_ids: List[uuid.UUID] | None = None
    import_id: uuid.UUID | None = None
    assignee_ids: List[uuid.UUID]
    strategy: Literal["RANGE", "SPLIT"]
    range_start: int | None = None
    range_end: int | None = None

    @model_validator(mode="after")
    def validate_identifiers(self):
        if not self.lead_ids and not self.import_id:
            raise ValueError("Either lead_ids or import_id must be provided")
        if self.lead_ids and self.import_id:
            raise ValueError("Cannot provide both lead_ids and import_id")
        if not self.assignee_ids:
            raise ValueError("assignee_ids list cannot be empty")
        return self

class LeadBulkAssignResponse(BaseModel):
    assigned_count: int
    lead_ids: List[uuid.UUID]
    assignee_ids: List[uuid.UUID]
