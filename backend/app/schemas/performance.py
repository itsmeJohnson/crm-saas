import uuid
from datetime import date, datetime
from typing import Any
from pydantic import BaseModel, Field


# ---------- KPIs ----------
class KPICreate(BaseModel):
    name: str = Field(..., max_length=120)
    code: str | None = Field(None, max_length=30)
    metric: str
    description: str | None = Field(None, max_length=300)
    unit: str | None = Field(None, pattern="^(count|percent|currency)$")
    weight: float = Field(1, ge=0)
    higher_is_better: bool = True
    status: str = Field("active", pattern="^(active|archived)$")
    color: str | None = Field(None, max_length=20)


class KPIUpdate(BaseModel):
    name: str | None = Field(None, max_length=120)
    code: str | None = Field(None, max_length=30)
    metric: str | None = None
    description: str | None = Field(None, max_length=300)
    unit: str | None = Field(None, pattern="^(count|percent|currency)$")
    weight: float | None = Field(None, ge=0)
    higher_is_better: bool | None = None
    status: str | None = Field(None, pattern="^(active|archived)$")
    color: str | None = Field(None, max_length=20)


class KPIResponse(BaseModel):
    id: str
    name: str
    code: str | None = None
    metric: str
    description: str | None = None
    unit: str
    weight: float
    higher_is_better: bool
    status: str
    color: str | None = None
    created_at: datetime


# ---------- Goals ----------
class GoalCreate(BaseModel):
    user_id: uuid.UUID
    kpi_id: uuid.UUID
    period: str = Field("monthly", pattern="^(daily|weekly|monthly|quarterly|yearly)$")
    target_value: float = Field(..., ge=0)
    start_date: date
    end_date: date
    status: str = Field("active", pattern="^(active|archived)$")


class GoalUpdate(BaseModel):
    period: str | None = Field(None, pattern="^(daily|weekly|monthly|quarterly|yearly)$")
    target_value: float | None = Field(None, ge=0)
    start_date: date | None = None
    end_date: date | None = None
    status: str | None = Field(None, pattern="^(active|archived)$")


class GoalResponse(BaseModel):
    id: str
    user_id: str
    user_name: str | None = None
    kpi_id: str
    kpi_name: str | None = None
    metric: str | None = None
    unit: str | None = None
    period: str
    target_value: float
    actual: float
    attainment: float
    start_date: str
    end_date: str
    status: str
    created_at: datetime


# ---------- Scorecard / trends / leaderboard ----------
class ScorecardKPIRow(BaseModel):
    kpi_id: str
    name: str
    metric: str
    unit: str
    actual: float
    target: float | None = None
    attainment: float | None = None
    weight: float


class ScorecardResponse(BaseModel):
    user_id: str
    user_name: str | None = None
    date_from: str
    date_to: str
    metrics: dict[str, Any]
    kpis: list[ScorecardKPIRow]
    composite_score: float | None = None


class TrendResponse(BaseModel):
    user_id: str
    granularity: str
    series: list[dict]


class LeaderboardRow(BaseModel):
    rank: int
    user_id: str
    name: str
    value: float


class AchievementRow(BaseModel):
    id: str
    user_id: str
    user_name: str | None = None
    title: str
    badge: str | None = None
    period_label: str | None = None
    achieved_value: float
    target_value: float
    attainment: float
    awarded_at: str


class DashboardResponse(BaseModel):
    my_metrics: dict[str, Any]
    my_composite_score: float | None = None
    my_open_goals: int
    my_achievements: int
    top_sales: list[dict]


class ReportResponse(BaseModel):
    date_from: str
    date_to: str
    rows: list[dict]


class SeedResult(BaseModel):
    created: int


class EvaluateResult(BaseModel):
    awarded: int
