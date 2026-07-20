"""Team Management service.

Makes the implicit TL/reporting-chain team explicit as a first-class entity.
Follows the Department module architecture: members are Users (join table
team_members so a user can serve on several teams), the leader is a User,
targets mirror DepartmentTarget, and performance reuses the same Lead/
Activity/Task rollup (via DepartmentService._metrics_for_members).
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
from app.models.calendar_event import CalendarEvent
from app.models.department import Department
from app.models.team import Team, TeamMember, TeamTarget
from app.services.audit_service import AuditService
from app.services.notification_service import NotificationService
from app.services.department_service import DepartmentService, METRICS


class TeamService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.audit = AuditService(db)
        self.notifier = NotificationService(db)
        # Shared Lead/Activity/Task metric rollup lives on the department
        # service; teams roll up the same metrics over their member set.
        self._rollup = DepartmentService(db)

    # ---------- permissions ----------
    def _can_manage(self, actor: User) -> bool:
        return actor.role in ("SuperAdmin", "OrgAdmin", "Manager")

    def _require_manage(self, actor: User):
        if not self._can_manage(actor):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN,
                                detail="Only an OrgAdmin or Manager can manage teams.")

    async def _visible_team_ids(self, actor: User) -> set[uuid.UUID] | None:
        """None = all teams. Employees (incl. TLs) see teams they lead or belong to."""
        if self._can_manage(actor):
            return None
        led = (await self.db.execute(select(Team.id).filter(
            Team.organization_id == actor.organization_id, Team.team_leader_id == actor.id,
            Team.is_deleted == False))).scalars().all()
        member_of = (await self.db.execute(select(TeamMember.team_id).filter(
            TeamMember.user_id == actor.id, TeamMember.organization_id == actor.organization_id,
            TeamMember.is_deleted == False))).scalars().all()
        return set(led) | set(member_of)

    async def _require_view(self, actor: User, team: Team) -> None:
        visible = await self._visible_team_ids(actor)
        if visible is not None and team.id not in visible:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN,
                                detail="You are not a member of this team.")

    def _is_leader(self, actor: User, team: Team) -> bool:
        return team.team_leader_id == actor.id

    # ---------- CRUD ----------
    async def _get(self, actor: User, team_id: uuid.UUID) -> Team:
        t = (await self.db.execute(select(Team).filter(
            Team.id == team_id, Team.organization_id == actor.organization_id,
            Team.is_deleted == False))).scalars().first()
        if not t:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Team not found")
        return t

    async def get(self, actor: User, team_id: uuid.UUID) -> dict:
        t = await self._get(actor, team_id)
        await self._require_view(actor, t)
        return await self._serialize(t)

    async def _validate_name(self, actor: User, name: str, exclude_id=None):
        q = select(Team.id).filter(Team.organization_id == actor.organization_id,
                                   Team.name == name, Team.is_deleted == False)
        if exclude_id:
            q = q.filter(Team.id != exclude_id)
        if (await self.db.execute(q)).scalar():
            raise HTTPException(status_code=status.HTTP_409_CONFLICT,
                                detail=f"Team '{name}' already exists.")

    async def _validate_user(self, actor: User, user_id, label="User") -> User | None:
        if not user_id:
            return None
        u = (await self.db.execute(select(User).filter(
            User.id == user_id, User.organization_id == actor.organization_id,
            User.is_deleted == False))).scalars().first()
        if not u:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST,
                                detail=f"{label} not found in this org.")
        return u

    async def _validate_department(self, actor: User, department_id):
        if not department_id:
            return
        ok = (await self.db.execute(select(Department.id).filter(
            Department.id == department_id, Department.organization_id == actor.organization_id,
            Department.is_deleted == False))).scalar()
        if not ok:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST,
                                detail="Department not found in this org.")

    async def create(self, actor: User, data: dict) -> dict:
        self._require_manage(actor)
        await self._validate_name(actor, data["name"])
        await self._validate_user(actor, data.get("team_leader_id"), "Team leader")
        await self._validate_department(actor, data.get("department_id"))
        if data.get("capacity") is not None and int(data["capacity"]) < 1:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST,
                                detail="capacity must be a positive number.")
        t = Team(organization_id=actor.organization_id, name=data["name"], code=data.get("code"),
                 description=data.get("description"), team_leader_id=data.get("team_leader_id"),
                 department_id=data.get("department_id"), capacity=data.get("capacity"),
                 status=data.get("status", "active"), color=data.get("color"), created_by=actor.id)
        self.db.add(t)
        await self.db.flush()
        # the leader is a member by definition
        if t.team_leader_id:
            self.db.add(TeamMember(organization_id=actor.organization_id, team_id=t.id,
                                   user_id=t.team_leader_id, role_in_team="leader"))
            await self.db.flush()
            await self.notifier.create_notification(
                organization_id=actor.organization_id, user_id=t.team_leader_id, category="team",
                title="You lead a new team", body=f"You were made leader of team {t.name}.",
                link_url=f"/teams?teamId={t.id}", action_metadata={"team_id": str(t.id)})
        await self.audit.log_event(organization_id=actor.organization_id, actor_user_id=actor.id,
                                   action="TEAM_CREATED", resource_type="team", resource_id=str(t.id),
                                   action_metadata={"name": t.name})
        return await self._serialize(t)

    async def update(self, actor: User, team_id: uuid.UUID, data: dict) -> dict:
        t = await self._get(actor, team_id)
        # a team leader may edit their own team's description/name/color
        if not self._can_manage(actor) and not self._is_leader(actor, t):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN,
                                detail="Only a manager or the team leader can edit this team.")
        if "name" in data and data["name"] and data["name"] != t.name:
            await self._validate_name(actor, data["name"], exclude_id=t.id)
        if "department_id" in data:
            await self._validate_department(actor, data.get("department_id"))
        if "capacity" in data and data["capacity"] is not None:
            if int(data["capacity"]) < 1:
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST,
                                    detail="capacity must be a positive number.")
            n = await self._member_count(t.id)
            if int(data["capacity"]) < n:
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST,
                                    detail=f"capacity cannot be below current member count ({n}).")
        new_leader = None
        if "team_leader_id" in data and data["team_leader_id"] != t.team_leader_id:
            if not self._can_manage(actor):
                raise HTTPException(status_code=status.HTTP_403_FORBIDDEN,
                                    detail="Only a manager can change the team leader.")
            new_leader = await self._validate_user(actor, data.get("team_leader_id"), "Team leader")
        for k in ("name", "code", "description", "team_leader_id", "department_id",
                  "capacity", "status", "color"):
            if k in data:
                setattr(t, k, data[k])
        self.db.add(t)
        await self.db.flush()
        if new_leader:
            # ensure the new leader is a member with role leader; demote others
            rows = list((await self.db.execute(select(TeamMember).filter(
                TeamMember.team_id == t.id, TeamMember.is_deleted == False))).scalars().all())
            found = False
            for m in rows:
                if m.user_id == new_leader.id:
                    m.role_in_team = "leader"
                    found = True
                elif m.role_in_team == "leader":
                    m.role_in_team = "member"
                self.db.add(m)
            if not found:
                self.db.add(TeamMember(organization_id=actor.organization_id, team_id=t.id,
                                       user_id=new_leader.id, role_in_team="leader"))
            await self.db.flush()
            await self.notifier.create_notification(
                organization_id=actor.organization_id, user_id=new_leader.id, category="team",
                title="You lead a team", body=f"You were made leader of team {t.name}.",
                link_url=f"/teams?teamId={t.id}", action_metadata={"team_id": str(t.id)})
        await self.audit.log_event(organization_id=actor.organization_id, actor_user_id=actor.id,
                                   action="TEAM_UPDATED", resource_type="team", resource_id=str(t.id),
                                   action_metadata={"name": t.name, "fields": sorted(set(data.keys()))})
        return await self._serialize(t)

    async def delete(self, actor: User, team_id: uuid.UUID) -> None:
        self._require_manage(actor)
        t = await self._get(actor, team_id)
        n = await self._member_count(t.id)
        # leader counts as a member; only block on members besides the leader
        non_leader = n - (1 if t.team_leader_id else 0)
        if non_leader > 0:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT,
                                detail=f"Remove {non_leader} member(s) first or archive the team.")
        t.is_deleted = True
        self.db.add(t)
        # soft-delete remaining membership rows
        rows = list((await self.db.execute(select(TeamMember).filter(
            TeamMember.team_id == t.id, TeamMember.is_deleted == False))).scalars().all())
        for m in rows:
            m.is_deleted = True
            self.db.add(m)
        await self.db.flush()
        await self.audit.log_event(organization_id=actor.organization_id, actor_user_id=actor.id,
                                   action="TEAM_DELETED", resource_type="team", resource_id=str(t.id),
                                   action_metadata={"name": t.name})

    # ---------- List / search / filter ----------
    async def list(self, actor: User, search=None, status_filter=None, department_id=None,
                   leader_id=None, skip=0, limit=100) -> dict:
        q = select(Team).filter(Team.organization_id == actor.organization_id,
                                Team.is_deleted == False)
        visible = await self._visible_team_ids(actor)
        if visible is not None:
            if not visible:
                return {"items": [], "total": 0}
            q = q.filter(Team.id.in_(visible))
        if status_filter:
            q = q.filter(Team.status == status_filter)
        if department_id:
            q = q.filter(Team.department_id == department_id)
        if leader_id:
            q = q.filter(Team.team_leader_id == leader_id)
        if search:
            s = f"%{search}%"
            q = q.filter(or_(Team.name.ilike(s), Team.code.ilike(s), Team.description.ilike(s)))
        total = (await self.db.execute(select(func.count()).select_from(q.subquery()))).scalar() or 0
        rows = list((await self.db.execute(q.order_by(Team.name.asc()).offset(skip).limit(limit))).scalars().all())
        return {"items": [await self._serialize(t) for t in rows], "total": total}

    # ---------- Members ----------
    async def _member_count(self, team_id: uuid.UUID) -> int:
        return (await self.db.execute(select(func.count(TeamMember.id)).filter(
            TeamMember.team_id == team_id, TeamMember.is_deleted == False))).scalar() or 0

    async def _member_ids(self, team_id: uuid.UUID) -> list[uuid.UUID]:
        return list((await self.db.execute(select(TeamMember.user_id).filter(
            TeamMember.team_id == team_id, TeamMember.is_deleted == False))).scalars().all())

    async def members(self, actor: User, team_id: uuid.UUID) -> list[dict]:
        t = await self._get(actor, team_id)
        await self._require_view(actor, t)
        rows = (await self.db.execute(
            select(TeamMember, User).join(User, User.id == TeamMember.user_id).filter(
                TeamMember.team_id == team_id, TeamMember.is_deleted == False,
                User.is_deleted == False).order_by(User.first_name.asc()))).all()
        return [{"id": str(u.id), "membership_id": str(m.id),
                 "name": f"{u.first_name or ''} {u.last_name or ''}".strip() or u.email,
                 "email": u.email, "role": u.role, "role_in_team": m.role_in_team,
                 "is_active": u.is_active,
                 "joined_at": m.joined_at.isoformat() if m.joined_at else None} for m, u in rows]

    async def add_members(self, actor: User, team_id: uuid.UUID, user_ids: list[uuid.UUID]) -> dict:
        t = await self._get(actor, team_id)
        if not self._can_manage(actor) and not self._is_leader(actor, t):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN,
                                detail="Only a manager or the team leader can manage members.")
        users = list((await self.db.execute(select(User).filter(
            User.id.in_(user_ids), User.organization_id == actor.organization_id,
            User.is_deleted == False))).scalars().all())
        existing = set(await self._member_ids(t.id))
        to_add = [u for u in users if u.id not in existing]
        # capacity guard
        if t.capacity is not None and len(existing) + len(to_add) > t.capacity:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Team capacity ({t.capacity}) exceeded: {len(existing)} member(s) + {len(to_add)} new.")
        for u in to_add:
            # revive a soft-deleted membership row if one exists (unique constraint)
            prev = (await self.db.execute(select(TeamMember).filter(
                TeamMember.team_id == t.id, TeamMember.user_id == u.id))).scalars().first()
            if prev:
                prev.is_deleted = False
                prev.role_in_team = "member"
                prev.joined_at = datetime.now(timezone.utc)
                self.db.add(prev)
            else:
                self.db.add(TeamMember(organization_id=actor.organization_id, team_id=t.id,
                                       user_id=u.id, role_in_team="member"))
            await self.notifier.create_notification(
                organization_id=actor.organization_id, user_id=u.id, category="team",
                title="Added to a team", body=f"You were added to team {t.name}.",
                link_url=f"/teams?teamId={t.id}", action_metadata={"team_id": str(t.id)})
        await self.db.flush()
        if t.team_leader_id and to_add and t.team_leader_id != actor.id:
            await self.notifier.create_notification(
                organization_id=actor.organization_id, user_id=t.team_leader_id, category="team",
                title="Team members added", body=f"{len(to_add)} member(s) added to {t.name}.",
                link_url=f"/teams?teamId={t.id}", action_metadata={"team_id": str(t.id)})
        return {"added": len(to_add), "skipped": len(users) - len(to_add)}

    async def remove_members(self, actor: User, team_id: uuid.UUID, user_ids: list[uuid.UUID]) -> dict:
        t = await self._get(actor, team_id)
        if not self._can_manage(actor) and not self._is_leader(actor, t):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN,
                                detail="Only a manager or the team leader can manage members.")
        if t.team_leader_id and t.team_leader_id in user_ids:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST,
                                detail="Assign a new team leader before removing the current one.")
        rows = list((await self.db.execute(select(TeamMember).filter(
            TeamMember.team_id == t.id, TeamMember.user_id.in_(user_ids),
            TeamMember.is_deleted == False))).scalars().all())
        for m in rows:
            m.is_deleted = True
            self.db.add(m)
        await self.db.flush()
        return {"removed": len(rows)}

    # ---------- Targets ----------
    async def list_targets(self, actor: User, team_id: uuid.UUID) -> list[TeamTarget]:
        t = await self._get(actor, team_id)
        await self._require_view(actor, t)
        return list((await self.db.execute(select(TeamTarget).filter(
            TeamTarget.team_id == team_id, TeamTarget.is_deleted == False)
            .order_by(TeamTarget.created_at.desc()))).scalars().all())

    async def create_target(self, actor: User, team_id: uuid.UUID, data: dict) -> TeamTarget:
        t = await self._get(actor, team_id)
        if not self._can_manage(actor) and not self._is_leader(actor, t):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN,
                                detail="Only a manager or the team leader can manage targets.")
        if data["metric"] not in METRICS:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST,
                                detail=f"metric must be one of {list(METRICS)}")
        target = TeamTarget(organization_id=actor.organization_id, team_id=team_id,
                            name=data["name"], metric=data["metric"],
                            target_value=Decimal(str(data["target_value"])),
                            period=data.get("period", "monthly"),
                            start_date=data.get("start_date"), end_date=data.get("end_date"),
                            created_by=actor.id)
        self.db.add(target)
        await self.db.flush()
        await self.db.refresh(target)
        if t.team_leader_id and t.team_leader_id != actor.id:
            await self.notifier.create_notification(
                organization_id=actor.organization_id, user_id=t.team_leader_id, category="team",
                title="New team target", body=f"Target '{target.name}' set for {t.name}.",
                link_url=f"/teams?teamId={t.id}", action_metadata={"team_id": str(t.id)})
        return target

    async def delete_target(self, actor: User, team_id: uuid.UUID, target_id: uuid.UUID) -> None:
        t = await self._get(actor, team_id)
        if not self._can_manage(actor) and not self._is_leader(actor, t):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN,
                                detail="Only a manager or the team leader can manage targets.")
        target = (await self.db.execute(select(TeamTarget).filter(
            TeamTarget.id == target_id, TeamTarget.team_id == team_id,
            TeamTarget.organization_id == actor.organization_id,
            TeamTarget.is_deleted == False))).scalars().first()
        if not target:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Target not found")
        target.is_deleted = True
        self.db.add(target)
        await self.db.flush()

    # ---------- Performance / analytics ----------
    async def performance(self, actor: User, team_id: uuid.UUID, date_from=None, date_to=None) -> dict:
        t = await self._get(actor, team_id)
        await self._require_view(actor, t)
        member_ids = await self._member_ids(t.id)
        metrics = await self._rollup._metrics_for_members(actor.organization_id, member_ids, date_from, date_to)
        targets = await self.list_targets(actor, team_id)
        kpis = []
        for target in targets:
            actual = float(metrics.get(target.metric, 0))
            tv = float(target.target_value or 0)
            kpis.append({"target_id": str(target.id), "name": target.name, "metric": target.metric,
                         "target_value": tv, "actual": actual,
                         "attainment": round(actual * 100 / tv, 1) if tv else 0.0,
                         "period": target.period})
        # per-member breakdown
        per_member = []
        names = await self._rollup._names(set(member_ids))
        for uid in member_ids:
            m = await self._rollup._metrics_for_members(actor.organization_id, [uid], date_from, date_to)
            per_member.append({"user_id": str(uid), "name": names.get(uid, ""), **m})
        per_member.sort(key=lambda x: -x["revenue"])
        return {"team_id": str(t.id), "name": t.name, "member_count": len(member_ids),
                "capacity": t.capacity, "metrics": metrics, "kpis": kpis, "members": per_member}

    async def dashboard(self, actor: User) -> dict:
        visible = await self._visible_team_ids(actor)
        q = select(Team).filter(Team.organization_id == actor.organization_id, Team.is_deleted == False)
        if visible is not None:
            q = q.filter(Team.id.in_(visible)) if visible else q.filter(Team.id.is_(None))
        rows = list((await self.db.execute(q)).scalars().all())
        counts = {}
        if rows:
            crows = (await self.db.execute(select(TeamMember.team_id, func.count(TeamMember.id)).filter(
                TeamMember.team_id.in_([t.id for t in rows]), TeamMember.is_deleted == False)
                .group_by(TeamMember.team_id))).all()
            counts = {tid: n for tid, n in crows}
        active = [t for t in rows if t.status == "active"]
        total_members = sum(counts.values())
        cap_teams = [t for t in active if t.capacity]
        utilization = (round(sum(counts.get(t.id, 0) for t in cap_teams) * 100 /
                             sum(t.capacity for t in cap_teams), 1) if cap_teams else None)
        return {"total": len(rows), "active": len(active), "archived": len(rows) - len(active),
                "total_members": total_members, "capacity_utilization": utilization,
                "largest": sorted([{"id": str(t.id), "name": t.name,
                                    "member_count": counts.get(t.id, 0), "capacity": t.capacity}
                                   for t in rows], key=lambda x: -x["member_count"])[:5]}

    async def analytics(self, actor: User, date_from=None, date_to=None) -> list[dict]:
        """Per-team rollup (comparison table). Managers/OrgAdmins: whole org;
        others: just their teams."""
        visible = await self._visible_team_ids(actor)
        q = select(Team).filter(Team.organization_id == actor.organization_id,
                                Team.is_deleted == False, Team.status == "active")
        if visible is not None:
            if not visible:
                return []
            q = q.filter(Team.id.in_(visible))
        rows = list((await self.db.execute(q)).scalars().all())
        out = []
        for t in rows:
            member_ids = await self._member_ids(t.id)
            m = await self._rollup._metrics_for_members(actor.organization_id, member_ids, date_from, date_to)
            out.append({"team_id": str(t.id), "name": t.name, "member_count": len(member_ids),
                        "capacity": t.capacity, **m})
        out.sort(key=lambda x: -x["revenue"])
        return out

    # ---------- Calendar ----------
    async def calendar(self, actor: User, team_id: uuid.UUID, date_from: datetime, date_to: datetime) -> list[dict]:
        """Events + due tasks for all team members in a range (team calendar)."""
        t = await self._get(actor, team_id)
        await self._require_view(actor, t)
        member_ids = await self._member_ids(t.id)
        if not member_ids:
            return []
        names = await self._rollup._names(set(member_ids))
        out = []
        evs = list((await self.db.execute(select(CalendarEvent).filter(
            CalendarEvent.organization_id == actor.organization_id,
            CalendarEvent.is_deleted == False, CalendarEvent.assigned_user_id.in_(member_ids),
            CalendarEvent.start_at <= date_to, CalendarEvent.end_at >= date_from))).scalars().all())
        for e in evs:
            out.append({"type": "event", "id": str(e.id), "title": e.title, "start": e.start_at,
                        "end": e.end_at, "status": e.status, "event_type": e.event_type,
                        "user_id": str(e.assigned_user_id) if e.assigned_user_id else None,
                        "user_name": names.get(e.assigned_user_id, "")})
        tasks = list((await self.db.execute(select(Task).filter(
            Task.organization_id == actor.organization_id, Task.is_deleted == False,
            Task.assigned_user_id.in_(member_ids), Task.due_date.isnot(None),
            Task.due_date >= date_from, Task.due_date <= date_to))).scalars().all())
        for task in tasks:
            out.append({"type": "task", "id": str(task.id), "title": task.title,
                        "start": task.due_date, "end": task.due_date, "status": task.status,
                        "event_type": "Task",
                        "user_id": str(task.assigned_user_id) if task.assigned_user_id else None,
                        "user_name": names.get(task.assigned_user_id, "")})
        out.sort(key=lambda x: (x["start"] is None, x["start"]))
        return out

    # ---------- Assignment ----------
    async def _pick_least_loaded(self, org_id, member_ids: list[uuid.UUID]) -> uuid.UUID:
        """Least-loaded active member by open (unconverted) lead count."""
        rows = (await self.db.execute(select(Lead.assigned_user_id, func.count(Lead.id)).filter(
            Lead.organization_id == org_id, Lead.is_deleted == False,
            Lead.assigned_user_id.in_(member_ids),
            Lead.converted_contact_id.is_(None)).group_by(Lead.assigned_user_id))).all()
        load = {uid: n for uid, n in rows}
        return sorted(member_ids, key=lambda uid: (load.get(uid, 0), str(uid)))[0]

    async def _active_member_ids(self, actor: User, t: Team) -> list[uuid.UUID]:
        member_ids = await self._member_ids(t.id)
        if not member_ids:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Team has no members.")
        active = list((await self.db.execute(select(User.id).filter(
            User.id.in_(member_ids), User.is_active == True, User.is_deleted == False))).scalars().all())
        if not active:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Team has no active members.")
        return active

    async def assign_leads(self, actor: User, team_id: uuid.UUID, lead_ids: list[uuid.UUID],
                           strategy: str = "round_robin") -> dict:
        t = await self._get(actor, team_id)
        if not self._can_manage(actor) and not self._is_leader(actor, t):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN,
                                detail="Only a manager or the team leader can assign work to the team.")
        if strategy not in ("round_robin", "leader"):
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST,
                                detail="strategy must be round_robin or leader.")
        active = await self._active_member_ids(actor, t)
        leads = list((await self.db.execute(select(Lead).filter(
            Lead.id.in_(lead_ids), Lead.organization_id == actor.organization_id,
            Lead.is_deleted == False))).scalars().all())
        assigned_to: dict[uuid.UUID, int] = {}
        for lead in leads:
            if strategy == "leader" and t.team_leader_id:
                uid = t.team_leader_id
            else:
                uid = await self._pick_least_loaded(actor.organization_id, active)
            lead.assigned_user_id = uid
            self.db.add(lead)
            await self.db.flush()  # so the next _pick_least_loaded sees this assignment
            assigned_to[uid] = assigned_to.get(uid, 0) + 1
        for uid, n in assigned_to.items():
            if uid != actor.id:
                await self.notifier.create_notification(
                    organization_id=actor.organization_id, user_id=uid, category="team",
                    title="Leads assigned", body=f"{n} lead(s) assigned to you via team {t.name}.",
                    link_url="/leads", action_metadata={"team_id": str(t.id)})
        await self.audit.log_event(organization_id=actor.organization_id, actor_user_id=actor.id,
                                   action="TEAM_LEADS_ASSIGNED", resource_type="team", resource_id=str(t.id),
                                   action_metadata={"count": len(leads), "strategy": strategy})
        return {"assigned": len(leads),
                "distribution": {str(k): v for k, v in assigned_to.items()}}

    async def assign_tasks(self, actor: User, team_id: uuid.UUID, task_ids: list[uuid.UUID],
                           strategy: str = "round_robin") -> dict:
        t = await self._get(actor, team_id)
        if not self._can_manage(actor) and not self._is_leader(actor, t):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN,
                                detail="Only a manager or the team leader can assign work to the team.")
        if strategy not in ("round_robin", "leader"):
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST,
                                detail="strategy must be round_robin or leader.")
        active = await self._active_member_ids(actor, t)
        tasks = list((await self.db.execute(select(Task).filter(
            Task.id.in_(task_ids), Task.organization_id == actor.organization_id,
            Task.is_deleted == False))).scalars().all())
        # open-task load per member for round robin
        rows = (await self.db.execute(select(Task.assigned_user_id, func.count(Task.id)).filter(
            Task.organization_id == actor.organization_id, Task.is_deleted == False,
            Task.assigned_user_id.in_(active), Task.status.in_(["Todo", "InProgress"]))
            .group_by(Task.assigned_user_id))).all()
        load = {uid: n for uid, n in rows}
        assigned_to: dict[uuid.UUID, int] = {}
        for task in tasks:
            if strategy == "leader" and t.team_leader_id:
                uid = t.team_leader_id
            else:
                uid = sorted(active, key=lambda u: (load.get(u, 0), str(u)))[0]
            task.assigned_user_id = uid
            self.db.add(task)
            load[uid] = load.get(uid, 0) + 1
            assigned_to[uid] = assigned_to.get(uid, 0) + 1
        await self.db.flush()
        for uid, n in assigned_to.items():
            if uid != actor.id:
                await self.notifier.create_notification(
                    organization_id=actor.organization_id, user_id=uid, category="team",
                    title="Tasks assigned", body=f"{n} task(s) assigned to you via team {t.name}.",
                    link_url="/tasks", action_metadata={"team_id": str(t.id)})
        await self.audit.log_event(organization_id=actor.organization_id, actor_user_id=actor.id,
                                   action="TEAM_TASKS_ASSIGNED", resource_type="team", resource_id=str(t.id),
                                   action_metadata={"count": len(tasks), "strategy": strategy})
        return {"assigned": len(tasks),
                "distribution": {str(k): v for k, v in assigned_to.items()}}

    # ---------- Bulk ----------
    async def bulk_action(self, actor: User, team_ids: list[uuid.UUID], action: str) -> dict:
        self._require_manage(actor)
        if action not in ("archive", "activate", "delete"):
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST,
                                detail="action must be archive, activate or delete.")
        done = 0
        errors = []
        for tid in team_ids:
            try:
                if action == "delete":
                    await self.delete(actor, tid)
                else:
                    t = await self._get(actor, tid)
                    t.status = "active" if action == "activate" else "archived"
                    self.db.add(t)
                done += 1
            except HTTPException as e:
                errors.append({"team_id": str(tid), "error": e.detail})
        await self.db.flush()
        return {"processed": done, "errors": errors}

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
            existing = (await self.db.execute(select(Team).filter(
                Team.organization_id == actor.organization_id, Team.name == name,
                Team.is_deleted == False))).scalars().first()
            leader = None
            leader_email = (row.get("leader_email") or "").strip()
            if leader_email:
                leader = (await self.db.execute(select(User).filter(
                    User.organization_id == actor.organization_id, User.email == leader_email,
                    User.is_deleted == False))).scalars().first()
                if not leader:
                    errors.append({"row": i, "error": f"leader '{leader_email}' not found"})
            try:
                capacity = int(row["capacity"]) if (row.get("capacity") or "").strip() else None
            except ValueError:
                capacity = None
            if existing:
                existing.description = (row.get("description") or "").strip() or existing.description
                if capacity is not None:
                    existing.capacity = capacity
                if leader:
                    existing.team_leader_id = leader.id
                self.db.add(existing)
                updated += 1
            else:
                t = Team(organization_id=actor.organization_id, name=name,
                         code=(row.get("code") or "").strip() or None,
                         description=(row.get("description") or "").strip() or None,
                         team_leader_id=leader.id if leader else None, capacity=capacity,
                         status=(row.get("status") or "active").strip() or "active",
                         created_by=actor.id)
                self.db.add(t)
                await self.db.flush()
                if leader:
                    self.db.add(TeamMember(organization_id=actor.organization_id, team_id=t.id,
                                           user_id=leader.id, role_in_team="leader"))
                created += 1
        await self.db.flush()
        return {"created": created, "updated": updated, "skipped": skipped, "errors": errors}

    async def export_csv(self, actor: User) -> str:
        listing = await self.list(actor, limit=200)
        buf = io.StringIO()
        w = csv.writer(buf)
        w.writerow(["name", "code", "description", "status", "leader", "leader_email",
                    "department", "capacity", "member_count"])
        dept_names = {str(d.id): d.name for d in (await self.db.execute(select(Department).filter(
            Department.organization_id == actor.organization_id,
            Department.is_deleted == False))).scalars().all()}
        for t in listing["items"]:
            w.writerow([t["name"], t["code"] or "", t["description"] or "", t["status"],
                        t["leader_name"] or "", t["leader_email"] or "",
                        dept_names.get(t["department_id"] or "", ""),
                        t["capacity"] if t["capacity"] is not None else "", t["member_count"]])
        return buf.getvalue()

    # ---------- Reports ----------
    async def report(self, actor: User, date_from=None, date_to=None) -> dict:
        """Org-level team report: dashboard summary + per-team performance rows."""
        return {"summary": await self.dashboard(actor),
                "teams": await self.analytics(actor, date_from=date_from, date_to=date_to)}

    # ---------- helpers ----------
    async def _serialize(self, t: Team) -> dict:
        n = await self._member_count(t.id)
        leader_name = leader_email = None
        if t.team_leader_id:
            u = (await self.db.execute(select(User).filter(User.id == t.team_leader_id))).scalars().first()
            if u:
                leader_name = f"{u.first_name or ''} {u.last_name or ''}".strip() or u.email
                leader_email = u.email
        dept_name = None
        if t.department_id:
            dept_name = (await self.db.execute(select(Department.name).filter(
                Department.id == t.department_id))).scalar()
        return {"id": str(t.id), "organization_id": str(t.organization_id), "name": t.name,
                "code": t.code, "description": t.description,
                "team_leader_id": str(t.team_leader_id) if t.team_leader_id else None,
                "leader_name": leader_name, "leader_email": leader_email,
                "department_id": str(t.department_id) if t.department_id else None,
                "department_name": dept_name, "capacity": t.capacity, "status": t.status,
                "color": t.color, "member_count": n, "created_at": t.created_at}
