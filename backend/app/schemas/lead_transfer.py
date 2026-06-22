import uuid
from typing import List
from pydantic import BaseModel, model_validator

class LeadTransferRequest(BaseModel):
    source_user_id: uuid.UUID
    destination_user_ids: List[uuid.UUID]
    quantity: int | None = None
    lead_ids: List[uuid.UUID] | None = None

    @model_validator(mode="after")
    def validate_input(self) -> 'LeadTransferRequest':
        if self.quantity is None and self.lead_ids is None:
            raise ValueError("Either quantity or lead_ids must be provided")
        if self.quantity is not None and self.lead_ids is not None:
            raise ValueError("Cannot provide both quantity and lead_ids")
        if self.quantity is not None and self.quantity <= 0:
            raise ValueError("Quantity must be greater than zero")
        if not self.destination_user_ids:
            raise ValueError("destination_user_ids list cannot be empty")
        return self

class LeadTransferResponse(BaseModel):
    transferred_count: int
    lead_ids: List[uuid.UUID]
    destination_user_ids: List[uuid.UUID]
