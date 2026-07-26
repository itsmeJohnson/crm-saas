import uuid
from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel, ConfigDict, Field

class NotificationResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    category: str
    title: str
    body: str
    link_url: str | None = None
    is_read: bool
    read_at: datetime | None = None
    action_metadata: dict | None = None
    priority: str = "normal"
    is_dismissed: bool = False
    actions: list | None = None
    channels_sent: list | None = None
    created_at: datetime

class UnreadCountResponse(BaseModel):
    unread_count: int


class CategoryCount(BaseModel):
    category: str
    count: int


class PreferenceItem(BaseModel):
    category: str
    in_app: bool = True
    email: bool = False
    sms: bool = False
    whatsapp: bool = False
    push: bool = False


class PreferenceUpdate(BaseModel):
    items: List[PreferenceItem]


class PushSubscribeReq(BaseModel):
    endpoint: str = Field(..., min_length=1)
    p256dh: Optional[str] = None
    auth: Optional[str] = None
    user_agent: Optional[str] = None


class PushUnsubscribeReq(BaseModel):
    endpoint: str


class DeviceRegisterReq(BaseModel):
    token: str = Field(..., min_length=1)
    platform: str = Field(..., pattern="^(fcm|apns)$")
    device_name: Optional[str] = None


class DeviceUnregisterReq(BaseModel):
    token: str = Field(..., min_length=1)


class BulkReadReq(BaseModel):
    ids: Optional[List[uuid.UUID]] = None
    category: Optional[str] = None


class BroadcastReq(BaseModel):
    title: str = Field(..., min_length=1, max_length=255)
    body: str = Field(..., min_length=1)
    category: str = "system"
    priority: str = "normal"
    role: Optional[str] = None       # limit to a role, else whole org
    link_url: Optional[str] = None
    actions: Optional[list] = None
    fanout: bool = False             # also send via email/SMS/WhatsApp/push per prefs


class BroadcastResult(BaseModel):
    recipients: int
    sent: int


class ReportBucket(BaseModel):
    label: str
    count: int


class NotificationStats(BaseModel):
    total: int
    unread: int
    read: int
    read_rate: float
    by_category: List[ReportBucket]
    by_priority: List[ReportBucket]
