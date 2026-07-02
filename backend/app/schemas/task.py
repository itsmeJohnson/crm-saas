import uuid
from datetime import datetime
from pydantic import BaseModel, ConfigDict, Field


class ChecklistItem(BaseModel):
    id: str | None = None
    text: str
    done: bool = False


class TaskBase(BaseModel):
    title: str = Field(..., max_length=255)
    description: str | None = None
    priority: str = Field("Medium", max_length=20)
    status: str = Field("Todo", max_length=20)
    due_date: datetime | None = None
    remind_at: datetime | None = None
    assigned_user_id: uuid.UUID | None = None
    lead_id: uuid.UUID | None = None
    contact_id: uuid.UUID | None = None
    company_id: uuid.UUID | None = None
    recurrence: str = Field("none", max_length=20)
    checklist: list[ChecklistItem] | None = None


class TaskCreate(TaskBase):
    pass


class TaskUpdate(BaseModel):
    title: str | None = Field(None, max_length=255)
    description: str | None = None
    priority: str | None = Field(None, max_length=20)
    status: str | None = Field(None, max_length=20)
    due_date: datetime | None = None
    remind_at: datetime | None = None
    assigned_user_id: uuid.UUID | None = None
    lead_id: uuid.UUID | None = None
    contact_id: uuid.UUID | None = None
    company_id: uuid.UUID | None = None
    recurrence: str | None = Field(None, max_length=20)
    checklist: list[ChecklistItem] | None = None


class TaskResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    organization_id: uuid.UUID
    title: str
    description: str | None = None
    priority: str
    status: str
    due_date: datetime | None = None
    remind_at: datetime | None = None
    completed_at: datetime | None = None
    assigned_user_id: uuid.UUID | None = None
    created_by: uuid.UUID
    lead_id: uuid.UUID | None = None
    contact_id: uuid.UUID | None = None
    company_id: uuid.UUID | None = None
    recurrence: str
    recurrence_parent_id: uuid.UUID | None = None
    checklist: list | None = None
    attachments: list | None = None
    created_at: datetime
    updated_at: datetime


class TaskCommentCreate(BaseModel):
    body: str = Field(..., min_length=1)


class TaskCommentResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    task_id: uuid.UUID
    body: str
    created_by: uuid.UUID
    created_at: datetime


class TaskDependencyCreate(BaseModel):
    depends_on_task_id: uuid.UUID


class TaskDependencyResponse(BaseModel):
    id: uuid.UUID
    task_id: uuid.UUID
    depends_on_task_id: uuid.UUID
    depends_on_title: str | None = None
    depends_on_status: str | None = None


class TaskChecklistToggle(BaseModel):
    item_id: str
    done: bool


class TaskBulkUpdateFields(BaseModel):
    status: str | None = Field(None, max_length=20)
    priority: str | None = Field(None, max_length=20)
    assigned_user_id: uuid.UUID | None = None


class TaskBulkUpdateRequest(BaseModel):
    task_ids: list[uuid.UUID] = Field(..., min_length=1)
    fields: TaskBulkUpdateFields


class TaskBulkDeleteRequest(BaseModel):
    task_ids: list[uuid.UUID] = Field(..., min_length=1)


class TaskBulkResult(BaseModel):
    affected_count: int
    task_ids: list[uuid.UUID]


class TaskAttachmentResponse(BaseModel):
    filename: str
    url: str
    size: int | None = None
    uploaded_by: str | None = None
    uploaded_at: str | None = None


class TaskReportResponse(BaseModel):
    total: int
    open: int
    completed: int
    overdue: int
    due_today: int
    completion_rate: float
    by_status: list[dict]
    by_priority: list[dict]
    by_assignee: list[dict]
