import uuid
from datetime import datetime, timezone
from typing import Sequence, Tuple
from fastapi import HTTPException, status
from sqlalchemy import select, func, or_
from sqlalchemy.ext.asyncio import AsyncSession
from app.repositories.company_repository import CompanyRepository
from app.repositories.user_repository import UserRepository
from app.repositories.activity_repository import ActivityRepository
from app.repositories.note_repository import NoteRepository
from app.services.audit_service import AuditService
from app.services.dashboard_service import DashboardService
from app.models.user import User
from app.models.company import Company

class CompanyService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.company_repo = CompanyRepository(db)
        self.user_repo = UserRepository(db)
        self.activity_repo = ActivityRepository(db)
        self.note_repo = NoteRepository(db)
        self.audit_service = AuditService(db)

    async def get_company(self, actor: User, company_id: uuid.UUID) -> Company:
        if not actor.is_active:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Actor is inactive")
        
        company = await self.company_repo.get_company_by_id(actor.organization_id, company_id)
        if not company:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Company not found")
        return company

    async def create_company(self, actor: User, company_data: dict) -> Company:
        if not actor.is_active:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Actor is inactive")

        # Validate assigned user organization
        assigned_user_id = company_data.get("assigned_user_id")
        if assigned_user_id:
            assigned_user = await self.user_repo.get_user_by_id(actor.organization_id, assigned_user_id)
            if not assigned_user or not assigned_user.is_active:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Assigned user not found or inactive in your organization"
                )

        company = await self.company_repo.create_company(actor.organization_id, company_data, actor.id)
        
        await self.audit_service.log_event(
            organization_id=actor.organization_id,
            actor_user_id=actor.id,
            action="COMPANY_CREATED",
            resource_type="company",
            resource_id=str(company.id),
            action_metadata={"name": company.name}
        )
        await DashboardService.invalidate_cache(actor.organization_id)
        return company

    async def paginate_companies(
        self,
        actor: User,
        skip: int = 0,
        limit: int = 100,
        search_query: str | None = None,
        industry: str | None = None,
        company_type: str | None = None,
        source: str | None = None,
        assigned_user_id: uuid.UUID | None = None,
        tag: str | None = None,
    ) -> Tuple[Sequence[Company], int]:
        if not actor.is_active:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Actor is inactive")
        return await self.company_repo.paginate_companies(
            actor.organization_id, skip, limit, search_query,
            industry=industry, company_type=company_type, source=source,
            assigned_user_id=assigned_user_id, tag=tag,
        )

    async def update_company(self, actor: User, company_id: uuid.UUID, company_data: dict) -> Company:
        if not actor.is_active:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Actor is inactive")

        company = await self.get_company(actor, company_id)

        # Validate assigned user organization
        assigned_user_id = company_data.get("assigned_user_id")
        if assigned_user_id:
            assigned_user = await self.user_repo.get_user_by_id(actor.organization_id, assigned_user_id)
            if not assigned_user or not assigned_user.is_active:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Assigned user not found or inactive in your organization"
                )

        updated = await self.company_repo.update_company(actor.organization_id, company_id, company_data)

        await self.audit_service.log_event(
            organization_id=actor.organization_id,
            actor_user_id=actor.id,
            action="COMPANY_UPDATED",
            resource_type="company",
            resource_id=str(company_id),
            action_metadata={"updated_fields": list(company_data.keys())}
        )
        await DashboardService.invalidate_cache(actor.organization_id)
        return updated

    async def soft_delete_company(self, actor: User, company_id: uuid.UUID) -> Company:
        if not actor.is_active:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Actor is inactive")

        company = await self.get_company(actor, company_id)

        # Soft delete company
        deleted = await self.company_repo.soft_delete_company(actor.organization_id, company_id)

        # Cascade soft-delete activities and notes
        await self.activity_repo.soft_delete_by_parent(actor.organization_id, "company", company_id)
        await self.note_repo.soft_delete_by_parent(actor.organization_id, "company", company_id)

        await self.audit_service.log_event(
            organization_id=actor.organization_id,
            actor_user_id=actor.id,
            action="COMPANY_DELETED",
            resource_type="company",
            resource_id=str(company_id)
        )
        await DashboardService.invalidate_cache(actor.organization_id)
        return deleted

    # --- Associations ---
    def _lead_match_clause(self, company: Company):
        """Leads belong to a company if linked by id OR their free-text name matches."""
        from app.models.lead import Lead
        clauses = [Lead.company_id == company.id]
        if company.name:
            clauses.append(func.lower(Lead.company_name) == company.name.lower())
        return or_(*clauses)

    async def get_contacts(self, actor: User, company_id: uuid.UUID) -> list:
        """Contacts (the company's people / employee roster)."""
        from app.models.contact import Contact
        company = await self.get_company(actor, company_id)
        res = await self.db.execute(
            select(Contact).filter(
                Contact.organization_id == actor.organization_id,
                Contact.company_id == company.id,
                Contact.is_deleted == False,
            ).order_by(Contact.last_name.asc(), Contact.first_name.asc())
        )
        return list(res.scalars().all())

    async def get_leads(self, actor: User, company_id: uuid.UUID) -> list:
        """Leads/opportunities associated with the company."""
        from app.models.lead import Lead
        from sqlalchemy.orm import selectinload
        company = await self.get_company(actor, company_id)
        res = await self.db.execute(
            select(Lead).options(selectinload(Lead.stage)).filter(
                Lead.organization_id == actor.organization_id,
                Lead.is_deleted == False,
                self._lead_match_clause(company),
            ).order_by(Lead.created_at.desc())
        )
        leads = list(res.scalars().all())
        return [
            {
                "id": l.id, "title": l.title, "status": l.status,
                "stage": l.stage.name if l.stage else None, "value": l.value,
                "assigned_user_id": l.assigned_user_id,
            }
            for l in leads
        ]

    async def get_deals_summary(self, actor: User, company_id: uuid.UUID) -> dict:
        """Rollup of the company's leads as deals; 'won' == Converted (associated customers)."""
        from app.models.lead import Lead
        from app.models.pipeline import PipelineStage
        company = await self.get_company(actor, company_id)
        match = self._lead_match_clause(company)

        res = await self.db.execute(
            select(Lead.stage_id, Lead.status, Lead.value).filter(
                Lead.organization_id == actor.organization_id,
                Lead.is_deleted == False,
                match,
            )
        )
        rows = res.all()

        # Stage names
        stage_res = await self.db.execute(
            select(PipelineStage.id, PipelineStage.name).filter(PipelineStage.organization_id == actor.organization_id)
        )
        stage_names = {sid: name for sid, name in stage_res.all()}

        total_value = 0.0
        won_value = 0.0
        won = lost = open_count = 0
        by_stage: dict[str, dict] = {}
        for stage_id, lead_status, value in rows:
            v = float(value) if value is not None else 0.0
            total_value += v
            sname = stage_names.get(stage_id, "Unknown")
            bucket = by_stage.setdefault(sname, {"stage": sname, "count": 0, "value": 0.0})
            bucket["count"] += 1
            bucket["value"] += v
            if sname == "Converted":
                won += 1
                won_value += v
            elif sname in ("Dropped", "Lost"):
                lost += 1
            else:
                open_count += 1

        return {
            "total_leads": len(rows),
            "open_count": open_count,
            "won_count": won,
            "lost_count": lost,
            "total_value": total_value,
            "won_value": won_value,
            "by_stage": list(by_stage.values()),
        }

    async def get_timeline(self, actor: User, company_id: uuid.UUID) -> list[dict]:
        from app.models.note import Note
        from app.models.activity import Activity
        from app.models.audit_log import AuditLog
        company = await self.get_company(actor, company_id)
        events: list[dict] = []
        notes = await self.db.execute(select(Note).filter(Note.company_id == company.id, Note.is_deleted == False))
        for n in notes.scalars().all():
            events.append({"type": "note", "id": str(n.id), "timestamp": n.created_at, "title": "Note added",
                           "description": n.content, "actor_user_id": str(n.created_by) if n.created_by else None, "event_metadata": None})
        acts = await self.db.execute(select(Activity).filter(Activity.company_id == company.id, Activity.is_deleted == False))
        for a in acts.scalars().all():
            events.append({"type": "activity", "id": str(a.id), "timestamp": a.created_at,
                           "title": f"{a.activity_type}: {a.subject}", "description": a.description,
                           "actor_user_id": str(a.assigned_user_id) if a.assigned_user_id else (str(a.created_by) if a.created_by else None),
                           "event_metadata": {"status": a.status}})
        audits = await self.db.execute(select(AuditLog).filter(
            AuditLog.organization_id == actor.organization_id, AuditLog.resource_id == str(company.id),
            or_(AuditLog.resource_type == "company", AuditLog.resource_type == "Company")))
        for al in audits.scalars().all():
            events.append({"type": "audit", "id": str(al.id), "timestamp": al.created_at, "title": al.action,
                           "description": None, "actor_user_id": str(al.actor_user_id) if al.actor_user_id else None,
                           "event_metadata": al.action_metadata})
        events.sort(key=lambda e: e["timestamp"], reverse=True)
        return events

    async def get_communications(self, actor: User, company_id: uuid.UUID) -> list[dict]:
        from app.models.activity import Activity
        company = await self.get_company(actor, company_id)
        res = await self.db.execute(
            select(Activity).filter(
                Activity.company_id == company.id,
                Activity.is_deleted == False,
                Activity.activity_type.in_(["Call", "Email"]),
            ).order_by(Activity.created_at.desc())
        )
        return [
            {"id": str(a.id), "channel": a.activity_type, "subject": a.subject, "description": a.description,
             "direction": a.call_direction, "status": a.status, "timestamp": a.created_at, "recording_url": a.recording_url}
            for a in res.scalars().all()
        ]

    # --- Attachments (Files) ---
    ATTACHMENT_EXTENSIONS = {"pdf", "png", "jpg", "jpeg", "webp", "csv", "xlsx", "docx"}

    async def add_attachment(self, actor: User, company_id: uuid.UUID, content: bytes, filename: str) -> dict:
        from app.core.storage import validate_and_sanitize_file, get_storage_provider
        company = await self.get_company(actor, company_id)
        try:
            sanitized, ext = validate_and_sanitize_file(content=content, filename=filename, allowed_extensions=self.ATTACHMENT_EXTENSIONS)
        except ValueError as e:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
        url = await get_storage_provider().upload_file(content, sanitized)
        attachment = {"filename": filename, "stored_name": sanitized, "url": url, "size": len(content),
                      "uploaded_by": str(actor.id), "uploaded_at": datetime.now(timezone.utc).isoformat()}
        existing = list(company.attachments or [])
        existing.append(attachment)
        company.attachments = existing
        self.db.add(company)
        await self.db.flush()
        await self.audit_service.log_event(
            organization_id=actor.organization_id, actor_user_id=actor.id,
            action="COMPANY_ATTACHMENT_ADDED", resource_type="company", resource_id=str(company_id),
            action_metadata={"filename": filename},
        )
        return attachment

    async def list_attachments(self, actor: User, company_id: uuid.UUID) -> list[dict]:
        company = await self.get_company(actor, company_id)
        return list(company.attachments or [])

    async def delete_attachment(self, actor: User, company_id: uuid.UUID, stored_name: str) -> dict:
        from app.core.storage import get_storage_provider
        company = await self.get_company(actor, company_id)
        existing = list(company.attachments or [])
        target = next((a for a in existing if a.get("stored_name") == stored_name or a.get("filename") == stored_name), None)
        if not target:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Attachment not found")
        company.attachments = [a for a in existing if a is not target]
        self.db.add(company)
        await self.db.flush()
        try:
            await get_storage_provider().delete_file(target["url"])
        except Exception:
            pass
        return {"deleted": True}

    # --- Tags ---
    async def get_tags(self, actor: User) -> list[str]:
        res = await self.db.execute(
            select(Company.tags).filter(
                Company.organization_id == actor.organization_id,
                Company.is_deleted == False,
                Company.tags.isnot(None),
            )
        )
        seen = set()
        for (tags,) in res.all():
            for t in (tags or []):
                seen.add(t)
        return sorted(seen)

    # --- Report ---
    async def get_company_report(self, actor: User, date_from=None, date_to=None) -> dict:
        def base(*cols):
            q = select(*cols).select_from(Company).filter(
                Company.organization_id == actor.organization_id, Company.is_deleted == False)
            if date_from is not None:
                q = q.filter(Company.created_at >= date_from)
            if date_to is not None:
                q = q.filter(Company.created_at <= date_to)
            return q

        total = (await self.db.execute(base(func.count(Company.id)))).scalar() or 0
        total_revenue = float((await self.db.execute(base(func.coalesce(func.sum(Company.annual_revenue), 0)))).scalar() or 0)
        total_employees = int((await self.db.execute(base(func.coalesce(func.sum(Company.employee_count), 0)))).scalar() or 0)

        async def typed_count(t):
            return (await self.db.execute(base(func.count(Company.id)).filter(Company.company_type == t))).scalar() or 0
        customers = await typed_count("Customer")
        prospects = await typed_count("Prospect")
        partners = await typed_count("Partner")

        async def grouped(col):
            res = await self.db.execute(
                base(col, func.count(Company.id), func.coalesce(func.sum(Company.annual_revenue), 0)).group_by(col)
            )
            return [
                {"label": (r[0] if r[0] is not None else "Unspecified"), "count": r[1], "revenue": float(r[2])}
                for r in res.all()
            ]

        by_industry = await grouped(Company.industry)
        by_type = await grouped(Company.company_type)
        by_source = await grouped(Company.source)

        top_res = await self.db.execute(
            base(Company.name, Company.annual_revenue).filter(Company.annual_revenue.isnot(None))
            .order_by(Company.annual_revenue.desc()).limit(5)
        )
        top_by_revenue = [{"name": r[0], "revenue": float(r[1])} for r in top_res.all()]

        return {
            "total_companies": total, "total_revenue": total_revenue, "total_employees": total_employees,
            "customers": customers, "prospects": prospects, "partners": partners,
            "by_industry": by_industry, "by_type": by_type, "by_source": by_source,
            "top_by_revenue": top_by_revenue,
        }
