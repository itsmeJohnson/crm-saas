import uuid
from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel, Field


class VoiceSendRequest(BaseModel):
    name: Optional[str] = Field(None, max_length=150)
    mode: str = Field(..., pattern="^(voice_note|tts)$")
    numbers: Optional[List[str]] = None
    lead_ids: Optional[List[uuid.UUID]] = None
    contact_ids: Optional[List[uuid.UUID]] = None

    # voice_note mode
    voice_type: Optional[str] = Field(None, max_length=8)  # 37 IVR / 34 promo-30 / 33 txn-30 / 35 TTS
    voice_medias_id: Optional[str] = Field(None, max_length=64)
    obd_type: Optional[str] = Field(None, max_length=20)  # single_voice | dtmf

    # tts mode
    tts_content: Optional[str] = Field(None, max_length=2000)
    tts_language: Optional[str] = Field(None, max_length=20)
    tts_gender: Optional[str] = Field(None, max_length=10)

    # scheduling / retry
    scheduled: bool = False
    scheduled_datetime: Optional[datetime] = None
    retry_interval: Optional[int] = Field(None, ge=0, le=1440)
    retry_count: Optional[int] = Field(None, ge=0, le=10)


class VoiceRecipientItem(BaseModel):
    id: str
    number: str
    unique_id: Optional[str] = None
    status: str
    vendor_status: Optional[str] = None
    dtmf: Optional[str] = None
    call_duration: Optional[str] = None
    lead_id: Optional[str] = None
    contact_id: Optional[str] = None


class VoiceBroadcastItem(BaseModel):
    id: str
    name: str
    mode: str
    status: str
    voice_type: Optional[str] = None
    voice_medias_id: Optional[str] = None
    tts_language: Optional[str] = None
    tts_gender: Optional[str] = None
    total_recipients: int
    provider_job_id: Optional[str] = None
    scheduled: bool
    sent_at: Optional[datetime] = None
    last_error: Optional[str] = None
    created_at: datetime


class VoiceBroadcastDetail(VoiceBroadcastItem):
    tts_content: Optional[str] = None
    recipients: List[VoiceRecipientItem] = []


class VoiceBroadcastList(BaseModel):
    items: List[VoiceBroadcastItem]
    total: int


class MissedCallRequest(BaseModel):
    did_number: str = Field(..., max_length=20)
    start_date: str = Field(..., description="YYYY-MM-DD")
    end_date: str = Field(..., description="YYYY-MM-DD")
