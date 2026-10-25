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
    # Professional Telecalling Agency Dispositions
    PICKED_CONNECTED = "Picked — Connected"
    RNR = "RNR — Ringing No Response"
    BUSY = "Busy"
    SWITCHED_OFF = "Switched Off"
    NOT_REACHABLE = "Not Reachable"
    CALL_REJECTED = "Call Rejected"
    WRONG_NUMBER = "Wrong Number"
    NUMBER_NOT_EXIST = "Number Does Not Exist"
    INTERESTED = "Interested"
    NOT_INTERESTED = "Not Interested"
    FOLLOW_UP_REQUIRED = "Follow-up Required"
    CALLBACK_SCHEDULED = "Callback Scheduled"
    CONVERTED = "Converted / Successful"
    LANGUAGE_BARRIER = "Language Barrier"
    DO_NOT_CALL = "Do Not Call"
    TECHNICAL_FAILURE = "Technical Failure"

    # Historical & Inbound Aliases (Backwards Compatibility)
    PICKED = "Picked"
    SWITCH_OFF = "Switch Off"
    NOT_EXIST = "Not Exist"
    OUT_OF_SERVICE = "Out of Service"
    ANSWERED = "Answered"
    NO_ANSWER = "No Answer"
    INBOUND_RESOLVED = "Answered / Resolved"
    INBOUND_CALLBACK = "Callback Requested"
    INBOUND_INTERESTED = "Inbound Interested"
    INBOUND_NOT_INTERESTED = "Inbound Not Interested"
    INBOUND_SPAM = "Spam / Junk"

class CallDispositionRequest(BaseModel):
    status: CallDispositionStatus
    remarks: str = Field(..., description="Mandatory remarks (min 3 chars, max 1,000 chars).")
    call_sid: Optional[str] = Field(default=None, description="Unique call/session ID for deduplication.")
    call_duration: Optional[int] = Field(default=0, ge=0, description="Connected duration in seconds.")
    call_direction: Optional[str] = Field(default="OUTBOUND", description="Call direction: OUTBOUND or INBOUND.")
    technical_status: Optional[str] = Field(default=None, description="Technical status from provider/WebRTC: connected, ringing_no_answer, failed, busy.")
    follow_up_date: Optional[str] = Field(default=None, description="YYYY-MM-DD for follow-up or callback.")
    follow_up_time: Optional[str] = Field(default=None, description="HH:MM for follow-up or callback.")
    follow_up_priority: Optional[str] = Field(default="Medium", description="Low, Medium, High, or Urgent.")
    custom_pipeline_stage_id: Optional[uuid.UUID] = Field(default=None, description="Pipeline stage to advance to.")
    dispatch_omnichannel_followup: bool = Field(default=False, description="Trigger instant WhatsApp/SMS follow-up.")
    followup_template_name: Optional[str] = None
    followup_custom_note: Optional[str] = None

    @model_validator(mode="before")
    @classmethod
    def normalize_and_validate_payload(cls, data: Any) -> Any:
        if isinstance(data, dict):
            # 1. Normalize Status
            raw_status = data.get("status")
            if isinstance(raw_status, str):
                normalized = raw_status.strip()
                status_map = {
                    "Picked": "Picked — Connected",
                    "Answered": "Picked — Connected",
                    "Answered (Connected)": "Picked — Connected",
                    "Connected": "Picked — Connected",
                    "RNR": "RNR — Ringing No Response",
                    "No Answer": "RNR — Ringing No Response",
                    "No Answer / Ringing Not Responded": "RNR — Ringing No Response",
                    "Switch Off": "Switched Off",
                    "Switched Off / Out of Coverage": "Switched Off",
                    "Not Exist": "Number Does Not Exist",
                    "Wrong Number / Does Not Exist": "Number Does Not Exist",
                    "Callback": "Callback Scheduled",
                    "Callback Requested": "Callback Scheduled",
                    "Follow-up": "Follow-up Required",
                    "Follow-up Scheduled": "Follow-up Required",
                    "Interested / Qualified": "Interested",
                    "Converted": "Converted / Successful",
                    "Failed": "Technical Failure",
                }
                data["status"] = status_map.get(normalized, normalized)

            # 2. Validate Remarks (mandatory >= 3 characters after trimming)
            raw_remarks = data.get("remarks")
            if raw_remarks is None or not isinstance(raw_remarks, str) or len(raw_remarks.strip()) < 3:
                raise ValueError("Remarks are mandatory and must be at least 3 characters after trimming whitespace.")
            if len(raw_remarks.strip()) > 1000:
                raise ValueError("Remarks cannot exceed 1,000 characters.")
            data["remarks"] = raw_remarks.strip()

            # 3. Validate Follow-up Date/Time if required
            status_val = data.get("status")
            is_followup = status_val in (
                "Follow-up Required", "Callback Scheduled",
                CallDispositionStatus.FOLLOW_UP_REQUIRED.value, CallDispositionStatus.CALLBACK_SCHEDULED.value
            )
            if is_followup:
                f_date = data.get("follow_up_date")
                f_time = data.get("follow_up_time")
                if not f_date or not str(f_date).strip():
                    raise ValueError("Follow-up date is required for callbacks and scheduled follow-ups.")
                if not f_time or not str(f_time).strip():
                    raise ValueError("Follow-up time is required for callbacks and scheduled follow-ups.")

                # Ensure date/time is not in the past
                try:
                    from datetime import datetime, timezone
                    dt_str = f"{str(f_date).strip()}T{str(f_time).strip()}"
                    parsed_dt = datetime.fromisoformat(dt_str).replace(tzinfo=timezone.utc)
                    if parsed_dt < datetime.now(timezone.utc):
                        raise ValueError("Follow-up date and time cannot be in the past.")
                except ValueError as ve:
                    if "past" in str(ve):
                        raise
                    # Ignore format parse if simple date
        return data

class InboundLeadLookupRequest(BaseModel):
    phone: str
    caller_name: Optional[str] = None
    call_id: Optional[str] = None

class CallEndedRequest(BaseModel):
    lead_id: Optional[uuid.UUID] = None
    call_sid: Optional[str] = None
    duration: int = Field(default=0, ge=0)
    call_direction: Optional[str] = "OUTBOUND"
    status: Optional[str] = "Completed"
    recording_url: Optional[str] = None
