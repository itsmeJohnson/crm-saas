import uuid
from enum import Enum
from typing import Any, Dict, Literal, Optional
from pydantic import BaseModel, Field, model_validator

class NextLeadRequest(BaseModel):
    collective_pooling: bool = Field(default=False, description="Whether to fetch unassigned leads from the TL's queue if no direct leads are assigned.")

class AgentStateUpdate(BaseModel):
    state: Literal["IDLE", "ACTIVE_CALLING", "BREAK"] = Field(..., description="The state to transition to: 'IDLE', 'ACTIVE_CALLING', 'BREAK'")
    metadata: Dict[str, Any] | None = Field(default=None, description="Optional metadata (e.g. break_reason: 'Lunch')")

class AgentStateResponse(BaseModel):
    state: str
    timestamp: str
    metadata: Dict[str, Any]

class CallDispositionStatus(str, Enum):
    RNR = "RNR"
    SWITCH_OFF = "Switch Off"
    BUSY = "Busy"
    NOT_EXIST = "Not Exist"
    OUT_OF_SERVICE = "Out of Service"
    PICKED = "Picked"

class CallDispositionRequest(BaseModel):
    status: CallDispositionStatus
    remarks: str = Field(..., min_length=1, description="Remarks are required and must not be empty.")
    custom_pipeline_stage_id: Optional[uuid.UUID] = Field(default=None, description="Pipeline stage to advance to when status is Picked.")

    @model_validator(mode="after")
    def validate_picked_stage(self) -> "CallDispositionRequest":
        if self.status == CallDispositionStatus.PICKED and not self.custom_pipeline_stage_id:
            raise ValueError("custom_pipeline_stage_id is required when status is 'Picked'.")
        if self.status != CallDispositionStatus.PICKED and self.custom_pipeline_stage_id is not None:
            raise ValueError("custom_pipeline_stage_id can only be specified when status is 'Picked'.")
        return self
