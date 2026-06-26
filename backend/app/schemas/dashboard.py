from pydantic import BaseModel
from datetime import datetime
from typing import Any, Dict, List, Optional


# ── Org CRM dashboard (used by /api/v1/dashboard/summary) ────────────────────
# The service returns plain dicts; these open models accept any structure.
class DashboardSummaryResponse(BaseModel):
    model_config = {"extra": "allow"}

    total_leads: Optional[int] = None
    total_contacts: Optional[int] = None
    total_companies: Optional[int] = None
    active_users: Optional[int] = None
    total_activities: Optional[int] = None
    leads_by_status: Optional[Dict[str, int]] = None
    recent_leads: Optional[List[Dict[str, Any]]] = None
    performance_metrics: Optional[Dict[str, Any]] = None


class RecentActivitiesResponse(BaseModel):
    model_config = {"extra": "allow"}

    activities: Optional[List[Dict[str, Any]]] = None
    total: Optional[int] = None
    page: Optional[int] = None
    limit: Optional[int] = None


# ── Super Admin Control Center dashboard schemas ──────────────────────────────
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
    # Period-filtered (reflects day/week/month toggle chosen by user)
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
