"""Goal & OKR Management.

Objectives with weighted Key Results at company / department / team / individual
level, run in quarterly, annual or custom cycles. Progress is computed at read
time: metric-linked KRs reuse the department rollup (_metrics_for_members) over
the objective's scope, manual KRs use their checked-in current_value. Check-ins,
periodic reviews and manager feedback are recorded as OKRReview rows. Completion
and at-risk states notify owners and fire okr_* workflow triggers (which fan out
to the Event Bus). The existing PerformanceGoal / TeamTarget / DepartmentTarget
stores and the Target Management aggregator are untouched.
"""
from __future__ import annotations
import uuid
from datetime import date, datetime, timezone
from fastapi import HTTPException, status
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User
from app.models.okr import Objective, KeyResult, OKRReview
from app.services.notification_service import NotificationService

LEVELS = ("company", "department", "team", "individual")
CYCLE_TYPES = ("quarterly", "annual", "custom")
OKR_METRICS = ("leads_converted", "calls_made", "tasks_completed", "revenue", "activities")
KR_KINDS = ("manual", "metric")
UNITS = ("count", "percent", "currency")
REVIEW_TYPES = ("checkin", "review", "feedback")
OBJECTIVE_STATUSES = ("draft", "active", "completed", "cancelled")


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _num(v) -> float:
    try:
        return float(v)
    except (TypeError, ValueError):
        return 0.0


def _cycle_window(cycle_type: str, year: int, quarter: int | None) -> tuple[date, date]:
    import calendar as _cal
    if cycle_type == "quarterly":
        q = quarter or ((date.today().month - 1) // 3 + 1)
        sm, em = (q - 1) * 3 + 1, (q - 1) * 3 + 3
        return date(year, sm, 1), date(year, em, _cal.monthrange(year, em)[1])
    return date(year, 1, 1), date(year, 12, 31)


def _kr_pct(start: float, target: float, current: float) -> float:
    """Progress of a KR from start_value toward target_value (works for both
    increase and decrease directions), clamped to 0..100."""
    if target == start:
        return 100.0 if ((target >= start and current >= target) or (target < start and current <= target)) else 0.0
    pct = (current - start) * 100.0 / (target - start)
    return round(min(100.0, max(0.0, pct)), 1)


def _pace_label(progress: float, start: date, end: date, obj_status: str, today: date | None = None) -> str:
    today = today or date.today()
    if obj_status == "completed" or progress >= 100:
        return "achieved"
    if obj_status in ("draft", "cancelled"):
        return obj_status
    if today > end:
        return "missed"
    span = max(1, (end - start).days + 1)
    elapsed = min(span, max(0, (today - start).days + 1))
    expected = 100.0 * elapsed / span
    return "on_track" if progress >= expected * 0.7 else "at_risk"


class _OKREvent:
    """Lightweight (non-ORM) entity for the workflow engine's okr_* rules."""
    def __init__(self, organization_id, obj_id, user_id, level, cycle_type, progress):
        self.organization_id = organization_id
        self.id = obj_id
        self.user_id = user_id
        self.level = level
        self.cycle_type = cycle_type
        self.progress = progress


class OKRService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.notifier = NotificationService(db)

    # ---------- permissions & scope ----------
    def _is_manager(self, actor: User) -> bool:
        return actor.role in ("SuperAdmin", "OrgAdmin", "Manager")

    def _require_manager(self, actor: User):
        if not self._is_manager(actor):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN,
                                detail="Only managers and admins can do this.")

    async def _actor_team_ids(self, actor: User) -> set:
        from app.models.team import TeamMember
        rows = (await self.db.execute(select(TeamMember.team_id).filter(
            TeamMember.user_id == actor.id, TeamMember.is_deleted == False))).scalars().all()
        return set(rows)

    async def _can_see(self, actor: User, o: Objective) -> bool:
        if self._is_manager(actor):
            return True
        if o.level == "company":
            return True
        if o.owner_id == actor.id or o.user_id == actor.id or o.created_by == actor.id:
            return True
        if o.level == "department" and actor.department_id and o.department_id == actor.department_id:
            return True
        if o.level == "team" and o.team_id in await self._actor_team_ids(actor):
            return True
        return False

    def _can_edit(self, actor: User, o: Objective) -> bool:
        return self._is_manager(actor) or o.owner_id == actor.id or o.created_by == actor.id

    # ---------- meta ----------
    def meta(self) -> dict:
        return {"levels": list(LEVELS), "cycle_types": list(CYCLE_TYPES), "metrics": list(OKR_METRICS),
                "kr_kinds": list(KR_KINDS), "units": list(UNITS), "review_types": list(REVIEW_TYPES),
                "statuses": list(OBJECTIVE_STATUSES)}

    # ---------- live KR values (reuses the department metric rollup) ----------
    async def _scope_member_ids(self, o: Objective) -> list:
        from app.services.department_service import DepartmentService
        from app.services.team_service import TeamService
        if o.level == "individual":
            return [o.user_id] if o.user_id else []
        if o.level == "team" and o.team_id:
            return await TeamService(self.db)._member_ids(o.team_id)
        if o.level == "department" and o.department_id:
            return await DepartmentService(self.db)._member_ids(o.organization_id, o.department_id)
        # company: every org user
        return list((await self.db.execute(select(User.id).filter(
            User.organization_id == o.organization_id, User.is_deleted == False))).scalars().all())

    async def _scope_metrics(self, o: Objective) -> dict:
        from app.services.department_service import DepartmentService
        members = await self._scope_member_ids(o)
        start = datetime(o.start_date.year, o.start_date.month, o.start_date.day, tzinfo=timezone.utc)
        end = datetime(o.end_date.year, o.end_date.month, o.end_date.day, 23, 59, 59, tzinfo=timezone.utc)
        return await DepartmentService(self.db)._metrics_for_members(o.organization_id, members, start, end)

    def _kr_row(self, kr: KeyResult, metrics: dict | None) -> dict:
        if kr.kind == "metric" and kr.metric and metrics is not None:
            current = _num(metrics.get(kr.metric, 0))
        else:
            current = _num(kr.current_value)
        pct = _kr_pct(_num(kr.start_value), _num(kr.target_value), current)
        return {"id": str(kr.id), "title": kr.title, "kind": kr.kind, "metric": kr.metric, "unit": kr.unit,
                "start_value": _num(kr.start_value), "target_value": _num(kr.target_value),
                "current_value": current, "weight": _num(kr.weight), "progress": pct, "status": kr.status,
                "last_checkin_at": kr.last_checkin_at.isoformat() if kr.last_checkin_at else None}

    async def _payload(self, o: Objective, krs: list[KeyResult], names: dict | None = None) -> dict:
        metrics = None
        if any(k.kind == "metric" for k in krs):
            try:
                metrics = await self._scope_metrics(o)
            except Exception:
                metrics = {}
        rows = [self._kr_row(k, metrics) for k in krs]
        wsum = sum(r["weight"] for r in rows)
        progress = round(sum(r["progress"] * r["weight"] for r in rows) / wsum, 1) if wsum else 0.0
        names = names or {}
        return {"id": str(o.id), "title": o.title, "description": o.description, "level": o.level,
                "department_id": str(o.department_id) if o.department_id else None,
                "team_id": str(o.team_id) if o.team_id else None,
                "user_id": str(o.user_id) if o.user_id else None,
                "owner_id": str(o.owner_id), "owner_name": names.get(o.owner_id),
                "parent_id": str(o.parent_id) if o.parent_id else None,
                "cycle_type": o.cycle_type, "cycle_year": o.cycle_year, "cycle_quarter": o.cycle_quarter,
                "cycle_label": (f"Q{o.cycle_quarter} {o.cycle_year}" if o.cycle_type == "quarterly"
                                else str(o.cycle_year) if o.cycle_type == "annual"
                                else f"{o.start_date.isoformat()} → {o.end_date.isoformat()}"),
                "start_date": o.start_date.isoformat(), "end_date": o.end_date.isoformat(),
                "status": o.status, "progress": progress,
                "status_label": _pace_label(progress, o.start_date, o.end_date, o.status),
                "key_results": rows, "created_at": o.created_at.isoformat() if o.created_at else None}

    async def _names(self, ids: set) -> dict:
        ids = {i for i in ids if i}
        if not ids:
            return {}
        rows = (await self.db.execute(select(User).filter(User.id.in_(list(ids))))).scalars().all()
        return {u.id: f"{u.first_name} {u.last_name}".strip() for u in rows}

    # ---------- CRUD: objectives ----------
    def _validate_kr(self, data: dict):
        kind = data.get("kind") or "manual"
        if kind not in KR_KINDS:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"kind must be one of {list(KR_KINDS)}")
        if kind == "metric" and data.get("metric") not in OKR_METRICS:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST,
                                detail=f"metric KRs need a metric from {list(OKR_METRICS)}")
        if data.get("unit") and data["unit"] not in UNITS:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"unit must be one of {list(UNITS)}")

    async def create_objective(self, actor: User, data: dict) -> dict:
        level = data.get("level")
        if level not in LEVELS:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"level must be one of {list(LEVELS)}")
        if level != "individual":
            self._require_manager(actor)
        cycle_type = data.get("cycle_type") or "quarterly"
        if cycle_type not in CYCLE_TYPES:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"cycle_type must be one of {list(CYCLE_TYPES)}")
        if level == "department" and not data.get("department_id"):
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="department objectives need department_id.")
        if level == "team" and not data.get("team_id"):
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="team objectives need team_id.")
        if level == "individual" and not data.get("user_id"):
            data["user_id"] = actor.id
        year = int(data.get("cycle_year") or date.today().year)
        quarter = data.get("cycle_quarter")
        if cycle_type == "custom":
            if not data.get("start_date") or not data.get("end_date"):
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="custom cycles need start_date and end_date.")
            start, end = date.fromisoformat(str(data["start_date"])), date.fromisoformat(str(data["end_date"]))
        else:
            start, end = _cycle_window(cycle_type, year, quarter)
            quarter = quarter if cycle_type == "quarterly" else None
            if cycle_type == "quarterly" and not data.get("cycle_quarter"):
                quarter = (date.today().month - 1) // 3 + 1
        if end < start:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="end_date must be after start_date.")
        if data.get("parent_id"):
            parent = await self._get(actor, uuid.UUID(str(data["parent_id"])))
            if parent.id == data.get("id"):
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="An objective cannot align to itself.")
        owner_id = data.get("owner_id") or (data.get("user_id") if level == "individual" else None) or actor.id
        o = Objective(organization_id=actor.organization_id, title=data["title"], description=data.get("description"),
                      level=level, department_id=data.get("department_id"), team_id=data.get("team_id"),
                      user_id=data.get("user_id") if level == "individual" else None,
                      owner_id=owner_id, parent_id=data.get("parent_id"), cycle_type=cycle_type,
                      cycle_year=year, cycle_quarter=quarter, start_date=start, end_date=end,
                      status=data.get("status") or "active", created_by=actor.id)
        self.db.add(o)
        await self.db.flush()
        krs: list[KeyResult] = []
        for kr in (data.get("key_results") or []):
            krs.append(await self._add_kr(actor, o, kr))
        if o.owner_id != actor.id:
            await self._notify(o.organization_id, o.owner_id, "New objective assigned to you",
                               f'You are the owner of "{o.title}" ({o.cycle_type}, ends {o.end_date.isoformat()}).')
        return await self._payload(o, krs, await self._names({o.owner_id}))

    async def _get(self, actor: User, objective_id: uuid.UUID) -> Objective:
        o = (await self.db.execute(select(Objective).filter(
            Objective.id == objective_id, Objective.organization_id == actor.organization_id,
            Objective.is_deleted == False))).scalars().first()
        if not o:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Objective not found")
        return o

    async def _krs(self, objective_id: uuid.UUID) -> list[KeyResult]:
        return list((await self.db.execute(select(KeyResult).filter(
            KeyResult.objective_id == objective_id, KeyResult.is_deleted == False)
            .order_by(KeyResult.created_at.asc()))).scalars().all())

    async def update_objective(self, actor: User, objective_id: uuid.UUID, data: dict) -> dict:
        o = await self._get(actor, objective_id)
        if not self._can_edit(actor, o):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="You cannot edit this objective.")
        if data.get("status") and data["status"] not in OBJECTIVE_STATUSES:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"status must be one of {list(OBJECTIVE_STATUSES)}")
        if data.get("parent_id"):
            pid = uuid.UUID(str(data["parent_id"]))
            if pid == o.id:
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="An objective cannot align to itself.")
            await self._get(actor, pid)
        for f in ("title", "description", "owner_id", "parent_id", "status"):
            if f in data and data[f] is not None:
                setattr(o, f, data[f])
        for f in ("start_date", "end_date"):
            if data.get(f):
                setattr(o, f, date.fromisoformat(str(data[f])))
        self.db.add(o)
        await self.db.flush()
        return await self._payload(o, await self._krs(o.id), await self._names({o.owner_id}))

    async def delete_objective(self, actor: User, objective_id: uuid.UUID) -> None:
        o = await self._get(actor, objective_id)
        if not self._can_edit(actor, o):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="You cannot delete this objective.")
        o.is_deleted = True
        self.db.add(o)
        await self.db.flush()

    # ---------- CRUD: key results ----------
    async def _add_kr(self, actor: User, o: Objective, data: dict) -> KeyResult:
        self._validate_kr(data)
        kr = KeyResult(organization_id=o.organization_id, objective_id=o.id, title=data["title"],
                       kind=data.get("kind") or "manual", metric=data.get("metric"),
                       unit=data.get("unit") or ("currency" if data.get("metric") == "revenue" else "count"),
                       start_value=data.get("start_value") or 0, target_value=data["target_value"],
                       current_value=data.get("current_value") if data.get("current_value") is not None else (data.get("start_value") or 0),
                       weight=data.get("weight") or 1, created_by=actor.id)
        self.db.add(kr)
        await self.db.flush()
        return kr

    async def add_key_result(self, actor: User, objective_id: uuid.UUID, data: dict) -> dict:
        o = await self._get(actor, objective_id)
        if not self._can_edit(actor, o):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="You cannot edit this objective.")
        await self._add_kr(actor, o, data)
        return await self._payload(o, await self._krs(o.id), await self._names({o.owner_id}))

    async def _get_kr(self, actor: User, kr_id: uuid.UUID) -> tuple[KeyResult, Objective]:
        kr = (await self.db.execute(select(KeyResult).filter(
            KeyResult.id == kr_id, KeyResult.organization_id == actor.organization_id,
            KeyResult.is_deleted == False))).scalars().first()
        if not kr:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Key result not found")
        return kr, await self._get(actor, kr.objective_id)

    async def update_key_result(self, actor: User, kr_id: uuid.UUID, data: dict) -> dict:
        kr, o = await self._get_kr(actor, kr_id)
        if not self._can_edit(actor, o):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="You cannot edit this objective.")
        if data.get("kind") or data.get("metric") or data.get("unit"):
            self._validate_kr({"kind": data.get("kind") or kr.kind, "metric": data.get("metric", kr.metric),
                               "unit": data.get("unit")})
        for f in ("title", "kind", "metric", "unit", "start_value", "target_value", "current_value", "weight", "status"):
            if f in data and data[f] is not None:
                setattr(kr, f, data[f])
        self.db.add(kr)
        await self.db.flush()
        return await self._payload(o, await self._krs(o.id), await self._names({o.owner_id}))

    async def delete_key_result(self, actor: User, kr_id: uuid.UUID) -> dict:
        kr, o = await self._get_kr(actor, kr_id)
        if not self._can_edit(actor, o):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="You cannot edit this objective.")
        kr.is_deleted = True
        self.db.add(kr)
        await self.db.flush()
        return await self._payload(o, await self._krs(o.id), await self._names({o.owner_id}))

    # ---------- check-ins ----------
    async def checkin(self, actor: User, kr_id: uuid.UUID, data: dict) -> dict:
        kr, o = await self._get_kr(actor, kr_id)
        if not (self._can_edit(actor, o) or o.user_id == actor.id):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="You cannot check in on this key result.")
        if kr.kind == "metric":
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST,
                                detail="Metric-linked key results update automatically; check-ins are for manual KRs.")
        kr.current_value = data["value"]
        kr.last_checkin_at = _now()
        pct = _kr_pct(_num(kr.start_value), _num(kr.target_value), _num(kr.current_value))
        if pct >= 100:
            kr.status = "completed"
        self.db.add(kr)
        await self.db.flush()
        payload = await self._payload(o, await self._krs(o.id), await self._names({o.owner_id}))
        self.db.add(OKRReview(organization_id=o.organization_id, objective_id=o.id, key_result_id=kr.id,
                              reviewer_id=actor.id, review_type="checkin", confidence=data.get("confidence"),
                              comment=data.get("comment"), progress_at=payload["progress"]))
        await self.db.flush()
        if payload["progress"] >= 100 and o.status == "active":
            await self._complete(actor, o, payload["progress"])
            payload["status"] = o.status
            payload["status_label"] = "achieved"
        return payload

    async def _complete(self, actor: User, o: Objective, progress: float):
        o.status = "completed"
        self.db.add(o)
        await self.db.flush()
        await self._notify(o.organization_id, o.owner_id, "Objective completed 🎯",
                           f'"{o.title}" reached 100% of its key results.')
        from app.services.workflow_service import WorkflowService
        ent = _OKREvent(o.organization_id, o.id, o.owner_id, o.level, o.cycle_type, progress)
        await WorkflowService(self.db).run("okr_objective_completed", ent, actor, entity_type="okr")

    # ---------- reviews & manager feedback ----------
    async def add_review(self, actor: User, objective_id: uuid.UUID, data: dict) -> dict:
        o = await self._get(actor, objective_id)
        if not await self._can_see(actor, o):
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Objective not found")
        rtype = data.get("review_type") or "review"
        if rtype not in ("review", "feedback"):
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="review_type must be review or feedback.")
        if rtype == "feedback":
            self._require_manager(actor)
        payload = await self._payload(o, await self._krs(o.id))
        r = OKRReview(organization_id=o.organization_id, objective_id=o.id, reviewer_id=actor.id,
                      review_type=rtype, rating=data.get("rating"), comment=data.get("comment"),
                      progress_at=payload["progress"])
        self.db.add(r)
        await self.db.flush()
        if o.owner_id != actor.id:
            label = "Manager feedback" if rtype == "feedback" else "New review"
            await self._notify(o.organization_id, o.owner_id, f'{label} on "{o.title}"',
                               (data.get("comment") or "")[:200])
        return self._review_row(r, await self._names({r.reviewer_id}))

    async def list_reviews(self, actor: User, objective_id: uuid.UUID) -> list[dict]:
        o = await self._get(actor, objective_id)
        if not await self._can_see(actor, o):
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Objective not found")
        rows = list((await self.db.execute(select(OKRReview).filter(
            OKRReview.objective_id == o.id, OKRReview.is_deleted == False)
            .order_by(OKRReview.created_at.desc()))).scalars().all())
        names = await self._names({r.reviewer_id for r in rows})
        return [self._review_row(r, names) for r in rows]

    def _review_row(self, r: OKRReview, names: dict) -> dict:
        return {"id": str(r.id), "objective_id": str(r.objective_id),
                "key_result_id": str(r.key_result_id) if r.key_result_id else None,
                "reviewer_id": str(r.reviewer_id), "reviewer_name": names.get(r.reviewer_id),
                "review_type": r.review_type, "rating": r.rating, "confidence": r.confidence,
                "comment": r.comment, "progress_at": _num(r.progress_at) if r.progress_at is not None else None,
                "created_at": r.created_at.isoformat() if r.created_at else None}

    # ---------- listing / tree / detail ----------
    async def list_objectives(self, actor: User, level=None, status_filter=None, cycle_year=None,
                              cycle_quarter=None, user_id=None) -> list[dict]:
        q = select(Objective).filter(Objective.organization_id == actor.organization_id,
                                     Objective.is_deleted == False)
        if level:
            q = q.filter(Objective.level == level)
        if status_filter:
            q = q.filter(Objective.status == status_filter)
        if cycle_year:
            q = q.filter(Objective.cycle_year == int(cycle_year))
        if cycle_quarter:
            q = q.filter(Objective.cycle_quarter == int(cycle_quarter))
        if user_id:
            q = q.filter(Objective.user_id == user_id)
        objs = list((await self.db.execute(q.order_by(Objective.created_at.desc()))).scalars().all())
        visible = [o for o in objs if await self._can_see(actor, o)]
        names = await self._names({o.owner_id for o in visible})
        out = []
        for o in visible:
            out.append(await self._payload(o, await self._krs(o.id), names))
        return out

    async def get_objective(self, actor: User, objective_id: uuid.UUID) -> dict:
        o = await self._get(actor, objective_id)
        if not await self._can_see(actor, o):
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Objective not found")
        payload = await self._payload(o, await self._krs(o.id), await self._names({o.owner_id}))
        payload["reviews"] = await self.list_reviews(actor, o.id)
        return payload

    async def tree(self, actor: User, cycle_year=None) -> list[dict]:
        """Alignment tree: company objectives at the root, children nested via parent_id."""
        rows = await self.list_objectives(actor, cycle_year=cycle_year)
        by_id = {r["id"]: {**r, "children": []} for r in rows}
        roots = []
        for r in by_id.values():
            parent = by_id.get(r["parent_id"]) if r["parent_id"] else None
            (parent["children"] if parent else roots).append(r)
        roots.sort(key=lambda r: (r["level"] != "company", -r["progress"]))
        return roots

    # ---------- dashboard & report ----------
    async def dashboard(self, actor: User) -> dict:
        rows = await self.list_objectives(actor)
        active = [r for r in rows if r["status"] in ("active", "completed")]
        total = len(active)
        by_label: dict[str, int] = {}
        by_level: dict[str, int] = {}
        for r in active:
            by_label[r["status_label"]] = by_label.get(r["status_label"], 0) + 1
            by_level[r["level"]] = by_level.get(r["level"], 0) + 1
        avg_progress = round(sum(r["progress"] for r in active) / total, 1) if total else 0.0
        reviews = (await self.db.execute(select(func.count(OKRReview.id)).filter(
            OKRReview.organization_id == actor.organization_id, OKRReview.is_deleted == False))).scalar() or 0
        return {"total": total, "achieved": by_label.get("achieved", 0), "on_track": by_label.get("on_track", 0),
                "at_risk": by_label.get("at_risk", 0), "missed": by_label.get("missed", 0),
                "avg_progress": avg_progress, "by_level": by_level, "reviews": reviews,
                "at_risk_objectives": [r for r in active if r["status_label"] == "at_risk"][:5]}

    async def report(self, actor: User, level=None, cycle_year=None, cycle_quarter=None) -> dict:
        rows = await self.list_objectives(actor, level=level, cycle_year=cycle_year, cycle_quarter=cycle_quarter)
        by_level: dict[str, dict] = {}
        for r in rows:
            b = by_level.setdefault(r["level"], {"level": r["level"], "count": 0, "achieved": 0, "at_risk": 0,
                                                 "progress_sum": 0.0})
            b["count"] += 1
            b["progress_sum"] += r["progress"]
            if r["status_label"] == "achieved":
                b["achieved"] += 1
            if r["status_label"] == "at_risk":
                b["at_risk"] += 1
        summary = [{**b, "avg_progress": round(b.pop("progress_sum") / b["count"], 1)} for b in by_level.values()]
        return {"rows": rows, "count": len(rows), "by_level": summary}

    # ---------- cron scan ----------
    async def scan(self, org_id: uuid.UUID) -> dict:
        """Daily cycle: auto-complete achieved objectives, and nudge owners of
        at-risk objectives as the cycle end approaches (7/3/1 days out, so the
        daily cron doesn't spam)."""
        actor = (await self.db.execute(select(User).filter(
            User.organization_id == org_id, User.is_deleted == False,
            User.role.in_(["OrgAdmin", "SuperAdmin"])).limit(1))).scalars().first()
        if not actor:
            return {"completed": 0, "nudged": 0}
        objs = list((await self.db.execute(select(Objective).filter(
            Objective.organization_id == org_id, Objective.is_deleted == False,
            Objective.status == "active"))).scalars().all())
        completed = nudged = 0
        today = date.today()
        for o in objs:
            payload = await self._payload(o, await self._krs(o.id))
            if payload["progress"] >= 100:
                await self._complete(actor, o, payload["progress"])
                completed += 1
                continue
            days_left = (o.end_date - today).days
            if payload["status_label"] == "at_risk" and days_left in (7, 3, 1):
                await self._notify(org_id, o.owner_id, f"Objective at risk: {o.title}",
                                   f'{payload["progress"]}% done with {days_left} day(s) left in the cycle.')
                from app.services.workflow_service import WorkflowService
                ent = _OKREvent(org_id, o.id, o.owner_id, o.level, o.cycle_type, payload["progress"])
                await WorkflowService(self.db).run("okr_objective_at_risk", ent, actor, entity_type="okr")
                nudged += 1
        return {"completed": completed, "nudged": nudged}

    async def scan_for(self, actor: User) -> dict:
        self._require_manager(actor)
        return await self.scan(actor.organization_id)

    # ---------- notify ----------
    async def _notify(self, org_id, user_id, title: str, body: str):
        try:
            await self.notifier.create_notification(
                organization_id=org_id, user_id=user_id, category="okr", title=title, body=body,
                link_url="/okr", priority="normal")
        except Exception:
            pass
