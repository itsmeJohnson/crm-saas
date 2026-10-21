import uuid
from enum import Enum
from typing import Any, Dict, Literal, Optional
from pydantic import BaseModel, Field, model_validator

class TelephonyCreds(BaseModel):
    """Per-request calling credentials, provider-agnostic. `provider` selects the
    outbound gateway; only that provider's fields need to be supplied. Kept as a
    mixin so next-lead and call-lead share one shape."""
    provider: Optional[str] = Field(default="knowlarity", description="Calling provider: 'knowlarity' or 'myoperator'.")
    agent_phone_number: Optional[str] = Field(default=None, description="Agent phone number to bridge with the customer call (both providers).")
    # Knowlarity
    knowlarity_api_key: Optional[str] = Field(default=None, description="Knowlarity API key for the outbound call.")
    knowlarity_srn: Optional[str] = Field(default=None, description="Knowlarity Caller ID (SRN) number.")
    # MyOperator (Calling APIs → Endpoint Details + a Public IVR / OBD flow)
    myop_x_api_key: Optional[str] = Field(default=None, description="MyOperator OBD x-api-key.")
    myop_secret_key: Optional[str] = Field(default=None, description="MyOperator OBD secret-key / Authentication (also sent as secret_token).")
    myop_company_id: Optional[str] = Field(default=None, description="MyOperator Company ID.")
    myop_public_ivr_id: Optional[str] = Field(default=None, description="MyOperator Public IVR / outbound flow id (required to route OBD calls).")
    myop_type: Optional[str] = Field(default="1", description="MyOperator OBD call type: '1' | '2' | '3'.")

class NextLeadRequest(TelephonyCreds):
    collective_pooling: bool = Field(default=False, description="Whether to fetch unassigned leads from the TL's queue if no direct leads are assigned.")

class CallLeadRequest(TelephonyCreds):
    """Place a server-side click-to-call to ONE specific already-known lead (from
    the Leads list), regardless of its status. Unlike next-lead this does not
    fetch from the queue — the lead is chosen by the agent. The customer number
    is dialed server-side so it is never exposed to a masked telecaller."""

class AgentStateUpdate(BaseModel):
    state: Literal["IDLE", "RINGING", "ACTIVE_CALLING", "ON_CALL", "BREAK"] = Field(..., description="The state to transition to: 'IDLE', 'RINGING', 'ACTIVE_CALLING', 'ON_CALL', 'BREAK'")
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
    # Aliases and Inbound statuses
    ANSWERED = "Answered"
    NO_ANSWER = "No Answer"
    SWITCHED_OFF = "Switched Off"
    WRONG_NUMBER = "Wrong Number"
    INBOUND_RESOLVED = "Answered / Resolved"
    INBOUND_CALLBACK = "Callback Requested"
    INBOUND_INTERESTED = "Interested"
    INBOUND_NOT_INTERESTED = "Not Interested"
    INBOUND_SPAM = "Spam / Junk"

class CallDispositionRequest(BaseModel):
    status: CallDispositionStatus
    remarks: str = Field(..., min_length=1, description="Remarks are required and must not be empty.")
    custom_pipeline_stage_id: Optional[uuid.UUID] = Field(default=None, description="Pipeline stage to advance to when status is Picked or Interested.")
    dispatch_omnichannel_followup: bool = Field(default=False, description="Whether to trigger 2-second WhatsApp rich follow-up with intelligent SMS carrier fallback.")
    followup_template_name: Optional[str] = None
    followup_custom_note: Optional[str] = None

    @model_validator(mode="before")
    @classmethod
    def normalize_status(cls, data: Any) -> Any:
        if isinstance(data, dict):
            raw_status = data.get("status")
            if isinstance(raw_status, str):
                normalized = raw_status.strip()
                status_map = {
                    "Answered": "Picked",
                    "Answered (Connected)": "Picked",
                    "Connected": "Picked",
                    "No Answer": "RNR",
                    "No Answer / Ringing Not Responded": "RNR",
                    "Switched Off": "Switch Off",
                    "Switched Off / Out of Coverage": "Switch Off",
                    "Wrong Number": "Not Exist",
                    "Wrong Number / Does Not Exist": "Not Exist",
                    "Callback": "Callback Requested",
                    "Callback Scheduled": "Callback Requested",
                    "Interested / Qualified": "Interested",
                }
                data["status"] = status_map.get(normalized, normalized)
        return data

    @model_validator(mode="after")
    def validate_picked_stage(self) -> "CallDispositionRequest":
        # Keep pipeline stage optional; leads remain in current stage if not moved
        return self

class InboundLeadLookupRequest(BaseModel):
    phone: str
    caller_name: Optional[str] = None
    call_id: Optional[str] = None
