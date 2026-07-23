"""AI Prompt Studio — the authoring surface for the Prompt Engine.

It manages the SAME `AIPromptTemplate` rows the AI gateway consumes (so a prompt
authored here is immediately usable once approved) and adds the lifecycle the
platform lacked: versioning + history, an approval workflow, variable detection,
a test/preview harness (dry render + live run through the gateway), a library,
categories and usage analytics.

COMPOSES, never duplicates:
  * render_template + TASK_TYPES + AIPromptTemplate (from ai_gateway_service).
  * AIGatewayService.generate for live test runs (multi-provider; never a
    provider directly).

Approval has teeth without touching the gateway's selection logic: a prompt is
`is_active` only while `status == "approved"`, so drafts/pending prompts are
never picked up in production.
"""
import re
import csv
import io
import uuid
from datetime import datetime, timezone

from fastapi import HTTPException, status
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User
from app.models.ai_platform import AIPromptTemplate, AIPromptTemplateVersion
from app.services.audit_service import AuditService
from app.services.ai_gateway_service import render_template, TASK_TYPES

MANAGER_ROLES = ("SuperAdmin", "OrgAdmin", "Manager")
STATUSES = ("draft", "pending_review", "approved", "rejected", "archived")
_VAR_RE = re.compile(r"\{\{\s*([a-zA-Z0-9_]+)\s*\}\}")


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _aware(dt):
    if dt is None:
        return None
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


def detect_variables(*texts: str) -> list[str]:
    """Ordered, de-duplicated {{var}} names across the system + user prompts."""
    seen, out = set(), []
    for t in texts:
        for m in _VAR_RE.finditer(t or ""):
            v = m.group(1).strip()
            if v not in seen:
                seen.add(v)
                out.append(v)
    return out


class PromptStudioService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.audit = AuditService(db)

    def _require_manager(self, actor: User):
        if actor.role not in MANAGER_ROLES:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN,
                                detail="Manager or admin role required")

    async def _get(self, actor: User, template_id: uuid.UUID) -> AIPromptTemplate:
        t = (await self.db.execute(select(AIPromptTemplate).filter(
            AIPromptTemplate.id == template_id,
            AIPromptTemplate.organization_id == actor.organization_id,
            AIPromptTemplate.is_deleted == False))).scalars().first()
        if not t:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Prompt not found")
        return t

    def _can_edit(self, actor: User, t: AIPromptTemplate) -> bool:
        if t.is_builtin and actor.role not in ("SuperAdmin", "OrgAdmin"):
            return False
        return actor.role in MANAGER_ROLES or t.created_by == actor.id

    # ---------- library / list / categories ----------
    async def _ensure_seeded(self, actor: User):
        """Make sure the builtin library exists (reuses the gateway seeder)."""
        from app.services.ai_gateway_service import AIGatewayService
        await AIGatewayService(self.db).seed_templates(actor.organization_id)

    async def list_prompts(self, actor: User, *, task_type=None, status_f=None,
                           q=None, tag=None, builtin=None) -> dict:
        await self._ensure_seeded(actor)
        query = select(AIPromptTemplate).filter(
            AIPromptTemplate.organization_id == actor.organization_id,
            AIPromptTemplate.is_deleted == False)
        if task_type:
            query = query.filter(AIPromptTemplate.task_type == task_type)
        if status_f:
            query = query.filter(AIPromptTemplate.status == status_f)
        if builtin is not None:
            query = query.filter(AIPromptTemplate.is_builtin == builtin)
        if q:
            like = f"%{q}%"
            query = query.filter(AIPromptTemplate.name.ilike(like) | AIPromptTemplate.key.ilike(like)
                                 | AIPromptTemplate.template.ilike(like))
        rows = (await self.db.execute(query.order_by(AIPromptTemplate.updated_at.desc()))).scalars().all()
        if tag:
            rows = [r for r in rows if tag in (r.tags or [])]
        return {"total": len(rows), "items": [self._ser(r, full=False) for r in rows]}

    async def get_prompt(self, actor: User, template_id: uuid.UUID) -> dict:
        return self._ser(await self._get(actor, template_id))

    async def categories(self, actor: User) -> dict:
        await self._ensure_seeded(actor)
        rows = (await self.db.execute(select(AIPromptTemplate.task_type, func.count(AIPromptTemplate.id))
                .filter(AIPromptTemplate.organization_id == actor.organization_id,
                        AIPromptTemplate.is_deleted == False)
                .group_by(AIPromptTemplate.task_type))).all()
        counts = {t: n for t, n in rows}
        tags: dict = {}
        for r in (await self.db.execute(select(AIPromptTemplate.tags).filter(
                AIPromptTemplate.organization_id == actor.organization_id,
                AIPromptTemplate.is_deleted == False))).scalars().all():
            for tg in (r or []):
                tags[tg] = tags.get(tg, 0) + 1
        return {"categories": [{"task_type": t, "count": counts.get(t, 0)} for t in TASK_TYPES],
                "tags": [{"tag": k, "count": v} for k, v in sorted(tags.items(), key=lambda kv: -kv[1])]}

    async def library(self, actor: User) -> dict:
        await self._ensure_seeded(actor)
        rows = (await self.db.execute(select(AIPromptTemplate).filter(
            AIPromptTemplate.organization_id == actor.organization_id,
            AIPromptTemplate.is_builtin == True, AIPromptTemplate.is_deleted == False)
            .order_by(AIPromptTemplate.task_type, AIPromptTemplate.name))).scalars().all()
        return {"count": len(rows), "items": [self._ser(r, full=False) for r in rows]}

    # ---------- create / edit (with version snapshots) ----------
    async def create_prompt(self, actor: User, data: dict) -> dict:
        self._require_manager(actor)
        key = (data.get("key") or "").strip()
        name = (data.get("name") or "").strip()
        template = (data.get("template") or "").strip()
        if not key or not name or not template:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST,
                                detail="key, name and template are required")
        if not re.fullmatch(r"[a-z0-9_]{2,60}", key):
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST,
                                detail="key must be lowercase letters/digits/underscores")
        task_type = data.get("task_type") or "general"
        if task_type not in TASK_TYPES:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST,
                                detail=f"task_type must be one of {list(TASK_TYPES)}")
        dup = (await self.db.execute(select(AIPromptTemplate.id).filter(
            AIPromptTemplate.organization_id == actor.organization_id,
            AIPromptTemplate.key == key, AIPromptTemplate.is_deleted == False))).scalar()
        if dup:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST,
                                detail=f"A prompt with key '{key}' already exists")
        t = AIPromptTemplate(
            organization_id=actor.organization_id, key=key, name=name, task_type=task_type,
            system_prompt=data.get("system_prompt"), template=template,
            model_override=data.get("model_override"), provider_override=data.get("provider_override"),
            temperature=data.get("temperature"), description=data.get("description"),
            tags=list(data.get("tags") or []),
            variables=detect_variables(data.get("system_prompt"), template),
            status="draft", is_active=False, version=1, created_by=actor.id)
        self.db.add(t)
        await self.db.flush()
        await self.db.commit()
        await self.db.refresh(t)
        return self._ser(t)

    async def update_prompt(self, actor: User, template_id: uuid.UUID, data: dict) -> dict:
        t = await self._get(actor, template_id)
        if not self._can_edit(actor, t):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN,
                                detail="You cannot edit this prompt")
        content_change = any(k in data and data[k] is not None and getattr(t, k) != data[k]
                             for k in ("name", "system_prompt", "template", "model_override",
                                       "provider_override", "temperature", "task_type"))
        if content_change:
            self._snapshot(t, actor, data.get("change_note"))
            t.version += 1
        if data.get("task_type") and data["task_type"] not in TASK_TYPES:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST,
                                detail=f"task_type must be one of {list(TASK_TYPES)}")
        for f in ("name", "task_type", "system_prompt", "template", "model_override",
                  "provider_override", "temperature", "description"):
            if f in data and data[f] is not None:
                setattr(t, f, data[f])
        if "tags" in data and data["tags"] is not None:
            t.tags = list(data["tags"])
        t.variables = detect_variables(t.system_prompt, t.template)
        t.updated_by = actor.id
        # editing an approved prompt sends it back for re-approval
        if content_change and t.status == "approved":
            t.status = "pending_review"
            t.is_active = False
        await self.db.commit()
        await self.db.refresh(t)
        return self._ser(t)

    def _snapshot(self, t: AIPromptTemplate, actor: User, note: str | None):
        self.db.add(AIPromptTemplateVersion(
            organization_id=t.organization_id, template_id=t.id, version=t.version,
            name=t.name, task_type=t.task_type, system_prompt=t.system_prompt, template=t.template,
            model_override=t.model_override, provider_override=t.provider_override,
            temperature=t.temperature, edited_by=actor.id, change_note=note))

    async def delete_prompt(self, actor: User, template_id: uuid.UUID) -> dict:
        t = await self._get(actor, template_id)
        if t.is_builtin:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST,
                                detail="Builtin library prompts cannot be deleted; archive instead")
        if not self._can_edit(actor, t):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="You cannot delete this prompt")
        t.is_deleted = True
        t.deleted_at = _now()
        t.is_active = False
        await self.db.commit()
        return {"deleted": True}

    async def duplicate(self, actor: User, template_id: uuid.UUID) -> dict:
        self._require_manager(actor)
        src = await self._get(actor, template_id)
        base = f"{src.key}_copy"
        key = base
        i = 1
        while (await self.db.execute(select(AIPromptTemplate.id).filter(
                AIPromptTemplate.organization_id == actor.organization_id,
                AIPromptTemplate.key == key, AIPromptTemplate.is_deleted == False))).scalar():
            i += 1
            key = f"{base}{i}"
        return await self.create_prompt(actor, {
            "key": key, "name": f"{src.name} (copy)", "task_type": src.task_type,
            "system_prompt": src.system_prompt, "template": src.template,
            "model_override": src.model_override, "provider_override": src.provider_override,
            "temperature": float(src.temperature) if src.temperature is not None else None,
            "description": src.description, "tags": list(src.tags or [])})

    # ---------- versions / history ----------
    async def versions(self, actor: User, template_id: uuid.UUID) -> list[dict]:
        t = await self._get(actor, template_id)
        rows = (await self.db.execute(select(AIPromptTemplateVersion).filter(
            AIPromptTemplateVersion.template_id == t.id,
            AIPromptTemplateVersion.is_deleted == False)
            .order_by(AIPromptTemplateVersion.version.desc()))).scalars().all()
        return [{"version": v.version, "name": v.name, "task_type": v.task_type,
                 "system_prompt": v.system_prompt, "template": v.template,
                 "model_override": v.model_override, "provider_override": v.provider_override,
                 "temperature": float(v.temperature) if v.temperature is not None else None,
                 "edited_by": str(v.edited_by) if v.edited_by else None, "change_note": v.change_note,
                 "created_at": _aware(v.created_at).isoformat() if v.created_at else None} for v in rows]

    async def restore_version(self, actor: User, template_id: uuid.UUID, version: int) -> dict:
        t = await self._get(actor, template_id)
        if not self._can_edit(actor, t):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="You cannot edit this prompt")
        snap = (await self.db.execute(select(AIPromptTemplateVersion).filter(
            AIPromptTemplateVersion.template_id == t.id, AIPromptTemplateVersion.version == version,
            AIPromptTemplateVersion.is_deleted == False))).scalars().first()
        if not snap:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Version not found")
        self._snapshot(t, actor, f"snapshot before restoring v{version}")
        t.version += 1
        t.name, t.task_type, t.system_prompt, t.template = snap.name, snap.task_type, snap.system_prompt, snap.template
        t.model_override, t.provider_override, t.temperature = snap.model_override, snap.provider_override, snap.temperature
        t.variables = detect_variables(t.system_prompt, t.template)
        t.updated_by = actor.id
        if t.status == "approved":
            t.status = "pending_review"
            t.is_active = False
        await self.db.commit()
        await self.db.refresh(t)
        return self._ser(t)

    # ---------- approval workflow ----------
    async def submit(self, actor: User, template_id: uuid.UUID) -> dict:
        t = await self._get(actor, template_id)
        if not self._can_edit(actor, t):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="You cannot submit this prompt")
        if t.status not in ("draft", "rejected"):
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST,
                                detail=f"Cannot submit a prompt in status '{t.status}'")
        t.status = "pending_review"
        t.is_active = False
        await self.db.commit()
        return {"id": str(t.id), "status": t.status}

    async def approve(self, actor: User, template_id: uuid.UUID, note: str | None = None) -> dict:
        self._require_manager(actor)
        t = await self._get(actor, template_id)
        if t.status not in ("draft", "pending_review"):
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST,
                                detail=f"Cannot approve a prompt in status '{t.status}'")
        t.status = "approved"
        t.is_active = True  # now the gateway will use it
        t.reviewed_by = actor.id
        t.reviewed_at = _now()
        t.review_note = note
        await self.audit.log_event(actor.organization_id, actor_user_id=actor.id,
                                   action="PROMPT_APPROVED", resource_type="prompt_studio",
                                   resource_id=str(t.id), action_metadata={"key": t.key})
        await self.db.commit()
        return {"id": str(t.id), "status": t.status, "is_active": t.is_active}

    async def reject(self, actor: User, template_id: uuid.UUID, note: str | None = None) -> dict:
        self._require_manager(actor)
        t = await self._get(actor, template_id)
        if t.status != "pending_review":
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST,
                                detail=f"Cannot reject a prompt in status '{t.status}'")
        t.status = "rejected"
        t.is_active = False
        t.reviewed_by = actor.id
        t.reviewed_at = _now()
        t.review_note = note
        await self.audit.log_event(actor.organization_id, actor_user_id=actor.id,
                                   action="PROMPT_REJECTED", resource_type="prompt_studio",
                                   resource_id=str(t.id), action_metadata={"key": t.key, "note": note})
        await self.db.commit()
        return {"id": str(t.id), "status": t.status}

    async def archive(self, actor: User, template_id: uuid.UUID) -> dict:
        t = await self._get(actor, template_id)
        if not self._can_edit(actor, t):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="You cannot archive this prompt")
        t.status = "archived"
        t.is_active = False
        await self.db.commit()
        return {"id": str(t.id), "status": t.status}

    # ---------- testing / preview ----------
    async def test_prompt(self, actor: User, data: dict) -> dict:
        """Dry render (variable substitution) and, when run=True, a live
        generation through the AI gateway. Works on a saved prompt (by id) or an
        inline draft (system_prompt/template supplied directly)."""
        variables = data.get("variables") or {}
        run = bool(data.get("run"))
        t = None
        if data.get("template_id"):
            t = await self._get(actor, uuid.UUID(str(data["template_id"])))
            system_prompt, template = t.system_prompt, t.template
            task_type = t.task_type
            model = data.get("model_override") or t.model_override
            provider = data.get("provider_override") or t.provider_override
            temperature = data.get("temperature") if data.get("temperature") is not None else (
                float(t.temperature) if t.temperature is not None else None)
        else:
            template = (data.get("template") or "").strip()
            if not template:
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST,
                                    detail="Provide template_id or an inline template")
            system_prompt = data.get("system_prompt")
            task_type = data.get("task_type") or "general"
            model = data.get("model_override")
            provider = data.get("provider_override")
            temperature = data.get("temperature")

        declared = detect_variables(system_prompt, template)
        rendered = render_template(template, variables)
        rendered_system = render_template(system_prompt, variables) if system_prompt else None
        missing = [v for v in declared if v not in variables or variables.get(v) in (None, "")]

        result = {"rendered_prompt": rendered, "rendered_system_prompt": rendered_system,
                  "declared_variables": declared, "missing_variables": missing, "ran": False}
        if run:
            from app.services.ai_gateway_service import AIGatewayService
            out = await AIGatewayService(self.db).generate(
                actor, prompt=rendered, task_type=(task_type if task_type in TASK_TYPES else "general"),
                provider=provider, model=model, temperature=temperature)
            result.update({"ran": True, "output": out.get("text"), "provider": out.get("provider"),
                           "model": out.get("model"), "tokens": out.get("tokens"),
                           "cached": out.get("cached", False)})
            if t is not None:
                t.last_tested_at = _now()
                await self.db.commit()
        return result

    # ---------- analytics / report / export ----------
    async def analytics(self, actor: User) -> dict:
        self._require_manager(actor)
        await self._ensure_seeded(actor)
        rows = (await self.db.execute(select(AIPromptTemplate).filter(
            AIPromptTemplate.organization_id == actor.organization_id,
            AIPromptTemplate.is_deleted == False))).scalars().all()
        by_status: dict = {}
        by_category: dict = {}
        total_usage = builtin = custom = 0
        for r in rows:
            by_status[r.status] = by_status.get(r.status, 0) + 1
            by_category[r.task_type] = by_category.get(r.task_type, 0) + 1
            total_usage += r.usage_count or 0
            builtin += 1 if r.is_builtin else 0
            custom += 0 if r.is_builtin else 1
        top = sorted(rows, key=lambda r: r.usage_count or 0, reverse=True)[:10]
        pending = [r for r in rows if r.status == "pending_review"]
        return {"totals": {"prompts": len(rows), "builtin": builtin, "custom": custom,
                           "total_usage": total_usage, "active": sum(1 for r in rows if r.is_active),
                           "pending_review": len(pending)},
                "by_status": by_status, "by_category": by_category,
                "top_used": [{"id": str(r.id), "key": r.key, "name": r.name,
                              "task_type": r.task_type, "usage_count": r.usage_count} for r in top],
                "pending_queue": [{"id": str(r.id), "name": r.name, "key": r.key} for r in pending]}

    async def dashboard(self, actor: User) -> dict:
        await self._ensure_seeded(actor)
        rows = (await self.db.execute(select(AIPromptTemplate).filter(
            AIPromptTemplate.organization_id == actor.organization_id,
            AIPromptTemplate.is_deleted == False))).scalars().all()
        return {"prompts": len(rows), "active": sum(1 for r in rows if r.is_active),
                "pending_review": sum(1 for r in rows if r.status == "pending_review"),
                "total_usage": sum(r.usage_count or 0 for r in rows),
                "categories": len({r.task_type for r in rows})}

    async def export_csv(self, actor: User) -> str:
        self._require_manager(actor)
        rows = (await self.db.execute(select(AIPromptTemplate).filter(
            AIPromptTemplate.organization_id == actor.organization_id,
            AIPromptTemplate.is_deleted == False).order_by(AIPromptTemplate.task_type,
            AIPromptTemplate.key))).scalars().all()
        buf = io.StringIO()
        w = csv.writer(buf)
        w.writerow(["key", "name", "category", "status", "version", "is_active", "is_builtin",
                    "usage_count", "variables"])
        for r in rows:
            w.writerow([r.key, r.name, r.task_type, r.status, r.version, r.is_active, r.is_builtin,
                        r.usage_count, ",".join(r.variables or [])])
        await self.audit.log_event(actor.organization_id, actor_user_id=actor.id,
                                   action="PROMPTS_EXPORTED", resource_type="prompt_studio",
                                   action_metadata={"rows": len(rows)})
        await self.db.commit()
        return buf.getvalue()

    # ---------- serialization ----------
    def _ser(self, t: AIPromptTemplate, full: bool = True) -> dict:
        d = {"id": str(t.id), "key": t.key, "name": t.name, "task_type": t.task_type,
             "status": t.status, "version": t.version, "is_active": t.is_active,
             "is_builtin": t.is_builtin, "usage_count": t.usage_count,
             "variables": t.variables or [], "tags": t.tags or [],
             "description": t.description,
             "model_override": t.model_override, "provider_override": t.provider_override,
             "temperature": float(t.temperature) if t.temperature is not None else None,
             "created_by": str(t.created_by) if t.created_by else None,
             "reviewed_by": str(t.reviewed_by) if t.reviewed_by else None,
             "review_note": t.review_note,
             "last_tested_at": _aware(t.last_tested_at).isoformat() if t.last_tested_at else None,
             "updated_at": _aware(t.updated_at).isoformat() if t.updated_at else None}
        if full:
            d["system_prompt"] = t.system_prompt
            d["template"] = t.template
        return d
