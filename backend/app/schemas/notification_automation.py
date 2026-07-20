from pydantic import BaseModel, Field


class Recipient(BaseModel):
    type: str
    value: str | None = None


class RuleCreate(BaseModel):
    name: str = Field(..., max_length=150)
    description: str | None = None
    trigger_event: str
    entity_type: str | None = None
    conditions: dict | None = None
    recipients: list[Recipient] = []
    channels: list[str] = ["in_app"]
    template_key: str | None = None
    title: str | None = None
    body: str | None = None
    category: str = "system"
    priority: str = "normal"
    digest: bool = False
    is_active: bool = True


class RuleUpdate(BaseModel):
    name: str | None = Field(None, max_length=150)
    description: str | None = None
    trigger_event: str | None = None
    entity_type: str | None = None
    conditions: dict | None = None
    recipients: list[Recipient] | None = None
    channels: list[str] | None = None
    template_key: str | None = None
    title: str | None = None
    body: str | None = None
    category: str | None = None
    priority: str | None = None
    digest: bool | None = None
    is_active: bool | None = None


class RuleResponse(BaseModel):
    id: str
    name: str
    description: str | None = None
    trigger_event: str
    entity_type: str | None = None
    conditions: dict | None = None
    recipients: list[dict]
    channels: list[str]
    template_key: str | None = None
    title: str | None = None
    body: str | None = None
    category: str
    priority: str
    digest: bool
    is_active: bool
    run_count: int
    notif_count: int
    created_at: str | None = None


class DeliveryResponse(BaseModel):
    id: str
    rule_id: str | None = None
    user_id: str
    channel: str
    status: str
    attempts: int
    error: str | None = None
    title: str | None = None
    queue_job_id: str | None = None
    sent_at: str | None = None
    created_at: str | None = None


class TemplateCreate(BaseModel):
    template_key: str = Field(..., max_length=80)
    template_name: str = Field(..., max_length=150)
    channel: str = "email"
    subject: str | None = None
    body: str = ""
    variables: list[str] | None = None
    category: str = "system"
    description: str | None = None


class TemplateUpdate(BaseModel):
    template_name: str | None = None
    channel: str | None = None
    subject: str | None = None
    body: str | None = None
    variables: list[str] | None = None
    category: str | None = None
    description: str | None = None
    is_active: bool | None = None


class TemplateResponse(BaseModel):
    template_key: str
    template_name: str
    channel: str
    subject: str | None = None
    body: str
    variables: list | None = None
    category: str
    description: str | None = None
    is_active: bool


class EnableRequest(BaseModel):
    enabled: bool


class AutomationReport(BaseModel):
    rules: int
    active_rules: int
    deliveries: int
    delivery_rate: float
    by_channel: dict
    by_status: dict
    pending_digest: int


class AutomationDashboard(BaseModel):
    rules: int
    active_rules: int
    deliveries: int
    delivery_rate: float
    pending_digest: int
    failed: int
    recent: list[dict]


class DigestResult(BaseModel):
    digests_sent: int = 0
