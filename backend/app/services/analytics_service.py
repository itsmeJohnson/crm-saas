import uuid
from datetime import datetime, date, time, timezone
from typing import List, Optional
from sqlalchemy import select, func, case, and_, or_
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.audit_log import AuditLog
from app.models.pipeline import PipelineStage
from app.models.user import User
from app.models.target import PerformanceTarget, TargetType, MetricType
from app.schemas.analytics import (
    PerformanceTargetCreate,
    TelecallerMetricsResponse,
    TelecallerPerformanceSummary,
    PerformerMetric,
    TeamLeaderMetricsResponse,
    TeamLeaderClusterSummary,
    ManagerMetricsResponse,
    TargetProgress,
    SuperAdminMetricsResponse
)

class AnalyticsService:
    @staticmethod
    async def get_converted_stage_id(db: AsyncSession, org_id: uuid.UUID) -> Optional[uuid.UUID]:
        """Resolve the ID of the 'Converted' pipeline stage for an organization."""
        query = select(PipelineStage.id).where(
            PipelineStage.organization_id == org_id,
            PipelineStage.name == "Converted",
            PipelineStage.is_deleted == False
        )
        res = await db.execute(query)
        return res.scalar()

    @staticmethod
    async def get_telecaller_metrics(
        db: AsyncSession,
        telecaller: User,
        target_date: date
    ) -> TelecallerMetricsResponse:
        """Calculate calls, unique leads contacted, and conversions for a telecaller on a specific date."""
        start_dt = datetime.combine(target_date, time.min).replace(tzinfo=timezone.utc)
        end_dt = datetime.combine(target_date, time.max).replace(tzinfo=timezone.utc)

        converted_stage_id = await AnalyticsService.get_converted_stage_id(db, telecaller.organization_id)

        # 1. Calls Made
        query_calls = select(func.count(AuditLog.id)).where(
            AuditLog.organization_id == telecaller.organization_id,
            AuditLog.actor_user_id == telecaller.id,
            AuditLog.action == "LEAD_DISPOSITION_SUBMITTED",
            AuditLog.created_at >= start_dt,
            AuditLog.created_at <= end_dt
        )
        res_calls = await db.execute(query_calls)
        calls_made = res_calls.scalar() or 0

        # 2. Unique Leads Contacted
        query_unique = select(func.count(func.distinct(AuditLog.resource_id))).where(
            AuditLog.organization_id == telecaller.organization_id,
            AuditLog.actor_user_id == telecaller.id,
            AuditLog.action == "LEAD_DISPOSITION_SUBMITTED",
            AuditLog.created_at >= start_dt,
            AuditLog.created_at <= end_dt
        )
        res_unique = await db.execute(query_unique)
        unique_leads = res_unique.scalar() or 0

        # 3. Conversions
        conversions = 0
        if converted_stage_id:
            is_conversion = (AuditLog.action_metadata['new_stage_id'].as_string() == str(converted_stage_id))
            query_conv = select(func.count(AuditLog.id)).where(
                AuditLog.organization_id == telecaller.organization_id,
                AuditLog.actor_user_id == telecaller.id,
                AuditLog.action == "LEAD_DISPOSITION_SUBMITTED",
                AuditLog.created_at >= start_dt,
                AuditLog.created_at <= end_dt,
                is_conversion
            )
            res_conv = await db.execute(query_conv)
            conversions = res_conv.scalar() or 0

        return TelecallerMetricsResponse(
            calls_made=calls_made,
            unique_leads_contacted=unique_leads,
            conversions=conversions,
            date=target_date
        )

    @staticmethod
    async def get_team_leader_metrics(
        db: AsyncSession,
        tl: User,
        target_date: Optional[date] = None
    ) -> TeamLeaderMetricsResponse:
        """Get summary and detailed metrics for all telecallers reporting to a Team Leader."""
        if not target_date:
            target_date = date.today()

        # Find all direct telecaller downlines
        stmt = select(User).where(
            User.organization_id == tl.organization_id,
            User.reporting_to_id == tl.id,
            User.role == "Employee",
            User.is_deleted == False
        )
        res = await db.execute(stmt)
        telecallers = res.scalars().all()

        total_calls = 0
        total_unique = 0
        total_conv = 0
        downlines_summaries = []

        for agent in telecallers:
            metrics = await AnalyticsService.get_telecaller_metrics(db, agent, target_date)
            
            rate = 0.0
            if metrics.calls_made > 0:
                rate = (metrics.conversions / metrics.calls_made) * 100.0

            summary = TelecallerPerformanceSummary(
                user_id=agent.id,
                first_name=agent.first_name,
                last_name=agent.last_name,
                email=agent.email,
                calls_made=metrics.calls_made,
                unique_leads_contacted=metrics.unique_leads_contacted,
                conversions=metrics.conversions,
                conversion_rate=round(rate, 2)
            )
            downlines_summaries.append(summary)
            
            total_calls += metrics.calls_made
            total_unique += metrics.unique_leads_contacted
            total_conv += metrics.conversions

        # Identify Top/Low performers
        top_perf: Optional[PerformerMetric] = None
        low_perf: Optional[PerformerMetric] = None

        # Filter agents who actually made calls to determine top/low performers
        active_summaries = [s for s in downlines_summaries if s.calls_made > 0]
        if active_summaries:
            # Top Performer: Highest conversion rate, tiebreaker: conversions desc, calls desc
            sorted_top = sorted(
                active_summaries,
                key=lambda x: (x.conversion_rate, x.conversions, x.calls_made),
                reverse=True
            )
            top = sorted_top[0]
            top_perf = PerformerMetric(
                user_id=top.user_id,
                first_name=top.first_name,
                last_name=top.last_name,
                email=top.email,
                calls_made=top.calls_made,
                conversions=top.conversions,
                conversion_rate=top.conversion_rate
            )

            # Low Performer: Lowest conversion rate, tiebreaker: conversions asc, calls asc
            sorted_low = sorted(
                active_summaries,
                key=lambda x: (x.conversion_rate, x.conversions, x.calls_made)
            )
            low = sorted_low[0]
            low_perf = PerformerMetric(
                user_id=low.user_id,
                first_name=low.first_name,
                last_name=low.last_name,
                email=low.email,
                calls_made=low.calls_made,
                conversions=low.conversions,
                conversion_rate=low.conversion_rate
            )

        return TeamLeaderMetricsResponse(
            total_calls_made=total_calls,
            total_unique_leads_contacted=total_unique,
            total_conversions=total_conv,
            downlines=downlines_summaries,
            top_performer=top_perf,
            low_performer=low_perf
        )

    @staticmethod
    async def get_manager_metrics(
        db: AsyncSession,
        manager: User,
        target_date: Optional[date] = None
    ) -> ManagerMetricsResponse:
        """Get summarized metrics of TL teams reporting to a Manager."""
        if not target_date:
            target_date = date.today()

        # Find direct Team Leaders
        stmt = select(User).where(
            User.organization_id == manager.organization_id,
            User.reporting_to_id == manager.id,
            User.role == "Employee",
            User.is_deleted == False
        )
        res = await db.execute(stmt)
        tls = res.scalars().all()

        teams_summaries = []
        overall_calls = 0
        overall_unique = 0
        overall_conv = 0

        for tl in tls:
            tl_metrics = await AnalyticsService.get_team_leader_metrics(db, tl, target_date)
            
            cluster = TeamLeaderClusterSummary(
                tl_id=tl.id,
                tl_first_name=tl.first_name,
                tl_last_name=tl.last_name,
                tl_email=tl.email,
                total_calls_made=tl_metrics.total_calls_made,
                total_unique_leads_contacted=tl_metrics.total_unique_leads_contacted,
                total_conversions=tl_metrics.total_conversions
            )
            teams_summaries.append(cluster)

            overall_calls += tl_metrics.total_calls_made
            overall_unique += tl_metrics.total_unique_leads_contacted
            overall_conv += tl_metrics.total_conversions

        return ManagerMetricsResponse(
            teams=teams_summaries,
            total_calls_made=overall_calls,
            total_unique_leads_contacted=overall_unique,
            total_conversions=overall_conv
        )

    @staticmethod
    async def get_super_admin_metrics(
        db: AsyncSession,
        org_id: uuid.UUID,
        current_date: Optional[date] = None
    ) -> SuperAdminMetricsResponse:
        """Get target progress gauges for active targets in the organization."""
        if not current_date:
            current_date = date.today()

        # Query all active targets
        stmt = select(PerformanceTarget).where(
            PerformanceTarget.organization_id == org_id,
            PerformanceTarget.start_date <= current_date,
            PerformanceTarget.end_date >= current_date,
            PerformanceTarget.is_deleted == False
        )
        res = await db.execute(stmt)
        targets = res.scalars().all()

        converted_stage_id = await AnalyticsService.get_converted_stage_id(db, org_id)
        progresses = []

        for target in targets:
            start_dt = datetime.combine(target.start_date, time.min).replace(tzinfo=timezone.utc)
            end_dt = datetime.combine(target.end_date, time.max).replace(tzinfo=timezone.utc)

            actual_value = 0
            if target.metric_type == MetricType.CALLS_MADE:
                query_actual = select(func.count(AuditLog.id)).where(
                    AuditLog.organization_id == org_id,
                    AuditLog.action == "LEAD_DISPOSITION_SUBMITTED",
                    AuditLog.created_at >= start_dt,
                    AuditLog.created_at <= end_dt
                )
                res_actual = await db.execute(query_actual)
                actual_value = res_actual.scalar() or 0

            elif target.metric_type == MetricType.LEADS_CONVERTED:
                if converted_stage_id:
                    is_conversion = (AuditLog.action_metadata['new_stage_id'].as_string() == str(converted_stage_id))
                    query_actual = select(func.count(AuditLog.id)).where(
                        AuditLog.organization_id == org_id,
                        AuditLog.action == "LEAD_DISPOSITION_SUBMITTED",
                        AuditLog.created_at >= start_dt,
                        AuditLog.created_at <= end_dt,
                        is_conversion
                    )
                    res_actual = await db.execute(query_actual)
                    actual_value = res_actual.scalar() or 0

            pct = 0.0
            if target.target_value > 0:
                pct = (actual_value / target.target_value) * 100.0

            progress = TargetProgress(
                target_id=target.id,
                target_type=target.target_type,
                metric_type=target.metric_type,
                target_value=target.target_value,
                actual_value=actual_value,
                progress_percentage=round(pct, 2),
                start_date=target.start_date,
                end_date=target.end_date
            )
            progresses.append(progress)

        return SuperAdminMetricsResponse(
            targets_progress=progresses
        )

    @staticmethod
    async def create_target(
        db: AsyncSession,
        org_id: uuid.UUID,
        target_in: PerformanceTargetCreate
    ) -> PerformanceTarget:
        """Create a new performance target for the organization."""
        target = PerformanceTarget(
            organization_id=org_id,
            target_type=target_in.target_type,
            metric_type=target_in.metric_type,
            target_value=target_in.target_value,
            start_date=target_in.start_date,
            end_date=target_in.end_date
        )
        db.add(target)
        await db.commit()
        await db.refresh(target)
        return target

    @staticmethod
    async def list_targets(
        db: AsyncSession,
        org_id: uuid.UUID
    ) -> List[PerformanceTarget]:
        """List all performance targets for the organization."""
        stmt = select(PerformanceTarget).where(
            PerformanceTarget.organization_id == org_id,
            PerformanceTarget.is_deleted == False
        ).order_index = select(PerformanceTarget).order_by(PerformanceTarget.created_at.desc())
        
        # Wait, the ordering code above has a slight typo. Let's fix that.
        stmt = select(PerformanceTarget).where(
            PerformanceTarget.organization_id == org_id,
            PerformanceTarget.is_deleted == False
        ).order_by(PerformanceTarget.created_at.desc())
        
        res = await db.execute(stmt)
        return list(res.scalars().all())
