import uuid
from datetime import datetime, timezone
from typing import Sequence, Tuple
from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from app.repositories.lead_repository import LeadRepository
from app.repositories.user_repository import UserRepository
from app.repositories.activity_repository import ActivityRepository
from app.repositories.note_repository import NoteRepository
from app.services.audit_service import AuditService
from app.services.dashboard_service import DashboardService
from app.services.notification_service import NotificationService
from app.services.lead_scoring import compute_score
from app.models.user import User
from app.models.lead import Lead

class LeadService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.lead_repo = LeadRepository(db)
        self.user_repo = UserRepository(db)
        self.activity_repo = ActivityRepository(db)
        self.note_repo = NoteRepository(db)
        self.audit_service = AuditService(db)
        self.notification_service = NotificationService(db)

    async def get_lead(self, actor: User, lead_id: uuid.UUID) -> Lead:
        if not actor.is_active:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Actor is inactive")

        lead = await self.lead_repo.get_lead_by_id(actor.organization_id, lead_id)
        if not lead:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Lead not found")

        if actor.role not in ("SuperAdmin", "OrgAdmin", "Manager"):
            from app.services.user_service import UserService
            user_service = UserService(self.db)
            downline_ids = await user_service.get_downline_user_ids(actor)
            allowed_user_ids = downline_ids | {actor.id}
            if lead.assigned_user_id not in allowed_user_ids:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Lead not found")

        return lead

    async def create_lead(self, actor: User, lead_data: dict) -> Lead:
        if not actor.is_active:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Actor is inactive")

        # Validate assigned user organization
        assigned_user_id = lead_data.get("assigned_user_id")
        if assigned_user_id:
            assigned_user = await self.user_repo.get_user_by_id(actor.organization_id, assigned_user_id)
            if not assigned_user or not assigned_user.is_active:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Assigned user not found or inactive in your organization"
                )

        # Auto-link to a company when the free-text name matches an existing account
        if lead_data.get("company_name") and not lead_data.get("company_id"):
            from sqlalchemy import select, func
            from app.models.company import Company
            comp_res = await self.db.execute(
                select(Company.id).filter(
                    Company.organization_id == actor.organization_id,
                    func.lower(Company.name) == lead_data["company_name"].strip().lower(),
                    Company.is_deleted == False,
                ).limit(1)
            )
            matched = comp_res.scalar()
            if matched:
                lead_data["company_id"] = matched

        # Auto-resolve branch & territory from the lead's PIN/city if a mapping
        # exists and the caller didn't set them (backward compatible: only fills
        # NULLs, best-effort — never blocks lead creation).
        if not lead_data.get("territory_id") or not lead_data.get("branch_id"):
            try:
                from app.services.branch_territory_service import BranchTerritoryService
                await BranchTerritoryService(self.db).apply_resolution_to_lead_data(
                    actor.organization_id, lead_data)
            except Exception:
                pass

        # Compute initial lead score from provided attributes
        lead_data["score"] = compute_score(
            email=lead_data.get("email"),
            phone=lead_data.get("phone"),
            company_name=lead_data.get("company_name"),
            value=lead_data.get("value"),
            source=lead_data.get("source"),
            priority=lead_data.get("priority"),
        )

        lead = await self.lead_repo.create_lead(actor.organization_id, lead_data, actor.id)

        await self.audit_service.log_event(
            organization_id=actor.organization_id,
            actor_user_id=actor.id,
            action="LEAD_CREATED",
            resource_type="lead",
            resource_id=str(lead.id),
            action_metadata={"title": lead.title, "status": lead.status}
        )

        if assigned_user_id and assigned_user_id != actor.id:
            await self.notification_service.create_notification(
                organization_id=actor.organization_id,
                user_id=assigned_user_id,
                category="lead",
                title="New lead assigned to you",
                body=f'"{lead.title}" was assigned to you.',
                link_url=f"/leads?leadId={lead.id}",
                action_metadata={"lead_id": str(lead.id)},
            )

        # Run lead-created automation rules
        from app.services.workflow_service import WorkflowService
        await WorkflowService(self.db).run("lead_created", lead, actor)

        # Open SLA clocks for any matching policy (best-effort, additive).
        try:
            from app.services.sla_service import SLAService
            await SLAService(self.db).start_tracking(lead, "lead", actor.organization_id)
        except Exception:
            pass

        await DashboardService.invalidate_cache(actor.organization_id)
        return await self.lead_repo.get_lead_by_id(actor.organization_id, lead.id)

    async def _resolve_scope(self, actor: User) -> set[uuid.UUID] | None:
        """Return the set of user ids whose leads the actor may see, or None for org-wide."""
        if actor.role in ("SuperAdmin", "OrgAdmin", "Manager"):
            return None
        from app.services.user_service import UserService
        user_service = UserService(self.db)
        downline_ids = await user_service.get_downline_user_ids(actor)
        return downline_ids | {actor.id}

    async def paginate_leads(
        self,
        actor: User,
        skip: int = 0,
        limit: int = 100,
        search_query: str | None = None,
        status_filter: str | None = None,
        assigned_user_id: uuid.UUID | None = None,
        name: str | None = None,
        city: str | None = None,
        source: str | None = None,
        stage_id: uuid.UUID | None = None,
        priority: str | None = None,
        min_value: float | None = None,
        max_value: float | None = None,
        created_from=None,
        created_to=None,
        include_archived: bool = False,
        updated_after=None,
    ) -> Tuple[Sequence[Lead], int]:
        if not actor.is_active:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Actor is inactive")

        # Org-wide visibility for admins/managers; everyone else is scoped to
        # themselves plus their recursive downline (so a telecaller only sees
        # their own leads, and a team lead sees their own + their team's).
        allowed_user_ids = await self._resolve_scope(actor)

        if assigned_user_id:
            assigned_user = await self.user_repo.get_user_by_id(actor.organization_id, assigned_user_id)
            if not assigned_user:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Assigned user not found in your organization"
                )
            if allowed_user_ids is not None and assigned_user_id not in allowed_user_ids:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Assigned user is not yourself or in your downline reporting chain"
                )

        return await self.lead_repo.paginate_leads(
            actor.organization_id, skip, limit, search_query, status_filter, assigned_user_id, name, city,
            allowed_user_ids, source=source, stage_id=stage_id, priority=priority,
            min_value=min_value, max_value=max_value, created_from=created_from,
            created_to=created_to, include_archived=include_archived,
            updated_after=updated_after,
        )

    async def export_leads(self, actor: User, filters: dict) -> Sequence[Lead]:
        """Return leads (scoped) matching filters for CSV/XLSX export."""
        if not actor.is_active:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Actor is inactive")
        allowed_user_ids = await self._resolve_scope(actor)
        return await self.lead_repo.stream_leads_for_export(
            actor.organization_id, allowed_user_ids=allowed_user_ids, **filters
        )

    async def find_duplicates(
        self, actor: User, email: str | None = None, phone: str | None = None,
        exclude_lead_id: uuid.UUID | None = None
    ) -> Sequence[Lead]:
        """Find leads sharing the same email or phone within the org."""
        if not actor.is_active:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Actor is inactive")
        if not email and not phone:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Provide an email or phone to search for duplicates"
            )
        candidates = await self.lead_repo.find_duplicates(
            actor.organization_id, email=email, phone=phone, exclude_lead_id=exclude_lead_id
        )
        # Apply visibility scoping for non-admins
        allowed_user_ids = await self._resolve_scope(actor)
        if allowed_user_ids is not None:
            candidates = [c for c in candidates if c.assigned_user_id in allowed_user_ids]
        return candidates

    async def archive_lead(self, actor: User, lead_id: uuid.UUID) -> Lead:
        if not actor.is_active:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Actor is inactive")
        lead = await self.get_lead(actor, lead_id)
        if not lead.is_archived:
            lead.is_archived = True
            lead.archived_at = datetime.now(timezone.utc)
            self.db.add(lead)
            await self.db.flush()
            await self.audit_service.log_event(
                organization_id=actor.organization_id,
                actor_user_id=actor.id,
                action="LEAD_ARCHIVED",
                resource_type="lead",
                resource_id=str(lead_id),
            )
            await DashboardService.invalidate_cache(actor.organization_id)
        return await self.lead_repo.get_lead_any_state(actor.organization_id, lead_id)

    async def restore_lead(self, actor: User, lead_id: uuid.UUID) -> Lead:
        """Un-archive and/or un-delete a lead."""
        if not actor.is_active:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Actor is inactive")
        lead = await self.lead_repo.get_lead_any_state(actor.organization_id, lead_id)
        if not lead:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Lead not found")
        # Scope check for non-admins
        allowed_user_ids = await self._resolve_scope(actor)
        if allowed_user_ids is not None and lead.assigned_user_id not in allowed_user_ids:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Lead not found")
        if not lead.is_archived and not lead.is_deleted:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Lead is already active"
            )
        lead.is_archived = False
        lead.archived_at = None
        lead.is_deleted = False
        lead.deleted_at = None
        self.db.add(lead)
        await self.db.flush()
        await self.audit_service.log_event(
            organization_id=actor.organization_id,
            actor_user_id=actor.id,
            action="LEAD_RESTORED",
            resource_type="lead",
            resource_id=str(lead_id),
        )
        await DashboardService.invalidate_cache(actor.organization_id)
        return await self.lead_repo.get_lead_any_state(actor.organization_id, lead_id)

    async def bulk_update(self, actor: User, lead_ids: list[uuid.UUID], fields: dict) -> dict:
        """Apply the same field updates to many scoped leads at once."""
        if not actor.is_active:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Actor is inactive")
        if not lead_ids:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="No lead_ids provided")
        if not fields:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="No fields to update")

        # Validate stage belongs to org if provided
        if fields.get("stage_id"):
            from app.models.pipeline import PipelineStage
            from sqlalchemy import select
            stage_res = await self.db.execute(
                select(PipelineStage.id).filter(
                    PipelineStage.id == fields["stage_id"],
                    PipelineStage.organization_id == actor.organization_id,
                    PipelineStage.is_deleted == False,
                )
            )
            if not stage_res.scalar():
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Stage not found in your organization")

        allowed_user_ids = await self._resolve_scope(actor)
        leads = await self.lead_repo.get_leads_for_update(actor.organization_id, lead_ids)

        updated_ids = []
        for lead in leads:
            if allowed_user_ids is not None and lead.assigned_user_id not in allowed_user_ids:
                continue
            for key, val in fields.items():
                setattr(lead, key, val)
            self.db.add(lead)
            updated_ids.append(lead.id)

        await self.db.flush()
        if updated_ids:
            await self.audit_service.log_event(
                organization_id=actor.organization_id,
                actor_user_id=actor.id,
                action="LEAD_BULK_UPDATED",
                resource_type="lead",
                resource_id=None,
                action_metadata={"lead_ids": [str(i) for i in updated_ids], "fields": list(fields.keys())},
            )
            await DashboardService.invalidate_cache(actor.organization_id)
        return {"updated_count": len(updated_ids), "lead_ids": updated_ids}

    async def update_lead(self, actor: User, lead_id: uuid.UUID, lead_data: dict) -> Lead:
        if not actor.is_active:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Actor is inactive")

        lead = await self.get_lead(actor, lead_id)

        # Field-level permission check (no-op unless actor has a custom role)
        from app.services.permission_service import PermissionService
        await PermissionService(self.db).enforce_field_writes(actor, "leads", lead_data)

        # Validate assigned user organization if updated
        assigned_user_id = lead_data.get("assigned_user_id")
        if assigned_user_id:
            assigned_user = await self.user_repo.get_user_by_id(actor.organization_id, assigned_user_id)
            if not assigned_user or not assigned_user.is_active:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Assigned user not found or inactive in your organization"
                )

        updated = await self.lead_repo.update_lead(actor.organization_id, lead_id, lead_data)

        # Recompute score if any scoring-relevant field changed
        if {"email", "phone", "company_name", "value", "source", "priority"} & set(lead_data.keys()):
            updated.score = compute_score(
                email=updated.email,
                phone=updated.phone,
                company_name=updated.company_name,
                value=updated.value,
                source=updated.source,
                priority=updated.priority,
            )
            self.db.add(updated)
            await self.db.flush()

        await self.audit_service.log_event(
            organization_id=actor.organization_id,
            actor_user_id=actor.id,
            action="LEAD_UPDATED",
            resource_type="lead",
            resource_id=str(lead_id),
            action_metadata={"updated_fields": list(lead_data.keys())}
        )

        # Run lead-updated automation rules
        from app.services.workflow_service import WorkflowService
        await WorkflowService(self.db).run("lead_updated", updated, actor)

        await DashboardService.invalidate_cache(actor.organization_id)
        return await self.lead_repo.get_lead_by_id(actor.organization_id, lead_id)

    async def soft_delete_lead(self, actor: User, lead_id: uuid.UUID) -> Lead:
        if not actor.is_active:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Actor is inactive")

        lead = await self.get_lead(actor, lead_id)

        deleted = await self.lead_repo.soft_delete_lead(actor.organization_id, lead_id)

        # Cascade soft-delete activities and notes
        await self.activity_repo.soft_delete_by_parent(actor.organization_id, "lead", lead_id)
        await self.note_repo.soft_delete_by_parent(actor.organization_id, "lead", lead_id)

        await self.audit_service.log_event(
            organization_id=actor.organization_id,
            actor_user_id=actor.id,
            action="LEAD_DELETED",
            resource_type="lead",
            resource_id=str(lead_id)
        )
        await DashboardService.invalidate_cache(actor.organization_id)
        return deleted

    async def convert_lead(self, actor: User, lead_id: uuid.UUID, create_company: bool = True) -> dict:
        """Convert a lead into a Contact (+ optional Company), archive & link the lead."""
        from sqlalchemy import select, func
        from app.models.contact import Contact
        from app.models.company import Company
        from app.models.pipeline import PipelineStage

        lead = await self.get_lead(actor, lead_id)  # scoping check
        if lead.converted_contact_id:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Lead is already converted")

        # Find-or-create company from company_name
        company_id = None
        if create_company and lead.company_name:
            existing = await self.db.execute(
                select(Company).filter(
                    Company.organization_id == actor.organization_id,
                    func.lower(Company.name) == lead.company_name.lower(),
                    Company.is_deleted == False,
                )
            )
            company = existing.scalars().first()
            if not company:
                company = Company(
                    organization_id=actor.organization_id,
                    name=lead.company_name,
                    phone=lead.phone,
                    assigned_user_id=lead.assigned_user_id,
                    created_by=actor.id,
                )
                self.db.add(company)
                await self.db.flush()
            company_id = company.id

        contact = Contact(
            organization_id=actor.organization_id,
            company_id=company_id,
            first_name=lead.first_name or lead.last_name,
            last_name=lead.last_name,
            email=lead.email,
            phone=lead.phone,
            job_title=lead.title,
            assigned_user_id=lead.assigned_user_id,
            created_by=actor.id,
        )
        self.db.add(contact)
        await self.db.flush()

        # Move to Converted stage if present
        conv_stage = await self.db.execute(
            select(PipelineStage.id).filter(
                PipelineStage.organization_id == actor.organization_id,
                PipelineStage.name == "Converted",
                PipelineStage.is_deleted == False,
            )
        )
        conv_stage_id = conv_stage.scalar()
        if conv_stage_id:
            lead.stage_id = conv_stage_id
        lead.status = "Converted"
        lead.converted_contact_id = contact.id
        lead.converted_at = datetime.now(timezone.utc)
        lead.is_archived = True
        lead.archived_at = datetime.now(timezone.utc)
        self.db.add(lead)
        await self.db.flush()

        await self.audit_service.log_event(
            organization_id=actor.organization_id, actor_user_id=actor.id,
            action="LEAD_CONVERTED", resource_type="lead", resource_id=str(lead_id),
            action_metadata={"contact_id": str(contact.id), "company_id": str(company_id) if company_id else None},
        )
        # Fire the lead_converted trigger (legacy engine + orchestration workflows).
        from app.services.workflow_service import WorkflowService
        await WorkflowService(self.db).run("lead_converted", lead, actor)

        # Conversion resolves the lead's SLA (best-effort, additive).
        try:
            from app.services.sla_service import SLAService
            await SLAService(self.db).record_resolution("lead", lead.id, actor.organization_id)
        except Exception:
            pass

        await DashboardService.invalidate_cache(actor.organization_id)
        return {"contact_id": contact.id, "company_id": company_id, "lead_id": lead.id}

    # --- Reminders ---
    async def create_reminder(self, actor: User, lead_id: uuid.UUID, remind_at, note: str | None, user_id: uuid.UUID | None = None):
        from app.models.lead_reminder import LeadReminder
        lead = await self.get_lead(actor, lead_id)  # scoping check
        target_user = user_id or lead.assigned_user_id or actor.id
        reminder = LeadReminder(
            organization_id=actor.organization_id,
            lead_id=lead.id,
            user_id=target_user,
            remind_at=remind_at,
            note=note,
            created_by=actor.id,
        )
        self.db.add(reminder)
        await self.db.flush()
        await self.db.refresh(reminder)
        return reminder

    async def list_reminders(self, actor: User, lead_id: uuid.UUID):
        from sqlalchemy import select
        from app.models.lead_reminder import LeadReminder
        await self.get_lead(actor, lead_id)  # scoping check
        res = await self.db.execute(
            select(LeadReminder).filter(
                LeadReminder.lead_id == lead_id,
                LeadReminder.is_deleted == False,
            ).order_by(LeadReminder.remind_at.asc())
        )
        return list(res.scalars().all())

    async def delete_reminder(self, actor: User, lead_id: uuid.UUID, reminder_id: uuid.UUID):
        from sqlalchemy import select
        from app.models.lead_reminder import LeadReminder
        await self.get_lead(actor, lead_id)  # scoping check
        res = await self.db.execute(
            select(LeadReminder).filter(
                LeadReminder.id == reminder_id,
                LeadReminder.lead_id == lead_id,
                LeadReminder.organization_id == actor.organization_id,
                LeadReminder.is_deleted == False,
            )
        )
        reminder = res.scalars().first()
        if not reminder:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Reminder not found")
        reminder.is_deleted = True
        self.db.add(reminder)
        await self.db.flush()

    async def get_lead_report(self, actor: User, date_from=None, date_to=None) -> dict:
        """Aggregate tenant-scoped lead metrics for reporting."""
        if not actor.is_active:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Actor is inactive")
        from sqlalchemy import select, func
        from app.models.pipeline import PipelineStage
        from app.services.analytics_service import AnalyticsService

        allowed_user_ids = await self._resolve_scope(actor)

        def base(*cols):
            q = select(*cols).select_from(Lead).filter(
                Lead.organization_id == actor.organization_id,
                Lead.is_deleted == False,
                Lead.is_archived == False,
            )
            if allowed_user_ids is not None:
                q = q.filter(Lead.assigned_user_id.in_(allowed_user_ids))
            if date_from is not None:
                q = q.filter(Lead.created_at >= date_from)
            if date_to is not None:
                q = q.filter(Lead.created_at <= date_to)
            return q

        # Totals
        totals_res = await self.db.execute(base(
            func.count(Lead.id), func.coalesce(func.sum(Lead.value), 0), func.coalesce(func.avg(Lead.score), 0)
        ))
        total_leads, total_value, avg_score = totals_res.one()

        # Converted count (leads currently in the "Converted" stage)
        converted_stage_id = await AnalyticsService.get_converted_stage_id(self.db, actor.organization_id)
        converted_count = 0
        if converted_stage_id:
            conv_res = await self.db.execute(base(func.count(Lead.id)).filter(Lead.stage_id == converted_stage_id))
            converted_count = conv_res.scalar() or 0

        conversion_rate = round((converted_count / total_leads) * 100, 2) if total_leads else 0.0

        async def grouped(col):
            res = await self.db.execute(
                base(col, func.count(Lead.id), func.coalesce(func.sum(Lead.value), 0)).group_by(col)
            )
            return [
                {"label": (row[0] if row[0] is not None else "Unspecified"), "count": row[1], "value": float(row[2])}
                for row in res.all()
            ]

        by_source = await grouped(Lead.source)
        by_status = await grouped(Lead.status)
        by_priority = await grouped(Lead.priority)

        # By stage (map stage_id -> name)
        stage_names = {}
        st_res = await self.db.execute(
            select(PipelineStage.id, PipelineStage.name).filter(PipelineStage.organization_id == actor.organization_id)
        )
        for sid, sname in st_res.all():
            stage_names[sid] = sname
        stage_rows = await self.db.execute(
            base(Lead.stage_id, func.count(Lead.id), func.coalesce(func.sum(Lead.value), 0)).group_by(Lead.stage_id)
        )
        by_stage = [
            {"label": stage_names.get(row[0], "Unknown"), "count": row[1], "value": float(row[2])}
            for row in stage_rows.all()
        ]

        # By owner
        from app.models.user import User as UserModel
        owner_rows = await self.db.execute(
            base(Lead.assigned_user_id, func.count(Lead.id), func.coalesce(func.sum(Lead.value), 0)).group_by(Lead.assigned_user_id)
        )
        owner_rows = owner_rows.all()
        owner_ids = [r[0] for r in owner_rows if r[0] is not None]
        owner_names = {}
        if owner_ids:
            u_res = await self.db.execute(
                select(UserModel.id, UserModel.first_name, UserModel.last_name, UserModel.email).filter(UserModel.id.in_(owner_ids))
            )
            for uid, fn, ln, em in u_res.all():
                owner_names[uid] = f"{fn or ''} {ln or ''}".strip() or em
        by_owner = [
            {
                "user_id": str(row[0]) if row[0] else None,
                "name": owner_names.get(row[0], "Unassigned") if row[0] else "Unassigned",
                "count": row[1], "value": float(row[2]),
            }
            for row in owner_rows
        ]

        return {
            "total_leads": total_leads,
            "total_value": float(total_value),
            "converted_count": converted_count,
            "conversion_rate": conversion_rate,
            "avg_score": round(float(avg_score), 1),
            "by_source": by_source,
            "by_status": by_status,
            "by_priority": by_priority,
            "by_stage": by_stage,
            "by_owner": by_owner,
        }

    async def recompute_score(self, actor: User, lead_id: uuid.UUID) -> Lead:
        """Recompute and persist the score for a single lead."""
        lead = await self.get_lead(actor, lead_id)
        lead.score = compute_score(
            email=lead.email, phone=lead.phone, company_name=lead.company_name,
            value=lead.value, source=lead.source, priority=lead.priority,
        )
        self.db.add(lead)
        await self.db.flush()
        return await self.lead_repo.get_lead_by_id(actor.organization_id, lead_id)

    async def get_timeline(self, actor: User, lead_id: uuid.UUID) -> list[dict]:
        """Merge notes, activities, and audit events for a lead into one chronological feed."""
        from sqlalchemy import select, or_
        from app.models.note import Note
        from app.models.activity import Activity
        from app.models.audit_log import AuditLog

        lead = await self.get_lead(actor, lead_id)  # scoping check

        events: list[dict] = []

        notes_res = await self.db.execute(
            select(Note).filter(Note.lead_id == lead.id, Note.is_deleted == False)
        )
        for n in notes_res.scalars().all():
            events.append({
                "type": "note", "id": str(n.id), "timestamp": n.created_at,
                "title": "Note added", "description": n.content,
                "actor_user_id": str(n.created_by) if n.created_by else None,
                "event_metadata": None,
            })

        acts_res = await self.db.execute(
            select(Activity).filter(Activity.lead_id == lead.id, Activity.is_deleted == False)
        )
        for a in acts_res.scalars().all():
            events.append({
                "type": "activity", "id": str(a.id), "timestamp": a.created_at,
                "title": f"{a.activity_type}: {a.subject}", "description": a.description,
                "actor_user_id": str(a.assigned_user_id) if a.assigned_user_id else (str(a.created_by) if a.created_by else None),
                "event_metadata": {"status": a.status, "due_date": a.due_date.isoformat() if a.due_date else None},
            })

        audit_res = await self.db.execute(
            select(AuditLog).filter(
                AuditLog.organization_id == actor.organization_id,
                AuditLog.resource_id == str(lead.id),
                or_(AuditLog.resource_type == "lead", AuditLog.resource_type == "Lead"),
            )
        )
        for al in audit_res.scalars().all():
            events.append({
                "type": "audit", "id": str(al.id), "timestamp": al.created_at,
                "title": al.action, "description": None,
                "actor_user_id": str(al.actor_user_id) if al.actor_user_id else None,
                "event_metadata": al.action_metadata,
            })

        events.sort(key=lambda e: e["timestamp"], reverse=True)
        return events

    async def get_audit_trail(self, actor: User, lead_id: uuid.UUID) -> list[dict]:
        """Return the tenant-visible audit log entries for a single lead."""
        from sqlalchemy import select, or_
        from app.models.audit_log import AuditLog

        lead = await self.get_lead(actor, lead_id)  # scoping check
        res = await self.db.execute(
            select(AuditLog).filter(
                AuditLog.organization_id == actor.organization_id,
                AuditLog.resource_id == str(lead.id),
                or_(AuditLog.resource_type == "lead", AuditLog.resource_type == "Lead"),
            ).order_by(AuditLog.created_at.desc())
        )
        return [
            {
                "id": str(al.id), "action": al.action,
                "actor_user_id": str(al.actor_user_id) if al.actor_user_id else None,
                "created_at": al.created_at, "action_metadata": al.action_metadata,
            }
            for al in res.scalars().all()
        ]

    # --- Attachments ---
    ATTACHMENT_EXTENSIONS = {"pdf", "png", "jpg", "jpeg", "webp", "csv", "xlsx", "docx"}

    async def add_attachment(self, actor: User, lead_id: uuid.UUID, content: bytes, filename: str) -> dict:
        """Validate, store, and attach a file to a lead."""
        from app.core.storage import validate_and_sanitize_file, get_storage_provider

        lead = await self.get_lead(actor, lead_id)  # scoping check
        try:
            sanitized, ext = validate_and_sanitize_file(
                content=content, filename=filename,
                allowed_extensions=self.ATTACHMENT_EXTENSIONS,
            )
        except ValueError as e:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))

        provider = get_storage_provider()
        url = await provider.upload_file(content, sanitized)

        attachment = {
            "filename": filename,
            "stored_name": sanitized,
            "url": url,
            "size": len(content),
            "uploaded_by": str(actor.id),
            "uploaded_at": datetime.now(timezone.utc).isoformat(),
        }
        existing = list(lead.attachments or [])
        existing.append(attachment)
        lead.attachments = existing
        self.db.add(lead)
        await self.db.flush()

        await self.audit_service.log_event(
            organization_id=actor.organization_id, actor_user_id=actor.id,
            action="LEAD_ATTACHMENT_ADDED", resource_type="lead", resource_id=str(lead_id),
            action_metadata={"filename": filename},
        )
        return attachment

    async def list_attachments(self, actor: User, lead_id: uuid.UUID) -> list[dict]:
        lead = await self.get_lead(actor, lead_id)
        return list(lead.attachments or [])

    async def delete_attachment(self, actor: User, lead_id: uuid.UUID, stored_name: str) -> dict:
        from app.core.storage import get_storage_provider

        lead = await self.get_lead(actor, lead_id)
        existing = list(lead.attachments or [])
        target = next((a for a in existing if a.get("stored_name") == stored_name or a.get("filename") == stored_name), None)
        if not target:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Attachment not found")

        remaining = [a for a in existing if a is not target]
        lead.attachments = remaining
        self.db.add(lead)
        await self.db.flush()

        try:
            await get_storage_provider().delete_file(target["url"])
        except Exception:
            pass  # best-effort; DB record already removed

        await self.audit_service.log_event(
            organization_id=actor.organization_id, actor_user_id=actor.id,
            action="LEAD_ATTACHMENT_REMOVED", resource_type="lead", resource_id=str(lead_id),
            action_metadata={"filename": target.get("filename")},
        )
        return {"deleted": True}

    # --- Export helpers ---
    EXPORT_COLUMNS = [
        "first_name", "last_name", "email", "phone", "company_name", "title",
        "status", "stage", "source", "city", "value", "priority", "score",
        "created_at",
    ]

    @staticmethod
    def _export_row(lead: Lead) -> list:
        return [
            lead.first_name or "",
            lead.last_name or "",
            lead.email or "",
            lead.phone or "",
            lead.company_name or "",
            lead.title or "",
            lead.status or "",
            lead.stage.name if lead.stage else "",
            lead.source or "",
            lead.city or "",
            str(lead.value) if lead.value is not None else "",
            lead.priority or "",
            lead.score,
            lead.created_at.isoformat() if lead.created_at else "",
        ]

    @staticmethod
    def build_export_csv(leads: Sequence[Lead]) -> str:
        import csv
        import io
        buf = io.StringIO()
        writer = csv.writer(buf)
        writer.writerow(LeadService.EXPORT_COLUMNS)
        for lead in leads:
            writer.writerow(LeadService._export_row(lead))
        return buf.getvalue()

    @staticmethod
    def build_export_xlsx(leads: Sequence[Lead]) -> bytes:
        import io
        import openpyxl
        wb = openpyxl.Workbook()
        ws = wb.active
        ws.title = "Leads"
        ws.append(LeadService.EXPORT_COLUMNS)
        for lead in leads:
            ws.append(LeadService._export_row(lead))
        out = io.BytesIO()
        wb.save(out)
        return out.getvalue()
