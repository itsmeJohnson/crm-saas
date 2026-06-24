from pydantic import BaseModel, Field
from typing import Optional

class CallRecordingWebhook(BaseModel):
    call_sid: str = Field(..., description="Unique transaction ID from the telephony provider")
    recording_url: str = Field(..., description="HTTP/S URL to access the audio recording file")
    duration: int = Field(..., description="Duration of the call in seconds")
    status: Optional[str] = Field(None, description="Telephony call outcome state")

class InboundCallWebhook(BaseModel):
    call_sid: str = Field(..., description="Unique transaction ID for this incoming call")
    from_number: str = Field(..., description="Caller's phone number")
    to_number: str = Field(..., description="Virtual number/SRN receiving the call")
