from typing import Any
from pydantic import BaseModel


class OverviewResponse(BaseModel):
    date_from: str
    date_to: str
    headcount: int
    present_today: int
    attendance_rate: float
    on_leave_today: int
    departments: int
    teams: int
    branches: int
    pending_leaves: int
    leads: int
    converted: int
    conversion_rate: float
    revenue: float
    calls: int
    activities: int
    tasks_completed: int
    task_completion_rate: float


class HealthComponent(BaseModel):
    name: str
    score: float
    weight: int


class HealthResponse(BaseModel):
    score: float
    rating: str
    components: list[HealthComponent]


class LeaderboardRow(BaseModel):
    rank: int
    user_id: str
    name: str
    value: float


class HeatmapResponse(BaseModel):
    weekdays: list[str]
    grid: list[list[int]]
    peak: dict[str, Any]


class TrendResponse(BaseModel):
    granularity: str
    series: list[dict]
