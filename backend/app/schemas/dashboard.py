from pydantic import BaseModel
from datetime import datetime
from typing import Any, Dict, List, Optional


class OrgMetrics(BaseModel):
    total: int
    active: int
    trial: int
    expired: int
    suspended: int
    new_today: int


class RevenueMetrics(BaseModel):
    mrr: float
    arr: float
    total_collected: float
    pending: float
    failed_count: int
    overdue_count: int
    currency: str = "INR"
    period_collected: float = 0.0
    period_onboarded: int = 0
    period: str = "month"


class LicensingMetrics(BaseModel):
    total_licensed_seats: int
    active_seats: int
    available_seats: int
    utilization_percent: float


class InfraMetrics(BaseModel):
    total_storage_gb: float
    call_recording_gb: float
    db_status: str
    redis_status: str


class ActivityMetrics(BaseModel):
    new_orgs_today: int
    renewals_due_7days: int
    trials_expiring_7days: int
    new_invoices_today: int
    payments_today: int


class SuperAdminDashboardResponse(BaseModel):
    orgs: OrgMetrics
    revenue: RevenueMetrics
    licensing: LicensingMetrics
    infra: InfraMetrics
    activity: ActivityMetrics
    generated_at: datetime


# ── CRM Tenant Dashboard schemas (used by app/api/v1/dashboard.py) ────────────

class DashboardSummaryResponse(BaseModel):
    total_leads: int = 0
    contacts_count: int = 0
    companies_count: int = 0
    user_count: int = 0
    activities_count: int = 0
    leads_by_status: Dict[str, int] = {}
    assigned_leads_breakdown: List[Dict[str, Any]] = []


class RecentActivityItem(BaseModel):
    id: str
    activity_type: Optional[str] = None
    subject: Optional[str] = None
    description: Optional[str] = None
    due_date: Optional[str] = None
    status: Optional[str] = None
    assigned_user_id: Optional[str] = None
    assigned_user_name: str = "Unassigned"
    created_at: str


class RecentActivitiesResponse(BaseModel):
    items: List[RecentActivityItem] = []
    total: int = 0
    page: int = 1
    limit: int = 10
