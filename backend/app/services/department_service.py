"""Department Management service.

Reuses the existing User architecture: members are Users carrying department_id
(nullable, backward compatible), heads are Users, and performance/KPIs roll up
member activity from Leads/Tasks/Activities. Departments form a self-referential
hierarchy independent of the reporting chain.
"""
from __future__ import annotations
import csv
import io
import uuid
from decimal import Decimal
from datetime import datetime, timezone
from fastapi import HTTPException, status
from sqlalchemy import select, func, or_
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User
from app.models.lead import Lead
from app.models.task import Task
from app.models.activity import Activity
from app.models.department import Department, DepartmentTarget
from app.services.audit_service import AuditService
from app.services.notification_service import NotificationService

METRICS = ("leads_converted", "calls_made", "tasks_completed", "revenue", "activities", "custom")
CONVERTED_LEAD_STATUSES = {"Won", "Converted", "Customer"}


def _now() -> datetime:
    return datetime.now(timezone.utc)


class DepartmentService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.audit = AuditService(db)
        self.notifier = NotificationService(db)

    def _can_manage(self, actor: User) -> bool:
        return actor.role in ("SuperAdmin", "OrgAdmin")

    def _require_manage(self, actor: User):
        if not self._can_manage(actor):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN,
                                detail="Only an OrgAdmin can manage departments.")

    # ---------- CRUD ----------
    async def _get(self, actor: User, department_id: uuid.UUID) -> Department:
        d = (await self.db.execute(select(Department).filter(
            Department.id == department_id, Department.organization_id == actor.organization_id,
            Department.is_deleted == False))).scalars().first()
        if not d:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Department not found")
        return d

    async def get(self, actor: User, department_id: uuid.UUID) -> dict:
        return await self._serialize(await self._get(actor, department_id))

    async def _validate_code(self, actor: User, code: str | None, exclude_id=None):
        if not code:
            return
        q = select(Department.id).filter(
            Department.organization_id == actor.organization_id, Department.code == code,
            Department.is_deleted == False)
        if exclude_id:
            q = q.filter(Department.id != exclude_id)
        if (await self.db.execute(q)).scalar():
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=f"Department code '{code}' already exists.")

    async def _validate_head(self, actor: User, head_user_id):
        if head_user_id:
            u = (await self.db.execute(select(User).filter(
                User.id == head_user_id, User.organization_id == actor.organization_id,
                User.is_deleted == False))).scalars().first()
            if not u:
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Head user not found in this org.")

    async def _validate_parent(self, actor: User, parent_id, self_id=None):
        """Ensure parent exists and adding it won't create a cycle."""
        if not parent_id:
            return
        if self_id and parent_id == self_id:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="A department cannot be its own parent.")
        # walk up the parent chain from the proposed parent
        seen = set()
        cur = parent_id
        while cur:
            if self_id and cur == self_id:
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Circular department hierarchy is not allowed.")
            if cur in seen:
                break
            seen.add(cur)
            row = (await self.db.execute(select(Department.parent_department_id).filter(
                Department.id == cur, Department.organization_id == actor.organization_id,
                Department.is_deleted == False))).first()
            if not row:
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Parent department not found.")
            cur = row[0]

    async def create(self, actor: User, data: dict) -> dict:
        self._require_manage(actor)
        await self._validate_code(actor, data.get("code"))
        await self._validate_head(actor, data.get("head_user_id"))
        await self._validate_parent(actor, data.get("parent_department_id"))
        d = Department(
            organization_id=actor.organization_id, name=data["name"], code=data.get("code"),
            description=data.get("description"), parent_department_id=data.get("parent_department_id"),
            head_user_id=data.get("head_user_id"), status=data.get("status", "active"),
            budget=Decimal(str(data["budget"])) if data.get("budget") is not None else None,
            budget_period=data.get("budget_period"), cost_center=data.get("cost_center"),
            color=data.get("color"), created_by=actor.id)
        self.db.add(d)
        await self.db.flush()
        await self.db.refresh(d)
        await self.audit.log_event(organization_id=actor.organization_id, actor_user_id=actor.id,
                                   action="DEPARTMENT_CREATED", resource_type="department", resource_id=str(d.id),
                                   action_metadata={"name": d.name})
        return await self._serialize(d)

    async def update(self, actor: User, department_id: uuid.UUID, data: dict) -> dict:
        self._require_manage(actor)
        d = await self._get(actor, department_id)
        if "code" in data:
            await self._validate_code(actor, data.get("code"), exclude_id=d.id)
        if "head_user_id" in data:
            await self._validate_head(actor, data.get("head_user_id"))
        if "parent_department_id" in data and data["parent_department_id"]:
            await self._validate_parent(actor, data["parent_department_id"], self_id=d.id)
        for k in ("name", "code", "description", "parent_department_id", "head_user_id", "status",
                  "budget_period", "cost_center", "color"):
            if k in data:
                setattr(d, k, data[k])
        if "budget" in data:
            d.budget = Decimal(str(data["budget"])) if data["budget"] is not None else None
        self.db.add(d)
        await self.db.flush()
        await self.db.refresh(d)
        return await self._serialize(d)

    async def set_status(self, actor: User, department_id: uuid.UUID, new_status: str) -> dict:
        self._require_manage(actor)
        if new_status not in ("active", "archived"):
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="status must be active or archived.")
        d = await self._get(actor, department_id)
        d.status = new_status
        self.db.add(d)
        await self.db.flush()
        await self.db.refresh(d)
        return await self._serialize(d)

    async def delete(self, actor: User, department_id: uuid.UUID) -> None:
        self._require_manage(actor)
        d = await self._get(actor, department_id)
        # Block deletion while members or sub-departments still reference it.
        member_count = (await self.db.execute(select(func.count(User.id)).filter(
            User.department_id == d.id, User.is_deleted == False))).scalar() or 0
        child_count = (await self.db.execute(select(func.count(Department.id)).filter(
            Department.parent_department_id == d.id, Department.is_deleted == False))).scalar() or 0
        if member_count or child_count:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT,
                                detail=f"Reassign {member_count} member(s) and {child_count} sub-department(s) first.")
        d.is_deleted = True
        self.db.add(d)
        await self.db.flush()

    # ---------- List / search / filter ----------
    async def list(self, actor: User, search=None, status_filter=None, parent_id=None,
                   skip=0, limit=100) -> dict:
        q = select(Department).filter(
            Department.organization_id == actor.organization_id, Department.is_deleted == False)
        if status_filter:
            q = q.filter(Department.status == status_filter)
        if parent_id:
            q = q.filter(Department.parent_department_id == parent_id)
        if search:
            s = f"%{search}%"
            q = q.filter(or_(Department.name.ilike(s), Department.code.ilike(s), Department.description.ilike(s)))
        total = (await self.db.execute(select(func.count()).select_from(q.subquery()))).scalar() or 0
        rows = list((await self.db.execute(q.order_by(Department.name.asc()).offset(skip).limit(limit))).scalars().all())
        items = [await self._serialize(d) for d in rows]
        return {"items": items, "total": total}

    async def tree(self, actor: User) -> list[dict]:
        rows = list((await self.db.execute(select(Department).filter(
            Department.organization_id == actor.organization_id, Department.is_deleted == False)
            .order_by(Department.name.asc()))).scalars().all())
        counts = await self._member_counts(actor)
        nodes = {d.id: {"id": str(d.id), "name": d.name, "code": d.code, "status": d.status,
                        "head_user_id": str(d.head_user_id) if d.head_user_id else None,
                        "member_count": counts.get(d.id, 0), "children": []} for d in rows}
        roots = []
        for d in rows:
            node = nodes[d.id]
            if d.parent_department_id and d.parent_department_id in nodes:
                nodes[d.parent_department_id]["children"].append(node)
            else:
                roots.append(node)
        return roots

    # ---------- Members ----------
    async def _member_counts(self, actor: User) -> dict:
        rows = (await self.db.execute(select(User.department_id, func.count(User.id)).filter(
            User.organization_id == actor.organization_id, User.is_deleted == False,
            User.department_id.isnot(None)).group_by(User.department_id))).all()
        return {did: n for did, n in rows}

    async def members(self, actor: User, department_id: uuid.UUID) -> list[dict]:
        await self._get(actor, department_id)
        rows = list((await self.db.execute(select(User).filter(
            User.department_id == department_id, User.organization_id == actor.organization_id,
            User.is_deleted == False).order_by(User.first_name.asc()))).scalars().all())
        return [{"id": str(u.id), "name": f"{u.first_name or ''} {u.last_name or ''}".strip() or u.email,
                 "email": u.email, "role": u.role, "is_active": u.is_active} for u in rows]

    async def assign_members(self, actor: User, department_id: uuid.UUID, user_ids: list[uuid.UUID]) -> dict:
        self._require_manage(actor)
        d = await self._get(actor, department_id)
        users = list((await self.db.execute(select(User).filter(
            User.id.in_(user_ids), User.organization_id == actor.organization_id, User.is_deleted == False))).scalars().all())
        for u in users:
            u.department_id = d.id
            self.db.add(u)
        await self.db.flush()
        # notify the head that members joined
        if d.head_user_id and users:
            await self.notifier.create_notification(
                organization_id=actor.organization_id, user_id=d.head_user_id, category="department",
                title="Department members added", body=f"{len(users)} member(s) added to {d.name}.",
                link_url=f"/departments?departmentId={d.id}", priority="normal",
                action_metadata={"department_id": str(d.id)})
        return {"assigned": len(users)}

    async def remove_members(self, actor: User, department_id: uuid.UUID, user_ids: list[uuid.UUID]) -> dict:
        self._require_manage(actor)
        d = await self._get(actor, department_id)
        users = list((await self.db.execute(select(User).filter(
            User.id.in_(user_ids), User.department_id == d.id,
            User.organization_id == actor.organization_id))).scalars().all())
        for u in users:
            u.department_id = None
            self.db.add(u)
        await self.db.flush()
        return {"removed": len(users)}

    async def _member_ids(self, org_id, department_id) -> list[uuid.UUID]:
        return list((await self.db.execute(select(User.id).filter(
            User.department_id == department_id, User.organization_id == org_id,
            User.is_deleted == False))).scalars().all())

    # ---------- Targets ----------
    async def list_targets(self, actor: User, department_id: uuid.UUID) -> list[DepartmentTarget]:
        await self._get(actor, department_id)
        return list((await self.db.execute(select(DepartmentTarget).filter(
            DepartmentTarget.department_id == department_id, DepartmentTarget.is_deleted == False)
            .order_by(DepartmentTarget.created_at.desc()))).scalars().all())

    async def create_target(self, actor: User, department_id: uuid.UUID, data: dict) -> DepartmentTarget:
        self._require_manage(actor)
        await self._get(actor, department_id)
        if data["metric"] not in METRICS:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"metric must be one of {list(METRICS)}")
        t = DepartmentTarget(organization_id=actor.organization_id, department_id=department_id,
                             name=data["name"], metric=data["metric"],
                             target_value=Decimal(str(data["target_value"])), period=data.get("period", "monthly"),
                             start_date=data.get("start_date"), end_date=data.get("end_date"), created_by=actor.id)
        self.db.add(t)
        await self.db.flush()
        await self.db.refresh(t)
        return t

    async def delete_target(self, actor: User, department_id: uuid.UUID, target_id: uuid.UUID) -> None:
        self._require_manage(actor)
        t = (await self.db.execute(select(DepartmentTarget).filter(
            DepartmentTarget.id == target_id, DepartmentTarget.department_id == department_id,
            DepartmentTarget.organization_id == actor.organization_id, DepartmentTarget.is_deleted == False))).scalars().first()
        if not t:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Target not found")
        t.is_deleted = True
        self.db.add(t)
        await self.db.flush()

    # ---------- Performance / KPIs ----------
    async def _metrics_for_members(self, org_id, member_ids: list, date_from=None, date_to=None) -> dict:
        if not member_ids:
            return {"leads_converted": 0, "calls_made": 0, "tasks_completed": 0, "revenue": 0.0, "activities": 0}
        # Leads assigned to members
        lq = select(Lead).filter(Lead.organization_id == org_id, Lead.is_deleted == False,
                                 Lead.assigned_user_id.in_(member_ids))
        leads = list((await self.db.execute(lq)).scalars().all())
        converted = 0
        revenue = 0.0
        for l in leads:
            if l.converted_contact_id is not None or l.status in CONVERTED_LEAD_STATUSES:
                converted += 1
                if l.value:
                    revenue += float(l.value)
        # Activities (calls + all comms) by members
        aq = select(Activity.activity_type, func.count(Activity.id)).filter(
            Activity.organization_id == org_id, Activity.is_deleted == False,
            Activity.assigned_user_id.in_(member_ids))
        if date_from is not None:
            aq = aq.filter(Activity.created_at >= date_from)
        if date_to is not None:
            aq = aq.filter(Activity.created_at <= date_to)
        act_rows = (await self.db.execute(aq.group_by(Activity.activity_type))).all()
        by_type = {t: n for t, n in act_rows}
        # Tasks completed by members
        tq = select(func.count(Task.id)).filter(
            Task.organization_id == org_id, Task.is_deleted == False,
            Task.assigned_user_id.in_(member_ids), Task.status == "Done")
        tasks_done = (await self.db.execute(tq)).scalar() or 0
        return {
            "leads_converted": converted, "calls_made": by_type.get("Call", 0),
            "tasks_completed": tasks_done, "revenue": round(revenue, 2),
            "activities": sum(by_type.values()),
        }

    async def performance(self, actor: User, department_id: uuid.UUID, date_from=None, date_to=None) -> dict:
        d = await self._get(actor, department_id)
        member_ids = await self._member_ids(actor.organization_id, department_id)
        metrics = await self._metrics_for_members(actor.organization_id, member_ids, date_from, date_to)
        targets = await self.list_targets(actor, department_id)
        kpis = []
        for t in targets:
            actual = float(metrics.get(t.metric, 0))
            tv = float(t.target_value or 0)
            kpis.append({"target_id": str(t.id), "name": t.name, "metric": t.metric,
                         "target_value": tv, "actual": actual,
                         "attainment": round(actual * 100 / tv, 1) if tv else 0.0,
                         "period": t.period})
        return {"department_id": str(d.id), "name": d.name, "member_count": len(member_ids),
                "budget": float(d.budget) if d.budget is not None else None,
                "metrics": metrics, "kpis": kpis}

    async def dashboard(self, actor: User) -> dict:
        rows = list((await self.db.execute(select(Department).filter(
            Department.organization_id == actor.organization_id, Department.is_deleted == False))).scalars().all())
        counts = await self._member_counts(actor)
        active = sum(1 for d in rows if d.status == "active")
        total_budget = sum(float(d.budget) for d in rows if d.budget is not None)
        unassigned = (await self.db.execute(select(func.count(User.id)).filter(
            User.organization_id == actor.organization_id, User.is_deleted == False,
            User.department_id.is_(None), User.is_active == True))).scalar() or 0
        return {"total": len(rows), "active": active, "archived": len(rows) - active,
                "total_budget": round(total_budget, 2), "unassigned_members": unassigned,
                "largest": sorted([{"id": str(d.id), "name": d.name, "member_count": counts.get(d.id, 0)}
                                   for d in rows], key=lambda x: -x["member_count"])[:5]}

    async def analytics(self, actor: User, date_from=None, date_to=None) -> list[dict]:
        """Per-department rollup for the whole org (comparison table)."""
        rows = list((await self.db.execute(select(Department).filter(
            Department.organization_id == actor.organization_id, Department.is_deleted == False,
            Department.status == "active"))).scalars().all())
        out = []
        for d in rows:
            member_ids = await self._member_ids(actor.organization_id, d.id)
            m = await self._metrics_for_members(actor.organization_id, member_ids, date_from, date_to)
            out.append({"department_id": str(d.id), "name": d.name, "member_count": len(member_ids),
                        "budget": float(d.budget) if d.budget is not None else None, **m})
        out.sort(key=lambda x: -x["revenue"])
        return out

    # ---------- Import / Export ----------
    async def import_csv(self, actor: User, content: bytes) -> dict:
        self._require_manage(actor)
        text = content.decode("utf-8-sig", errors="replace")
        reader = csv.DictReader(io.StringIO(text))
        created = updated = skipped = 0
        errors = []
        for i, row in enumerate(reader, start=2):
            name = (row.get("name") or "").strip()
            if not name:
                skipped += 1
                continue
            code = (row.get("code") or "").strip() or None
            existing = None
            if code:
                existing = (await self.db.execute(select(Department).filter(
                    Department.organization_id == actor.organization_id, Department.code == code,
                    Department.is_deleted == False))).scalars().first()
            try:
                budget = Decimal(row["budget"]) if row.get("budget") else None
            except Exception:
                budget = None
            if existing:
                existing.name = name
                existing.description = (row.get("description") or "").strip() or existing.description
                if budget is not None:
                    existing.budget = budget
                self.db.add(existing)
                updated += 1
            else:
                self.db.add(Department(organization_id=actor.organization_id, name=name, code=code,
                                       description=(row.get("description") or "").strip() or None,
                                       budget=budget, status=(row.get("status") or "active").strip() or "active",
                                       created_by=actor.id))
                created += 1
        await self.db.flush()
        return {"created": created, "updated": updated, "skipped": skipped, "errors": errors}

    async def export_csv(self, actor: User) -> str:
        rows = list((await self.db.execute(select(Department).filter(
            Department.organization_id == actor.organization_id, Department.is_deleted == False)
            .order_by(Department.name.asc()))).scalars().all())
        counts = await self._member_counts(actor)
        names = await self._names({d.head_user_id for d in rows if d.head_user_id})
        parent_names = {d.id: d.name for d in rows}
        buf = io.StringIO()
        w = csv.writer(buf)
        w.writerow(["name", "code", "description", "status", "parent", "head", "budget", "budget_period",
                    "cost_center", "member_count"])
        for d in rows:
            w.writerow([d.name, d.code or "", d.description or "", d.status,
                        parent_names.get(d.parent_department_id, ""), names.get(d.head_user_id, ""),
                        float(d.budget) if d.budget is not None else "", d.budget_period or "",
                        d.cost_center or "", counts.get(d.id, 0)])
        return buf.getvalue()

    # ---------- helpers ----------
    async def _serialize(self, d: Department) -> dict:
        member_count = (await self.db.execute(select(func.count(User.id)).filter(
            User.department_id == d.id, User.is_deleted == False))).scalar() or 0
        head_name = None
        if d.head_user_id:
            head_name = (await self._names({d.head_user_id})).get(d.head_user_id)
        return {
            "id": str(d.id), "organization_id": str(d.organization_id), "name": d.name, "code": d.code,
            "description": d.description, "parent_department_id": str(d.parent_department_id) if d.parent_department_id else None,
            "head_user_id": str(d.head_user_id) if d.head_user_id else None, "head_name": head_name,
            "status": d.status, "budget": float(d.budget) if d.budget is not None else None,
            "budget_period": d.budget_period, "cost_center": d.cost_center, "color": d.color,
            "member_count": member_count, "created_at": d.created_at,
        }

    async def _names(self, ids) -> dict:
        ids = {i for i in ids if i}
        if not ids:
            return {}
        res = await self.db.execute(select(User.id, User.first_name, User.last_name, User.email).filter(User.id.in_(ids)))
        return {uid: (f"{fn or ''} {ln or ''}".strip() or em) for uid, fn, ln, em in res.all()}
