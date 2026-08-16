"""AI Security & Governance — the guard rail in front of every LLM call.

Sits in the AI gateway's guard phase and, per org policy, will:
  * DETECT PII and MASK it out of the prompt before it ever leaves for a
    provider (or block / flag instead);
  * DETECT PROMPT INJECTION ("ignore previous instructions", system-prompt
    override, exfiltration attempts) and block or flag;
  * FILTER CONTENT against an org blocked-terms list;
  * ENFORCE MODEL/PROVIDER RESTRICTIONS and per-role task allowlists;
  * CAP PROMPT SIZE (usage policy);
  * LOG every decision to ai_governance_events for compliance.

Deterministic and dependency-free — no external moderation API. Defaults are
deliberately non-breaking: PII is masked (not blocked), injection is blocked,
content filtering is off until terms are set, and there are no provider/model
restrictions until an allowlist is configured.
"""
import csv
import io
import re
import uuid
from datetime import datetime, timezone, timedelta

from fastapi import HTTPException, status
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User
from app.models.ai_governance import AIGovernancePolicy, AIGovernanceEvent
from app.services.audit_service import AuditService

MANAGER_ROLES = ("SuperAdmin", "OrgAdmin", "Manager")
PII_ACTIONS = ("mask", "block", "flag")
INJECTION_ACTIONS = ("block", "flag")

# ---- PII detectors. Deliberately strict to avoid false positives on ordinary
# business text (deal values, counts, dates).
PII_PATTERNS: dict[str, re.Pattern] = {
    "email": re.compile(r"\b[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}\b"),
    "phone": re.compile(r"(?<!\d)(?:\+\d{1,3}[ -]?)?(?:\d[ -]?){9,14}\d(?!\d)"),
    "pan": re.compile(r"\b[A-Z]{5}\d{4}[A-Z]\b"),
    "aadhaar": re.compile(r"\b\d{4}[ -]\d{4}[ -]\d{4}\b"),
    "passport": re.compile(r"\b[A-Z]\d{7}\b"),
    "credit_card": re.compile(r"\b(?:\d[ -]?){13,19}\b"),
    "ifsc": re.compile(r"\b[A-Z]{4}0[A-Z0-9]{6}\b"),
    "ip_address": re.compile(r"\b(?:\d{1,3}\.){3}\d{1,3}\b"),
}

# ---- Prompt-injection signatures (high-confidence phrasings only).
INJECTION_PATTERNS: list[tuple[str, re.Pattern]] = [
    ("ignore_instructions", re.compile(r"ignore\s+(?:all\s+|any\s+)?(?:previous|prior|above|earlier)\s+(?:instructions|prompts|rules)", re.I)),
    ("disregard_instructions", re.compile(r"disregard\s+(?:all\s+)?(?:previous|prior|above)\s+(?:instructions|rules)", re.I)),
    ("system_prompt_override", re.compile(r"(?:you\s+are\s+now|from\s+now\s+on,?\s+you\s+are)\s+(?:a|an|the)?\s*\w+", re.I)),
    ("reveal_system_prompt", re.compile(r"(?:reveal|show|print|repeat|output)\s+(?:me\s+)?(?:your\s+)?(?:system\s+prompt|initial\s+instructions|the\s+prompt\s+above)", re.I)),
    ("developer_mode", re.compile(r"\b(?:developer\s+mode|DAN\s+mode|jailbreak|do\s+anything\s+now)\b", re.I)),
    ("ignore_guardrails", re.compile(r"(?:ignore|bypass|override)\s+(?:your\s+)?(?:safety|guardrails|restrictions|filters)", re.I)),
    ("exfiltrate", re.compile(r"(?:list|dump|export)\s+(?:all\s+)?(?:api\s*keys|passwords|credentials|secrets)", re.I)),
]


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _aware(dt):
    if dt is None:
        return None
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


def _mask_value(v: str) -> str:
    """Keep the last 2 visible so humans can still correlate; redact the rest."""
    core = v.strip()
    if len(core) <= 4:
        return "*" * len(core)
    return "*" * (len(core) - 2) + core[-2:]


def scan_pii(text: str, types: list[str] | None = None) -> dict:
    """Return {pii_type: [matched values]} for the enabled detectors."""
    if not text:
        return {}
    enabled = [t for t in (types or PII_PATTERNS.keys()) if t in PII_PATTERNS]
    found: dict = {}
    for t in enabled:
        hits = [m.group(0) for m in PII_PATTERNS[t].finditer(text)]
        # phone/credit_card overlap: require enough digits to be meaningful
        if t in ("phone", "credit_card"):
            hits = [h for h in hits if sum(c.isdigit() for c in h) >= (13 if t == "credit_card" else 10)]
        if hits:
            found[t] = hits
    return found


def mask_pii(text: str, findings: dict) -> str:
    """Replace each detected value with a redacted marker."""
    out = text or ""
    for pii_type, values in findings.items():
        for v in sorted(set(values), key=len, reverse=True):
            out = out.replace(v, f"[REDACTED_{pii_type.upper()}:{_mask_value(v)}]")
    return out


def detect_injection(text: str) -> list[str]:
    if not text:
        return []
    return [name for name, rx in INJECTION_PATTERNS if rx.search(text)]


def scan_terms(text: str, terms: list[str]) -> list[str]:
    if not text or not terms:
        return []
    low = text.lower()
    return [t for t in terms if t and t.lower() in low]


class AIGovernanceService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.audit = AuditService(db)

    def _require_manager(self, actor: User):
        if actor.role not in MANAGER_ROLES:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN,
                                detail="Manager or admin role required")

    # ---------- policy ----------
    async def get_policy(self, organization_id: uuid.UUID) -> AIGovernancePolicy:
        p = (await self.db.execute(select(AIGovernancePolicy).filter(
            AIGovernancePolicy.organization_id == organization_id,
            AIGovernancePolicy.is_deleted == False))).scalars().first()
        if p is None:
            p = AIGovernancePolicy(organization_id=organization_id)
            self.db.add(p)
            await self.db.flush()
        return p

    async def policy(self, actor: User) -> dict:
        return self._ser_policy(await self.get_policy(actor.organization_id))

    async def update_policy(self, actor: User, data: dict) -> dict:
        self._require_manager(actor)
        p = await self.get_policy(actor.organization_id)
        if data.get("pii_action") and data["pii_action"] not in PII_ACTIONS:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST,
                                detail=f"pii_action must be one of {list(PII_ACTIONS)}")
        if data.get("injection_action") and data["injection_action"] not in INJECTION_ACTIONS:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST,
                                detail=f"injection_action must be one of {list(INJECTION_ACTIONS)}")
        for f in ("is_enabled", "pii_detection", "pii_action", "pii_types", "injection_protection",
                  "injection_action", "content_filter", "blocked_terms", "allowed_providers",
                  "allowed_models", "role_restrictions", "max_prompt_chars", "require_grounding",
                  "log_prompt_snippets"):
            if f in data and data[f] is not None:
                setattr(p, f, data[f])
        await self.audit.log_event(actor.organization_id, actor_user_id=actor.id,
                                   action="AI_POLICY_UPDATED", resource_type="ai_governance",
                                   action_metadata={"fields": [k for k in data if data[k] is not None]})
        await self.db.commit()
        await self.db.refresh(p)
        return self._ser_policy(p)

    # ---------- enforcement (called from the gateway guard phase) ----------
    async def enforce(self, actor: User, *, prompt: str | None, system_prompt: str | None = None,
                      task_type: str = "general", provider: str | None = None,
                      model: str | None = None) -> dict:
        """Run every enabled control. Returns
        {prompt, system_prompt, violations, findings, action}. Raises 403 when a
        control blocks. Always logs a governance event."""
        p = await self.get_policy(actor.organization_id)
        report = {"prompt": prompt, "system_prompt": system_prompt, "violations": [],
                  "findings": {}, "action": "allowed"}
        if not p.is_enabled:
            return report

        combined = f"{system_prompt or ''}\n{prompt or ''}"

        # 1) usage policy: prompt size
        if p.max_prompt_chars and len(combined) > p.max_prompt_chars:
            await self._log(actor, "prompt_size", "blocked", rule="max_prompt_chars",
                            task_type=task_type, provider=provider, model=model,
                            findings={"length": len(combined), "limit": p.max_prompt_chars}, policy=p)
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST,
                                detail=f"Prompt exceeds the {p.max_prompt_chars}-character policy limit.")

        # 2) model / provider / role restrictions
        denied = self._check_restrictions(actor, p, provider, model, task_type)
        if denied:
            await self._log(actor, "model_restriction", "blocked", rule=denied,
                            task_type=task_type, provider=provider, model=model,
                            findings={"provider": provider, "model": model, "role": actor.role}, policy=p)
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN,
                                detail=f"AI policy denies this request ({denied}).")

        # 3) prompt injection
        if p.injection_protection:
            hits = detect_injection(combined)
            if hits:
                report["violations"].append({"type": "injection", "rules": hits})
                if p.injection_action == "block":
                    await self._log(actor, "injection", "blocked", rule=",".join(hits),
                                    task_type=task_type, provider=provider, model=model,
                                    findings={"patterns": hits}, policy=p, snippet=combined)
                    raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST,
                                        detail="Prompt blocked: possible prompt-injection attempt.")
                await self._log(actor, "injection", "flagged", rule=",".join(hits),
                                task_type=task_type, provider=provider, model=model,
                                findings={"patterns": hits}, policy=p, snippet=combined)

        # 4) content filter
        if p.content_filter and p.blocked_terms:
            hits = scan_terms(combined, list(p.blocked_terms))
            if hits:
                report["violations"].append({"type": "content", "terms": hits})
                await self._log(actor, "content", "blocked", rule=",".join(hits[:5]),
                                task_type=task_type, provider=provider, model=model,
                                findings={"terms": hits}, policy=p, snippet=combined)
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST,
                                    detail="Prompt blocked by the content policy.")

        # 5) PII detection / masking
        if p.pii_detection:
            findings = scan_pii(combined, list(p.pii_types or []))
            if findings:
                summary = {k: len(v) for k, v in findings.items()}
                report["findings"] = summary
                report["violations"].append({"type": "pii", "types": list(findings.keys())})
                if p.pii_action == "block":
                    await self._log(actor, "pii", "blocked", rule=",".join(findings.keys()),
                                    task_type=task_type, provider=provider, model=model,
                                    findings=summary, policy=p)
                    raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST,
                                        detail=f"Prompt blocked: contains sensitive data ({', '.join(findings)}).")
                if p.pii_action == "mask":
                    report["prompt"] = mask_pii(prompt or "", findings)
                    report["system_prompt"] = mask_pii(system_prompt, findings) if system_prompt else system_prompt
                    report["action"] = "masked"
                    await self._log(actor, "pii", "masked", rule=",".join(findings.keys()),
                                    task_type=task_type, provider=provider, model=model,
                                    findings=summary, policy=p)
                else:  # flag
                    await self._log(actor, "pii", "flagged", rule=",".join(findings.keys()),
                                    task_type=task_type, provider=provider, model=model,
                                    findings=summary, policy=p)
        return report

    def _check_restrictions(self, actor: User, p: AIGovernancePolicy,
                            provider: str | None, model: str | None, task_type: str) -> str | None:
        if provider and p.allowed_providers and provider not in p.allowed_providers:
            return "provider_not_allowed"
        if model and p.allowed_models and model not in p.allowed_models:
            return "model_not_allowed"
        rr = p.role_restrictions or {}
        allowed_tasks = rr.get(actor.role)
        if allowed_tasks and task_type not in allowed_tasks:
            return "task_not_allowed_for_role"
        return None

    async def _log(self, actor: User, event_type: str, action_taken: str, *, rule=None,
                   task_type=None, provider=None, model=None, findings=None,
                   policy: AIGovernancePolicy | None = None, snippet: str | None = None):
        snip = None
        if snippet and policy is not None and policy.log_prompt_snippets:
            # never store raw PII in the compliance log
            snip = mask_pii(snippet[:400], scan_pii(snippet[:400]))
        self.db.add(AIGovernanceEvent(
            organization_id=actor.organization_id, user_id=actor.id, event_type=event_type,
            action_taken=action_taken, rule=(rule or "")[:80], task_type=task_type,
            provider=provider, model=model, findings=findings or {}, prompt_snippet=snip))
        await self.db.flush()

    # ---------- events / dashboard / report ----------
    async def events(self, actor: User, *, limit: int = 100, event_type: str | None = None,
                     action: str | None = None) -> dict:
        self._require_manager(actor)
        q = select(AIGovernanceEvent).filter(
            AIGovernanceEvent.organization_id == actor.organization_id,
            AIGovernanceEvent.is_deleted == False)
        if event_type:
            q = q.filter(AIGovernanceEvent.event_type == event_type)
        if action:
            q = q.filter(AIGovernanceEvent.action_taken == action)
        rows = (await self.db.execute(q.order_by(AIGovernanceEvent.created_at.desc())
                                      .limit(limit))).scalars().all()
        return {"count": len(rows), "items": [self._ser_event(e) for e in rows]}

    async def dashboard(self, actor: User) -> dict:
        p = await self.get_policy(actor.organization_id)
        cutoff = _now() - timedelta(days=30)
        rows = (await self.db.execute(select(AIGovernanceEvent).filter(
            AIGovernanceEvent.organization_id == actor.organization_id,
            AIGovernanceEvent.is_deleted == False).order_by(
            AIGovernanceEvent.created_at.desc()).limit(5000))).scalars().all()
        recent = [e for e in rows if e.created_at and _aware(e.created_at) >= cutoff]
        by_type: dict = {}
        by_action: dict = {}
        for e in recent:
            by_type[e.event_type] = by_type.get(e.event_type, 0) + 1
            by_action[e.action_taken] = by_action.get(e.action_taken, 0) + 1
        controls = {"pii_detection": p.pii_detection, "injection_protection": p.injection_protection,
                    "content_filter": p.content_filter,
                    "model_restrictions": bool(p.allowed_providers or p.allowed_models),
                    "role_restrictions": bool(p.role_restrictions),
                    "require_grounding": p.require_grounding}
        return {"policy_enabled": p.is_enabled,
                "controls_active": sum(1 for v in controls.values() if v), "controls": controls,
                "events_30d": len(recent), "blocked_30d": by_action.get("blocked", 0),
                "masked_30d": by_action.get("masked", 0), "flagged_30d": by_action.get("flagged", 0),
                "by_type": by_type, "by_action": by_action,
                "recent": [self._ser_event(e) for e in recent[:10]]}

    async def report(self, actor: User) -> dict:
        self._require_manager(actor)
        dash = await self.dashboard(actor)
        return {"generated_at": _now().isoformat(), "policy": await self.policy(actor),
                "summary": {k: dash[k] for k in ("controls_active", "events_30d", "blocked_30d",
                                                 "masked_30d", "flagged_30d")},
                "by_type": dash["by_type"], "by_action": dash["by_action"],
                "recent": dash["recent"]}

    async def export_csv(self, actor: User) -> str:
        self._require_manager(actor)
        rows = (await self.db.execute(select(AIGovernanceEvent).filter(
            AIGovernanceEvent.organization_id == actor.organization_id,
            AIGovernanceEvent.is_deleted == False)
            .order_by(AIGovernanceEvent.created_at.desc()).limit(5000))).scalars().all()
        buf = io.StringIO()
        w = csv.writer(buf)
        w.writerow(["created_at", "event_type", "action", "rule", "task_type", "provider", "model", "findings"])
        for e in rows:
            w.writerow([_aware(e.created_at).isoformat() if e.created_at else "", e.event_type,
                        e.action_taken, e.rule, e.task_type, e.provider, e.model, str(e.findings)])
        await self.audit.log_event(actor.organization_id, actor_user_id=actor.id,
                                   action="AI_GOVERNANCE_EXPORTED", resource_type="ai_governance",
                                   action_metadata={"rows": len(rows)})
        await self.db.commit()
        return buf.getvalue()

    # ---------- preview (test the controls without calling an LLM) ----------
    async def preview(self, actor: User, text: str) -> dict:
        p = await self.get_policy(actor.organization_id)
        findings = scan_pii(text, list(p.pii_types or [])) if p.pii_detection else {}
        return {"pii": {k: len(v) for k, v in findings.items()},
                "masked_preview": mask_pii(text, findings) if findings else text,
                "injection": detect_injection(text) if p.injection_protection else [],
                "blocked_terms": scan_terms(text, list(p.blocked_terms or [])) if p.content_filter else [],
                "length": len(text or ""), "max_prompt_chars": p.max_prompt_chars}

    def catalog(self) -> dict:
        return {"pii_types": list(PII_PATTERNS.keys()),
                "injection_rules": [n for n, _ in INJECTION_PATTERNS],
                "pii_actions": list(PII_ACTIONS), "injection_actions": list(INJECTION_ACTIONS)}

    # ---------- serialization ----------
    @staticmethod
    def _ser_policy(p: AIGovernancePolicy) -> dict:
        return {"is_enabled": p.is_enabled, "pii_detection": p.pii_detection,
                "pii_action": p.pii_action, "pii_types": p.pii_types or [],
                "injection_protection": p.injection_protection, "injection_action": p.injection_action,
                "content_filter": p.content_filter, "blocked_terms": p.blocked_terms or [],
                "allowed_providers": p.allowed_providers or [], "allowed_models": p.allowed_models or [],
                "role_restrictions": p.role_restrictions or {},
                "max_prompt_chars": p.max_prompt_chars, "require_grounding": p.require_grounding,
                "log_prompt_snippets": p.log_prompt_snippets}

    @staticmethod
    def _ser_event(e: AIGovernanceEvent) -> dict:
        return {"id": str(e.id), "event_type": e.event_type, "action_taken": e.action_taken,
                "rule": e.rule, "task_type": e.task_type, "provider": e.provider, "model": e.model,
                "findings": e.findings or {}, "prompt_snippet": e.prompt_snippet,
                "user_id": str(e.user_id) if e.user_id else None,
                "created_at": _aware(e.created_at).isoformat() if e.created_at else None}
