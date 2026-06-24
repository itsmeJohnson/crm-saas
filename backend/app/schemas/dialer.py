import uuid
from enum import Enum
from typing import Any, Dict, Literal, Optional
from pydantic import BaseModel, Field, model_validator

class NextLeadRequest(BaseModel):
    collective_pooling: bool = Field(default=False, description="Whether to fetch unassigned leads from the TL's queue if no direct leads are assigned.")
    knowlarity_api_key: Optional[str] = Field(default=None, description="Optional Knowlarity API key for outbound dialer calls.")
    knowlarity_srn: Optional[str] = Field(default=None, description="Optional Knowlarity Caller ID (SRN) number.")
    agent_phone_number: Optional[str] = Field(default=None, description="Optional Agent phone number to bridge with the customer call.")

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
    # Inbound specific dispositions
    INBOUND_RESOLVED = "Answered / Resolved"
    INBOUND_CALLBACK = "Callback Requested"
    INBOUND_INTERESTED = "Interested"
    INBOUND_NOT_INTERESTED = "Not Interested"
    INBOUND_SPAM = "Spam / Junk"

class CallDispositionRequest(BaseModel):
    status: CallDispositionStatus
    remarks: str = Field(..., min_length=1, description="Remarks are required and must not be empty.")
    custom_pipeline_stage_id: Optional[uuid.UUID] = Field(default=None, description="Pipeline stage to advance to when status is Picked or Interested.")

    @model_validator(mode="after")
    def validate_picked_stage(self) -> "CallDispositionRequest":
        requires_stage = {CallDispositionStatus.PICKED, CallDispositionStatus.INBOUND_INTERESTED}
        allows_stage = {CallDispositionStatus.PICKED, CallDispositionStatus.INBOUND_INTERESTED, CallDispositionStatus.INBOUND_RESOLVED, CallDispositionStatus.INBOUND_CALLBACK}
        
        if self.status in requires_stage and not self.custom_pipeline_stage_id:
            raise ValueError(f"custom_pipeline_stage_id is required when status is '{self.status.value}'.")
        if self.status not in allows_stage and self.custom_pipeline_stage_id is not None:
            raise ValueError(f"custom_pipeline_stage_id can only be specified for Picked, Interested, Resolved, or Callback statuses.")
        return self
