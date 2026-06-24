import uuid
from datetime import datetime, date
from pydantic import BaseModel, ConfigDict, Field
from app.models.target import TargetType, MetricType

class PerformanceTargetBase(BaseModel):
    target_type: TargetType
    metric_type: MetricType
    target_value: int = Field(..., gt=0, description="Target quota must be greater than zero")
    start_date: date
    end_date: date

class PerformanceTargetCreate(PerformanceTargetBase):
    pass

class PerformanceTargetResponse(PerformanceTargetBase):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    organization_id: uuid.UUID
    created_at: datetime
    updated_at: datetime

class TelecallerMetricsResponse(BaseModel):
    calls_made: int
    unique_leads_contacted: int
    conversions: int
    date: date

class TelecallerPerformanceSummary(BaseModel):
    user_id: uuid.UUID
    first_name: str | None
    last_name: str | None
    email: str
    calls_made: int
    unique_leads_contacted: int
    conversions: int
    conversion_rate: float

class PerformerMetric(BaseModel):
    user_id: uuid.UUID
    first_name: str | None
    last_name: str | None
    email: str
    calls_made: int
    conversions: int
    conversion_rate: float

class TeamLeaderMetricsResponse(BaseModel):
    total_calls_made: int
    total_unique_leads_contacted: int
    total_conversions: int
    downlines: list[TelecallerPerformanceSummary]
    top_performer: PerformerMetric | None
    low_performer: PerformerMetric | None

class TeamLeaderClusterSummary(BaseModel):
    tl_id: uuid.UUID
    tl_first_name: str | None
    tl_last_name: str | None
    tl_email: str
    total_calls_made: int
    total_unique_leads_contacted: int
    total_conversions: int

class ManagerMetricsResponse(BaseModel):
    teams: list[TeamLeaderClusterSummary]
    total_calls_made: int
    total_unique_leads_contacted: int
    total_conversions: int

class TargetProgress(BaseModel):
    target_id: uuid.UUID
    target_type: TargetType
    metric_type: MetricType
    target_value: int
    actual_value: int
    progress_percentage: float
    start_date: date
    end_date: date

class SuperAdminMetricsResponse(BaseModel):
    targets_progress: list[TargetProgress]

class UnifiedDashboardResponse(BaseModel):
    role: str
    metrics: TelecallerMetricsResponse | TeamLeaderMetricsResponse | ManagerMetricsResponse | SuperAdminMetricsResponse
