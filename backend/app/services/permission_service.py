"""Permission service.

Two layers live here:

1. The original static hierarchy helpers (verify_role_hierarchy /
   check_user_management_permission) — untouched, still used by user_service
   and the messaging modules. Base roles SuperAdmin/OrgAdmin/Manager/Employee
   and the runtime Team-Leader/Telecaller concepts keep working as before.

2. The custom-role overlay (instance methods): tenant-defined roles with a
   resource×action permission matrix, per-resource data scope
   (own|team|department|all), and field-level access. A user WITHOUT a
   custom_role_id is completely unaffected — enforcement no-ops and the
   legacy checks remain authoritative. Inheritance: a custom role starts
   from its base_role's default matrix; stored rows override cells.
   Per-plan defaults: resources whose gating feature is inactive for the
   tenant are denied in the effective matrix.
"""
from __future__ import annotations
import uuid
from fastapi import HTTPException, status
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User
from app.models.custom_role import CustomRole, RolePermission, FieldPermission
from app.models.team import TeamMember
from app.services.audit_service import AuditService

# ---------- Catalog ----------
RESOURCES = (
    "leads", "contacts", "companies", "customers", "tasks", "calendar",
    "communications", "calling", "sms", "whatsapp", "email", "templates",
    "campaigns", "notifications", "analytics", "departments", "teams",
    "branches", "territories", "attendance", "leave", "shifts", "performance",
    "targets", "approvals", "announcements", "workflows", "rules", "automation", "events", "queue", "scheduler", "users", "roles", "settings",
)
ACTIONS = ("view", "create", "edit", "delete", "export", "import", "assign", "bulk")
SCOPES = ("own", "team", "department", "all")
FIELD_ACCESS = ("read", "write", "hidden")
BASE_ROLES = ("Employee", "Manager", "OrgAdmin")

# Resources gated by a plan feature: if the tenant's plan lacks the feature,
# the effective matrix denies the resource regardless of the stored matrix.
RESOURCE_FEATURE_MAP = {
    "leads": "LEAD_MANAGEMENT",
    "sms": "SMS_MESSAGING",
    "whatsapp": "WHATSAPP_MESSAGING",
    "email": "EMAIL_MESSAGING",
    "campaigns": "CAMPAIGN_MANAGEMENT",
}

# Editable-field catalog per resource (drives the field-permission editor).
FIELD_CATALOG = {
    "leads": ["name", "email", "phone", "company_name", "value", "source", "status",
              "priority", "assigned_user_id", "notes", "tags"],
    "contacts": ["first_name", "last_name", "email", "phone", "company_id",
                 "assigned_user_id", "tags"],
    "companies": ["name", "industry", "website", "phone", "annual_revenue", "employee_count"],
    "customers": ["name", "email", "phone", "billing_address"],
    "tasks": ["title", "description", "status", "priority", "due_date", "assigned_user_id"],
    "users": ["first_name", "last_name", "email", "phone", "role", "reporting_to_id",
              "department_id", "custom_role_id"],
}

# Default matrix per base role (permission inheritance baseline). Shaped to
# mirror what the legacy role checks already allow, so a freshly created
# custom role behaves like its base role until edited.
_MANAGE = set(ACTIONS)
_CONTRIB = {"view", "create", "edit"}
_VIEW = {"view"}

DEFAULT_MATRIX: dict[str, dict[str, tuple[set, str]]] = {
    "OrgAdmin": {r: (set(ACTIONS), "all") for r in RESOURCES},
    "Manager": {
        **{r: (set(ACTIONS) - {"delete"}, "team") for r in RESOURCES},
        "leads": (set(ACTIONS), "team"),
        "contacts": (set(ACTIONS), "team"),
        "tasks": (set(ACTIONS), "team"),
        "teams": (set(ACTIONS) - {"delete"}, "team"),
        "departments": (_VIEW, "all"),
        "branches": (_VIEW, "all"),
        "territories": (_VIEW, "all"),
        "users": (_CONTRIB | {"view"}, "team"),
        "roles": (_VIEW, "all"),
        "settings": (_VIEW, "all"),
        "analytics": ({"view", "export"}, "team"),
    },
    "Employee": {
        **{r: (_CONTRIB, "own") for r in RESOURCES},
        "calendar": (_CONTRIB, "own"),
        "notifications": (_CONTRIB, "own"),
        "teams": (_VIEW, "own"),
        "departments": (_VIEW, "own"),
        "branches": (_VIEW, "own"),
        "territories": (_VIEW, "own"),
        "analytics": (set(), "own"),
        "users": (set(), "own"),
        "roles": (set(), "own"),
        "settings": (set(), "own"),
        "campaigns": (_VIEW, "own"),
    },
}
# SuperAdmin bypasses everything (platform owner).
DEFAULT_MATRIX["SuperAdmin"] = {r: (set(ACTIONS), "all") for r in RESOURCES}


class PermissionService:
    # ================= Legacy static hierarchy (unchanged) =================
    @staticmethod
    def verify_role_hierarchy(actor_role: str, target_role: str) -> bool:
        """
        Enforce hierarchical RBAC control.
        - OrgAdmin can manage any role.
        - Manager can only manage Employee.
        - Employee cannot manage anyone.
        """
        if actor_role == "OrgAdmin":
            return True
        if actor_role == "Manager":
            return target_role == "Employee"
        return False

    @staticmethod
    def check_user_management_permission(
        actor: User,
        target_user_role: str,
        target_reporting_to_id: uuid.UUID | None = None,
        is_tl: bool = False
    ) -> None:
        """
        Verify if the actor is active and has permissions to manipulate a target user with a given role.
        Raises 403 Forbidden on failure.
        """
        if not actor.is_active:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="User account is deactivated"
            )

        # If the actor is a Team Leader (is_tl=True), they can manage an Employee reporting to them.
        if actor.role == "Employee" and is_tl and target_user_role == "Employee" and target_reporting_to_id == actor.id:
            return

        if not PermissionService.verify_role_hierarchy(actor.role, target_user_role):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You do not have permission to manage this role level"
            )

    # ================= Custom-role overlay =================
    def __init__(self, db: AsyncSession):
        self.db = db
        self.audit = AuditService(db)

    def _require_admin(self, actor: User):
        if actor.role not in ("SuperAdmin", "OrgAdmin"):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN,
                                detail="Only an OrgAdmin can manage roles and permissions.")

    @staticmethod
    def catalog() -> dict:
        return {
            "resources": list(RESOURCES),
            "actions": list(ACTIONS),
            "scopes": list(SCOPES),
            "field_access": list(FIELD_ACCESS),
            "base_roles": list(BASE_ROLES),
            "fields": FIELD_CATALOG,
            "feature_gated": RESOURCE_FEATURE_MAP,
        }

    # ---------- CRUD ----------
    async def _get_role(self, actor: User, role_id: uuid.UUID) -> CustomRole:
        r = (await self.db.execute(select(CustomRole).filter(
            CustomRole.id == role_id, CustomRole.organization_id == actor.organization_id,
            CustomRole.is_deleted == False))).scalars().first()
        if not r:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Role not found")
        return r

    async def list_roles(self, actor: User, search: str | None = None,
                         status_filter: str | None = None) -> list[dict]:
        q = select(CustomRole).filter(CustomRole.organization_id == actor.organization_id,
                                      CustomRole.is_deleted == False)
        if search:
            q = q.filter(CustomRole.name.ilike(f"%{search}%"))
        if status_filter:
            q = q.filter(CustomRole.status == status_filter)
        rows = list((await self.db.execute(q.order_by(CustomRole.name.asc()))).scalars().all())
        counts = dict((await self.db.execute(
            select(User.custom_role_id, func.count(User.id))
            .filter(User.organization_id == actor.organization_id, User.is_deleted == False,
                    User.custom_role_id.isnot(None)).group_by(User.custom_role_id))).all())
        return [self._serialize_role(r, counts.get(r.id, 0)) for r in rows]

    async def create_role(self, actor: User, data: dict) -> dict:
        self._require_admin(actor)
        base_role = data.get("base_role", "Employee")
        if base_role not in BASE_ROLES:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST,
                                detail=f"base_role must be one of {list(BASE_ROLES)}")
        dup = (await self.db.execute(select(CustomRole.id).filter(
            CustomRole.organization_id == actor.organization_id, CustomRole.name == data["name"],
            CustomRole.is_deleted == False))).scalar()
        if dup:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT,
                                detail=f"Role '{data['name']}' already exists.")
        role = CustomRole(organization_id=actor.organization_id, name=data["name"],
                          description=data.get("description"), base_role=base_role,
                          created_by=actor.id)
        self.db.add(role)
        await self.db.flush()
        # Inheritance: seed the matrix from the base role's defaults so the new
        # role starts as an exact copy of what its base role can do.
        for resource, (actions, scope) in DEFAULT_MATRIX[base_role].items():
            for action in ACTIONS:
                self.db.add(RolePermission(
                    organization_id=actor.organization_id, role_id=role.id,
                    resource=resource, action=action, allowed=action in actions,
                    scope=scope if action in ("view", "edit", "delete") else None))
        await self.db.flush()
        await self.audit.log_event(
            organization_id=actor.organization_id, actor_user_id=actor.id,
            action="ROLE_CREATED", resource_type="role", resource_id=str(role.id),
            action_metadata={"name": role.name, "base_role": base_role})
        return self._serialize_role(role, 0)

    async def update_role(self, actor: User, role_id: uuid.UUID, data: dict) -> dict:
        self._require_admin(actor)
        role = await self._get_role(actor, role_id)
        changes = {}
        if "name" in data and data["name"] != role.name:
            dup = (await self.db.execute(select(CustomRole.id).filter(
                CustomRole.organization_id == actor.organization_id, CustomRole.name == data["name"],
                CustomRole.id != role.id, CustomRole.is_deleted == False))).scalar()
            if dup:
                raise HTTPException(status_code=status.HTTP_409_CONFLICT,
                                    detail=f"Role '{data['name']}' already exists.")
        for k in ("name", "description", "status"):
            if k in data and data[k] is not None and getattr(role, k) != data[k]:
                changes[k] = {"from": getattr(role, k), "to": data[k]}
                setattr(role, k, data[k])
        self.db.add(role)
        await self.db.flush()
        if changes:
            await self.audit.log_event(
                organization_id=actor.organization_id, actor_user_id=actor.id,
                action="ROLE_UPDATED", resource_type="role", resource_id=str(role.id),
                action_metadata={"name": role.name, "changes": changes})
        n = (await self.db.execute(select(func.count(User.id)).filter(
            User.custom_role_id == role.id, User.is_deleted == False))).scalar() or 0
        return self._serialize_role(role, n)

    async def delete_role(self, actor: User, role_id: uuid.UUID) -> None:
        self._require_admin(actor)
        role = await self._get_role(actor, role_id)
        n = (await self.db.execute(select(func.count(User.id)).filter(
            User.custom_role_id == role.id, User.is_deleted == False))).scalar() or 0
        if n:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT,
                                detail=f"Unassign {n} user(s) from this role first.")
        role.is_deleted = True
        self.db.add(role)
        await self.db.flush()
        await self.audit.log_event(
            organization_id=actor.organization_id, actor_user_id=actor.id,
            action="ROLE_DELETED", resource_type="role", resource_id=str(role.id),
            action_metadata={"name": role.name})

    # ---------- Matrix ----------
    async def get_role_detail(self, actor: User, role_id: uuid.UUID) -> dict:
        role = await self._get_role(actor, role_id)
        perms = list((await self.db.execute(select(RolePermission).filter(
            RolePermission.role_id == role.id, RolePermission.is_deleted == False))).scalars().all())
        fields = list((await self.db.execute(select(FieldPermission).filter(
            FieldPermission.role_id == role.id, FieldPermission.is_deleted == False))).scalars().all())
        n = (await self.db.execute(select(func.count(User.id)).filter(
            User.custom_role_id == role.id, User.is_deleted == False))).scalar() or 0
        matrix: dict = {}
        for p in perms:
            cell = matrix.setdefault(p.resource, {"actions": {}, "scope": None})
            cell["actions"][p.action] = p.allowed
            if p.action == "view" and p.scope:
                cell["scope"] = p.scope
        return {**self._serialize_role(role, n),
                "matrix": matrix,
                "field_permissions": [
                    {"resource": f.resource, "field_name": f.field_name, "access": f.access}
                    for f in fields]}

    async def set_matrix(self, actor: User, role_id: uuid.UUID, matrix: dict) -> dict:
        """Bulk-upsert matrix cells. `matrix` = {resource: {"actions": {action: bool}, "scope": str}}"""
        self._require_admin(actor)
        role = await self._get_role(actor, role_id)
        existing = {(p.resource, p.action): p for p in (await self.db.execute(
            select(RolePermission).filter(RolePermission.role_id == role.id,
                                          RolePermission.is_deleted == False))).scalars().all()}
        changed = []
        for resource, cell in matrix.items():
            if resource not in RESOURCES:
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST,
                                    detail=f"Unknown resource '{resource}'")
            scope = cell.get("scope")
            if scope is not None and scope not in SCOPES:
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST,
                                    detail=f"scope must be one of {list(SCOPES)}")
            if scope is not None:
                # scope applies to the whole resource: update every scope-bearing
                # row (view/edit/delete), not just the actions in this payload
                for scoped_action in ("view", "edit", "delete"):
                    p = existing.get((resource, scoped_action))
                    if p and p.scope != scope:
                        changed.append({"resource": resource, "action": scoped_action,
                                        "from": {"allowed": p.allowed, "scope": p.scope},
                                        "to": {"allowed": p.allowed, "scope": scope}})
                        p.scope = scope
                        self.db.add(p)
            for action, allowed in (cell.get("actions") or {}).items():
                if action not in ACTIONS:
                    raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST,
                                        detail=f"Unknown action '{action}'")
                allowed = bool(allowed)
                row_scope = scope if action in ("view", "edit", "delete") else None
                p = existing.get((resource, action))
                if p:
                    if p.allowed != allowed or (row_scope and p.scope != row_scope):
                        changed.append({"resource": resource, "action": action,
                                        "from": {"allowed": p.allowed, "scope": p.scope},
                                        "to": {"allowed": allowed, "scope": row_scope or p.scope}})
                        p.allowed = allowed
                        if row_scope:
                            p.scope = row_scope
                        self.db.add(p)
                else:
                    changed.append({"resource": resource, "action": action,
                                    "from": None, "to": {"allowed": allowed, "scope": row_scope}})
                    self.db.add(RolePermission(
                        organization_id=actor.organization_id, role_id=role.id,
                        resource=resource, action=action, allowed=allowed, scope=row_scope))
        await self.db.flush()
        if changed:
            await self.audit.log_event(
                organization_id=actor.organization_id, actor_user_id=actor.id,
                action="PERMISSION_CHANGED", resource_type="permission", resource_id=str(role.id),
                action_metadata={"role": role.name, "changes": changed[:100]})
        return await self.get_role_detail(actor, role_id)

    async def set_field_permissions(self, actor: User, role_id: uuid.UUID, items: list[dict]) -> dict:
        self._require_admin(actor)
        role = await self._get_role(actor, role_id)
        existing = {(f.resource, f.field_name): f for f in (await self.db.execute(
            select(FieldPermission).filter(FieldPermission.role_id == role.id,
                                           FieldPermission.is_deleted == False))).scalars().all()}
        changed = []
        for item in items:
            resource, field_name, access = item["resource"], item["field_name"], item["access"]
            if access not in FIELD_ACCESS:
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST,
                                    detail=f"access must be one of {list(FIELD_ACCESS)}")
            f = existing.get((resource, field_name))
            if f:
                if f.access != access:
                    changed.append({"resource": resource, "field": field_name,
                                    "from": f.access, "to": access})
                    f.access = access
                    self.db.add(f)
            else:
                changed.append({"resource": resource, "field": field_name, "from": None, "to": access})
                self.db.add(FieldPermission(organization_id=actor.organization_id, role_id=role.id,
                                            resource=resource, field_name=field_name, access=access))
        await self.db.flush()
        if changed:
            await self.audit.log_event(
                organization_id=actor.organization_id, actor_user_id=actor.id,
                action="FIELD_PERMISSION_CHANGED", resource_type="permission", resource_id=str(role.id),
                action_metadata={"role": role.name, "changes": changed[:100]})
        return await self.get_role_detail(actor, role_id)

    # ---------- Assignment ----------
    async def assign_role(self, actor: User, role_id: uuid.UUID, user_ids: list[uuid.UUID]) -> dict:
        self._require_admin(actor)
        role = await self._get_role(actor, role_id)
        users = list((await self.db.execute(select(User).filter(
            User.id.in_(user_ids), User.organization_id == actor.organization_id,
            User.is_deleted == False))).scalars().all())
        for u in users:
            if u.role in ("SuperAdmin", "OrgAdmin"):
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST,
                                    detail="Custom roles cannot be assigned to OrgAdmin/SuperAdmin users.")
            u.custom_role_id = role.id
            self.db.add(u)
        await self.db.flush()
        await self.audit.log_event(
            organization_id=actor.organization_id, actor_user_id=actor.id,
            action="ROLE_ASSIGNED", resource_type="role", resource_id=str(role.id),
            action_metadata={"role": role.name, "user_ids": [str(u.id) for u in users]})
        return {"assigned": len(users)}

    async def unassign_role(self, actor: User, role_id: uuid.UUID, user_ids: list[uuid.UUID]) -> dict:
        self._require_admin(actor)
        role = await self._get_role(actor, role_id)
        users = list((await self.db.execute(select(User).filter(
            User.id.in_(user_ids), User.custom_role_id == role.id,
            User.organization_id == actor.organization_id))).scalars().all())
        for u in users:
            u.custom_role_id = None
            self.db.add(u)
        await self.db.flush()
        await self.audit.log_event(
            organization_id=actor.organization_id, actor_user_id=actor.id,
            action="ROLE_UNASSIGNED", resource_type="role", resource_id=str(role.id),
            action_metadata={"role": role.name, "user_ids": [str(u.id) for u in users]})
        return {"unassigned": len(users)}

    async def users_for_role(self, actor: User, role_id: uuid.UUID) -> list[dict]:
        await self._get_role(actor, role_id)
        rows = list((await self.db.execute(select(User).filter(
            User.custom_role_id == role_id, User.organization_id == actor.organization_id,
            User.is_deleted == False).order_by(User.first_name.asc()))).scalars().all())
        return [{"id": str(u.id), "name": f"{u.first_name or ''} {u.last_name or ''}".strip() or u.email,
                 "email": u.email, "role": u.role, "is_active": u.is_active} for u in rows]

    # ---------- Effective permissions ----------
    async def effective_permissions(self, user: User) -> dict:
        """Full effective matrix for a user: base-role defaults (inheritance),
        minus plan-feature denials, overridden by custom-role rows."""
        base_role = user.role if user.role in DEFAULT_MATRIX else "Employee"
        custom_role = None
        if user.custom_role_id:
            custom_role = (await self.db.execute(select(CustomRole).filter(
                CustomRole.id == user.custom_role_id, CustomRole.is_deleted == False,
                CustomRole.status == "active"))).scalars().first()
            if custom_role and custom_role.base_role in DEFAULT_MATRIX and user.role != "SuperAdmin":
                base_role = custom_role.base_role
        matrix: dict = {}
        for resource, (actions, scope) in DEFAULT_MATRIX[base_role].items():
            matrix[resource] = {"actions": {a: a in actions for a in ACTIONS}, "scope": scope}
        fields: dict = {}
        if custom_role:
            perms = list((await self.db.execute(select(RolePermission).filter(
                RolePermission.role_id == custom_role.id,
                RolePermission.is_deleted == False))).scalars().all())
            for p in perms:
                cell = matrix.setdefault(p.resource, {"actions": {}, "scope": "own"})
                cell["actions"][p.action] = p.allowed
                if p.action == "view" and p.scope:
                    cell["scope"] = p.scope
            frows = list((await self.db.execute(select(FieldPermission).filter(
                FieldPermission.role_id == custom_role.id,
                FieldPermission.is_deleted == False))).scalars().all())
            for f in frows:
                fields.setdefault(f.resource, {})[f.field_name] = f.access
        # Per-plan defaults: deny feature-gated resources the tenant doesn't have.
        if user.role != "SuperAdmin" and user.organization_id:
            from app.dependencies.feature_guard import get_active_features
            active = await get_active_features(self.db, user.organization_id)
            for resource, feature in RESOURCE_FEATURE_MAP.items():
                if feature not in active and resource in matrix:
                    matrix[resource]["actions"] = {a: False for a in ACTIONS}
        return {"base_role": user.role,
                "custom_role": self._serialize_role(custom_role, 0) if custom_role else None,
                "matrix": matrix, "fields": fields}

    async def check(self, user: User, resource: str, action: str) -> bool:
        """Custom-role enforcement. Users without a custom role pass — the
        legacy role dependencies on each endpoint remain authoritative."""
        if user.role == "SuperAdmin" or not user.custom_role_id:
            return True
        eff = await self.effective_permissions(user)
        cell = eff["matrix"].get(resource)
        if not cell:
            return True
        return bool(cell["actions"].get(action, False))

    async def require(self, user: User, resource: str, action: str) -> None:
        if not await self.check(user, resource, action):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN,
                                detail=f"Your role does not permit '{action}' on {resource}.")

    async def scope_for(self, user: User, resource: str) -> str:
        """Effective data scope for a resource: own|team|department|all."""
        eff = await self.effective_permissions(user)
        cell = eff["matrix"].get(resource)
        return (cell or {}).get("scope") or "own"

    async def visible_user_ids(self, user: User, resource: str) -> list[uuid.UUID] | None:
        """Record-visibility helper: None = unrestricted (all); otherwise the
        list of user ids whose records the user may see for this resource."""
        scope = await self.scope_for(user, resource)
        if scope == "all" or user.role in ("SuperAdmin", "OrgAdmin"):
            return None
        if scope == "own":
            return [user.id]
        if scope == "department":
            if not user.department_id:
                return [user.id]
            rows = (await self.db.execute(select(User.id).filter(
                User.organization_id == user.organization_id, User.is_deleted == False,
                User.department_id == user.department_id))).scalars().all()
            return list(rows) or [user.id]
        # team scope: members of teams the user belongs to or leads, plus
        # the legacy reporting chain (downlines) for backward compatibility.
        team_ids = (await self.db.execute(select(TeamMember.team_id).filter(
            TeamMember.user_id == user.id, TeamMember.is_deleted == False))).scalars().all()
        ids: set[uuid.UUID] = {user.id}
        if team_ids:
            rows = (await self.db.execute(select(TeamMember.user_id).filter(
                TeamMember.team_id.in_(team_ids), TeamMember.is_deleted == False))).scalars().all()
            ids.update(rows)
        downlines = (await self.db.execute(select(User.id).filter(
            User.reporting_to_id == user.id, User.is_deleted == False))).scalars().all()
        ids.update(downlines)
        return list(ids)

    async def enforce_field_writes(self, user: User, resource: str, data: dict) -> None:
        """Server-side field-level write enforcement. No-ops unless the user
        has a custom role with restrictive field rows for this resource."""
        if user.role == "SuperAdmin" or not user.custom_role_id or not data:
            return
        rows = list((await self.db.execute(select(FieldPermission).filter(
            FieldPermission.role_id == user.custom_role_id, FieldPermission.resource == resource,
            FieldPermission.is_deleted == False))).scalars().all())
        if not rows:
            return
        blocked = [f.field_name for f in rows if f.access in ("read", "hidden") and f.field_name in data]
        if blocked:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN,
                                detail=f"Your role cannot modify field(s): {', '.join(sorted(blocked))}")

    # ---------- Audit trail ----------
    async def permission_audit(self, actor: User, limit: int = 100) -> list[dict]:
        self._require_admin(actor)
        from app.models.audit_log import AuditLog
        rows = list((await self.db.execute(select(AuditLog).filter(
            AuditLog.organization_id == actor.organization_id,
            AuditLog.resource_type.in_(["role", "permission"]))
            .order_by(AuditLog.created_at.desc()).limit(limit))).scalars().all())
        names = {}
        actor_ids = {r.actor_user_id for r in rows if r.actor_user_id}
        if actor_ids:
            res = await self.db.execute(select(User.id, User.first_name, User.last_name, User.email)
                                        .filter(User.id.in_(actor_ids)))
            names = {uid: (f"{fn or ''} {ln or ''}".strip() or em) for uid, fn, ln, em in res.all()}
        return [{"id": str(r.id), "action": r.action, "resource_type": r.resource_type,
                 "resource_id": r.resource_id,
                 "actor_name": names.get(r.actor_user_id, ""),
                 "metadata": r.action_metadata, "created_at": r.created_at} for r in rows]

    # ---------- helpers ----------
    @staticmethod
    def _serialize_role(r: CustomRole | None, user_count: int) -> dict:
        if r is None:
            return {}
        return {"id": str(r.id), "organization_id": str(r.organization_id), "name": r.name,
                "description": r.description, "base_role": r.base_role, "is_system": r.is_system,
                "status": r.status, "user_count": user_count, "created_at": r.created_at}
