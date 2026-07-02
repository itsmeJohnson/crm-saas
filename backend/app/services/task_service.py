import uuid
from datetime import datetime, timezone, timedelta
from fastapi import HTTPException, status
from sqlalchemy import select, func, or_
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User
from app.models.task import Task
from app.models.task_comment import TaskComment
from app.models.task_dependency import TaskDependency
from app.services.audit_service import AuditService
from app.services.notification_service import NotificationService
from app.services.dashboard_service import DashboardService

OPEN_STATUSES = ("Todo", "InProgress")
ATTACHMENT_EXTENSIONS = {"pdf", "png", "jpg", "jpeg", "webp", "csv", "xlsx", "docx"}


def _advance(dt: datetime, recurrence: str) -> datetime:
    if recurrence == "daily":
        return dt + timedelta(days=1)
    if recurrence == "weekly":
        return dt + timedelta(weeks=1)
    if recurrence == "monthly":
        month = dt.month + 1
        year = dt.year + (1 if month > 12 else 0)
        month = 1 if month > 12 else month
        day = min(dt.day, 28)
        return dt.replace(year=year, month=month, day=day)
    return dt


class TaskService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.audit = AuditService(db)
        self.notifier = NotificationService(db)

    def _is_privileged(self, actor: User) -> bool:
        return actor.role in ("SuperAdmin", "OrgAdmin", "Manager")

    async def _get(self, actor: User, task_id: uuid.UUID) -> Task:
        res = await self.db.execute(
            select(Task).filter(Task.id == task_id, Task.organization_id == actor.organization_id, Task.is_deleted == False)
        )
        task = res.scalars().first()
        if not task:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Task not found")
        if not self._is_privileged(actor) and task.assigned_user_id != actor.id and task.created_by != actor.id:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Task not found")
        return task

    async def _validate_assignee(self, actor: User, assignee_id) -> None:
        if not assignee_id:
            return
        from app.repositories.user_repository import UserRepository
        u = await UserRepository(self.db).get_user_by_id(actor.organization_id, assignee_id)
        if not u or not u.is_active:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Assigned user not found or inactive")

    async def _notify_assignment(self, actor: User, task: Task) -> None:
        if task.assigned_user_id and task.assigned_user_id != actor.id:
            await self.notifier.create_notification(
                organization_id=actor.organization_id, user_id=task.assigned_user_id,
                category="task", title="Task assigned to you",
                body=f'"{task.title}" was assigned to you.',
                link_url=f"/tasks?taskId={task.id}",
                action_metadata={"task_id": str(task.id)},
            )

    @staticmethod
    def _prep_checklist(items) -> list | None:
        if items is None:
            return None
        out = []
        for it in items:
            d = dict(it)
            if not d.get("id"):
                d["id"] = uuid.uuid4().hex[:8]
            out.append({"id": d["id"], "text": d.get("text", ""), "done": bool(d.get("done", False))})
        return out

    async def create_task(self, actor: User, data: dict) -> Task:
        await self._validate_assignee(actor, data.get("assigned_user_id"))
        task = Task(
            organization_id=actor.organization_id,
            title=data["title"], description=data.get("description"),
            priority=data.get("priority", "Medium"), status=data.get("status", "Todo"),
            due_date=data.get("due_date"), remind_at=data.get("remind_at"),
            assigned_user_id=data.get("assigned_user_id"), created_by=actor.id,
            lead_id=data.get("lead_id"), contact_id=data.get("contact_id"), company_id=data.get("company_id"),
            recurrence=data.get("recurrence", "none"),
            checklist=self._prep_checklist(data.get("checklist")),
        )
        self.db.add(task)
        await self.db.flush()
        await self.audit.log_event(organization_id=actor.organization_id, actor_user_id=actor.id,
                                   action="TASK_CREATED", resource_type="task", resource_id=str(task.id),
                                   action_metadata={"title": task.title})
        await self._notify_assignment(actor, task)
        from app.services.workflow_service import WorkflowService
        await WorkflowService(self.db).run("task_created", task, actor, entity_type="task")
        await DashboardService.invalidate_cache(actor.organization_id)
        await self.db.refresh(task)
        return task

    async def list_tasks(self, actor: User, status_filter=None, priority=None, assigned_user_id=None,
                         lead_id=None, contact_id=None, company_id=None, overdue=None,
                         due_from=None, due_to=None, search=None, skip=0, limit=50) -> list[Task]:
        q = select(Task).filter(Task.organization_id == actor.organization_id, Task.is_deleted == False)
        if not self._is_privileged(actor):
            q = q.filter(or_(Task.assigned_user_id == actor.id, Task.created_by == actor.id))
        if status_filter:
            q = q.filter(Task.status == status_filter)
        if priority:
            q = q.filter(Task.priority == priority)
        if assigned_user_id:
            q = q.filter(Task.assigned_user_id == assigned_user_id)
        if lead_id:
            q = q.filter(Task.lead_id == lead_id)
        if contact_id:
            q = q.filter(Task.contact_id == contact_id)
        if company_id:
            q = q.filter(Task.company_id == company_id)
        if overdue:
            q = q.filter(Task.due_date.isnot(None), Task.due_date < datetime.now(timezone.utc), Task.status.in_(OPEN_STATUSES))
        if due_from is not None:
            q = q.filter(Task.due_date >= due_from)
        if due_to is not None:
            q = q.filter(Task.due_date <= due_to)
        if search:
            q = q.filter(Task.title.ilike(f"%{search}%"))
        q = q.order_by(Task.due_date.asc().nullslast(), Task.created_at.desc()).offset(skip).limit(limit)
        return list((await self.db.execute(q)).scalars().all())

    async def get_task(self, actor: User, task_id: uuid.UUID) -> Task:
        return await self._get(actor, task_id)

    async def update_task(self, actor: User, task_id: uuid.UUID, data: dict) -> Task:
        task = await self._get(actor, task_id)
        if "assigned_user_id" in data:
            await self._validate_assignee(actor, data["assigned_user_id"])
        prev_assignee = task.assigned_user_id
        prev_status = task.status
        if "checklist" in data:
            data["checklist"] = self._prep_checklist(data["checklist"])
        for key, val in data.items():
            setattr(task, key, val)
        # completion bookkeeping if status set to Done via update
        if task.status == "Done" and prev_status != "Done":
            await self._on_complete(actor, task)
        self.db.add(task)
        await self.db.flush()
        await self.audit.log_event(organization_id=actor.organization_id, actor_user_id=actor.id,
                                   action="TASK_UPDATED", resource_type="task", resource_id=str(task_id),
                                   action_metadata={"updated_fields": list(data.keys())})
        if "assigned_user_id" in data and task.assigned_user_id != prev_assignee:
            await self._notify_assignment(actor, task)
        from app.services.workflow_service import WorkflowService
        await WorkflowService(self.db).run("task_updated", task, actor, entity_type="task")
        await DashboardService.invalidate_cache(actor.organization_id)
        await self.db.refresh(task)
        return task

    async def _blockers_open(self, task_id: uuid.UUID) -> bool:
        res = await self.db.execute(
            select(func.count(Task.id)).select_from(TaskDependency)
            .join(Task, Task.id == TaskDependency.depends_on_task_id)
            .filter(TaskDependency.task_id == task_id, TaskDependency.is_deleted == False,
                    Task.is_deleted == False, Task.status.in_(OPEN_STATUSES))
        )
        return (res.scalar() or 0) > 0

    async def _on_complete(self, actor: User, task: Task) -> None:
        """Set completion metadata + spawn next occurrence if recurring. Enforces dependencies."""
        if await self._blockers_open(task.id):
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Cannot complete: this task is blocked by unfinished dependencies")
        task.completed_at = datetime.now(timezone.utc)
        # reset checklist done? keep. Spawn next occurrence for recurring
        if task.recurrence and task.recurrence != "none" and task.due_date:
            nxt = Task(
                organization_id=task.organization_id, title=task.title, description=task.description,
                priority=task.priority, status="Todo", due_date=_advance(task.due_date, task.recurrence),
                remind_at=_advance(task.remind_at, task.recurrence) if task.remind_at else None,
                assigned_user_id=task.assigned_user_id, created_by=actor.id,
                lead_id=task.lead_id, contact_id=task.contact_id, company_id=task.company_id,
                recurrence=task.recurrence, recurrence_parent_id=task.recurrence_parent_id or task.id,
                checklist=[{**c, "done": False} for c in (task.checklist or [])] or None,
            )
            self.db.add(nxt)

    async def complete_task(self, actor: User, task_id: uuid.UUID) -> Task:
        task = await self._get(actor, task_id)
        if task.status == "Done":
            return task
        task.status = "Done"
        await self._on_complete(actor, task)
        self.db.add(task)
        await self.db.flush()
        await self.audit.log_event(organization_id=actor.organization_id, actor_user_id=actor.id,
                                   action="TASK_COMPLETED", resource_type="task", resource_id=str(task_id))
        await DashboardService.invalidate_cache(actor.organization_id)
        await self.db.refresh(task)
        return task

    async def delete_task(self, actor: User, task_id: uuid.UUID) -> None:
        task = await self._get(actor, task_id)
        task.is_deleted = True
        task.deleted_at = datetime.now(timezone.utc)
        self.db.add(task)
        await self.db.flush()

    # --- Checklist ---
    async def toggle_checklist(self, actor: User, task_id: uuid.UUID, item_id: str, done: bool) -> Task:
        task = await self._get(actor, task_id)
        # Fresh dicts so SQLAlchemy reliably detects the JSON change on reassignment
        items = [dict(it) for it in (task.checklist or [])]
        found = False
        for it in items:
            if it.get("id") == item_id:
                it["done"] = done
                found = True
        if not found:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Checklist item not found")
        task.checklist = items
        self.db.add(task)
        await self.db.flush()
        await self.db.refresh(task)
        return task

    # --- Comments ---
    async def add_comment(self, actor: User, task_id: uuid.UUID, body: str) -> TaskComment:
        await self._get(actor, task_id)
        comment = TaskComment(organization_id=actor.organization_id, task_id=task_id, body=body, created_by=actor.id)
        self.db.add(comment)
        await self.db.flush()
        await self.db.refresh(comment)
        return comment

    async def list_comments(self, actor: User, task_id: uuid.UUID) -> list[TaskComment]:
        await self._get(actor, task_id)
        res = await self.db.execute(
            select(TaskComment).filter(TaskComment.task_id == task_id, TaskComment.is_deleted == False).order_by(TaskComment.created_at.asc())
        )
        return list(res.scalars().all())

    async def delete_comment(self, actor: User, task_id: uuid.UUID, comment_id: uuid.UUID) -> None:
        await self._get(actor, task_id)
        res = await self.db.execute(select(TaskComment).filter(
            TaskComment.id == comment_id, TaskComment.task_id == task_id,
            TaskComment.organization_id == actor.organization_id, TaskComment.is_deleted == False))
        c = res.scalars().first()
        if not c:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Comment not found")
        c.is_deleted = True
        self.db.add(c)
        await self.db.flush()

    # --- Attachments ---
    async def add_attachment(self, actor: User, task_id: uuid.UUID, content: bytes, filename: str) -> dict:
        from app.core.storage import validate_and_sanitize_file, get_storage_provider
        task = await self._get(actor, task_id)
        try:
            sanitized, ext = validate_and_sanitize_file(content=content, filename=filename, allowed_extensions=ATTACHMENT_EXTENSIONS)
        except ValueError as e:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
        url = await get_storage_provider().upload_file(content, sanitized)
        att = {"filename": filename, "stored_name": sanitized, "url": url, "size": len(content),
               "uploaded_by": str(actor.id), "uploaded_at": datetime.now(timezone.utc).isoformat()}
        existing = list(task.attachments or [])
        existing.append(att)
        task.attachments = existing
        self.db.add(task)
        await self.db.flush()
        return att

    async def list_attachments(self, actor: User, task_id: uuid.UUID) -> list[dict]:
        task = await self._get(actor, task_id)
        return list(task.attachments or [])

    async def delete_attachment(self, actor: User, task_id: uuid.UUID, stored_name: str) -> dict:
        from app.core.storage import get_storage_provider
        task = await self._get(actor, task_id)
        existing = list(task.attachments or [])
        target = next((a for a in existing if a.get("stored_name") == stored_name or a.get("filename") == stored_name), None)
        if not target:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Attachment not found")
        task.attachments = [a for a in existing if a is not target]
        self.db.add(task)
        await self.db.flush()
        try:
            await get_storage_provider().delete_file(target["url"])
        except Exception:
            pass
        return {"deleted": True}

    # --- Dependencies ---
    async def add_dependency(self, actor: User, task_id: uuid.UUID, depends_on_task_id: uuid.UUID) -> TaskDependency:
        if task_id == depends_on_task_id:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="A task cannot depend on itself")
        await self._get(actor, task_id)
        await self._get(actor, depends_on_task_id)
        # cycle guard: does depends_on already (transitively) depend on task_id?
        if await self._would_cycle(depends_on_task_id, task_id):
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="This dependency would create a cycle")
        # dup guard
        existing = await self.db.execute(select(TaskDependency.id).filter(
            TaskDependency.task_id == task_id, TaskDependency.depends_on_task_id == depends_on_task_id,
            TaskDependency.is_deleted == False))
        if existing.scalar():
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Dependency already exists")
        dep = TaskDependency(organization_id=actor.organization_id, task_id=task_id,
                             depends_on_task_id=depends_on_task_id, created_by=actor.id)
        self.db.add(dep)
        await self.db.flush()
        await self.db.refresh(dep)
        return dep

    async def _would_cycle(self, start_task_id: uuid.UUID, target_id: uuid.UUID, depth: int = 0) -> bool:
        if depth > 50:
            return True
        res = await self.db.execute(select(TaskDependency.depends_on_task_id).filter(
            TaskDependency.task_id == start_task_id, TaskDependency.is_deleted == False))
        for (dep_id,) in res.all():
            if dep_id == target_id:
                return True
            if await self._would_cycle(dep_id, target_id, depth + 1):
                return True
        return False

    async def list_dependencies(self, actor: User, task_id: uuid.UUID) -> list[dict]:
        await self._get(actor, task_id)
        res = await self.db.execute(
            select(TaskDependency, Task.title, Task.status)
            .join(Task, Task.id == TaskDependency.depends_on_task_id)
            .filter(TaskDependency.task_id == task_id, TaskDependency.is_deleted == False)
        )
        return [
            {"id": dep.id, "task_id": dep.task_id, "depends_on_task_id": dep.depends_on_task_id,
             "depends_on_title": title, "depends_on_status": st}
            for dep, title, st in res.all()
        ]

    async def delete_dependency(self, actor: User, task_id: uuid.UUID, dependency_id: uuid.UUID) -> None:
        await self._get(actor, task_id)
        res = await self.db.execute(select(TaskDependency).filter(
            TaskDependency.id == dependency_id, TaskDependency.task_id == task_id,
            TaskDependency.organization_id == actor.organization_id, TaskDependency.is_deleted == False))
        dep = res.scalars().first()
        if not dep:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Dependency not found")
        dep.is_deleted = True
        self.db.add(dep)
        await self.db.flush()

    # --- Bulk ---
    async def bulk_update(self, actor: User, task_ids: list[uuid.UUID], fields: dict) -> dict:
        if fields.get("assigned_user_id"):
            await self._validate_assignee(actor, fields["assigned_user_id"])
        q = select(Task).filter(Task.id.in_(task_ids), Task.organization_id == actor.organization_id, Task.is_deleted == False).with_for_update()
        tasks = list((await self.db.execute(q)).scalars().all())
        affected = []
        for t in tasks:
            if not self._is_privileged(actor) and t.assigned_user_id != actor.id and t.created_by != actor.id:
                continue
            for k, v in fields.items():
                setattr(t, k, v)
            if fields.get("status") == "Done" and not t.completed_at:
                t.completed_at = datetime.now(timezone.utc)
            self.db.add(t)
            affected.append(t.id)
        await self.db.flush()
        if affected:
            await DashboardService.invalidate_cache(actor.organization_id)
        return {"affected_count": len(affected), "task_ids": affected}

    async def bulk_delete(self, actor: User, task_ids: list[uuid.UUID]) -> dict:
        q = select(Task).filter(Task.id.in_(task_ids), Task.organization_id == actor.organization_id, Task.is_deleted == False).with_for_update()
        tasks = list((await self.db.execute(q)).scalars().all())
        affected = []
        now = datetime.now(timezone.utc)
        for t in tasks:
            if not self._is_privileged(actor) and t.assigned_user_id != actor.id and t.created_by != actor.id:
                continue
            t.is_deleted = True
            t.deleted_at = now
            self.db.add(t)
            affected.append(t.id)
        await self.db.flush()
        if affected:
            await DashboardService.invalidate_cache(actor.organization_id)
        return {"affected_count": len(affected), "task_ids": affected}

    # --- Calendar ---
    async def calendar(self, actor: User, date_from, date_to) -> list[Task]:
        return await self.list_tasks(actor, due_from=date_from, due_to=date_to, limit=500)

    # --- Reports ---
    async def get_report(self, actor: User) -> dict:
        org = actor.organization_id
        now = datetime.now(timezone.utc)

        def base(*cols):
            q = select(*cols).filter(Task.organization_id == org, Task.is_deleted == False)
            if not self._is_privileged(actor):
                q = q.filter(or_(Task.assigned_user_id == actor.id, Task.created_by == actor.id))
            return q

        total = (await self.db.execute(base(func.count(Task.id)))).scalar() or 0
        completed = (await self.db.execute(base(func.count(Task.id)).filter(Task.status == "Done"))).scalar() or 0
        open_count = (await self.db.execute(base(func.count(Task.id)).filter(Task.status.in_(OPEN_STATUSES)))).scalar() or 0
        overdue = (await self.db.execute(base(func.count(Task.id)).filter(
            Task.due_date.isnot(None), Task.due_date < now, Task.status.in_(OPEN_STATUSES)))).scalar() or 0
        today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        today_end = today_start + timedelta(days=1)
        due_today = (await self.db.execute(base(func.count(Task.id)).filter(
            Task.due_date >= today_start, Task.due_date < today_end, Task.status.in_(OPEN_STATUSES)))).scalar() or 0

        status_rows = (await self.db.execute(base(Task.status, func.count(Task.id)).group_by(Task.status))).all()
        prio_rows = (await self.db.execute(base(Task.priority, func.count(Task.id)).group_by(Task.priority))).all()

        # by assignee
        from app.models.user import User as UserModel
        asg_rows = (await self.db.execute(base(Task.assigned_user_id, func.count(Task.id)).group_by(Task.assigned_user_id))).all()
        asg_ids = [r[0] for r in asg_rows if r[0]]
        names = {}
        if asg_ids:
            u = await self.db.execute(select(UserModel.id, UserModel.first_name, UserModel.last_name, UserModel.email).filter(UserModel.id.in_(asg_ids)))
            for uid, fn, ln, em in u.all():
                names[uid] = f"{fn or ''} {ln or ''}".strip() or em

        return {
            "total": total, "open": open_count, "completed": completed, "overdue": overdue, "due_today": due_today,
            "completion_rate": round((completed / total) * 100, 1) if total else 0.0,
            "by_status": [{"label": r[0], "count": r[1]} for r in status_rows],
            "by_priority": [{"label": r[0], "count": r[1]} for r in prio_rows],
            "by_assignee": [{"label": names.get(r[0], "Unassigned") if r[0] else "Unassigned", "count": r[1]} for r in asg_rows],
        }
