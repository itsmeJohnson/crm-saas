"""AI Platform — the LLM Gateway.

ONE reusable pipeline every AI feature goes through — nothing calls a provider
directly. A generate() call flows:

  settings gate → rate limit (requests/day) → budget cap (USD/month)
  → Prompt Engine (template render) → Context Manager (CRM grounding, bounded)
  → Conversation Memory (windowed history) → Cache lookup
  → Model Selection + Fallback chain (ordered provider configs; Mock when none)
  → provider call (llm_providers — OpenAI / Azure / Anthropic / Gemini / Ollama
    / custom / Mock over httpx) → Cost Tracking (per-model pricing)
  → AI Logging (ai_usage_logs, incl. failed attempts & cache hits) → response.

Streaming uses the same selection/limits and logs after the stream closes.
Integrations (CRM summaries & drafts, report narratives, communication replies,
knowledge-base answers, note/document summaries, workflow/queue ai_task) are
thin wrappers that build context and call the same gateway — no isolated AI
features, no hardcoded provider.
"""
from __future__ import annotations
import hashlib
import json
import re
import uuid
from datetime import datetime, timedelta, timezone
from fastapi import HTTPException, status
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User
from app.models.ai_platform import (AISettings, AIProviderConfig, AIPromptTemplate,
                                    AIConversation, AIMessage, AIUsageLog, AICacheEntry)
from app.services.llm_providers import (get_llm_provider, LLMResult, PROVIDER_KEYS, DEFAULT_PRICING)

TASK_TYPES = ("general", "chat", "crm", "report", "communication", "knowledge", "document",
              "automation", "workflow")

# Seeded platform templates — the integrations' prompt layer (editable per org).
BUILTIN_TEMPLATES = [
    {"key": "crm_record_summary", "name": "CRM record summary", "task_type": "crm",
     "system_prompt": "You are a CRM assistant. Be concise, factual and actionable.",
     "template": "Summarize this {{record_type}} for a sales rep in 4-6 bullet points, ending with the "
                 "single next best action.\n\n{{record}}"},
    {"key": "crm_email_draft", "name": "Follow-up email draft", "task_type": "communication",
     "system_prompt": "You draft professional, warm, concise business emails. Return only the email body.",
     "template": "Draft a follow-up email to {{name}}.\nGoal: {{goal}}\n\nWhat we know:\n{{record}}"},
    {"key": "crm_call_script", "name": "Call script", "task_type": "crm",
     "system_prompt": "You write short practical call scripts: opener, 3 discovery questions, close.",
     "template": "Write a call script for phoning {{name}} about {{goal}}.\n\nBackground:\n{{record}}"},
    {"key": "report_narrative", "name": "Report narrative", "task_type": "report",
     "system_prompt": "You are a business analyst. Explain data plainly, flag trends and outliers.",
     "template": "Write a short narrative (max 150 words) summarizing this report for management.\n\n"
                 "Report: {{report_name}}\n{{table}}"},
    {"key": "reply_draft", "name": "Message reply draft", "task_type": "communication",
     "system_prompt": "You draft replies in the same channel and tone as the incoming message. "
                      "Return only the reply text.",
     "template": "Draft a reply to this {{channel}} message.\n\nConversation so far:\n{{thread}}"},
    {"key": "kb_answer", "name": "Knowledge-base answer", "task_type": "knowledge",
     "system_prompt": "Answer ONLY from the provided knowledge snippets. If they don't contain the "
                      "answer, say so briefly.",
     "template": "Question: {{question}}\n\nKnowledge snippets:\n{{snippets}}"},
    {"key": "text_summary", "name": "Document / note summary", "task_type": "document",
     "system_prompt": "You produce faithful, compact summaries.",
     "template": "Summarize the following in {{length}} bullet points:\n\n{{text}}"},
]


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _aware(dt):
    if dt is None:
        return None
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


def render_template(template: str, variables: dict) -> str:
    """Prompt Engine rendering: replaces {{var}}; unknown vars become empty."""
    def sub(m):
        return str(variables.get(m.group(1).strip(), ""))
    return re.sub(r"\{\{\s*([a-zA-Z0-9_]+)\s*\}\}", sub, template or "")


class AIGatewayService:
    def __init__(self, db: AsyncSession):
        self.db = db

    # ---------- permissions ----------
    def _require_manager(self, actor: User):
        if actor.role not in ("SuperAdmin", "OrgAdmin", "Manager"):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN,
                                detail="AI platform administration is for managers and admins only.")

    # ---------- settings ----------
    async def _settings(self, org_id: uuid.UUID) -> AISettings:
        s = (await self.db.execute(select(AISettings).filter(
            AISettings.organization_id == org_id, AISettings.is_deleted == False))).scalars().first()
        if not s:
            s = AISettings(organization_id=org_id)
            self.db.add(s)
            await self.db.flush()
        return s

    async def get_settings(self, actor: User) -> dict:
        self._require_manager(actor)
        return self._ser_settings(await self._settings(actor.organization_id))

    async def update_settings(self, actor: User, data: dict) -> dict:
        self._require_manager(actor)
        s = await self._settings(actor.organization_id)
        if data.get("default_provider") and data["default_provider"] not in PROVIDER_KEYS:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST,
                                detail=f"default_provider must be one of {list(PROVIDER_KEYS)}")
        for f in ("is_enabled", "default_provider", "default_model", "temperature", "max_tokens",
                  "daily_request_limit", "monthly_budget_usd", "cache_enabled", "cache_ttl_minutes",
                  "streaming_enabled", "memory_messages", "context_max_chars"):
            if f in data and data[f] is not None:
                setattr(s, f, data[f])
        self.db.add(s)
        await self.db.flush()
        return self._ser_settings(s)

    # ---------- provider configs (Provider Abstraction admin) ----------
    async def list_providers(self, actor: User) -> list[dict]:
        self._require_manager(actor)
        rows = (await self.db.execute(select(AIProviderConfig).filter(
            AIProviderConfig.organization_id == actor.organization_id,
            AIProviderConfig.is_deleted == False).order_by(AIProviderConfig.priority.asc()))).scalars().all()
        return [self._ser_provider(p) for p in rows]

    async def create_provider(self, actor: User, data: dict) -> dict:
        self._require_manager(actor)
        if data.get("provider") not in PROVIDER_KEYS:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST,
                                detail=f"provider must be one of {list(PROVIDER_KEYS)}")
        p = AIProviderConfig(organization_id=actor.organization_id, provider=data["provider"],
                             name=data.get("name") or data["provider"], api_key=data.get("api_key"),
                             base_url=data.get("base_url"), deployment=data.get("deployment"),
                             api_version=data.get("api_version"),
                             default_model=data.get("default_model") or "mock-ai",
                             models=data.get("models"), priority=int(data.get("priority", 1)),
                             is_active=bool(data.get("is_active", True)), created_by=actor.id)
        self.db.add(p)
        await self.db.flush()
        return self._ser_provider(p)

    async def _provider_row(self, actor: User, provider_id: uuid.UUID) -> AIProviderConfig:
        p = (await self.db.execute(select(AIProviderConfig).filter(
            AIProviderConfig.id == provider_id, AIProviderConfig.organization_id == actor.organization_id,
            AIProviderConfig.is_deleted == False))).scalars().first()
        if not p:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Provider not found")
        return p

    async def update_provider(self, actor: User, provider_id: uuid.UUID, data: dict) -> dict:
        self._require_manager(actor)
        p = await self._provider_row(actor, provider_id)
        for f in ("name", "api_key", "base_url", "deployment", "api_version", "default_model",
                  "models", "priority", "is_active"):
            if f in data and data[f] is not None:
                setattr(p, f, data[f])
        self.db.add(p)
        await self.db.flush()
        return self._ser_provider(p)

    async def delete_provider(self, actor: User, provider_id: uuid.UUID) -> None:
        self._require_manager(actor)
        p = await self._provider_row(actor, provider_id)
        p.is_deleted = True
        self.db.add(p)
        await self.db.flush()

    async def test_provider(self, actor: User, provider_id: uuid.UUID) -> dict:
        """Connectivity check: one tiny completion through the configured provider."""
        self._require_manager(actor)
        p = await self._provider_row(actor, provider_id)
        provider = get_llm_provider(p.provider, api_key=p.api_key, base_url=p.base_url,
                                    deployment=p.deployment, api_version=p.api_version)
        res = await provider.complete(messages=[{"role": "user", "content": "ping"}],
                                      model=p.default_model, max_tokens=8)
        return {"provider": p.provider, "model": p.default_model, "status": res.status,
                "latency_ms": res.latency_ms, "error": res.error}

    # ---------- prompt templates (Prompt Engine) ----------
    async def seed_templates(self, org_id: uuid.UUID) -> int:
        existing = {t.key for t in (await self.db.execute(select(AIPromptTemplate).filter(
            AIPromptTemplate.organization_id == org_id,
            AIPromptTemplate.is_deleted == False))).scalars().all()}
        added = 0
        for tpl in BUILTIN_TEMPLATES:
            if tpl["key"] in existing:
                continue
            self.db.add(AIPromptTemplate(organization_id=org_id, is_builtin=True, **tpl))
            added += 1
        await self.db.flush()
        return added

    async def list_templates(self, actor: User) -> list[dict]:
        await self.seed_templates(actor.organization_id)
        rows = (await self.db.execute(select(AIPromptTemplate).filter(
            AIPromptTemplate.organization_id == actor.organization_id,
            AIPromptTemplate.is_deleted == False).order_by(AIPromptTemplate.key.asc()))).scalars().all()
        return [self._ser_template(t) for t in rows]

    async def _template(self, org_id: uuid.UUID, key: str) -> AIPromptTemplate:
        await self.seed_templates(org_id)
        t = (await self.db.execute(select(AIPromptTemplate).filter(
            AIPromptTemplate.organization_id == org_id, AIPromptTemplate.key == key,
            AIPromptTemplate.is_deleted == False, AIPromptTemplate.is_active == True))).scalars().first()
        if not t:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Template '{key}' not found")
        return t

    async def create_template(self, actor: User, data: dict) -> dict:
        self._require_manager(actor)
        if data.get("task_type") and data["task_type"] not in TASK_TYPES:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST,
                                detail=f"task_type must be one of {list(TASK_TYPES)}")
        t = AIPromptTemplate(organization_id=actor.organization_id, key=data["key"], name=data["name"],
                             task_type=data.get("task_type") or "general",
                             system_prompt=data.get("system_prompt"), template=data["template"],
                             model_override=data.get("model_override"),
                             provider_override=data.get("provider_override"),
                             temperature=data.get("temperature"), created_by=actor.id)
        self.db.add(t)
        await self.db.flush()
        return self._ser_template(t)

    async def update_template(self, actor: User, template_id: uuid.UUID, data: dict) -> dict:
        self._require_manager(actor)
        t = (await self.db.execute(select(AIPromptTemplate).filter(
            AIPromptTemplate.id == template_id, AIPromptTemplate.organization_id == actor.organization_id,
            AIPromptTemplate.is_deleted == False))).scalars().first()
        if not t:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Template not found")
        for f in ("name", "task_type", "system_prompt", "template", "model_override",
                  "provider_override", "temperature", "is_active"):
            if f in data and data[f] is not None:
                setattr(t, f, data[f])
        self.db.add(t)
        await self.db.flush()
        return self._ser_template(t)

    # ---------- guards: rate limit + budget ----------
    async def _check_limits(self, s: AISettings):
        if not s.is_enabled:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN,
                                detail="AI is disabled for this organization.")
        day_start = _now().replace(hour=0, minute=0, second=0, microsecond=0)
        used_today = (await self.db.execute(select(func.count(AIUsageLog.id)).filter(
            AIUsageLog.organization_id == s.organization_id, AIUsageLog.is_deleted == False,
            AIUsageLog.cache_hit == False, AIUsageLog.created_at >= day_start))).scalar() or 0
        if used_today >= s.daily_request_limit:
            raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                                detail=f"Daily AI request limit reached ({s.daily_request_limit}).")
        month_start = _now().replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        spent = (await self.db.execute(select(func.coalesce(func.sum(AIUsageLog.cost_usd), 0)).filter(
            AIUsageLog.organization_id == s.organization_id, AIUsageLog.is_deleted == False,
            AIUsageLog.created_at >= month_start))).scalar() or 0
        if float(spent) >= float(s.monthly_budget_usd):
            raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                                detail=f"Monthly AI budget exhausted (${float(s.monthly_budget_usd):g}).")

    # ---------- model selection + fallback chain ----------
    async def _chain(self, s: AISettings, provider: str | None, model: str | None) -> list[dict]:
        """Ordered candidates: explicit request > configured chain > settings default (Mock-safe)."""
        configs = (await self.db.execute(select(AIProviderConfig).filter(
            AIProviderConfig.organization_id == s.organization_id, AIProviderConfig.is_deleted == False,
            AIProviderConfig.is_active == True).order_by(AIProviderConfig.priority.asc()))).scalars().all()
        chain = [{"provider": c.provider, "model": model or c.default_model,
                  "api_key": c.api_key, "base_url": c.base_url, "deployment": c.deployment,
                  "api_version": c.api_version, "models": c.models or []} for c in configs]
        if provider:  # explicit provider first
            chain = ([c for c in chain if c["provider"] == provider]
                     + [c for c in chain if c["provider"] != provider])
            if not any(c["provider"] == provider for c in chain):
                chain.insert(0, {"provider": provider, "model": model or s.default_model,
                                 "api_key": None, "base_url": None, "deployment": None,
                                 "api_version": None, "models": []})
        if not chain:
            chain = [{"provider": s.default_provider, "model": model or s.default_model,
                      "api_key": None, "base_url": None, "deployment": None,
                      "api_version": None, "models": []}]
        return chain

    @staticmethod
    def _cost(candidate: dict, model: str, prompt_tokens: int, completion_tokens: int) -> float:
        for m in candidate.get("models") or []:
            if m.get("model") == model:
                return round(prompt_tokens / 1000 * float(m.get("input_cost_per_1k") or 0)
                             + completion_tokens / 1000 * float(m.get("output_cost_per_1k") or 0), 6)
        pin, pout = DEFAULT_PRICING.get(model, (0.001, 0.002))
        return round(prompt_tokens / 1000 * pin + completion_tokens / 1000 * pout, 6)

    # ---------- cache ----------
    @staticmethod
    def _cache_key(provider: str, model: str, messages: list[dict], temperature: float) -> str:
        raw = json.dumps({"p": provider, "m": model, "t": round(temperature, 2), "msgs": messages},
                         sort_keys=True, default=str)
        return hashlib.sha256(raw.encode()).hexdigest()

    async def _cache_get(self, org_id, key: str) -> AICacheEntry | None:
        e = (await self.db.execute(select(AICacheEntry).filter(
            AICacheEntry.organization_id == org_id, AICacheEntry.cache_key == key,
            AICacheEntry.is_deleted == False))).scalars().first()
        if e and (e.expires_at is None or _aware(e.expires_at) > _now()):
            return e
        return None

    async def _cache_put(self, org_id, key: str, candidate: dict, res: LLMResult, ttl_minutes: int):
        if await self._cache_get(org_id, key):
            return
        self.db.add(AICacheEntry(organization_id=org_id, cache_key=key, provider=candidate["provider"],
                                 model=res.model, response_text=res.text,
                                 prompt_tokens=res.prompt_tokens, completion_tokens=res.completion_tokens,
                                 expires_at=_now() + timedelta(minutes=ttl_minutes)))
        await self.db.flush()

    # ---------- logging ----------
    async def _log(self, org_id, user_id, candidate: dict, res: LLMResult, *, task_type: str,
                   template_key: str | None, cost: float, cached: bool = False,
                   fallback_from: str | None = None) -> None:
        self.db.add(AIUsageLog(organization_id=org_id, user_id=user_id,
                               provider=candidate["provider"], model=res.model or candidate["model"],
                               task_type=task_type, template_key=template_key,
                               status="cached" if cached else res.status,
                               prompt_tokens=res.prompt_tokens, completion_tokens=res.completion_tokens,
                               total_tokens=res.total_tokens, cost_usd=cost, latency_ms=res.latency_ms,
                               cache_hit=cached, fallback_from=fallback_from, error=res.error))
        await self.db.flush()

    # ---------- Context Manager (CRM grounding, bounded) ----------
    async def build_context(self, actor: User, context_type: str, context_id: str,
                            max_chars: int = 4000) -> str:
        org = actor.organization_id
        lines: list[str] = []
        cid = uuid.UUID(str(context_id))
        if context_type == "lead":
            from app.models.lead import Lead
            l = (await self.db.execute(select(Lead).filter(
                Lead.id == cid, Lead.organization_id == org, Lead.is_deleted == False))).scalars().first()
            if not l:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Lead not found")
            lines.append(f"LEAD: {l.first_name or ''} {l.last_name}".strip())
            lines.append(f"Status: {l.status} | Source: {l.source or '—'} | Priority: {l.priority or '—'} "
                         f"| Value: {l.value or 0} | Score: {l.score}")
            lines.append(f"Company: {l.company_name or '—'} | City: {l.city or '—'} | Email: {l.email or '—'}")
        elif context_type == "contact":
            from app.models.contact import Contact
            c = (await self.db.execute(select(Contact).filter(
                Contact.id == cid, Contact.organization_id == org,
                Contact.is_deleted == False))).scalars().first()
            if not c:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Contact not found")
            lines.append(f"CONTACT: {c.first_name or ''} {c.last_name or ''}".strip())
            lines.append(f"Email: {c.email or '—'} | Phone: {c.phone or '—'} | Title: {c.job_title or '—'}")
        elif context_type == "company":
            from app.models.company import Company
            co = (await self.db.execute(select(Company).filter(
                Company.id == cid, Company.organization_id == org,
                Company.is_deleted == False))).scalars().first()
            if not co:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Company not found")
            lines.append(f"COMPANY: {co.name}")
            lines.append(f"Industry: {co.industry or '—'} | Type: {co.company_type or '—'}")
        else:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST,
                                detail="context_type must be lead, contact or company.")
        # recent touchpoints
        from app.models.activity import Activity
        fk = {"lead": Activity.lead_id, "contact": Activity.contact_id, "company": Activity.company_id}[context_type]
        acts = (await self.db.execute(select(Activity).filter(
            Activity.organization_id == org, Activity.is_deleted == False, fk == cid)
            .order_by(Activity.created_at.desc()).limit(5))).scalars().all()
        if acts:
            lines.append("Recent activity:")
            for a in acts:
                when = _aware(a.created_at).date().isoformat() if a.created_at else "—"
                lines.append(f"- [{when}] {a.activity_type}: {(a.subject or '')[:80]}")
        return "\n".join(lines)[:max_chars]

    # ---------- THE gateway ----------
    async def generate(self, actor: User, *, prompt: str | None = None,
                       messages: list[dict] | None = None, task_type: str = "general",
                       template_key: str | None = None, variables: dict | None = None,
                       context_type: str | None = None, context_id: str | None = None,
                       conversation_id: uuid.UUID | None = None,
                       provider: str | None = None, model: str | None = None,
                       temperature: float | None = None, max_tokens: int | None = None) -> dict:
        org = actor.organization_id
        s = await self._settings(org)
        await self._check_limits(s)
        if task_type not in TASK_TYPES:
            task_type = "general"

        # Prompt Engine
        system_prompt = None
        if template_key:
            tpl = await self._template(org, template_key)
            prompt = render_template(tpl.template, variables or {})
            system_prompt = tpl.system_prompt
            model = model or tpl.model_override
            provider = provider or tpl.provider_override
            if temperature is None and tpl.temperature is not None:
                temperature = float(tpl.temperature)
            tpl.usage_count = (tpl.usage_count or 0) + 1
            self.db.add(tpl)
        if not prompt and not messages:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST,
                                detail="Provide prompt, messages or template_key.")

        # Context Manager
        context_block = None
        if context_type and context_id:
            context_block = await self.build_context(actor, context_type, str(context_id),
                                                     max_chars=s.context_max_chars)

        # assemble neutral message list (+ Conversation Memory)
        msgs: list[dict] = []
        if system_prompt:
            msgs.append({"role": "system", "content": system_prompt})
        if context_block:
            msgs.append({"role": "system", "content": f"Context:\n{context_block}"})
        convo = None
        if conversation_id:
            convo = await self._conversation(actor, conversation_id)
            history = (await self.db.execute(select(AIMessage).filter(
                AIMessage.conversation_id == convo.id, AIMessage.is_deleted == False)
                .order_by(AIMessage.created_at.desc()).limit(s.memory_messages))).scalars().all()
            msgs.extend({"role": m.role, "content": m.content} for m in reversed(history))
        if messages:
            msgs.extend(messages)
        elif prompt:
            msgs.append({"role": "user", "content": prompt})

        temperature = s and (temperature if temperature is not None else float(s.temperature))
        max_tokens = max_tokens or s.max_tokens
        chain = await self._chain(s, provider, model)

        # Cache (deterministic-ish requests only)
        first = chain[0]
        cache_key = self._cache_key(first["provider"], first["model"], msgs, temperature)
        if s.cache_enabled and not conversation_id:
            hit = await self._cache_get(org, cache_key)
            if hit:
                hit.hits = (hit.hits or 0) + 1
                self.db.add(hit)
                res = LLMResult(status="success", text=hit.response_text, model=hit.model,
                                prompt_tokens=hit.prompt_tokens, completion_tokens=hit.completion_tokens)
                await self._log(org, actor.id, first, res, task_type=task_type,
                                template_key=template_key, cost=0.0, cached=True)
                return {"text": res.text, "model": res.model, "provider": hit.provider,
                        "tokens": {"prompt": res.prompt_tokens, "completion": res.completion_tokens,
                                   "total": res.total_tokens},
                        "cost_usd": 0.0, "cached": True, "fallback_used": False,
                        "task_type": task_type}

        # Fallback chain
        last_error, fallback_from = None, None
        for candidate in chain:
            p = get_llm_provider(candidate["provider"], api_key=candidate["api_key"],
                                 base_url=candidate["base_url"], deployment=candidate["deployment"],
                                 api_version=candidate["api_version"])
            res = await p.complete(messages=msgs, model=candidate["model"],
                                   temperature=temperature, max_tokens=max_tokens)
            cost = self._cost(candidate, res.model or candidate["model"],
                              res.prompt_tokens, res.completion_tokens) if res.status == "success" else 0.0
            await self._log(org, actor.id, candidate, res, task_type=task_type,
                            template_key=template_key, cost=cost, fallback_from=fallback_from)
            if res.status == "success":
                if s.cache_enabled and not conversation_id:
                    await self._cache_put(org, cache_key, candidate, res, s.cache_ttl_minutes)
                if convo is not None:
                    await self._append_message(convo, "user",
                                               (messages[-1]["content"] if messages else prompt) or "")
                    await self._append_message(convo, "assistant", res.text, model=res.model,
                                               provider=candidate["provider"],
                                               tokens=res.total_tokens, cost=cost)
                return {"text": res.text, "model": res.model, "provider": candidate["provider"],
                        "tokens": {"prompt": res.prompt_tokens, "completion": res.completion_tokens,
                                   "total": res.total_tokens},
                        "cost_usd": cost, "cached": False,
                        "fallback_used": fallback_from is not None, "task_type": task_type,
                        "conversation_id": str(convo.id) if convo else None}
            last_error = res.error
            fallback_from = candidate["provider"]
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY,
                            detail=f"All AI providers failed. Last error: {last_error}")

    async def stream_generate(self, actor: User, **kwargs):
        """Streaming variant: same gates and selection; yields text chunks and
        writes the usage log when the stream completes."""
        s = await self._settings(actor.organization_id)
        if not s.streaming_enabled:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST,
                                detail="Streaming is disabled for this organization.")
        await self._check_limits(s)
        prompt = kwargs.get("prompt")
        msgs = list(kwargs.get("messages") or [])
        if prompt and not msgs:
            msgs = [{"role": "user", "content": prompt}]
        if not msgs:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Provide prompt or messages.")
        chain = await self._chain(s, kwargs.get("provider"), kwargs.get("model"))
        candidate = chain[0]
        p = get_llm_provider(candidate["provider"], api_key=candidate["api_key"],
                             base_url=candidate["base_url"], deployment=candidate["deployment"],
                             api_version=candidate["api_version"])
        collected: list[str] = []
        async for chunk in p.stream(messages=msgs, model=candidate["model"],
                                    temperature=float(s.temperature), max_tokens=s.max_tokens):
            collected.append(chunk)
            yield chunk
        text = "".join(collected)
        from app.services.llm_providers import _approx_tokens
        res = LLMResult(status="success" if text else "failed", text=text, model=candidate["model"],
                        prompt_tokens=_approx_tokens(str(msgs)), completion_tokens=_approx_tokens(text),
                        error=None if text else "Empty stream")
        cost = self._cost(candidate, candidate["model"], res.prompt_tokens, res.completion_tokens)
        await self._log(actor.organization_id, actor.id, candidate, res,
                        task_type=kwargs.get("task_type") or "general", template_key=None,
                        cost=cost if text else 0.0)

    # ---------- Conversation Memory ----------
    async def _conversation(self, actor: User, conversation_id: uuid.UUID) -> AIConversation:
        c = (await self.db.execute(select(AIConversation).filter(
            AIConversation.id == conversation_id, AIConversation.organization_id == actor.organization_id,
            AIConversation.user_id == actor.id, AIConversation.is_deleted == False))).scalars().first()
        if not c:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Conversation not found")
        return c

    async def _append_message(self, convo: AIConversation, role: str, content: str, *,
                              model: str | None = None, provider: str | None = None,
                              tokens: int = 0, cost: float = 0.0):
        self.db.add(AIMessage(organization_id=convo.organization_id, conversation_id=convo.id,
                              role=role, content=content, model=model, provider=provider,
                              tokens=tokens, cost_usd=cost))
        convo.message_count = (convo.message_count or 0) + 1
        convo.last_message_at = _now()
        if convo.title == "New conversation" and role == "user":
            convo.title = content[:60]
        self.db.add(convo)
        await self.db.flush()

    async def create_conversation(self, actor: User, data: dict) -> dict:
        c = AIConversation(organization_id=actor.organization_id, user_id=actor.id,
                           title=data.get("title") or "New conversation",
                           context_type=data.get("context_type"), context_id=data.get("context_id"))
        self.db.add(c)
        await self.db.flush()
        return self._ser_conversation(c)

    async def list_conversations(self, actor: User) -> list[dict]:
        rows = (await self.db.execute(select(AIConversation).filter(
            AIConversation.organization_id == actor.organization_id,
            AIConversation.user_id == actor.id, AIConversation.is_deleted == False)
            .order_by(AIConversation.last_message_at.desc().nullslast(),
                      AIConversation.created_at.desc()).limit(50))).scalars().all()
        return [self._ser_conversation(c) for c in rows]

    async def conversation_messages(self, actor: User, conversation_id: uuid.UUID) -> list[dict]:
        c = await self._conversation(actor, conversation_id)
        rows = (await self.db.execute(select(AIMessage).filter(
            AIMessage.conversation_id == c.id, AIMessage.is_deleted == False)
            .order_by(AIMessage.created_at.asc()).limit(200))).scalars().all()
        return [{"id": str(m.id), "role": m.role, "content": m.content, "model": m.model,
                 "provider": m.provider, "tokens": m.tokens, "cost_usd": float(m.cost_usd),
                 "created_at": _aware(m.created_at).isoformat() if m.created_at else None} for m in rows]

    async def chat(self, actor: User, data: dict) -> dict:
        """Chat with memory: creates the conversation on first message."""
        conversation_id = data.get("conversation_id")
        if not conversation_id:
            convo = await self.create_conversation(actor, data)
            conversation_id = convo["id"]
        c = await self._conversation(actor, uuid.UUID(str(conversation_id)))
        return await self.generate(actor, prompt=data["message"], task_type="chat",
                                   conversation_id=c.id,
                                   context_type=c.context_type, context_id=c.context_id,
                                   provider=data.get("provider"), model=data.get("model"))

    # ---------- integrations (all through the same gateway) ----------
    async def crm_summarize(self, actor: User, context_type: str, context_id: str) -> dict:
        record = await self.build_context(actor, context_type, context_id)
        return await self.generate(actor, task_type="crm", template_key="crm_record_summary",
                                   variables={"record_type": context_type, "record": record})

    async def crm_draft_email(self, actor: User, context_type: str, context_id: str, goal: str) -> dict:
        record = await self.build_context(actor, context_type, context_id)
        name = record.splitlines()[0].split(":", 1)[-1].strip() if record else "the customer"
        return await self.generate(actor, task_type="communication", template_key="crm_email_draft",
                                   variables={"name": name, "goal": goal, "record": record})

    async def crm_call_script(self, actor: User, context_type: str, context_id: str, goal: str) -> dict:
        record = await self.build_context(actor, context_type, context_id)
        name = record.splitlines()[0].split(":", 1)[-1].strip() if record else "the customer"
        return await self.generate(actor, task_type="crm", template_key="crm_call_script",
                                   variables={"name": name, "goal": goal, "record": record})

    async def report_narrative(self, actor: User, report_id: uuid.UUID) -> dict:
        from app.services.report_builder_service import ReportBuilderService
        rb = ReportBuilderService(self.db)
        res = await rb.run_saved(actor, report_id, limit=30)
        r = await rb._get(actor, report_id)
        keys = [c["key"] for c in res["columns"]]
        table = "\n".join([" | ".join(keys)] +
                          [" | ".join(str(row.get(k, "")) for k in keys) for row in res["rows"][:30]])
        return await self.generate(actor, task_type="report", template_key="report_narrative",
                                   variables={"report_name": r.name, "table": table[:6000]})

    async def draft_reply(self, actor: User, activity_id: uuid.UUID) -> dict:
        from app.models.activity import Activity
        a = (await self.db.execute(select(Activity).filter(
            Activity.id == activity_id, Activity.organization_id == actor.organization_id,
            Activity.is_deleted == False))).scalars().first()
        if not a:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Activity not found")
        q = select(Activity).filter(Activity.organization_id == actor.organization_id,
                                    Activity.is_deleted == False,
                                    Activity.activity_type == a.activity_type)
        if a.lead_id:
            q = q.filter(Activity.lead_id == a.lead_id)
        elif a.contact_id:
            q = q.filter(Activity.contact_id == a.contact_id)
        else:
            q = q.filter(Activity.id == a.id)
        thread = (await self.db.execute(q.order_by(Activity.created_at.desc()).limit(6))).scalars().all()
        lines = [f"[{m.call_direction or '—'}] {(m.subject or '')[:60]}: {(m.description or '')[:240]}"
                 for m in reversed(thread)]
        return await self.generate(actor, task_type="communication", template_key="reply_draft",
                                   variables={"channel": a.activity_type, "thread": "\n".join(lines)[:5000]})

    async def kb_answer(self, actor: User, question: str) -> dict:
        """Knowledge Base integration: grounds the answer in notes + communication
        templates matching the question keywords."""
        from app.models.note import Note
        from app.models.communication import CommunicationTemplate
        words = [w for w in re.findall(r"[a-zA-Z0-9]{3,}", question.lower())][:6]
        snippets: list[str] = []
        notes = (await self.db.execute(select(Note).filter(
            Note.organization_id == actor.organization_id, Note.is_deleted == False)
            .order_by(Note.created_at.desc()).limit(300))).scalars().all()
        for n in notes:
            body = (getattr(n, "content", None) or getattr(n, "body", None) or "")
            if any(w in body.lower() for w in words):
                snippets.append(f"[note] {body[:400]}")
            if len(snippets) >= 6:
                break
        if len(snippets) < 6:
            tpls = (await self.db.execute(select(CommunicationTemplate).filter(
                CommunicationTemplate.organization_id == actor.organization_id,
                CommunicationTemplate.is_deleted == False).limit(200))).scalars().all()
            for t in tpls:
                body = (getattr(t, "body", None) or getattr(t, "content", None) or "")
                hay = f"{getattr(t, 'name', '')} {body}".lower()
                if any(w in hay for w in words):
                    snippets.append(f"[template:{getattr(t, 'name', '')}] {body[:400]}")
                if len(snippets) >= 6:
                    break
        return await self.generate(actor, task_type="knowledge", template_key="kb_answer",
                                   variables={"question": question,
                                              "snippets": "\n\n".join(snippets) or "(no matching knowledge found)"})

    async def summarize_text(self, actor: User, text: str, length: int = 5) -> dict:
        """Documents integration: summarize arbitrary text (note, doc extract, transcript)."""
        return await self.generate(actor, task_type="document", template_key="text_summary",
                                   variables={"text": text[:8000], "length": max(1, min(int(length), 10))})

    async def run_automation_task(self, org_id: uuid.UUID, payload: dict) -> dict:
        """Workflow/Automation/Queue integration: the queue's ai_task handler.
        Resolves an org actor and routes through the same gateway."""
        actor_id = payload.get("actor_user_id")
        actor = None
        if actor_id:
            actor = (await self.db.execute(select(User).filter(User.id == uuid.UUID(str(actor_id)),
                                                               User.is_deleted == False))).scalars().first()
        if actor is None:
            actor = (await self.db.execute(select(User).filter(
                User.organization_id == org_id, User.is_deleted == False,
                User.role.in_(["OrgAdmin", "SuperAdmin"])).limit(1))).scalars().first()
        if actor is None:
            raise RuntimeError("No actor available for AI task")
        out = await self.generate(actor, prompt=str(payload.get("prompt") or ""),
                                  task_type="automation",
                                  template_key=payload.get("template_key"),
                                  variables=payload.get("variables"),
                                  model=payload.get("model"), provider=payload.get("provider"))
        return {"model": out["model"], "completion": out["text"], "tokens": out["tokens"]["total"],
                "cost_usd": out["cost_usd"], "provider": out["provider"]}

    # ---------- monitoring ----------
    async def usage_dashboard(self, actor: User, days: int = 30) -> dict:
        self._require_manager(actor)
        org = actor.organization_id
        since = _now() - timedelta(days=max(1, min(int(days), 365)))
        rows = (await self.db.execute(select(AIUsageLog).filter(
            AIUsageLog.organization_id == org, AIUsageLog.is_deleted == False,
            AIUsageLog.created_at >= since).order_by(AIUsageLog.created_at.desc())
            .limit(5000))).scalars().all()
        s = await self._settings(org)
        total = len(rows)
        failed = sum(1 for r in rows if r.status == "failed")
        cached = sum(1 for r in rows if r.cache_hit)
        fallbacks = sum(1 for r in rows if r.fallback_from)
        cost = round(sum(float(r.cost_usd) for r in rows), 4)
        tokens = sum(r.total_tokens for r in rows)
        lat = [r.latency_ms for r in rows if r.status == "success" and not r.cache_hit]
        by_provider: dict[str, dict] = {}
        by_task: dict[str, int] = {}
        by_day: dict[str, dict] = {}
        for r in rows:
            bp = by_provider.setdefault(r.provider, {"requests": 0, "tokens": 0, "cost": 0.0, "failed": 0})
            bp["requests"] += 1
            bp["tokens"] += r.total_tokens
            bp["cost"] = round(bp["cost"] + float(r.cost_usd), 4)
            bp["failed"] += 1 if r.status == "failed" else 0
            by_task[r.task_type] = by_task.get(r.task_type, 0) + 1
            day = _aware(r.created_at).date().isoformat() if r.created_at else "—"
            bd = by_day.setdefault(day, {"requests": 0, "cost": 0.0})
            bd["requests"] += 1
            bd["cost"] = round(bd["cost"] + float(r.cost_usd), 4)
        month_start = _now().replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        month_cost = (await self.db.execute(select(func.coalesce(func.sum(AIUsageLog.cost_usd), 0)).filter(
            AIUsageLog.organization_id == org, AIUsageLog.is_deleted == False,
            AIUsageLog.created_at >= month_start))).scalar() or 0
        return {"days": days, "requests": total, "failed": failed, "cached": cached,
                "fallbacks": fallbacks, "tokens": tokens, "cost_usd": cost,
                "error_rate": round(failed * 100 / total, 1) if total else 0.0,
                "cache_hit_rate": round(cached * 100 / total, 1) if total else 0.0,
                "avg_latency_ms": round(sum(lat) / len(lat), 1) if lat else 0,
                "by_provider": by_provider, "by_task": by_task,
                "by_day": [{"day": d, **v} for d, v in sorted(by_day.items())],
                "budget": {"monthly_budget_usd": float(s.monthly_budget_usd),
                           "spent_this_month_usd": round(float(month_cost), 4),
                           "daily_request_limit": s.daily_request_limit}}

    async def usage_logs(self, actor: User, limit: int = 100) -> list[dict]:
        self._require_manager(actor)
        rows = (await self.db.execute(select(AIUsageLog).filter(
            AIUsageLog.organization_id == actor.organization_id, AIUsageLog.is_deleted == False)
            .order_by(AIUsageLog.created_at.desc()).limit(min(limit, 300)))).scalars().all()
        return [{"id": str(r.id), "provider": r.provider, "model": r.model, "task_type": r.task_type,
                 "template_key": r.template_key, "status": r.status, "tokens": r.total_tokens,
                 "cost_usd": float(r.cost_usd), "latency_ms": r.latency_ms, "cache_hit": r.cache_hit,
                 "fallback_from": r.fallback_from, "error": r.error,
                 "created_at": _aware(r.created_at).isoformat() if r.created_at else None} for r in rows]

    # ---------- serializers ----------
    @staticmethod
    def _ser_settings(s: AISettings) -> dict:
        return {"is_enabled": s.is_enabled, "default_provider": s.default_provider,
                "default_model": s.default_model, "temperature": float(s.temperature),
                "max_tokens": s.max_tokens, "daily_request_limit": s.daily_request_limit,
                "monthly_budget_usd": float(s.monthly_budget_usd), "cache_enabled": s.cache_enabled,
                "cache_ttl_minutes": s.cache_ttl_minutes, "streaming_enabled": s.streaming_enabled,
                "memory_messages": s.memory_messages, "context_max_chars": s.context_max_chars}

    @staticmethod
    def _ser_provider(p: AIProviderConfig) -> dict:
        return {"id": str(p.id), "provider": p.provider, "name": p.name,
                "api_key": f"…{p.api_key[-4:]}" if p.api_key else None,
                "base_url": p.base_url, "deployment": p.deployment, "api_version": p.api_version,
                "default_model": p.default_model, "models": p.models or [],
                "priority": p.priority, "is_active": p.is_active,
                "created_at": _aware(p.created_at).isoformat() if p.created_at else None}

    @staticmethod
    def _ser_template(t: AIPromptTemplate) -> dict:
        return {"id": str(t.id), "key": t.key, "name": t.name, "task_type": t.task_type,
                "system_prompt": t.system_prompt, "template": t.template,
                "model_override": t.model_override, "provider_override": t.provider_override,
                "temperature": float(t.temperature) if t.temperature is not None else None,
                "is_active": t.is_active, "is_builtin": t.is_builtin, "usage_count": t.usage_count}

    @staticmethod
    def _ser_conversation(c: AIConversation) -> dict:
        return {"id": str(c.id), "title": c.title, "context_type": c.context_type,
                "context_id": c.context_id, "message_count": c.message_count,
                "last_message_at": _aware(c.last_message_at).isoformat() if c.last_message_at else None,
                "created_at": _aware(c.created_at).isoformat() if c.created_at else None}
