from pydantic import BaseModel
from datetime import date, datetime


class LeadReportBucket(BaseModel):
    label: str
    count: int
    value: float


class LeadOwnerBucket(BaseModel):
    user_id: str | None
    name: str
    count: int
    value: float


class LeadReportResponse(BaseModel):
    total_leads: int
    total_value: float
    converted_count: int
    conversion_rate: float
    avg_score: float
    by_source: list[LeadReportBucket]
    by_status: list[LeadReportBucket]
    by_priority: list[LeadReportBucket]
    by_stage: list[LeadReportBucket]
    by_owner: list[LeadOwnerBucket]


class MonthlyRevenue(BaseModel):
    month: str
    mrr: float
    collections: float
    new_subscriptions: int


class RevenueReportResponse(BaseModel):
    period_start: date
    period_end: date
    total_mrr: float
    total_arr: float
    total_collected: float
    monthly_breakdown: list[MonthlyRevenue]
    top_plans: list[dict]
    currency: str


class TenantSummaryReport(BaseModel):
    total: int
    active: int
    trial: int
    expired: int
    suspended: int
    by_plan: list[dict]


class SeatUtilizationReport(BaseModel):
    total_licensed: int
    total_active: int
    utilization_pct: float
    by_organization: list[dict]
