"""Audit & Compliance Reporting.

A unified reporting layer over the existing audit_logs trail — NO new tables,
nothing re-instrumented. Every subsystem already writes AuditLog rows (auth
logins, user/role/permission changes, workflow & rule edits, settings/config
updates, invoices & payments, messaging sends, data exports/BI feed access,
approval decisions); this module classifies those actions into compliance
categories and serves the org-wide audit trail, login history, per-user
activity, a periodic compliance report, a dashboard and CSV exports.
Admin-only (OrgAdmin/SuperAdmin) — stricter than the analytics modules, since
the trail includes security-sensitive events. The scoped audit views that
already exist (rules audit tab, portal, super-admin) are untouched.
"""
from __future__ import annotations
import csv
import io
import uuid
from datetime import datetime, timedelta, timezone
from fastapi import HTTPException, status
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User
from app.models.audit_log import AuditLog

MAX_SCAN = 5000  # bounded window for Python-side category filtering

# Ordered — first match wins (e.g. INVOICE_CONFIG_* is configuration, not financial).
CATEGORIES: dict[str, dict] = {
    "login": {
        "label": "Login & Authentication",
        "prefixes": ("AUTH_",), "exact": (), "contains": ()},
    "permission": {
        "label": "Permissions & Roles",
        "prefixes": ("ROLE_", "PERMISSION_", "FIELD_PERMISSION"),
        "exact": ("USER_CREATED", "USER_UPDATED", "USER_DELETED", "USER_DEACTIVATED", "USER_ACTIVATED",
                  "INVITE_CREATED", "INVITE_REVOKED", "INVITE_ACCEPTED"),
        "contains": ()},
    "workflow": {
        "label": "Workflow & Rule Changes",
        "prefixes": ("WORKFLOW_", "RULE_"), "exact": (), "contains": ()},
    "configuration": {
        "label": "Configuration Changes",
        "prefixes": ("INVOICE_CONFIG", "INVOICE_LOGO", "INVOICE_QR", "COMMERCIAL_SETTINGS", "SCHEDULE_"),
        "exact": ("UPDATE_PROFILE", "UPDATE_BILLING", "TENANT_ACTIVATED", "TENANT_DEACTIVATED"),
        "contains": ("_SETTINGS_", "_CONFIG_")},
    "financial": {
        "label": "Financial",
        "prefixes": ("CUSTOMER_INVOICE", "CUSTOMER_PAYMENT", "GENERATE_", "PAY_INVOICE", "TRIAL_"),
        "exact": (), "contains": ("_INVOICE_", "_PAYMENT_")},
    "communication": {
        "label": "Communication",
        "prefixes": ("SMS_", "WHATSAPP_", "EMAIL_", "CAMPAIGN_", "TEMPLATE_"),
        "exact": (), "contains": ()},
    "export": {
        "label": "Data Exports",
        "prefixes": ("DATA_EXPORT", "BI_FEED"), "exact": (), "contains": ("_EXPORTED",)},
    "approval": {
        "label": "Approvals",
        "prefixes": ("APPROVAL_",), "exact": (), "contains": ()},
    "activity": {
        "label": "User Activity",
        "prefixes": (), "exact": (), "contains": ()},  # catch-all
}


def classify(action: str | None) -> str:
    a = (action or "").upper()
    for key, meta in CATEGORIES.items():
        if key == "activity":
            continue
        if a in meta["exact"] or any(a.startswith(p) for p in meta["prefixes"]) \
                or any(c in a for c in meta["contains"]):
            return key
    return "activity"


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _aware(dt: datetime | None) -> datetime | None:
    if dt is None:
        return None
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


class ComplianceService:
    def __init__(self, db: AsyncSession):
        self.db = db

    # ---------- permissions (stricter than analytics — admins only) ----------
    def _require_admin(self, actor: User):
        if actor.role not in ("SuperAdmin", "OrgAdmin"):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN,
                                detail="Audit & compliance reporting is available to org admins only.")

    # ---------- meta ----------
    def meta(self) -> dict:
        return {"categories": [{"key": k, "label": v["label"]} for k, v in CATEGORIES.items()]}

    # ---------- shared fetch ----------
    async def _fetch(self, org_id: uuid.UUID, *, days: int | None = None,
                     actor_user_id: uuid.UUID | None = None, action: str | None = None,
                     resource_type: str | None = None, limit: int = MAX_SCAN) -> list[AuditLog]:
        q = select(AuditLog).filter(AuditLog.organization_id == org_id)
        if days:
            q = q.filter(AuditLog.created_at >= _now() - timedelta(days=days))
        if actor_user_id:
            q = q.filter(AuditLog.actor_user_id == actor_user_id)
        if action:
            q = q.filter(AuditLog.action == action)
        if resource_type:
            q = q.filter(AuditLog.resource_type == resource_type)
        return list((await self.db.execute(
            q.order_by(AuditLog.created_at.desc()).limit(limit))).scalars().all())

    async def _names(self, ids: set) -> dict:
        ids = {i for i in ids if i}
        if not ids:
            return {}
        rows = (await self.db.execute(select(User).filter(User.id.in_(list(ids))))).scalars().all()
        return {u.id: f"{u.first_name} {u.last_name}".strip() or u.email for u in rows}

    def _row(self, log: AuditLog, names: dict) -> dict:
        return {"id": str(log.id), "action": log.action, "category": classify(log.action),
                "resource_type": log.resource_type, "resource_id": log.resource_id,
                "actor_user_id": str(log.actor_user_id) if log.actor_user_id else None,
                "actor_name": names.get(log.actor_user_id, "System") if log.actor_user_id else "System",
                "metadata": log.action_metadata,
                "created_at": _aware(log.created_at).isoformat() if log.created_at else None}

    # ---------- audit trail (User Activity browse with filters) ----------
    async def logs(self, actor: User, *, category: str | None = None, action: str | None = None,
                   actor_user_id: uuid.UUID | None = None, resource_type: str | None = None,
                   q: str | None = None, days: int = 90, limit: int = 100, offset: int = 0) -> dict:
        self._require_admin(actor)
        if category and category not in CATEGORIES:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST,
                                detail=f"category must be one of {list(CATEGORIES)}")
        rows = await self._fetch(actor.organization_id, days=days, actor_user_id=actor_user_id,
                                 action=action, resource_type=resource_type)
        if category:
            rows = [r for r in rows if classify(r.action) == category]
        if q:
            needle = q.lower()
            rows = [r for r in rows if needle in (r.action or "").lower()
                    or needle in (r.resource_type or "").lower()
                    or needle in str(r.action_metadata or "").lower()]
        total = len(rows)
        page = rows[offset:offset + limit]
        names = await self._names({r.actor_user_id for r in page})
        return {"total": total, "rows": [self._row(r, names) for r in page]}

    # ---------- login history ----------
    async def login_history(self, actor: User, user_id: uuid.UUID | None = None, days: int = 30,
                            limit: int = 200) -> list[dict]:
        self._require_admin(actor)
        rows = await self._fetch(actor.organization_id, days=days, actor_user_id=user_id)
        rows = [r for r in rows if (r.action or "").startswith("AUTH_")][:limit]
        names = await self._names({r.actor_user_id for r in rows})
        out = []
        for r in rows:
            md = r.action_metadata or {}
            out.append({"id": str(r.id), "event": r.action,
                        "success": r.action not in ("AUTH_LOGIN_FAILED",),
                        "user_id": str(r.actor_user_id) if r.actor_user_id else None,
                        "user_name": names.get(r.actor_user_id, "—") if r.actor_user_id else "—",
                        "ip_address": md.get("ip_address"), "browser": md.get("browser_info"),
                        "description": md.get("description"),
                        "created_at": _aware(r.created_at).isoformat() if r.created_at else None})
        return out

    # ---------- per-user activity ----------
    async def user_activity(self, actor: User, user_id: uuid.UUID, days: int = 30) -> dict:
        self._require_admin(actor)
        rows = await self._fetch(actor.organization_id, days=days, actor_user_id=user_id)
        by_category: dict[str, int] = {}
        by_action: dict[str, int] = {}
        for r in rows:
            by_category[classify(r.action)] = by_category.get(classify(r.action), 0) + 1
            by_action[r.action] = by_action.get(r.action, 0) + 1
        names = await self._names({user_id})
        top_actions = sorted(by_action.items(), key=lambda x: -x[1])[:10]
        recent = rows[:25]
        return {"user_id": str(user_id), "user_name": names.get(user_id, "—"), "days": days,
                "total": len(rows), "by_category": by_category,
                "top_actions": [{"action": a, "count": c} for a, c in top_actions],
                "recent": [self._row(r, names) for r in recent]}

    # ---------- dashboard ----------
    async def dashboard(self, actor: User) -> dict:
        self._require_admin(actor)
        org = actor.organization_id
        counts = {}
        for label, days in (("last_24h", 1), ("last_7d", 7), ("last_30d", 30)):
            counts[label] = (await self.db.execute(select(func.count(AuditLog.id)).filter(
                AuditLog.organization_id == org,
                AuditLog.created_at >= _now() - timedelta(days=days)))).scalar() or 0
        rows = await self._fetch(org, days=30)
        by_category: dict[str, int] = {k: 0 for k in CATEGORIES}
        by_actor: dict = {}
        failed_logins = 0
        sensitive = []
        for r in rows:
            cat = classify(r.action)
            by_category[cat] += 1
            if r.actor_user_id:
                by_actor[r.actor_user_id] = by_actor.get(r.actor_user_id, 0) + 1
            if r.action == "AUTH_LOGIN_FAILED":
                failed_logins += 1
            if cat in ("permission", "configuration", "export") and len(sensitive) < 10:
                sensitive.append(r)
        names = await self._names(set(by_actor) | {r.actor_user_id for r in sensitive})
        top_actors = sorted(by_actor.items(), key=lambda x: -x[1])[:5]
        return {"counts": counts,
                "by_category": [{"key": k, "label": CATEGORIES[k]["label"], "count": v}
                                for k, v in by_category.items()],
                "top_actors": [{"user_id": str(uid), "name": names.get(uid, "—"), "events": n}
                               for uid, n in top_actors],
                "failed_logins_30d": failed_logins,
                "recent_sensitive": [self._row(r, names) for r in sensitive]}

    # ---------- compliance report ----------
    async def report(self, actor: User, days: int = 30) -> dict:
        """The periodic compliance report: per-category activity, actor coverage,
        auth failures and the security-relevant change lists for the window."""
        self._require_admin(actor)
        days = max(1, min(int(days), 365))
        rows = await self._fetch(actor.organization_id, days=days)
        by_category: dict[str, dict] = {k: {"count": 0, "actions": {}} for k in CATEGORIES}
        actors = set()
        failed_logins = 0
        perm_changes, config_changes, exports = [], [], []
        for r in rows:
            cat = classify(r.action)
            b = by_category[cat]
            b["count"] += 1
            b["actions"][r.action] = b["actions"].get(r.action, 0) + 1
            if r.actor_user_id:
                actors.add(r.actor_user_id)
            if r.action == "AUTH_LOGIN_FAILED":
                failed_logins += 1
            if cat == "permission" and len(perm_changes) < 20:
                perm_changes.append(r)
            if cat == "configuration" and len(config_changes) < 20:
                config_changes.append(r)
            if cat == "export" and len(exports) < 20:
                exports.append(r)
        names = await self._names(actors | {r.actor_user_id for r in perm_changes + config_changes + exports})
        cats = []
        for k, b in by_category.items():
            top = sorted(b["actions"].items(), key=lambda x: -x[1])[:5]
            cats.append({"key": k, "label": CATEGORIES[k]["label"], "count": b["count"],
                         "top_actions": [{"action": a, "count": c} for a, c in top]})
        return {"generated_at": _now().isoformat(), "days": days,
                "window_start": (_now() - timedelta(days=days)).isoformat(),
                "total_events": len(rows), "unique_actors": len(actors),
                "failed_logins": failed_logins, "categories": cats,
                "permission_changes": [self._row(r, names) for r in perm_changes],
                "configuration_changes": [self._row(r, names) for r in config_changes],
                "data_exports": [self._row(r, names) for r in exports]}

    # ---------- export ----------
    async def export_csv(self, actor: User, *, category: str | None = None, days: int = 90) -> str:
        self._require_admin(actor)
        res = await self.logs(actor, category=category, days=days, limit=MAX_SCAN)
        buf = io.StringIO()
        w = csv.writer(buf)
        w.writerow(["created_at", "category", "action", "actor", "resource_type", "resource_id", "metadata"])
        for r in res["rows"]:
            w.writerow([r["created_at"], r["category"], r["action"], r["actor_name"],
                        r["resource_type"], r["resource_id"], str(r["metadata"] or "")[:500]])
        return buf.getvalue()
