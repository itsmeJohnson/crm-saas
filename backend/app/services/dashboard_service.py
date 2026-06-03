import uuid
import json
import asyncio
from typing import Dict, Any, List, Tuple
from fastapi import HTTPException, status
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User
from app.models.lead import Lead
from app.models.contact import Contact
from app.models.company import Company
from app.models.activity import Activity
from app.core.redis import redis_client

class DashboardService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_summary(self, actor: User) -> Dict[str, Any]:
        if not actor.is_active:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Actor is inactive")

        org_id = actor.organization_id
        cache_key = f"dashboard_summary:{org_id}"

        # Try to retrieve from cache
        cached_data = await redis_client.get(cache_key)
        if cached_data:
            try:
                return json.loads(cached_data)
            except Exception:
                pass # Fallback to database query if json load fails

        # Database queries
        total_leads_query = select(func.count(Lead.id)).filter(
            Lead.organization_id == org_id,
            Lead.is_deleted == False
        )
        contacts_count_query = select(func.count(Contact.id)).filter(
            Contact.organization_id == org_id,
            Contact.is_deleted == False
        )
        companies_count_query = select(func.count(Company.id)).filter(
            Company.organization_id == org_id,
            Company.is_deleted == False
        )
        user_count_query = select(func.count(User.id)).filter(
            User.organization_id == org_id,
            User.is_active == True,
            User.is_deleted == False
        )
        activities_count_query = select(func.count(Activity.id)).filter(
            Activity.organization_id == org_id,
            Activity.is_deleted == False
        )
        leads_by_status_query = select(
            Lead.status, 
            func.count(Lead.id)
        ).filter(
            Lead.organization_id == org_id,
            Lead.is_deleted == False
        ).group_by(Lead.status)

        assigned_leads_query = (
            select(
                Lead.assigned_user_id,
                User.first_name,
                User.last_name,
                func.count(Lead.id)
            )
            .outerjoin(User, Lead.assigned_user_id == User.id)
            .filter(
                Lead.organization_id == org_id,
                Lead.is_deleted == False
            )
            .group_by(Lead.assigned_user_id, User.first_name, User.last_name)
        )

        # Run queries in parallel
        db_results = await asyncio.gather(
            self.db.execute(total_leads_query),
            self.db.execute(contacts_count_query),
            self.db.execute(companies_count_query),
            self.db.execute(user_count_query),
            self.db.execute(activities_count_query),
            self.db.execute(leads_by_status_query),
            self.db.execute(assigned_leads_query)
        )

        total_leads = db_results[0].scalar_one()
        contacts_count = db_results[1].scalar_one()
        companies_count = db_results[2].scalar_one()
        user_count = db_results[3].scalar_one()
        activities_count = db_results[4].scalar_one()

        # Parse leads by status
        leads_by_status = {}
        for status_row in db_results[5].all():
            status_name = status_row[0] or "Unknown"
            status_count = status_row[1]
            leads_by_status[status_name] = status_count

        # Parse assigned leads breakdown
        assigned_leads_breakdown = []
        for row in db_results[6].all():
            user_id = row[0]
            first_name = row[1]
            last_name = row[2]
            count = row[3]

            if user_id is None:
                assigned_leads_breakdown.append({
                    "user_id": "unassigned",
                    "user_name": "Unassigned",
                    "lead_count": count
                })
            else:
                user_name = f"{first_name or ''} {last_name or ''}".strip() or "Unnamed User"
                assigned_leads_breakdown.append({
                    "user_id": str(user_id),
                    "user_name": user_name,
                    "lead_count": count
                })

        summary = {
            "total_leads": total_leads,
            "contacts_count": contacts_count,
            "companies_count": companies_count,
            "user_count": user_count,
            "activities_count": activities_count,
            "leads_by_status": leads_by_status,
            "assigned_leads_breakdown": assigned_leads_breakdown
        }

        # Cache results for 5 minutes
        try:
            await redis_client.set(cache_key, json.dumps(summary), ex=300)
        except Exception:
            pass

        return summary

    async def get_recent_activities(
        self, actor: User, page: int = 1, limit: int = 10
    ) -> Dict[str, Any]:
        if not actor.is_active:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Actor is inactive")

        if page < 1:
            page = 1
        if limit < 1:
            limit = 10

        offset = (page - 1) * limit
        org_id = actor.organization_id

        # Query recent activities
        recent_activities_query = (
            select(Activity, User.first_name, User.last_name)
            .outerjoin(User, Activity.assigned_user_id == User.id)
            .filter(
                Activity.organization_id == org_id,
                Activity.is_deleted == False
            )
            .order_by(Activity.created_at.desc())
            .offset(offset)
            .limit(limit)
        )

        total_recent_activities_query = select(func.count(Activity.id)).filter(
            Activity.organization_id == org_id,
            Activity.is_deleted == False
        )

        db_results = await asyncio.gather(
            self.db.execute(recent_activities_query),
            self.db.execute(total_recent_activities_query)
        )

        records = db_results[0].all()
        total = db_results[1].scalar_one()

        items = []
        for row in records:
            activity = row[0]
            first_name = row[1]
            last_name = row[2]
            
            assigned_user_name = "Unassigned"
            if activity.assigned_user_id:
                assigned_user_name = f"{first_name or ''} {last_name or ''}".strip() or "Unnamed User"

            items.append({
                "id": str(activity.id),
                "activity_type": activity.activity_type,
                "subject": activity.subject,
                "description": activity.description,
                "due_date": activity.due_date.isoformat() if activity.due_date else None,
                "status": activity.status,
                "assigned_user_id": str(activity.assigned_user_id) if activity.assigned_user_id else None,
                "assigned_user_name": assigned_user_name,
                "created_at": activity.created_at.isoformat()
            })

        return {
            "items": items,
            "total": total,
            "page": page,
            "limit": limit
        }

    @staticmethod
    async def invalidate_cache(org_id: uuid.UUID):
        cache_key = f"dashboard_summary:{org_id}"
        await redis_client.delete(cache_key)
