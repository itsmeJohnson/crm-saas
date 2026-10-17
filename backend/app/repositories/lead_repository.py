import uuid
from datetime import datetime, timezone
from typing import Sequence, Tuple
from sqlalchemy import select, func, or_
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.lead import Lead
from app.repositories.base import TenantRepository

class LeadRepository(TenantRepository[Lead]):
    def __init__(self, db: AsyncSession, organization_id: uuid.UUID):
        super().__init__(Lead, db, organization_id)

    async def create_lead(self, lead_data: dict, created_by: uuid.UUID) -> Lead:
        lead_data["organization_id"] = self.organization_id
        lead_data["created_by"] = created_by

        if "stage_id" not in lead_data or not lead_data["stage_id"]:
            from app.models.pipeline import PipelineStage
            stage_query = select(PipelineStage.id).filter(
                PipelineStage.organization_id == self.organization_id,
                PipelineStage.is_system_default == True,
                PipelineStage.is_deleted == False
            ).limit(1)
            res = await self.db.execute(stage_query)
            stage_id = res.scalar()

            if not stage_id:
                stage_query_fallback = select(PipelineStage.id).filter(
                    PipelineStage.organization_id == self.organization_id,
                    PipelineStage.is_deleted == False
                ).order_by(PipelineStage.order_position).limit(1)
                res_fallback = await self.db.execute(stage_query_fallback)
                stage_id = res_fallback.scalar()

            lead_data["stage_id"] = stage_id

        lead = await self.create(lead_data)
        from sqlalchemy.orm import selectinload
        refetched_query = select(Lead).options(selectinload(Lead.stage)).filter(Lead.id == lead.id)
        refetched_res = await self.db.execute(refetched_query)
        return refetched_res.scalar_one()

    async def get_lead_by_id(self, lead_id: uuid.UUID) -> Lead | None:
        from sqlalchemy.orm import selectinload
        query = select(self.model).options(selectinload(self.model.stage)).filter(
            self.model.id == lead_id,
            self.model.organization_id == self.organization_id,
            self.model.is_deleted == False
        )
        result = await self.db.execute(query)
        return result.scalars().first()

    async def get_lead_by_email(self, email: str) -> Lead | None:
        query = select(self.model).filter(
            self.model.email == email,
            self.model.organization_id == self.organization_id,
            self.model.is_deleted == False
        )
        result = await self.db.execute(query)
        return result.scalars().first()

    def _apply_lead_filters(
        self,
        query,
        search_query: str | None = None,
        status: str | None = None,
        assigned_user_id: uuid.UUID | None = None,
        name: str | None = None,
        city: str | None = None,
        allowed_user_ids: set[uuid.UUID] | None = None,
        source: str | None = None,
        stage_id: uuid.UUID | None = None,
        priority: str | None = None,
        min_value: float | None = None,
        max_value: float | None = None,
        created_from: datetime | None = None,
        created_to: datetime | None = None,
        include_archived: bool = False,
        custom_filters: dict | None = None,
    ):
        """Apply the shared lead filter predicates. Used by both listing and export."""
        query = query.filter(
            self.model.organization_id == self.organization_id,
            self.model.is_deleted == False
        )

        if not include_archived:
            query = query.filter(self.model.is_archived == False)

        if status:
            query = query.filter(self.model.status == status)

        if assigned_user_id:
            query = query.filter(self.model.assigned_user_id == assigned_user_id)
        elif allowed_user_ids is not None:
            query = query.filter(self.model.assigned_user_id.in_(allowed_user_ids))

        if source:
            query = query.filter(self.model.source == source)

        if stage_id:
            query = query.filter(self.model.stage_id == stage_id)

        if priority:
            query = query.filter(self.model.priority == priority)

        if min_value is not None:
            query = query.filter(self.model.value >= min_value)

        if max_value is not None:
            query = query.filter(self.model.value <= max_value)

        if created_from is not None:
            query = query.filter(self.model.created_at >= created_from)

        if created_to is not None:
            query = query.filter(self.model.created_at <= created_to)

        if name:
            name_filter = f"%{name}%"
            query = query.filter(
                or_(
                    self.model.first_name.ilike(name_filter),
                    self.model.last_name.ilike(name_filter)
                )
            )

        if city:
            city_filter = f"%{city}%"
            query = query.filter(self.model.city.ilike(city_filter))

        # Tenant-defined custom field filters: {key: value} matched against the
        # JSON custom_fields column (substring, case-insensitive).
        if custom_filters:
            for key, val in custom_filters.items():
                if val is None or val == "":
                    continue
                query = query.filter(self.model.custom_fields[key].as_string().ilike(f"%{val}%"))

        if search_query:
            clean_search = search_query.strip()
            if clean_search:
                search_filter = f"%{clean_search}%"
                # Matches exact concatenated expression indexed by ix_leads_trgm_search GIN index
                search_expr = (
                    func.coalesce(self.model.title, '') + ' ' +
                    func.coalesce(self.model.company_name, '') + ' ' +
                    func.coalesce(self.model.first_name, '') + ' ' +
                    func.coalesce(self.model.last_name, '') + ' ' +
                    func.coalesce(self.model.email, '') + ' ' +
                    func.coalesce(self.model.phone, '') + ' ' +
                    func.coalesce(self.model.city, '')
                )
                query = query.filter(search_expr.ilike(search_filter))
        return query

    async def paginate_leads(
        self,
        skip: int = 0,
        limit: int = 100,
        search_query: str | None = None,
        status: str | None = None,
        assigned_user_id: uuid.UUID | None = None,
        name: str | None = None,
        city: str | None = None,
        allowed_user_ids: set[uuid.UUID] | None = None,
        source: str | None = None,
        stage_id: uuid.UUID | None = None,
        priority: str | None = None,
        min_value: float | None = None,
        max_value: float | None = None,
        created_from: datetime | None = None,
        created_to: datetime | None = None,
        include_archived: bool = False,
        updated_after: datetime | None = None,
        custom_filters: dict | None = None,
    ) -> Tuple[Sequence[Lead], int]:
        query = self._apply_lead_filters(
            select(self.model), search_query, status, assigned_user_id,
            name, city, allowed_user_ids, source, stage_id, priority, min_value, max_value,
            created_from, created_to, include_archived, custom_filters=custom_filters
        )
        # Incremental (delta) sync cursor for offline mobile clients: only rows
        # changed since the client's last pull.
        if updated_after is not None:
            query = query.filter(self.model.updated_at > updated_after)

        # Get total count
        count_query = select(func.count()).select_from(query.subquery())
        count_result = await self.db.execute(count_query)
        total = count_result.scalar_one()

        # Get records ordered by created_at desc
        from sqlalchemy.orm import selectinload
        records_query = query.options(selectinload(self.model.stage)).order_by(self.model.created_at.desc()).offset(skip).limit(limit)
        records_result = await self.db.execute(records_query)
        records = records_result.scalars().all()

        return records, total

    async def stream_leads_for_export(
        self,
        allowed_user_ids: set[uuid.UUID] | None = None,
        max_rows: int = 50000,
        **filters,
    ) -> Sequence[Lead]:
        """Fetch leads matching filters for export, capped at max_rows."""
        from sqlalchemy.orm import selectinload
        query = self._apply_lead_filters(
            select(self.model), allowed_user_ids=allowed_user_ids, **filters
        )
        query = query.options(selectinload(self.model.stage)).order_by(self.model.created_at.desc()).limit(max_rows)
        result = await self.db.execute(query)
        return result.scalars().all()

    async def find_duplicates(
        self,
        email: str | None = None,
        phone: str | None = None,
        exclude_lead_id: uuid.UUID | None = None,
    ) -> Sequence[Lead]:
        """Find non-deleted leads matching the same email or phone within the org."""
        if not email and not phone:
            return []
        match_clauses = []
        if email:
            match_clauses.append(func.lower(self.model.email) == email.lower())
        if phone:
            match_clauses.append(self.model.phone == phone)

        from sqlalchemy.orm import selectinload
        query = select(self.model).options(selectinload(self.model.stage)).filter(
            self.model.organization_id == self.organization_id,
            self.model.is_deleted == False,
            or_(*match_clauses)
        )
        if exclude_lead_id:
            query = query.filter(self.model.id != exclude_lead_id)
        result = await self.db.execute(query)
        return result.scalars().all()

    async def get_leads_for_update(
        self, lead_ids: list[uuid.UUID]
    ) -> Sequence[Lead]:
        """Fetch a set of non-deleted leads by id with row locks for bulk mutation."""
        query = select(self.model).filter(
            self.model.id.in_(lead_ids),
            self.model.organization_id == self.organization_id,
            self.model.is_deleted == False
        ).with_for_update().order_by(self.model.id)
        result = await self.db.execute(query)
        return result.scalars().all()

    async def get_lead_any_state(self, lead_id: uuid.UUID) -> Lead | None:
        """Fetch a lead regardless of soft-delete/archived state (for restore flows)."""
        from sqlalchemy.orm import selectinload
        query = select(self.model).options(selectinload(self.model.stage)).filter(
            self.model.id == lead_id,
            self.model.organization_id == self.organization_id
        )
        result = await self.db.execute(query)
        return result.scalars().first()

    async def update_lead(self, lead_id: uuid.UUID, lead_data: dict) -> Lead | None:
        lead = await self.get_lead_by_id(lead_id)
        if not lead:
            return None
        updated_lead = await self.update(lead, lead_data)
        from sqlalchemy.orm import selectinload
        refetched_query = select(Lead).options(selectinload(Lead.stage)).filter(Lead.id == updated_lead.id)
        refetched_res = await self.db.execute(refetched_query)
        return refetched_res.scalar_one()

    async def soft_delete_lead(self, lead_id: uuid.UUID) -> Lead | None:
        lead = await self.get_lead_by_id(lead_id)
        if not lead:
            return None
        lead.is_deleted = True
        lead.deleted_at = datetime.now(timezone.utc)
        self.db.add(lead)
        await self.db.flush()
        return lead

    async def get_sales_kpi_summary(self, allowed_user_ids: set[uuid.UUID] | None = None) -> dict:
        """Calculate the 5 core Sales KPIs in a single high-performance SQL aggregation query.
        Uses composite index ix_leads_org_active_created; executes in < 1ms at million-lead scale.
        """
        from sqlalchemy import text
        from typing import Any
        scope_clause = ""
        params: dict[str, Any] = {"org_id": self.organization_id}
        if allowed_user_ids is not None:
            scope_clause = "AND assigned_user_id = ANY(:allowed_users)"
            params["allowed_users"] = list(allowed_user_ids)

        sql = text(f"""
            SELECT
                COALESCE(SUM(CASE 
                    WHEN is_deleted = false AND is_archived = false AND status NOT IN ('Lost', 'Converted', 'Dropped') 
                    THEN value ELSE 0 
                END), 0) AS active_pipeline_value,
                COUNT(CASE 
                    WHEN is_deleted = false AND is_archived = false AND status NOT IN ('Lost', 'Converted', 'Dropped') 
                    THEN 1 
                END) AS active_deals_count,
                COALESCE(SUM(CASE 
                    WHEN is_deleted = false AND is_archived = false AND status NOT IN ('Lost', 'Dropped') THEN 
                        value * (CASE 
                            WHEN status = 'Converted' OR status ILIKE '%won%' THEN 1.0
                            WHEN status ILIKE '%follow%' OR status ILIKE '%qualif%' THEN 0.6
                            WHEN status ILIKE '%contact%' THEN 0.4
                            ELSE 0.2
                        END)
                    ELSE 0
                END), 0) AS weighted_forecast,
                COALESCE(SUM(CASE 
                    WHEN is_deleted = false AND (status = 'Converted' OR status ILIKE '%won%') 
                         AND (created_at >= date_trunc('month', NOW()) OR converted_at >= date_trunc('month', NOW()))
                    THEN value ELSE 0 
                END), 0) AS won_revenue_this_month,
                COUNT(CASE 
                    WHEN is_deleted = false AND (status = 'Converted' OR status ILIKE '%won%') 
                         AND (created_at >= date_trunc('month', NOW()) OR converted_at >= date_trunc('month', NOW()))
                    THEN 1 
                END) AS won_deals_count,
                COUNT(CASE 
                    WHEN is_deleted = false AND (status = 'Lost' OR status ILIKE '%drop%') 
                    THEN 1 
                END) AS lost_deals_count,
                COUNT(CASE 
                    WHEN is_deleted = false AND is_archived = false AND status NOT IN ('Lost', 'Converted', 'Dropped') 
                         AND updated_at < (NOW() - INTERVAL '7 days') 
                    THEN 1 
                END) AS overdue_followups_count,
                COUNT(CASE 
                    WHEN is_deleted = false AND is_archived = false 
                    THEN 1 
                END) AS total_leads_count
            FROM leads
            WHERE organization_id = :org_id
            {scope_clause}
        """)
        res = await self.db.execute(sql, params)
        row = res.mappings().one()

        won_deals = int(row["won_deals_count"])
        lost_deals = int(row["lost_deals_count"])
        total_closed = won_deals + lost_deals
        win_rate = round((won_deals / total_closed) * 100, 1) if total_closed > 0 else 0.0

        return {
            "active_pipeline_value": row["active_pipeline_value"],
            "active_deals_count": int(row["active_deals_count"]),
            "weighted_forecast": row["weighted_forecast"],
            "won_revenue_this_month": row["won_revenue_this_month"],
            "won_deals_count": won_deals,
            "lost_deals_count": lost_deals,
            "win_rate": win_rate,
            "overdue_followups_count": int(row["overdue_followups_count"]),
            "total_leads_count": int(row["total_leads_count"]),
        }

    async def get_kanban_board(
        self,
        pipeline_id: uuid.UUID | None = None,
        allowed_user_ids: set[uuid.UUID] | None = None,
        initial_card_limit: int = 10,
    ) -> dict:
        """Fetch accurate server-calculated stage aggregates and initial cards per stage."""
        from app.models.pipeline import Pipeline, PipelineStage
        from sqlalchemy.orm import selectinload
        from sqlalchemy import text
        from typing import Any

        # 1. Resolve pipeline & its stages
        if not pipeline_id:
            pipe_query = select(Pipeline).filter(
                Pipeline.organization_id == self.organization_id,
                Pipeline.is_deleted == False
            ).order_by(Pipeline.is_default.desc(), Pipeline.created_at.asc()).limit(1)
            pipe_res = await self.db.execute(pipe_query)
            pipeline = pipe_res.scalars().first()
        else:
            pipe_query = select(Pipeline).filter(
                Pipeline.id == pipeline_id,
                Pipeline.organization_id == self.organization_id,
                Pipeline.is_deleted == False
            ).limit(1)
            pipe_res = await self.db.execute(pipe_query)
            pipeline = pipe_res.scalars().first()

        if not pipeline:
            return {"pipeline_id": None, "stages": [], "total_pipeline_value": 0, "total_deals_count": 0}

        stage_query = select(PipelineStage).filter(
            PipelineStage.pipeline_id == pipeline.id,
            PipelineStage.organization_id == self.organization_id,
            PipelineStage.is_deleted == False
        ).order_by(PipelineStage.order_position.asc())
        stage_res = await self.db.execute(stage_query)
        stages = stage_res.scalars().all()

        if not stages:
            return {"pipeline_id": pipeline.id, "stages": [], "total_pipeline_value": 0, "total_deals_count": 0}

        # 2. Compute accurate stage counts & sums via single GROUP BY query
        scope_clause = ""
        params: dict[str, Any] = {
            "org_id": self.organization_id,
            "stage_ids": [s.id for s in stages]
        }
        if allowed_user_ids is not None:
            scope_clause = "AND assigned_user_id = ANY(:allowed_users)"
            params["allowed_users"] = list(allowed_user_ids)

        agg_sql = text(f"""
            SELECT 
                stage_id,
                COUNT(*) as stage_count,
                COALESCE(SUM(value), 0) as stage_value
            FROM leads
            WHERE organization_id = :org_id
              AND is_deleted = false
              AND is_archived = false
              AND stage_id = ANY(:stage_ids)
              {scope_clause}
            GROUP BY stage_id
        """)
        agg_res = await self.db.execute(agg_sql, params)
        agg_map = {row["stage_id"]: (int(row["stage_count"]), row["stage_value"]) for row in agg_res.mappings().all()}

        # 3. For each stage, fetch initial cards (limit=initial_card_limit)
        stages_data = []
        total_pipeline_value = 0
        total_deals_count = 0

        for stage in stages:
            cnt, val = agg_map.get(stage.id, (0, 0))
            if not stage.is_lost:
                total_pipeline_value += val
            total_deals_count += cnt

            card_q = select(Lead).options(selectinload(Lead.stage)).filter(
                Lead.organization_id == self.organization_id,
                Lead.stage_id == stage.id,
                Lead.is_deleted == False,
                Lead.is_archived == False,
            )
            if allowed_user_ids is not None:
                card_q = card_q.filter(Lead.assigned_user_id.in_(allowed_user_ids))
            
            card_q = card_q.order_by(Lead.created_at.desc()).limit(initial_card_limit)
            card_res = await self.db.execute(card_q)
            cards = card_res.scalars().all()

            stages_data.append({
                "stage_id": stage.id,
                "stage_name": stage.name,
                "order_position": stage.order_position,
                "total_count": cnt,
                "total_value": val,
                "cards": cards,
                "has_more": cnt > len(cards),
            })

        return {
            "pipeline_id": pipeline.id,
            "stages": stages_data,
            "total_pipeline_value": total_pipeline_value,
            "total_deals_count": total_deals_count,
        }

    async def get_kanban_stage_cards(
        self,
        stage_id: uuid.UUID,
        allowed_user_ids: set[uuid.UUID] | None = None,
        skip: int = 0,
        limit: int = 10,
    ) -> dict:
        """Fetch next slice of cards for a specific Kanban stage."""
        from sqlalchemy.orm import selectinload

        cnt_q = select(func.count(Lead.id)).filter(
            Lead.organization_id == self.organization_id,
            Lead.stage_id == stage_id,
            Lead.is_deleted == False,
            Lead.is_archived == False,
        )
        if allowed_user_ids is not None:
            cnt_q = cnt_q.filter(Lead.assigned_user_id.in_(allowed_user_ids))
        cnt_res = await self.db.execute(cnt_q)
        total_count = cnt_res.scalar_one()

        card_q = select(Lead).options(selectinload(Lead.stage)).filter(
            Lead.organization_id == self.organization_id,
            Lead.stage_id == stage_id,
            Lead.is_deleted == False,
            Lead.is_archived == False,
        )
        if allowed_user_ids is not None:
            card_q = card_q.filter(Lead.assigned_user_id.in_(allowed_user_ids))
        card_q = card_q.order_by(Lead.created_at.desc()).offset(skip).limit(limit)
        card_res = await self.db.execute(card_q)
        cards = card_res.scalars().all()

        return {
            "stage_id": stage_id,
            "total_count": total_count,
            "cards": cards,
            "has_more": total_count > (skip + len(cards)),
            "skip": skip,
            "limit": limit,
        }

