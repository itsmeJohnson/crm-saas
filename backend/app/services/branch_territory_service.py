"""Branch & Territory Management service.

Two related concerns share one service (like a small subsystem):

* Territories — a self-referential geographic hierarchy (region > zone > city >
  area), mirroring the Department tree pattern (parent cycle guard, tree view).
* Branches — physical offices with a manager, address and owning territory.
* PIN-code mapping — territory_pincodes maps postal codes to a territory (and
  optionally a branch). This drives automatic lead territory assignment:
  a lead's pin_code (or, failing that, its city) resolves to a territory+branch.

Performance/dashboards roll up Leads by branch_id / territory_id, reusing the
same converted-status + revenue conventions as the Department module.
"""
from __future__ import annotations
import csv
import io
import uuid
from datetime import datetime, timezone
from fastapi import HTTPException, status
from sqlalchemy import select, func, or_
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User
from app.models.lead import Lead
from app.models.activity import Activity
from app.models.branch import Territory, Branch, TerritoryPincode
from app.services.audit_service import AuditService
from app.services.notification_service import NotificationService

TERRITORY_LEVELS = ("region", "zone", "city", "area")
CONVERTED_LEAD_STATUSES = {"Won", "Converted", "Customer"}


def _now() -> datetime:
    return datetime.now(timezone.utc)


class BranchTerritoryService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.audit = AuditService(db)
        self.notifier = NotificationService(db)

    # ---------- permissions ----------
    def _can_manage(self, actor: User) -> bool:
        return actor.role in ("SuperAdmin", "OrgAdmin")

    def _require_manage(self, actor: User):
        if not self._can_manage(actor):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN,
                                detail="Only an OrgAdmin can manage branches and territories.")

    # ================= Territories =================
    async def _get_territory(self, actor: User, territory_id: uuid.UUID) -> Territory:
        t = (await self.db.execute(select(Territory).filter(
            Territory.id == territory_id, Territory.organization_id == actor.organization_id,
            Territory.is_deleted == False))).scalars().first()
        if not t:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Territory not found")
        return t

    async def _validate_territory_code(self, actor: User, code: str | None, exclude_id=None):
        if not code:
            return
        q = select(Territory.id).filter(
            Territory.organization_id == actor.organization_id, Territory.code == code,
            Territory.is_deleted == False)
        if exclude_id:
            q = q.filter(Territory.id != exclude_id)
        if (await self.db.execute(q)).scalar():
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=f"Territory code '{code}' already exists.")

    async def _validate_manager(self, actor: User, manager_user_id):
        if manager_user_id:
            ok = (await self.db.execute(select(User.id).filter(
                User.id == manager_user_id, User.organization_id == actor.organization_id,
                User.is_deleted == False))).scalar()
            if not ok:
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Manager user not found in this org.")

    async def _validate_territory_parent(self, actor: User, parent_id, self_id=None):
        """Ensure parent exists and no cycle results (walk up the parent chain)."""
        if not parent_id:
            return
        if self_id and parent_id == self_id:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="A territory cannot be its own parent.")
        seen = set()
        cur = parent_id
        while cur:
            if self_id and cur == self_id:
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Circular territory hierarchy is not allowed.")
            if cur in seen:
                break
            seen.add(cur)
            row = (await self.db.execute(select(Territory.parent_id).filter(
                Territory.id == cur, Territory.organization_id == actor.organization_id,
                Territory.is_deleted == False))).first()
            if not row:
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Parent territory not found.")
            cur = row[0]

    async def create_territory(self, actor: User, data: dict) -> dict:
        self._require_manage(actor)
        level = data.get("level", "region")
        if level not in TERRITORY_LEVELS:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST,
                                detail=f"level must be one of {list(TERRITORY_LEVELS)}")
        await self._validate_territory_code(actor, data.get("code"))
        await self._validate_manager(actor, data.get("manager_user_id"))
        await self._validate_territory_parent(actor, data.get("parent_id"))
        t = Territory(organization_id=actor.organization_id, name=data["name"], code=data.get("code"),
                      level=level, parent_id=data.get("parent_id"),
                      manager_user_id=data.get("manager_user_id"), description=data.get("description"),
                      status=data.get("status", "active"), color=data.get("color"), created_by=actor.id)
        self.db.add(t)
        await self.db.flush()
        await self.db.refresh(t)
        if t.manager_user_id:
            await self.notifier.create_notification(
                organization_id=actor.organization_id, user_id=t.manager_user_id, category="territory",
                title="You manage a territory", body=f"You were assigned as manager of {t.name}.",
                link_url=f"/branches?territoryId={t.id}", action_metadata={"territory_id": str(t.id)})
        await self.audit.log_event(organization_id=actor.organization_id, actor_user_id=actor.id,
                                   action="TERRITORY_CREATED", resource_type="territory", resource_id=str(t.id),
                                   action_metadata={"name": t.name, "level": level})
        return await self._serialize_territory(t)

    async def update_territory(self, actor: User, territory_id: uuid.UUID, data: dict) -> dict:
        self._require_manage(actor)
        t = await self._get_territory(actor, territory_id)
        if "level" in data and data["level"] not in TERRITORY_LEVELS:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST,
                                detail=f"level must be one of {list(TERRITORY_LEVELS)}")
        if "code" in data:
            await self._validate_territory_code(actor, data.get("code"), exclude_id=t.id)
        if "manager_user_id" in data:
            await self._validate_manager(actor, data.get("manager_user_id"))
        if "parent_id" in data and data["parent_id"]:
            await self._validate_territory_parent(actor, data["parent_id"], self_id=t.id)
        for k in ("name", "code", "level", "parent_id", "manager_user_id", "description", "status", "color"):
            if k in data:
                setattr(t, k, data[k])
        self.db.add(t)
        await self.db.flush()
        await self.db.refresh(t)
        return await self._serialize_territory(t)

    async def delete_territory(self, actor: User, territory_id: uuid.UUID) -> None:
        self._require_manage(actor)
        t = await self._get_territory(actor, territory_id)
        # block while sub-territories, branches or pincode mappings reference it
        children = (await self.db.execute(select(func.count(Territory.id)).filter(
            Territory.parent_id == t.id, Territory.is_deleted == False))).scalar() or 0
        branches = (await self.db.execute(select(func.count(Branch.id)).filter(
            Branch.territory_id == t.id, Branch.is_deleted == False))).scalar() or 0
        pins = (await self.db.execute(select(func.count(TerritoryPincode.id)).filter(
            TerritoryPincode.territory_id == t.id, TerritoryPincode.is_deleted == False))).scalar() or 0
        if children or branches or pins:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT,
                                detail=f"Reassign {children} sub-territory(ies), {branches} branch(es) and {pins} PIN mapping(s) first.")
        t.is_deleted = True
        self.db.add(t)
        await self.db.flush()
        await self.audit.log_event(organization_id=actor.organization_id, actor_user_id=actor.id,
                                   action="TERRITORY_DELETED", resource_type="territory", resource_id=str(t.id),
                                   action_metadata={"name": t.name})

    async def list_territories(self, actor: User, search=None, level=None, status_filter=None,
                               parent_id=None) -> list[dict]:
        q = select(Territory).filter(Territory.organization_id == actor.organization_id,
                                     Territory.is_deleted == False)
        if level:
            q = q.filter(Territory.level == level)
        if status_filter:
            q = q.filter(Territory.status == status_filter)
        if parent_id:
            q = q.filter(Territory.parent_id == parent_id)
        if search:
            s = f"%{search}%"
            q = q.filter(or_(Territory.name.ilike(s), Territory.code.ilike(s)))
        rows = list((await self.db.execute(q.order_by(Territory.level.asc(), Territory.name.asc()))).scalars().all())
        return [await self._serialize_territory(t) for t in rows]

    async def territory_tree(self, actor: User) -> list[dict]:
        rows = list((await self.db.execute(select(Territory).filter(
            Territory.organization_id == actor.organization_id, Territory.is_deleted == False)
            .order_by(Territory.name.asc()))).scalars().all())
        nodes = {t.id: {"id": str(t.id), "name": t.name, "code": t.code, "level": t.level,
                        "status": t.status, "manager_user_id": str(t.manager_user_id) if t.manager_user_id else None,
                        "children": []} for t in rows}
        roots = []
        for t in rows:
            node = nodes[t.id]
            if t.parent_id and t.parent_id in nodes:
                nodes[t.parent_id]["children"].append(node)
            else:
                roots.append(node)
        return roots

    async def locations(self, actor: User) -> dict:
        """Distinct regions / zones / cities for location filters."""
        rows = list((await self.db.execute(select(Territory.level, Territory.id, Territory.name).filter(
            Territory.organization_id == actor.organization_id, Territory.is_deleted == False,
            Territory.status == "active").order_by(Territory.name.asc()))).all())
        out: dict[str, list] = {"regions": [], "zones": [], "cities": [], "areas": []}
        key = {"region": "regions", "zone": "zones", "city": "cities", "area": "areas"}
        for level, tid, name in rows:
            out.get(key.get(level, "areas"), out["areas"]).append({"id": str(tid), "name": name})
        return out

    # ================= Branches =================
    async def _get_branch(self, actor: User, branch_id: uuid.UUID) -> Branch:
        b = (await self.db.execute(select(Branch).filter(
            Branch.id == branch_id, Branch.organization_id == actor.organization_id,
            Branch.is_deleted == False))).scalars().first()
        if not b:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Branch not found")
        return b

    async def get_branch(self, actor: User, branch_id: uuid.UUID) -> dict:
        return await self._serialize_branch(await self._get_branch(actor, branch_id))

    async def _validate_branch_code(self, actor: User, code: str | None, exclude_id=None):
        if not code:
            return
        q = select(Branch.id).filter(
            Branch.organization_id == actor.organization_id, Branch.code == code, Branch.is_deleted == False)
        if exclude_id:
            q = q.filter(Branch.id != exclude_id)
        if (await self.db.execute(q)).scalar():
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=f"Branch code '{code}' already exists.")

    async def _validate_branch_territory(self, actor: User, territory_id):
        if territory_id:
            ok = (await self.db.execute(select(Territory.id).filter(
                Territory.id == territory_id, Territory.organization_id == actor.organization_id,
                Territory.is_deleted == False))).scalar()
            if not ok:
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Territory not found in this org.")

    async def create_branch(self, actor: User, data: dict) -> dict:
        self._require_manage(actor)
        await self._validate_branch_code(actor, data.get("code"))
        await self._validate_manager(actor, data.get("branch_manager_id"))
        await self._validate_branch_territory(actor, data.get("territory_id"))
        b = Branch(organization_id=actor.organization_id, name=data["name"], code=data.get("code"),
                   branch_manager_id=data.get("branch_manager_id"), territory_id=data.get("territory_id"),
                   address_line=data.get("address_line"), city=data.get("city"), state=data.get("state"),
                   country=data.get("country"), pin_code=data.get("pin_code"), phone=data.get("phone"),
                   email=data.get("email"), is_head_office=bool(data.get("is_head_office", False)),
                   status=data.get("status", "active"), created_by=actor.id)
        self.db.add(b)
        await self.db.flush()
        await self.db.refresh(b)
        if b.branch_manager_id:
            await self.notifier.create_notification(
                organization_id=actor.organization_id, user_id=b.branch_manager_id, category="branch",
                title="You manage a branch", body=f"You were assigned as manager of {b.name}.",
                link_url=f"/branches?branchId={b.id}", action_metadata={"branch_id": str(b.id)})
        await self.audit.log_event(organization_id=actor.organization_id, actor_user_id=actor.id,
                                   action="BRANCH_CREATED", resource_type="branch", resource_id=str(b.id),
                                   action_metadata={"name": b.name})
        return await self._serialize_branch(b)

    async def update_branch(self, actor: User, branch_id: uuid.UUID, data: dict) -> dict:
        self._require_manage(actor)
        b = await self._get_branch(actor, branch_id)
        if "code" in data:
            await self._validate_branch_code(actor, data.get("code"), exclude_id=b.id)
        if "branch_manager_id" in data:
            await self._validate_manager(actor, data.get("branch_manager_id"))
        if "territory_id" in data:
            await self._validate_branch_territory(actor, data.get("territory_id"))
        prev_manager = b.branch_manager_id
        for k in ("name", "code", "branch_manager_id", "territory_id", "address_line", "city", "state",
                  "country", "pin_code", "phone", "email", "is_head_office", "status"):
            if k in data:
                setattr(b, k, data[k])
        self.db.add(b)
        await self.db.flush()
        await self.db.refresh(b)
        if b.branch_manager_id and b.branch_manager_id != prev_manager:
            await self.notifier.create_notification(
                organization_id=actor.organization_id, user_id=b.branch_manager_id, category="branch",
                title="You manage a branch", body=f"You were assigned as manager of {b.name}.",
                link_url=f"/branches?branchId={b.id}", action_metadata={"branch_id": str(b.id)})
        return await self._serialize_branch(b)

    async def delete_branch(self, actor: User, branch_id: uuid.UUID) -> None:
        self._require_manage(actor)
        b = await self._get_branch(actor, branch_id)
        lead_count = (await self.db.execute(select(func.count(Lead.id)).filter(
            Lead.branch_id == b.id, Lead.is_deleted == False))).scalar() or 0
        if lead_count:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT,
                                detail=f"{lead_count} lead(s) are assigned to this branch. Reassign them first or archive the branch.")
        # detach any pincode mappings that point to this branch
        pins = list((await self.db.execute(select(TerritoryPincode).filter(
            TerritoryPincode.branch_id == b.id, TerritoryPincode.is_deleted == False))).scalars().all())
        for p in pins:
            p.branch_id = None
            self.db.add(p)
        b.is_deleted = True
        self.db.add(b)
        await self.db.flush()
        await self.audit.log_event(organization_id=actor.organization_id, actor_user_id=actor.id,
                                   action="BRANCH_DELETED", resource_type="branch", resource_id=str(b.id),
                                   action_metadata={"name": b.name})

    async def list_branches(self, actor: User, search=None, status_filter=None, territory_id=None,
                            city=None, manager_id=None, skip=0, limit=100) -> dict:
        q = select(Branch).filter(Branch.organization_id == actor.organization_id, Branch.is_deleted == False)
        if status_filter:
            q = q.filter(Branch.status == status_filter)
        if territory_id:
            q = q.filter(Branch.territory_id == territory_id)
        if city:
            q = q.filter(Branch.city.ilike(f"%{city}%"))
        if manager_id:
            q = q.filter(Branch.branch_manager_id == manager_id)
        if search:
            s = f"%{search}%"
            q = q.filter(or_(Branch.name.ilike(s), Branch.code.ilike(s), Branch.city.ilike(s), Branch.pin_code.ilike(s)))
        total = (await self.db.execute(select(func.count()).select_from(q.subquery()))).scalar() or 0
        rows = list((await self.db.execute(q.order_by(Branch.name.asc()).offset(skip).limit(limit))).scalars().all())
        return {"items": [await self._serialize_branch(b) for b in rows], "total": total}

    # ================= PIN-code mapping =================
    async def list_pincodes(self, actor: User, search=None, territory_id=None, skip=0, limit=200) -> dict:
        q = select(TerritoryPincode).filter(TerritoryPincode.organization_id == actor.organization_id,
                                            TerritoryPincode.is_deleted == False)
        if territory_id:
            q = q.filter(TerritoryPincode.territory_id == territory_id)
        if search:
            s = f"%{search}%"
            q = q.filter(or_(TerritoryPincode.pin_code.ilike(s), TerritoryPincode.city.ilike(s)))
        total = (await self.db.execute(select(func.count()).select_from(q.subquery()))).scalar() or 0
        rows = list((await self.db.execute(q.order_by(TerritoryPincode.pin_code.asc()).offset(skip).limit(limit))).scalars().all())
        names = await self._territory_names({r.territory_id for r in rows})
        bnames = await self._branch_names({r.branch_id for r in rows if r.branch_id})
        items = [{"id": str(r.id), "pin_code": r.pin_code, "city": r.city,
                  "territory_id": str(r.territory_id), "territory_name": names.get(r.territory_id),
                  "branch_id": str(r.branch_id) if r.branch_id else None,
                  "branch_name": bnames.get(r.branch_id) if r.branch_id else None} for r in rows]
        return {"items": items, "total": total}

    async def upsert_pincode(self, actor: User, data: dict) -> dict:
        self._require_manage(actor)
        pin = (data.get("pin_code") or "").strip()
        if not pin:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="pin_code is required.")
        await self._validate_branch_territory(actor, data.get("territory_id"))  # reuse existence check
        territory_id = data.get("territory_id")
        if not territory_id:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="territory_id is required.")
        branch_id = data.get("branch_id")
        if branch_id:
            await self._get_branch(actor, branch_id)
        existing = (await self.db.execute(select(TerritoryPincode).filter(
            TerritoryPincode.organization_id == actor.organization_id, TerritoryPincode.pin_code == pin,
            TerritoryPincode.is_deleted == False))).scalars().first()
        if existing:
            existing.territory_id = territory_id
            existing.branch_id = branch_id
            existing.city = data.get("city") or existing.city
            self.db.add(existing)
            row = existing
        else:
            row = TerritoryPincode(organization_id=actor.organization_id, pin_code=pin, city=data.get("city"),
                                   territory_id=territory_id, branch_id=branch_id, created_by=actor.id)
            self.db.add(row)
        await self.db.flush()
        await self.db.refresh(row)
        return {"id": str(row.id), "pin_code": row.pin_code, "city": row.city,
                "territory_id": str(row.territory_id), "branch_id": str(row.branch_id) if row.branch_id else None}

    async def delete_pincode(self, actor: User, pincode_id: uuid.UUID) -> None:
        self._require_manage(actor)
        row = (await self.db.execute(select(TerritoryPincode).filter(
            TerritoryPincode.id == pincode_id, TerritoryPincode.organization_id == actor.organization_id,
            TerritoryPincode.is_deleted == False))).scalars().first()
        if not row:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="PIN mapping not found")
        row.is_deleted = True
        self.db.add(row)
        await self.db.flush()

    async def import_pincodes(self, actor: User, content: bytes) -> dict:
        """CSV columns: pin_code, city, territory_code, branch_code (last two optional)."""
        self._require_manage(actor)
        text = content.decode("utf-8-sig", errors="replace")
        reader = csv.DictReader(io.StringIO(text))
        # preload code→id maps for the org
        terr = {c: i for i, c in (await self.db.execute(select(Territory.id, Territory.code).filter(
            Territory.organization_id == actor.organization_id, Territory.is_deleted == False,
            Territory.code.isnot(None)))).all()}
        branch = {c: i for i, c in (await self.db.execute(select(Branch.id, Branch.code).filter(
            Branch.organization_id == actor.organization_id, Branch.is_deleted == False,
            Branch.code.isnot(None)))).all()}
        created = updated = skipped = 0
        errors = []
        for i, r in enumerate(reader, start=2):
            pin = (r.get("pin_code") or "").strip()
            tcode = (r.get("territory_code") or "").strip()
            if not pin or not tcode:
                skipped += 1
                continue
            tid = terr.get(tcode)
            if not tid:
                errors.append({"row": i, "error": f"territory_code '{tcode}' not found"})
                continue
            bid = branch.get((r.get("branch_code") or "").strip()) if (r.get("branch_code") or "").strip() else None
            existing = (await self.db.execute(select(TerritoryPincode).filter(
                TerritoryPincode.organization_id == actor.organization_id, TerritoryPincode.pin_code == pin,
                TerritoryPincode.is_deleted == False))).scalars().first()
            if existing:
                existing.territory_id = tid
                existing.branch_id = bid
                existing.city = (r.get("city") or "").strip() or existing.city
                self.db.add(existing)
                updated += 1
            else:
                self.db.add(TerritoryPincode(organization_id=actor.organization_id, pin_code=pin,
                                             city=(r.get("city") or "").strip() or None, territory_id=tid,
                                             branch_id=bid, created_by=actor.id))
                created += 1
        await self.db.flush()
        return {"created": created, "updated": updated, "skipped": skipped, "errors": errors}

    # ================= Lead territory assignment =================
    async def resolve_for_lead(self, org_id: uuid.UUID, pin_code: str | None, city: str | None) -> dict | None:
        """Resolve a (territory_id, branch_id) for a lead by PIN first, then city.
        Returns None if nothing maps. Safe to call for any lead."""
        pin = (pin_code or "").strip()
        if pin:
            row = (await self.db.execute(select(TerritoryPincode).filter(
                TerritoryPincode.organization_id == org_id, TerritoryPincode.pin_code == pin,
                TerritoryPincode.is_deleted == False))).scalars().first()
            if row:
                branch_id = row.branch_id
                if branch_id is None:
                    branch_id = (await self.db.execute(select(Branch.id).filter(
                        Branch.organization_id == org_id, Branch.territory_id == row.territory_id,
                        Branch.is_deleted == False, Branch.status == "active").limit(1))).scalar()
                return {"territory_id": row.territory_id, "branch_id": branch_id}
        city_clean = (city or "").strip()
        if city_clean:
            # a pincode mapping tagged with this city
            row = (await self.db.execute(select(TerritoryPincode).filter(
                TerritoryPincode.organization_id == org_id, TerritoryPincode.city.ilike(city_clean),
                TerritoryPincode.is_deleted == False).limit(1))).scalars().first()
            if row:
                return {"territory_id": row.territory_id, "branch_id": row.branch_id}
            # a city-level territory by name
            terr = (await self.db.execute(select(Territory.id).filter(
                Territory.organization_id == org_id, Territory.level == "city",
                Territory.name.ilike(city_clean), Territory.is_deleted == False,
                Territory.status == "active").limit(1))).scalar()
            if terr:
                branch_id = (await self.db.execute(select(Branch.id).filter(
                    Branch.organization_id == org_id, Branch.territory_id == terr,
                    Branch.is_deleted == False, Branch.status == "active").limit(1))).scalar()
                return {"territory_id": terr, "branch_id": branch_id}
            # a branch located in this city
            branch = (await self.db.execute(select(Branch).filter(
                Branch.organization_id == org_id, Branch.city.ilike(city_clean),
                Branch.is_deleted == False, Branch.status == "active").limit(1))).scalars().first()
            if branch:
                return {"territory_id": branch.territory_id, "branch_id": branch.id}
        return None

    async def apply_resolution_to_lead_data(self, org_id: uuid.UUID, lead_data: dict) -> None:
        """Fill territory_id/branch_id into a lead payload if unset and resolvable.
        Best-effort and backward-compatible: only fills NULLs, never overwrites."""
        if lead_data.get("territory_id") and lead_data.get("branch_id"):
            return
        resolved = await self.resolve_for_lead(org_id, lead_data.get("pin_code"), lead_data.get("city"))
        if not resolved:
            return
        if not lead_data.get("territory_id") and resolved.get("territory_id"):
            lead_data["territory_id"] = resolved["territory_id"]
        if not lead_data.get("branch_id") and resolved.get("branch_id"):
            lead_data["branch_id"] = resolved["branch_id"]

    async def assign_leads(self, actor: User, lead_ids: list[uuid.UUID], branch_id=None,
                           territory_id=None, auto: bool = False) -> dict:
        """Assign a branch/territory to leads — either explicitly or auto-resolved
        from each lead's pin_code/city."""
        self._require_manage(actor)
        if not auto and not branch_id and not territory_id:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST,
                                detail="Provide branch_id/territory_id, or set auto=true.")
        if branch_id:
            await self._get_branch(actor, branch_id)
        if territory_id:
            await self._get_territory(actor, territory_id)
        leads = list((await self.db.execute(select(Lead).filter(
            Lead.id.in_(lead_ids), Lead.organization_id == actor.organization_id,
            Lead.is_deleted == False))).scalars().all())
        assigned = 0
        unresolved = 0
        per_branch: dict[uuid.UUID, int] = {}
        for lead in leads:
            tid, bid = territory_id, branch_id
            if auto:
                resolved = await self.resolve_for_lead(actor.organization_id, lead.pin_code, lead.city)
                if not resolved:
                    unresolved += 1
                    continue
                tid = resolved.get("territory_id")
                bid = resolved.get("branch_id")
            if tid:
                lead.territory_id = tid
            if bid:
                lead.branch_id = bid
                per_branch[bid] = per_branch.get(bid, 0) + 1
            self.db.add(lead)
            assigned += 1
        await self.db.flush()
        # notify branch managers of inflow
        for bid, n in per_branch.items():
            mgr = (await self.db.execute(select(Branch.branch_manager_id).filter(Branch.id == bid))).scalar()
            if mgr and mgr != actor.id:
                await self.notifier.create_notification(
                    organization_id=actor.organization_id, user_id=mgr, category="branch",
                    title="Leads routed to your branch", body=f"{n} lead(s) assigned to your branch.",
                    link_url="/leads", action_metadata={"branch_id": str(bid)})
        await self.audit.log_event(organization_id=actor.organization_id, actor_user_id=actor.id,
                                   action="LEADS_TERRITORY_ASSIGNED", resource_type="branch",
                                   resource_id=str(branch_id) if branch_id else None,
                                   action_metadata={"count": assigned, "auto": auto})
        return {"assigned": assigned, "unresolved": unresolved}

    # ================= Dashboards / performance / reports =================
    async def _lead_metrics(self, org_id, *, branch_id=None, territory_id=None, date_from=None, date_to=None) -> dict:
        q = select(Lead).filter(Lead.organization_id == org_id, Lead.is_deleted == False)
        if branch_id:
            q = q.filter(Lead.branch_id == branch_id)
        if territory_id:
            q = q.filter(Lead.territory_id == territory_id)
        if date_from is not None:
            q = q.filter(Lead.created_at >= date_from)
        if date_to is not None:
            q = q.filter(Lead.created_at <= date_to)
        leads = list((await self.db.execute(q)).scalars().all())
        total = len(leads)
        converted = 0
        revenue = 0.0
        for l in leads:
            if l.converted_contact_id is not None or l.status in CONVERTED_LEAD_STATUSES:
                converted += 1
                if l.value:
                    revenue += float(l.value)
        # activities on those leads
        activities = 0
        if leads:
            lead_ids = [l.id for l in leads]
            activities = (await self.db.execute(select(func.count(Activity.id)).filter(
                Activity.organization_id == org_id, Activity.is_deleted == False,
                Activity.lead_id.in_(lead_ids)))).scalar() or 0
        return {"leads": total, "converted": converted,
                "conversion_rate": round(converted * 100 / total, 1) if total else 0.0,
                "revenue": round(revenue, 2), "activities": activities}

    async def branch_performance(self, actor: User, branch_id: uuid.UUID, date_from=None, date_to=None) -> dict:
        b = await self._get_branch(actor, branch_id)
        metrics = await self._lead_metrics(actor.organization_id, branch_id=branch_id,
                                           date_from=date_from, date_to=date_to)
        # status breakdown
        rows = (await self.db.execute(select(Lead.status, func.count(Lead.id)).filter(
            Lead.organization_id == actor.organization_id, Lead.is_deleted == False,
            Lead.branch_id == branch_id).group_by(Lead.status))).all()
        return {"branch_id": str(b.id), "name": b.name, "metrics": metrics,
                "by_status": [{"status": s, "count": n} for s, n in rows]}

    async def dashboard(self, actor: User) -> dict:
        branches = list((await self.db.execute(select(Branch).filter(
            Branch.organization_id == actor.organization_id, Branch.is_deleted == False))).scalars().all())
        active = [b for b in branches if b.status == "active"]
        terr_total = (await self.db.execute(select(func.count(Territory.id)).filter(
            Territory.organization_id == actor.organization_id, Territory.is_deleted == False))).scalar() or 0
        pin_total = (await self.db.execute(select(func.count(TerritoryPincode.id)).filter(
            TerritoryPincode.organization_id == actor.organization_id, TerritoryPincode.is_deleted == False))).scalar() or 0
        unmapped = (await self.db.execute(select(func.count(Lead.id)).filter(
            Lead.organization_id == actor.organization_id, Lead.is_deleted == False,
            Lead.branch_id.is_(None)))).scalar() or 0
        # top branches by lead count
        rows = (await self.db.execute(select(Lead.branch_id, func.count(Lead.id)).filter(
            Lead.organization_id == actor.organization_id, Lead.is_deleted == False,
            Lead.branch_id.isnot(None)).group_by(Lead.branch_id))).all()
        counts = {bid: n for bid, n in rows}
        bnames = {b.id: b.name for b in branches}
        top = sorted([{"id": str(bid), "name": bnames.get(bid, "?"), "lead_count": n}
                      for bid, n in counts.items()], key=lambda x: -x["lead_count"])[:5]
        return {"total_branches": len(branches), "active_branches": len(active),
                "archived_branches": len(branches) - len(active), "total_territories": terr_total,
                "mapped_pincodes": pin_total, "unmapped_leads": unmapped, "top_branches": top}

    async def branch_analytics(self, actor: User, date_from=None, date_to=None) -> list[dict]:
        """Per-branch comparison table (branch report)."""
        branches = list((await self.db.execute(select(Branch).filter(
            Branch.organization_id == actor.organization_id, Branch.is_deleted == False,
            Branch.status == "active"))).scalars().all())
        out = []
        mgr_names = await self._user_names({b.branch_manager_id for b in branches if b.branch_manager_id})
        for b in branches:
            m = await self._lead_metrics(actor.organization_id, branch_id=b.id, date_from=date_from, date_to=date_to)
            out.append({"branch_id": str(b.id), "name": b.name, "city": b.city,
                        "manager_name": mgr_names.get(b.branch_manager_id), **m})
        out.sort(key=lambda x: -x["revenue"])
        return out

    async def territory_analytics(self, actor: User, date_from=None, date_to=None) -> list[dict]:
        """Per-territory comparison table."""
        terrs = list((await self.db.execute(select(Territory).filter(
            Territory.organization_id == actor.organization_id, Territory.is_deleted == False,
            Territory.status == "active"))).scalars().all())
        out = []
        for t in terrs:
            m = await self._lead_metrics(actor.organization_id, territory_id=t.id, date_from=date_from, date_to=date_to)
            out.append({"territory_id": str(t.id), "name": t.name, "level": t.level, **m})
        out.sort(key=lambda x: -x["revenue"])
        return out

    # ---------- CSV export ----------
    async def export_branches(self, actor: User) -> str:
        listing = await self.list_branches(actor, limit=200)
        buf = io.StringIO()
        w = csv.writer(buf)
        w.writerow(["name", "code", "manager", "territory", "city", "state", "country", "pin_code",
                    "phone", "email", "is_head_office", "status", "lead_count"])
        for b in listing["items"]:
            w.writerow([b["name"], b["code"] or "", b["manager_name"] or "", b["territory_name"] or "",
                        b["city"] or "", b["state"] or "", b["country"] or "", b["pin_code"] or "",
                        b["phone"] or "", b["email"] or "", b["is_head_office"], b["status"], b["lead_count"]])
        return buf.getvalue()

    # ---------- helpers ----------
    async def _territory_names(self, ids) -> dict:
        ids = {i for i in ids if i}
        if not ids:
            return {}
        res = await self.db.execute(select(Territory.id, Territory.name).filter(Territory.id.in_(ids)))
        return {tid: name for tid, name in res.all()}

    async def _branch_names(self, ids) -> dict:
        ids = {i for i in ids if i}
        if not ids:
            return {}
        res = await self.db.execute(select(Branch.id, Branch.name).filter(Branch.id.in_(ids)))
        return {bid: name for bid, name in res.all()}

    async def _user_names(self, ids) -> dict:
        ids = {i for i in ids if i}
        if not ids:
            return {}
        res = await self.db.execute(select(User.id, User.first_name, User.last_name, User.email).filter(User.id.in_(ids)))
        return {uid: (f"{fn or ''} {ln or ''}".strip() or em) for uid, fn, ln, em in res.all()}

    async def _serialize_territory(self, t: Territory) -> dict:
        mgr_name = None
        if t.manager_user_id:
            mgr_name = (await self._user_names({t.manager_user_id})).get(t.manager_user_id)
        branch_count = (await self.db.execute(select(func.count(Branch.id)).filter(
            Branch.territory_id == t.id, Branch.is_deleted == False))).scalar() or 0
        pin_count = (await self.db.execute(select(func.count(TerritoryPincode.id)).filter(
            TerritoryPincode.territory_id == t.id, TerritoryPincode.is_deleted == False))).scalar() or 0
        return {"id": str(t.id), "organization_id": str(t.organization_id), "name": t.name, "code": t.code,
                "level": t.level, "parent_id": str(t.parent_id) if t.parent_id else None,
                "manager_user_id": str(t.manager_user_id) if t.manager_user_id else None, "manager_name": mgr_name,
                "description": t.description, "status": t.status, "color": t.color,
                "branch_count": branch_count, "pincode_count": pin_count, "created_at": t.created_at}

    async def _serialize_branch(self, b: Branch) -> dict:
        mgr_name = None
        if b.branch_manager_id:
            mgr_name = (await self._user_names({b.branch_manager_id})).get(b.branch_manager_id)
        terr_name = None
        if b.territory_id:
            terr_name = (await self._territory_names({b.territory_id})).get(b.territory_id)
        lead_count = (await self.db.execute(select(func.count(Lead.id)).filter(
            Lead.branch_id == b.id, Lead.is_deleted == False))).scalar() or 0
        return {"id": str(b.id), "organization_id": str(b.organization_id), "name": b.name, "code": b.code,
                "branch_manager_id": str(b.branch_manager_id) if b.branch_manager_id else None,
                "manager_name": mgr_name, "territory_id": str(b.territory_id) if b.territory_id else None,
                "territory_name": terr_name, "address_line": b.address_line, "city": b.city, "state": b.state,
                "country": b.country, "pin_code": b.pin_code, "phone": b.phone, "email": b.email,
                "is_head_office": b.is_head_office, "status": b.status, "lead_count": lead_count,
                "created_at": b.created_at}
