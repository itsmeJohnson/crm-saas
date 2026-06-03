import uuid
from pydantic import BaseModel
from typing import List, Dict, Optional

class AssignedLeadBreakdown(BaseModel):
    user_id: str
    user_name: str
    lead_count: int

class DashboardSummaryResponse(BaseModel):
    total_leads: int
    contacts_count: int
    companies_count: int
    user_count: int
    activities_count: int
    leads_by_status: Dict[str, int]
    assigned_leads_breakdown: List[AssignedLeadBreakdown]

class RecentActivityItem(BaseModel):
    id: str
    activity_type: str
    subject: str
    description: Optional[str] = None
    due_date: Optional[str] = None
    status: str
    assigned_user_id: Optional[str] = None
    assigned_user_name: str
    created_at: str

class RecentActivitiesResponse(BaseModel):
    items: List[RecentActivityItem]
    total: int
    page: int
    limit: int
