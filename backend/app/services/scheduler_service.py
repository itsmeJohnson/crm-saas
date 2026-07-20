"""Scheduler service.

A first-class, configurable scheduling layer on top of the app's existing
subsystems. A Schedule runs on a cron expression or a structured recurrence
(hourly/daily/weekly/monthly/interval) at a specific local time, timezone-aware,
optionally gated to business hours and skipping holidays. When due it dispatches
to the automation engine, background queue, event bus, a report, or a webhook —
so producers stay decoupled.

The single hardcoded midnight loop is left intact; a new minute-granularity tick
(scheduler_tick.py) drives `run_due`, which reuses the existing WorkingHoursConfig
and Holiday tables for gating.
"""
from __future__ import annotations
import time
import uuid
from datetime import datetime, timezone, timedelta, date, time as dtime
from zoneinfo import ZoneInfo
from fastapi import HTTPException, status
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User
from app.models.scheduler import Schedule, ScheduleRun
from app.models.calendar_event import Holiday, WorkingHoursConfig
from app.services import cron_utils

TASK_TYPES = ("run_automation_job", "enqueue_queue_job", "run_report", "event_publish", "webhook",
              "notification_digest", "noop")
SCHEDULE_KINDS = ("cron", "interval", "hourly", "daily", "weekly", "monthly")
WEEKDAYS = ["mon", "tue", "wed", "thu", "fri", "sat", "sun"]  # index 0=Mon .. 6=Sun


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _aware(dt: datetime | None) -> datetime | None:
    if dt is None:
        return None
    return dt if dt.tzinfo is not None else dt.replace(tzinfo=timezone.utc)


def _tz(name: str) -> ZoneInfo:
    try:
        return ZoneInfo(name or "UTC")
    except Exception:
        return ZoneInfo("UTC")


def _parse_hhmm(s: str | None, default=(0, 0)) -> tuple[int, int]:
    if not s:
        return default
    try:
        h, m = s.split(":")
        return int(h), int(m)
    except (ValueError, AttributeError):
        return default


class SchedulerService:
    def __init__(self, db: AsyncSession):
        self.db = db

    # ---------- permissions ----------
    def _require_manager(self, actor: User):
        if actor.role not in ("SuperAdmin", "OrgAdmin", "Manager"):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN,
                                detail="Only managers and admins can manage schedules.")

    @staticmethod
    def catalog() -> dict:
        return {"task_types": list(TASK_TYPES), "schedule_kinds": list(SCHEDULE_KINDS),
                "weekdays": WEEKDAYS}

    # ================= next-run computation =================
    def compute_next_run(self, sched: Schedule, after: datetime | None = None) -> datetime | None:
        """Next UTC fire time strictly after `after` (default: now), honouring the
        schedule's kind and timezone."""
        after = _aware(after) or _now()
        tz = _tz(sched.timezone)
        local_after = after.astimezone(tz)

        if sched.schedule_kind == "cron":
            if not sched.cron_expr or not cron_utils.is_valid_cron(sched.cron_expr):
                return None
            nxt_local = cron_utils.cron_next(sched.cron_expr, local_after)
            return nxt_local.replace(tzinfo=tz).astimezone(timezone.utc) if nxt_local else None

        if sched.schedule_kind == "interval":
            mins = max(1, sched.interval_minutes or 60)
            return after + timedelta(minutes=mins)

        if sched.schedule_kind == "hourly":
            _, mm = _parse_hhmm(sched.time_of_day, (0, 0))
            cand = local_after.replace(minute=mm, second=0, microsecond=0)
            if cand <= local_after:
                cand += timedelta(hours=1)
            return cand.astimezone(timezone.utc)

        hh, mm = _parse_hhmm(sched.time_of_day, (0, 0))
        base = local_after.replace(hour=hh, minute=mm, second=0, microsecond=0)

        if sched.schedule_kind == "daily":
            cand = base
            if cand <= local_after:
                cand += timedelta(days=1)
            return cand.astimezone(timezone.utc)

        if sched.schedule_kind == "weekly":
            target = sched.day_of_week if sched.day_of_week is not None else 0  # Mon
            cand = base
            delta = (target - cand.weekday()) % 7
            cand += timedelta(days=delta)
            if cand <= local_after:
                cand += timedelta(days=7)
            return cand.astimezone(timezone.utc)

        if sched.schedule_kind == "monthly":
            dom = sched.day_of_month or 1
            cand = self._month_day(local_after, dom, hh, mm)
            if cand <= local_after:
                # advance one month
                nxt_month = (local_after.replace(day=1) + timedelta(days=32)).replace(day=1)
                cand = self._month_day(nxt_month, dom, hh, mm)
            return cand.astimezone(timezone.utc)
        return None

    @staticmethod
    def _month_day(ref: datetime, dom: int, hh: int, mm: int) -> datetime:
        # clamp day to the month's length
        first_next = (ref.replace(day=1) + timedelta(days=32)).replace(day=1)
        last_day = (first_next - timedelta(days=1)).day
        return ref.replace(day=min(dom, last_day), hour=hh, minute=mm, second=0, microsecond=0)

    # ================= business hours / holidays (reused tables) =================
    async def _is_business_hours(self, org_id: uuid.UUID, at: datetime) -> bool:
        cfg = (await self.db.execute(select(WorkingHoursConfig).filter(
            WorkingHoursConfig.organization_id == org_id))).scalars().first()
        tzname = cfg.timezone if cfg else "UTC"
        local = at.astimezone(_tz(tzname))
        days = cfg.days if cfg else None
        if not days:
            # default: Mon–Fri 09:00–17:00
            if local.weekday() >= 5:
                return False
            return dtime(9, 0) <= local.time() <= dtime(17, 0)
        day = days.get(WEEKDAYS[local.weekday()], {})
        if not day.get("enabled"):
            return False
        sh, sm = _parse_hhmm(day.get("start"), (9, 0))
        eh, em = _parse_hhmm(day.get("end"), (17, 0))
        return dtime(sh, sm) <= local.time() <= dtime(eh, em)

    async def _is_holiday(self, org_id: uuid.UUID, at: datetime) -> bool:
        cfg = (await self.db.execute(select(WorkingHoursConfig).filter(
            WorkingHoursConfig.organization_id == org_id))).scalars().first()
        d = at.astimezone(_tz(cfg.timezone if cfg else "UTC")).date()
        rows = (await self.db.execute(select(Holiday).filter(
            Holiday.organization_id == org_id, Holiday.is_deleted == False))).scalars().all()
        for h in rows:
            if h.recurring_annual:
                if h.holiday_date.month == d.month and h.holiday_date.day == d.day:
                    return True
            elif h.holiday_date == d:
                return True
        return False

    # ================= CRUD =================
    def _validate(self, data: dict):
        tt = data.get("task_type")
        if tt and tt not in TASK_TYPES:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"task_type must be one of {TASK_TYPES}")
        kind = data.get("schedule_kind")
        if kind and kind not in SCHEDULE_KINDS:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"schedule_kind must be one of {SCHEDULE_KINDS}")
        if kind == "cron":
            expr = data.get("cron_expr")
            if not expr or not cron_utils.is_valid_cron(expr):
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="A valid 5-field cron_expr is required for cron schedules.")
        if data.get("timezone"):
            try:
                ZoneInfo(data["timezone"])
            except Exception:
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Unknown timezone: {data['timezone']}")

    async def _get(self, actor: User, schedule_id: uuid.UUID) -> Schedule:
        s = (await self.db.execute(select(Schedule).filter(
            Schedule.id == schedule_id, Schedule.organization_id == actor.organization_id,
            Schedule.is_deleted == False))).scalars().first()
        if not s:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Schedule not found.")
        return s

    async def list_schedules(self, actor: User, active_only: bool = False) -> list[dict]:
        q = select(Schedule).filter(Schedule.organization_id == actor.organization_id, Schedule.is_deleted == False)
        if active_only:
            q = q.filter(Schedule.is_active == True)
        q = q.order_by(Schedule.next_run_at.asc().nullslast(), Schedule.created_at.desc())
        return [self._dict(s) for s in (await self.db.execute(q)).scalars().all()]

    async def get(self, actor: User, schedule_id: uuid.UUID) -> dict:
        return self._dict(await self._get(actor, schedule_id))

    async def create(self, actor: User, data: dict) -> dict:
        self._require_manager(actor)
        self._validate(data)
        s = Schedule(organization_id=actor.organization_id, name=data["name"], description=data.get("description"),
                     task_type=data["task_type"], task_config=data.get("task_config"),
                     schedule_kind=data.get("schedule_kind") or "daily", cron_expr=data.get("cron_expr"),
                     time_of_day=data.get("time_of_day"), day_of_week=data.get("day_of_week"),
                     day_of_month=data.get("day_of_month"), interval_minutes=data.get("interval_minutes"),
                     timezone=data.get("timezone") or "UTC",
                     business_hours_only=bool(data.get("business_hours_only", False)),
                     skip_holidays=bool(data.get("skip_holidays", False)),
                     is_active=bool(data.get("is_active", True)), max_retries=int(data.get("max_retries", 1)),
                     created_by=actor.id)
        s.next_run_at = self.compute_next_run(s)
        self.db.add(s)
        await self.db.flush()
        return self._dict(s)

    async def update(self, actor: User, schedule_id: uuid.UUID, data: dict) -> dict:
        self._require_manager(actor)
        s = await self._get(actor, schedule_id)
        merged = {**self._dict(s), **data}
        self._validate(merged)
        for f in ("name", "description", "task_type", "task_config", "schedule_kind", "cron_expr",
                  "time_of_day", "day_of_week", "day_of_month", "interval_minutes", "timezone",
                  "business_hours_only", "skip_holidays", "is_active", "max_retries"):
            if f in data and data[f] is not None:
                setattr(s, f, data[f])
        # recompute the next fire time whenever the timing changes
        if any(k in data for k in ("schedule_kind", "cron_expr", "time_of_day", "day_of_week",
                                   "day_of_month", "interval_minutes", "timezone", "is_active")):
            s.next_run_at = self.compute_next_run(s) if s.is_active else None
        self.db.add(s)
        await self.db.flush()
        return self._dict(s)

    async def set_enabled(self, actor: User, schedule_id: uuid.UUID, enabled: bool) -> dict:
        self._require_manager(actor)
        s = await self._get(actor, schedule_id)
        s.is_active = enabled
        s.next_run_at = self.compute_next_run(s) if enabled else None
        self.db.add(s)
        await self.db.flush()
        return self._dict(s)

    async def delete(self, actor: User, schedule_id: uuid.UUID) -> None:
        self._require_manager(actor)
        s = await self._get(actor, schedule_id)
        s.is_deleted = True
        self.db.add(s)
        await self.db.flush()

    async def preview_next_runs(self, actor: User, schedule_id: uuid.UUID, count: int = 5) -> list[str]:
        s = await self._get(actor, schedule_id)
        out, cursor = [], _now()
        for _ in range(min(count, 20)):
            nxt = self.compute_next_run(s, cursor)
            if not nxt:
                break
            out.append(nxt.isoformat())
            cursor = nxt
        return out

    # ================= execution =================
    async def run_now(self, actor: User, schedule_id: uuid.UUID) -> dict:
        self._require_manager(actor)
        s = await self._get(actor, schedule_id)
        run = await self._fire(s, triggered_by="manual", advance=False)
        return self._run_dict(run)

    async def run_due(self, org_id: uuid.UUID | None = None) -> int:
        """Scheduler tick: fire every active schedule whose next_run_at has passed."""
        q = select(Schedule).filter(Schedule.is_active == True, Schedule.is_deleted == False,
                                    Schedule.next_run_at.isnot(None), Schedule.next_run_at <= _now())
        if org_id is not None:
            q = q.filter(Schedule.organization_id == org_id)
        due = (await self.db.execute(q.limit(200))).scalars().all()
        fired = 0
        for s in due:
            await self._fire(s, triggered_by="schedule", advance=True)
            fired += 1
        return fired

    async def _fire(self, s: Schedule, *, triggered_by: str, advance: bool) -> ScheduleRun:
        now = _now()
        run = ScheduleRun(organization_id=s.organization_id, schedule_id=s.id, triggered_by=triggered_by,
                          scheduled_for=s.next_run_at, started_at=now, status="success")
        started = time.monotonic()

        # gating (only for scheduled fires, not manual run-now)
        skip_reason = None
        if triggered_by == "schedule":
            if s.skip_holidays and await self._is_holiday(s.organization_id, now):
                skip_reason = "holiday"
            elif s.business_hours_only and not await self._is_business_hours(s.organization_id, now):
                skip_reason = "outside_business_hours"

        if skip_reason:
            run.status = "skipped"
            run.reason = skip_reason
            s.skip_count = (s.skip_count or 0) + 1
        else:
            attempts, error, result = 0, None, None
            for attempts in range(1, max(1, s.max_retries) + 1):
                try:
                    result = await self._execute_task(s)
                    error = None
                    break
                except Exception as e:
                    error = f"{type(e).__name__}: {e}"
            run.attempts = attempts
            run.error = error
            run.result = result if isinstance(result, dict) else ({"result": result} if result is not None else None)
            run.status = "failed" if error else "success"
            s.run_count = (s.run_count or 0) + 1
            if error:
                s.fail_count = (s.fail_count or 0) + 1

        run.finished_at = _now()
        run.duration_ms = int((time.monotonic() - started) * 1000)
        s.last_run_at = run.finished_at
        s.last_status = run.status
        if advance:
            s.next_run_at = self.compute_next_run(s, now)
        self.db.add(run)
        self.db.add(s)
        await self.db.flush()
        return run

    async def _execute_task(self, s: Schedule) -> dict:
        cfg = s.task_config or {}
        tt = s.task_type
        if tt == "noop":
            return {"ok": True}
        if tt == "run_automation_job":
            from app.services.automation_service import run_tracked
            run = await run_tracked(self.db, s.organization_id, cfg.get("job_key") or "sla_scan",
                                    triggered_by="schedule")
            return {"automation_run": str(run.id), "status": run.status, "items": run.items_processed}
        if tt == "enqueue_queue_job":
            from app.services.queue_service import QueueService
            job = await QueueService(self.db).enqueue(
                organization_id=s.organization_id, job_type=cfg.get("job_type") or "noop",
                payload=cfg.get("payload"), queue=cfg.get("queue"), priority=int(cfg.get("priority", 5)),
                max_attempts=int(cfg.get("max_attempts", 3)))
            return {"queued_job": str(job.id), "queue": job.queue}
        if tt == "run_report":
            from app.services.queue_service import QueueService
            job = await QueueService(self.db).enqueue(
                organization_id=s.organization_id, job_type="generate_report",
                payload={"report_type": cfg.get("report_type") or "lead_summary"})
            return {"report_job": str(job.id)}
        if tt == "event_publish":
            from app.services.event_bus import EventBus
            ev = await EventBus(self.db).publish(
                cfg.get("event_type") or "custom.scheduled", organization_id=s.organization_id,
                source="system", payload=cfg.get("payload") or {"schedule": s.name})
            return {"event": str(ev.id), "type": ev.event_type}
        if tt == "notification_digest":
            from app.services.notification_automation_service import NotificationAutomationService
            sent = await NotificationAutomationService(self.db).flush_digests(s.organization_id)
            return {"digests_sent": sent}
        if tt == "webhook":
            url = cfg.get("url")
            if not url:
                raise ValueError("webhook task requires task_config.url")
            import httpx
            async with httpx.AsyncClient(timeout=8.0) as client:
                resp = await client.post(url, json=cfg.get("payload") or {"schedule": s.name})
                if resp.status_code >= 400:
                    raise RuntimeError(f"webhook returned {resp.status_code}")
            return {"webhook": url, "status": resp.status_code}
        raise ValueError(f"Unknown task_type {tt}")

    # ================= history / monitoring =================
    async def runs(self, actor: User, schedule_id: uuid.UUID | None = None, status_filter: str | None = None,
                   limit: int = 50) -> list[dict]:
        q = select(ScheduleRun).filter(ScheduleRun.organization_id == actor.organization_id,
                                       ScheduleRun.is_deleted == False)
        if schedule_id:
            q = q.filter(ScheduleRun.schedule_id == schedule_id)
        if status_filter:
            q = q.filter(ScheduleRun.status == status_filter)
        q = q.order_by(ScheduleRun.started_at.desc()).limit(min(limit, 200))
        return [self._run_dict(r) for r in (await self.db.execute(q)).scalars().all()]

    async def report(self, actor: User) -> dict:
        org = actor.organization_id
        total = (await self.db.execute(select(func.count(Schedule.id)).filter(
            Schedule.organization_id == org, Schedule.is_deleted == False))).scalar() or 0
        active = (await self.db.execute(select(func.count(Schedule.id)).filter(
            Schedule.organization_id == org, Schedule.is_deleted == False, Schedule.is_active == True))).scalar() or 0
        runs = (await self.db.execute(select(func.count(ScheduleRun.id)).filter(
            ScheduleRun.organization_id == org, ScheduleRun.is_deleted == False))).scalar() or 0
        failed = (await self.db.execute(select(func.count(ScheduleRun.id)).filter(
            ScheduleRun.organization_id == org, ScheduleRun.is_deleted == False, ScheduleRun.status == "failed"))).scalar() or 0
        skipped = (await self.db.execute(select(func.count(ScheduleRun.id)).filter(
            ScheduleRun.organization_id == org, ScheduleRun.is_deleted == False, ScheduleRun.status == "skipped"))).scalar() or 0
        executed = runs - skipped
        return {"total": total, "active": active, "inactive": total - active, "runs": runs,
                "failed": failed, "skipped": skipped,
                "success_rate": round((executed - failed) / executed * 100, 1) if executed else 100.0}

    async def dashboard(self, actor: User) -> dict:
        rep = await self.report(actor)
        upcoming = (await self.db.execute(select(Schedule).filter(
            Schedule.organization_id == actor.organization_id, Schedule.is_deleted == False,
            Schedule.is_active == True, Schedule.next_run_at.isnot(None)
        ).order_by(Schedule.next_run_at.asc()).limit(5))).scalars().all()
        recent = await self.runs(actor, limit=5)
        return {"total": rep["total"], "active": rep["active"], "success_rate": rep["success_rate"],
                "failed": rep["failed"], "skipped": rep["skipped"],
                "upcoming": [{"id": str(s.id), "name": s.name,
                              "next_run_at": s.next_run_at.isoformat() if s.next_run_at else None} for s in upcoming],
                "recent": recent}

    # ---------- serialize ----------
    def _dict(self, s: Schedule) -> dict:
        return {"id": str(s.id), "name": s.name, "description": s.description, "task_type": s.task_type,
                "task_config": s.task_config, "schedule_kind": s.schedule_kind, "cron_expr": s.cron_expr,
                "time_of_day": s.time_of_day, "day_of_week": s.day_of_week, "day_of_month": s.day_of_month,
                "interval_minutes": s.interval_minutes, "timezone": s.timezone,
                "business_hours_only": s.business_hours_only, "skip_holidays": s.skip_holidays,
                "is_active": s.is_active, "max_retries": s.max_retries,
                "last_run_at": s.last_run_at.isoformat() if s.last_run_at else None,
                "last_status": s.last_status,
                "next_run_at": s.next_run_at.isoformat() if s.next_run_at else None,
                "run_count": s.run_count, "fail_count": s.fail_count, "skip_count": s.skip_count}

    def _run_dict(self, r: ScheduleRun) -> dict:
        return {"id": str(r.id), "schedule_id": str(r.schedule_id), "status": r.status, "reason": r.reason,
                "triggered_by": r.triggered_by, "attempts": r.attempts, "error": r.error, "result": r.result,
                "scheduled_for": r.scheduled_for.isoformat() if r.scheduled_for else None,
                "started_at": r.started_at.isoformat() if r.started_at else None,
                "finished_at": r.finished_at.isoformat() if r.finished_at else None,
                "duration_ms": r.duration_ms}
