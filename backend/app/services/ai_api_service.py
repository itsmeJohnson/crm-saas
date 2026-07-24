"""AI API & SDK — the public developer surface of the AI Platform.

This module does NOT reimplement any AI capability. It is a thin, hardened
edge in front of :class:`AIGatewayService`:

  * API KEYS      — hashed at rest, scoped, per-key rate limit + daily quota,
                    optional provider/model/IP allowlists and expiry.
  * AUTHENTICATION— `Authorization: Bearer crm_live_…` or `X-API-Key`. A key
                    acts as its creating user, so org scoping, downline scoping,
                    RBAC and AI governance all keep working unchanged.
  * RATE LIMITS   — durable sliding-minute window + UTC-day quota computed from
                    the ai_api_requests ledger (no Redis dependency, so it is
                    deterministic in tests and correct across instances).
  * VERSIONING    — an explicit version registry, X-API-Version on every
                    response, and a discovery endpoint.
  * WEBHOOKS      — signed (HMAC-SHA256) outbound delivery of AI events with
                    exponential-backoff retries and a dead-letter state.
  * SDK + DOCS    — generated Python / Node / Java clients, an OpenAPI 3.1 spec
                    for the public surface, endpoint reference and examples.
  * PORTAL        — one aggregated payload for the Developer Portal page.

Provider neutrality is preserved end to end: the public API accepts optional
provider/model hints but never assumes one, and routing stays in the gateway's
configured fallback chain.
"""
import csv
import hashlib
import hmac
import io
import json
import secrets
import time
import uuid
from datetime import datetime, timezone, timedelta

from fastapi import HTTPException, status
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User
from app.models.ai_api import AIApiKey, AIApiRequest, AIWebhook, AIWebhookDelivery
from app.models.ai_platform import AIPromptTemplate, AIProviderConfig
from app.services.ai_gateway_service import AIGatewayService
from app.services.audit_service import AuditService

MANAGER_ROLES = ("SuperAdmin", "OrgAdmin", "Manager")

CURRENT_VERSION = "v1"
API_VERSIONS = [
    {"version": "v1", "status": "stable", "released": "2026-07-23", "sunset": None,
     "notes": "Generate, chat, streaming, models, templates and usage."},
]

DEFAULT_BASE_URL = "https://api.example.com/api/v1/ai-api"

# ---- Scopes. A key with an empty scope list gets DEFAULT_SCOPES.
SCOPES: dict[str, str] = {
    "ai:generate": "Create one-shot completions (POST /generate)",
    "ai:chat": "Multi-turn chat with conversation memory (POST /chat)",
    "ai:stream": "Server-sent-events streaming (POST /stream)",
    "ai:models": "List routable providers and models (GET /models)",
    "ai:templates": "List approved prompt templates (GET /templates)",
    "ai:usage": "Read this key's usage and quota (GET /usage)",
}
DEFAULT_SCOPES = ["ai:generate", "ai:chat", "ai:stream", "ai:models", "ai:templates", "ai:usage"]

ENVIRONMENTS = ("live", "test")

# ---- Webhook events emitted by the AI API edge.
WEBHOOK_EVENTS: dict[str, str] = {
    "ai.generation.completed": "A completion finished successfully via the public API.",
    "ai.generation.failed": "A completion failed (provider error or a governance block).",
    "ai.rate_limit.exceeded": "An API key exceeded its per-minute rate limit.",
    "ai.quota.exceeded": "An API key exhausted its daily quota.",
    "ai.key.created": "A new API key was issued.",
    "ai.key.revoked": "An API key was revoked.",
    "ai.webhook.test": "A manual test delivery from the Developer Portal.",
}

# Exponential backoff between webhook delivery attempts (minutes).
RETRY_BACKOFF_MINUTES = [1, 5, 15, 60, 240]

SIGNATURE_HEADER = "X-CRM-AI-Signature"


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _aware(dt):
    """SQLite hands back naive datetimes — normalise before any comparison."""
    if dt is None:
        return None
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


def _iso(dt):
    a = _aware(dt)
    return a.isoformat() if a else None


def hash_key(raw: str) -> str:
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def generate_key(environment: str = "live") -> tuple[str, str, str]:
    """Return (raw_key, key_prefix, key_hash). The raw key is shown once."""
    env = environment if environment in ENVIRONMENTS else "live"
    raw = f"crm_{env}_{secrets.token_urlsafe(32)}"
    return raw, raw[:20], hash_key(raw)


def sign_payload(secret: str, timestamp: int, body: str) -> str:
    """HMAC-SHA256 over "<timestamp>.<raw body>" — the value of the v1 element."""
    msg = f"{timestamp}.{body}".encode("utf-8")
    return hmac.new(secret.encode("utf-8"), msg, hashlib.sha256).hexdigest()


def build_signature_header(secret: str, body: str, timestamp: int | None = None) -> str:
    ts = timestamp if timestamp is not None else int(time.time())
    return f"t={ts},v1={sign_payload(secret, ts, body)}"


def verify_signature(secret: str, header: str, body: str, tolerance_seconds: int = 300) -> bool:
    """Server-side counterpart of the SDK helpers — used by tests and by any
    inbound relay that needs to prove a payload came from us."""
    parts = dict(p.split("=", 1) for p in (header or "").split(",") if "=" in p)
    ts, sig = parts.get("t"), parts.get("v1")
    if not ts or not sig:
        return False
    try:
        if abs(time.time() - int(ts)) > tolerance_seconds:
            return False
    except ValueError:
        return False
    return hmac.compare_digest(sign_payload(secret, int(ts), body), sig)


class AIApiService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.audit = AuditService(db)

    # ================= guards =================
    def _require_manager(self, actor: User):
        if actor.role not in MANAGER_ROLES:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN,
                                detail="Only managers and administrators can manage developer API access.")

    @staticmethod
    def catalog() -> dict:
        return {
            "scopes": [{"key": k, "description": v} for k, v in SCOPES.items()],
            "default_scopes": DEFAULT_SCOPES,
            "environments": list(ENVIRONMENTS),
            "webhook_events": [{"key": k, "description": v} for k, v in WEBHOOK_EVENTS.items()],
            "versions": API_VERSIONS,
            "current_version": CURRENT_VERSION,
            "retry_backoff_minutes": RETRY_BACKOFF_MINUTES,
            "signature_header": SIGNATURE_HEADER,
            "sdk_languages": _sdk_languages(),
        }

    # ================= API keys =================
    async def create_key(self, actor: User, data: dict) -> dict:
        self._require_manager(actor)
        env = data.get("environment") or "live"
        if env not in ENVIRONMENTS:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST,
                                detail=f"environment must be one of {list(ENVIRONMENTS)}")
        scopes = self._validate_scopes(data.get("scopes"))
        raw, prefix, digest = generate_key(env)
        expires_in = data.get("expires_in_days")
        key = AIApiKey(
            organization_id=actor.organization_id, name=data.get("name") or "API key",
            environment=env, key_prefix=prefix, key_hash=digest, scopes=scopes,
            rate_limit_per_min=int(data.get("rate_limit_per_min") or 60),
            daily_quota=int(data.get("daily_quota") or 1000),
            allowed_providers=data.get("allowed_providers") or [],
            allowed_models=data.get("allowed_models") or [],
            allowed_ips=data.get("allowed_ips") or [],
            expires_at=_now() + timedelta(days=int(expires_in)) if expires_in else None,
            is_active=True, created_by=actor.id,
        )
        self.db.add(key)
        await self.db.flush()
        await self._audit(actor, "AI_API_KEY_CREATED", key.id, {"name": key.name, "scopes": scopes})
        await self.fire_event(actor.organization_id, "ai.key.created",
                              {"key_id": str(key.id), "name": key.name, "environment": env})
        out = self._ser_key(key)
        out["api_key"] = raw  # shown exactly once
        return out

    async def list_keys(self, actor: User) -> list[dict]:
        self._require_manager(actor)
        rows = (await self.db.execute(select(AIApiKey).filter(
            AIApiKey.organization_id == actor.organization_id, AIApiKey.is_deleted == False)
            .order_by(AIApiKey.created_at.desc()))).scalars().all()
        return [self._ser_key(k) for k in rows]

    async def _key_row(self, actor: User, key_id: uuid.UUID) -> AIApiKey:
        k = (await self.db.execute(select(AIApiKey).filter(
            AIApiKey.id == key_id, AIApiKey.organization_id == actor.organization_id,
            AIApiKey.is_deleted == False))).scalars().first()
        if not k:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="API key not found")
        return k

    async def update_key(self, actor: User, key_id: uuid.UUID, data: dict) -> dict:
        self._require_manager(actor)
        k = await self._key_row(actor, key_id)
        if "scopes" in data and data["scopes"] is not None:
            k.scopes = self._validate_scopes(data["scopes"])
        for f in ("name", "rate_limit_per_min", "daily_quota", "allowed_providers",
                  "allowed_models", "allowed_ips", "is_active"):
            if f in data and data[f] is not None:
                setattr(k, f, data[f])
        if data.get("expires_in_days") is not None:
            days = int(data["expires_in_days"])
            k.expires_at = _now() + timedelta(days=days) if days > 0 else None
        self.db.add(k)
        await self.db.flush()
        await self._audit(actor, "AI_API_KEY_UPDATED", k.id, {"fields": sorted(data.keys())})
        return self._ser_key(k)

    async def rotate_key(self, actor: User, key_id: uuid.UUID) -> dict:
        self._require_manager(actor)
        k = await self._key_row(actor, key_id)
        raw, prefix, digest = generate_key(k.environment)
        k.key_prefix, k.key_hash = prefix, digest
        k.revoked_at = None
        k.is_active = True
        self.db.add(k)
        await self.db.flush()
        await self._audit(actor, "AI_API_KEY_ROTATED", k.id, {"name": k.name})
        out = self._ser_key(k)
        out["api_key"] = raw
        return out

    async def revoke_key(self, actor: User, key_id: uuid.UUID) -> dict:
        self._require_manager(actor)
        k = await self._key_row(actor, key_id)
        k.is_active = False
        k.revoked_at = _now()
        self.db.add(k)
        await self.db.flush()
        await self._audit(actor, "AI_API_KEY_REVOKED", k.id, {"name": k.name})
        await self.fire_event(actor.organization_id, "ai.key.revoked",
                              {"key_id": str(k.id), "name": k.name})
        return self._ser_key(k)

    async def delete_key(self, actor: User, key_id: uuid.UUID) -> None:
        self._require_manager(actor)
        k = await self._key_row(actor, key_id)
        k.is_deleted = True
        k.is_active = False
        self.db.add(k)
        await self.db.flush()
        await self._audit(actor, "AI_API_KEY_DELETED", k.id, {"name": k.name})

    @staticmethod
    def _validate_scopes(scopes) -> list[str]:
        if not scopes:
            return list(DEFAULT_SCOPES)
        bad = [s for s in scopes if s not in SCOPES]
        if bad:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST,
                                detail=f"Unknown scope(s): {bad}. Allowed: {sorted(SCOPES)}")
        return list(dict.fromkeys(scopes))

    # ================= authentication =================
    async def authenticate(self, raw_key: str | None, *, client_ip: str | None = None) -> tuple[AIApiKey, User]:
        """Resolve a raw API key to (key, owning user). Raises 401/403."""
        if not raw_key:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED,
                                detail="Missing API key. Send 'Authorization: Bearer <key>' or 'X-API-Key: <key>'.",
                                headers={"WWW-Authenticate": "Bearer"})
        k = (await self.db.execute(select(AIApiKey).filter(
            AIApiKey.key_hash == hash_key(raw_key.strip()),
            AIApiKey.is_deleted == False))).scalars().first()
        if not k:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid API key.")
        if not k.is_active or k.revoked_at is not None:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="This API key has been revoked.")
        exp = _aware(k.expires_at)
        if exp and exp < _now():
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="This API key has expired.")
        if k.allowed_ips and client_ip and client_ip not in k.allowed_ips:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN,
                                detail="This API key is not permitted from this IP address.")
        owner = (await self.db.execute(select(User).filter(
            User.id == k.created_by, User.is_active == True))).scalars().first()
        if not owner:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED,
                                detail="The user that owns this API key is no longer active.")
        k.last_used_at = _now()
        k.use_count = (k.use_count or 0) + 1
        self.db.add(k)
        await self.db.flush()
        return k, owner

    def require_scope(self, key: AIApiKey, scope: str) -> None:
        scopes = key.scopes or DEFAULT_SCOPES
        if scope not in scopes:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN,
                                detail=f"This API key lacks the '{scope}' scope.")

    def check_model_allowed(self, key: AIApiKey, provider: str | None, model: str | None) -> None:
        if provider and key.allowed_providers and provider not in key.allowed_providers:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN,
                                detail=f"This API key may not route to provider '{provider}'.")
        if model and key.allowed_models and model not in key.allowed_models:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN,
                                detail=f"This API key may not use model '{model}'.")

    # ================= rate limits + quota =================
    async def rate_limit_state(self, key: AIApiKey) -> dict:
        """Sliding 60-second window + UTC-day quota, read from the request ledger."""
        now = _now()
        minute_ago = now - timedelta(seconds=60)
        day_start = datetime(now.year, now.month, now.day, tzinfo=timezone.utc)
        minute_used = (await self.db.execute(select(func.count(AIApiRequest.id)).filter(
            AIApiRequest.api_key_id == key.id, AIApiRequest.created_at >= minute_ago))).scalar() or 0
        day_used = (await self.db.execute(select(func.count(AIApiRequest.id)).filter(
            AIApiRequest.api_key_id == key.id, AIApiRequest.created_at >= day_start))).scalar() or 0
        return {
            "limit": key.rate_limit_per_min, "used": int(minute_used),
            "remaining": max(0, key.rate_limit_per_min - int(minute_used)),
            "reset": int((now + timedelta(seconds=60)).timestamp()),
            "quota": key.daily_quota, "quota_used": int(day_used),
            "quota_remaining": max(0, key.daily_quota - int(day_used)),
            "quota_reset": int((day_start + timedelta(days=1)).timestamp()),
        }

    async def enforce_rate_limit(self, key: AIApiKey) -> dict:
        """Raise 429 when the minute window or the daily quota is spent.

        Nothing is written here — the request row and the webhook event are
        recorded by :meth:`record_failure`, which the caller invokes and commits
        so the ledger survives the request's rollback.
        """
        state = await self.rate_limit_state(key)
        if state["quota_remaining"] <= 0:
            raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                                detail=f"Daily quota of {key.daily_quota} requests exhausted for this API key.",
                                headers={"Retry-After": str(max(1, state["quota_reset"] - int(time.time()))),
                                         "X-Quota-Remaining": "0"})
        if state["remaining"] <= 0:
            raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                                detail=f"Rate limit of {key.rate_limit_per_min} requests/minute exceeded.",
                                headers={"Retry-After": "60", "X-RateLimit-Remaining": "0"})
        return state

    async def record_failure(self, key: AIApiKey, endpoint: str, exc: HTTPException) -> None:
        """Log a failed public-API call and fan the matching event out to
        webhooks. The caller must commit before re-raising."""
        detail = str(exc.detail)
        await self.log_request(key, endpoint, status_code=exc.status_code, error=detail)
        if exc.status_code == status.HTTP_429_TOO_MANY_REQUESTS:
            event = "ai.quota.exceeded" if "quota" in detail.lower() else "ai.rate_limit.exceeded"
            data = {"key_id": str(key.id), "name": key.name, "endpoint": endpoint,
                    "limit_per_min": key.rate_limit_per_min, "daily_quota": key.daily_quota}
        else:
            event = "ai.generation.failed"
            data = {"key_id": str(key.id), "name": key.name, "endpoint": endpoint,
                    "status_code": exc.status_code, "error": detail}
        await self.fire_event(key.organization_id, event, data)

    @staticmethod
    def rate_limit_headers(state: dict) -> dict:
        return {
            "X-RateLimit-Limit": str(state["limit"]),
            "X-RateLimit-Remaining": str(max(0, state["remaining"] - 1)),
            "X-RateLimit-Reset": str(state["reset"]),
            "X-Quota-Limit": str(state["quota"]),
            "X-Quota-Remaining": str(max(0, state["quota_remaining"] - 1)),
            "X-API-Version": CURRENT_VERSION,
        }

    async def log_request(self, key: AIApiKey, endpoint: str, *, method: str = "POST",
                          status_code: int = 200, latency_ms: int = 0, tokens: int = 0,
                          cost_usd: float = 0.0, provider: str | None = None,
                          model: str | None = None, error: str | None = None) -> AIApiRequest:
        row = AIApiRequest(organization_id=key.organization_id, api_key_id=key.id,
                           endpoint=endpoint, method=method, api_version=CURRENT_VERSION,
                           status_code=status_code, latency_ms=latency_ms, tokens=tokens,
                           cost_usd=cost_usd, provider=provider, model=model,
                           error=(error or None) and str(error)[:300])
        self.db.add(row)
        await self.db.flush()
        return row

    # ================= public API operations =================
    async def api_generate(self, key: AIApiKey, owner: User, payload: dict) -> tuple[dict, dict]:
        """POST /generate — delegates to the AI gateway (governance, caching,
        provider fallback and usage logging all still apply)."""
        self.require_scope(key, "ai:generate")
        self.check_model_allowed(key, payload.get("provider"), payload.get("model"))
        state = await self.enforce_rate_limit(key)
        started = time.monotonic()
        out = await AIGatewayService(self.db).generate(owner, **payload)
        latency = int((time.monotonic() - started) * 1000)
        tokens = _total_tokens(out)
        await self.log_request(key, "generate", latency_ms=latency, tokens=tokens,
                               cost_usd=float(out.get("cost_usd") or 0),
                               provider=out.get("provider"), model=out.get("model"))
        await self.fire_event(key.organization_id, "ai.generation.completed",
                              {"key_id": str(key.id), "endpoint": "generate",
                               "provider": out.get("provider"), "model": out.get("model"),
                               "tokens": tokens, "cost_usd": out.get("cost_usd"),
                               "latency_ms": latency})
        return out, self.rate_limit_headers(state)

    async def api_chat(self, key: AIApiKey, owner: User, payload: dict) -> tuple[dict, dict]:
        self.require_scope(key, "ai:chat")
        self.check_model_allowed(key, payload.get("provider"), payload.get("model"))
        state = await self.enforce_rate_limit(key)
        started = time.monotonic()
        out = await AIGatewayService(self.db).chat(owner, payload)
        latency = int((time.monotonic() - started) * 1000)
        tokens = _total_tokens(out)
        await self.log_request(key, "chat", latency_ms=latency, tokens=tokens,
                               cost_usd=float(out.get("cost_usd") or 0),
                               provider=out.get("provider"), model=out.get("model"))
        await self.fire_event(key.organization_id, "ai.generation.completed",
                              {"key_id": str(key.id), "endpoint": "chat",
                               "provider": out.get("provider"), "model": out.get("model"),
                               "tokens": tokens, "latency_ms": latency})
        return out, self.rate_limit_headers(state)

    async def api_models(self, key: AIApiKey, owner: User) -> dict:
        """Every provider/model this key may route to — never a hardcoded list."""
        self.require_scope(key, "ai:models")
        gw = AIGatewayService(self.db)
        settings_row = await gw._settings(owner.organization_id)
        rows = (await self.db.execute(select(AIProviderConfig).filter(
            AIProviderConfig.organization_id == owner.organization_id,
            AIProviderConfig.is_active == True, AIProviderConfig.is_deleted == False)
            .order_by(AIProviderConfig.priority.asc()))).scalars().all()
        providers = []
        for p in rows:
            if key.allowed_providers and p.provider not in key.allowed_providers:
                continue
            models = [m.get("model") for m in (p.models or []) if m.get("model")] or [p.default_model]
            if key.allowed_models:
                models = [m for m in models if m in key.allowed_models]
            providers.append({"provider": p.provider, "name": p.name, "priority": p.priority,
                              "default_model": p.default_model, "models": models})
        if not providers:
            providers.append({"provider": settings_row.default_provider, "name": "Default route",
                              "priority": 1, "default_model": settings_row.default_model,
                              "models": [settings_row.default_model]})
        return {"default_provider": settings_row.default_provider,
                "default_model": settings_row.default_model,
                "streaming_enabled": settings_row.streaming_enabled,
                "fallback_chain": [p["provider"] for p in providers],
                "providers": providers}

    async def api_templates(self, key: AIApiKey, owner: User) -> list[dict]:
        """Approved templates only — Prompt Studio drafts stay private."""
        self.require_scope(key, "ai:templates")
        rows = (await self.db.execute(select(AIPromptTemplate).filter(
            AIPromptTemplate.organization_id == owner.organization_id,
            AIPromptTemplate.is_active == True, AIPromptTemplate.is_deleted == False)
            .order_by(AIPromptTemplate.key.asc()))).scalars().all()
        return [{"key": t.key, "name": t.name, "task_type": t.task_type,
                 "description": t.description, "variables": t.variables or [],
                 "version": t.version, "status": t.status}
                for t in rows if (t.status or "approved") == "approved"]

    async def api_usage(self, key: AIApiKey, days: int = 30) -> dict:
        self.require_scope(key, "ai:usage")
        since = _now() - timedelta(days=days)
        rows = (await self.db.execute(select(AIApiRequest).filter(
            AIApiRequest.api_key_id == key.id, AIApiRequest.created_at >= since))).scalars().all()
        ok = [r for r in rows if r.status_code < 400]
        by_endpoint: dict[str, int] = {}
        for r in rows:
            by_endpoint[r.endpoint] = by_endpoint.get(r.endpoint, 0) + 1
        latencies = sorted(r.latency_ms for r in ok)
        state = await self.rate_limit_state(key)
        return {
            "key_id": str(key.id), "name": key.name, "environment": key.environment,
            "window_days": days, "requests": len(rows), "successful": len(ok),
            "failed": len(rows) - len(ok),
            "tokens": sum(int(r.tokens or 0) for r in rows),
            "cost_usd": round(sum(float(r.cost_usd or 0) for r in rows), 6),
            "avg_latency_ms": int(sum(latencies) / len(latencies)) if latencies else 0,
            "by_endpoint": by_endpoint,
            "rate_limit": state,
        }

    # ================= webhooks =================
    async def list_webhooks(self, actor: User) -> list[dict]:
        self._require_manager(actor)
        rows = (await self.db.execute(select(AIWebhook).filter(
            AIWebhook.organization_id == actor.organization_id, AIWebhook.is_deleted == False)
            .order_by(AIWebhook.created_at.desc()))).scalars().all()
        return [self._ser_webhook(w) for w in rows]

    async def create_webhook(self, actor: User, data: dict) -> dict:
        self._require_manager(actor)
        url = (data.get("url") or "").strip()
        if not url.startswith(("http://", "https://")):
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST,
                                detail="Webhook url must be an http(s) URL.")
        events = self._validate_events(data.get("events"))
        w = AIWebhook(organization_id=actor.organization_id, name=data.get("name") or "AI webhook",
                      url=url, events=events, secret=secrets.token_urlsafe(32)[:64],
                      is_active=data.get("is_active", True),
                      max_attempts=int(data.get("max_attempts") or 5), created_by=actor.id)
        self.db.add(w)
        await self.db.flush()
        await self._audit(actor, "AI_WEBHOOK_CREATED", w.id, {"url": url, "events": events})
        return self._ser_webhook(w, reveal_secret=True)

    async def _webhook_row(self, actor: User, webhook_id: uuid.UUID) -> AIWebhook:
        w = (await self.db.execute(select(AIWebhook).filter(
            AIWebhook.id == webhook_id, AIWebhook.organization_id == actor.organization_id,
            AIWebhook.is_deleted == False))).scalars().first()
        if not w:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Webhook not found")
        return w

    async def update_webhook(self, actor: User, webhook_id: uuid.UUID, data: dict) -> dict:
        self._require_manager(actor)
        w = await self._webhook_row(actor, webhook_id)
        if "events" in data and data["events"] is not None:
            w.events = self._validate_events(data["events"])
        for f in ("name", "url", "is_active", "max_attempts"):
            if f in data and data[f] is not None:
                setattr(w, f, data[f])
        self.db.add(w)
        await self.db.flush()
        return self._ser_webhook(w)

    async def rotate_webhook_secret(self, actor: User, webhook_id: uuid.UUID) -> dict:
        self._require_manager(actor)
        w = await self._webhook_row(actor, webhook_id)
        w.secret = secrets.token_urlsafe(32)[:64]
        self.db.add(w)
        await self.db.flush()
        await self._audit(actor, "AI_WEBHOOK_SECRET_ROTATED", w.id, {"name": w.name})
        return self._ser_webhook(w, reveal_secret=True)

    async def delete_webhook(self, actor: User, webhook_id: uuid.UUID) -> None:
        self._require_manager(actor)
        w = await self._webhook_row(actor, webhook_id)
        w.is_deleted = True
        w.is_active = False
        self.db.add(w)
        await self.db.flush()

    async def test_webhook(self, actor: User, webhook_id: uuid.UUID) -> dict:
        self._require_manager(actor)
        w = await self._webhook_row(actor, webhook_id)
        d = await self._queue_delivery(w, "ai.webhook.test",
                                       {"message": "Test delivery from the CRM Developer Portal.",
                                        "organization_id": str(actor.organization_id)})
        await self._attempt_delivery(w, d)
        return self._ser_delivery(d)

    @staticmethod
    def _validate_events(events) -> list[str]:
        if not events:
            return []
        bad = [e for e in events if e not in WEBHOOK_EVENTS]
        if bad:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST,
                                detail=f"Unknown event(s): {bad}. Allowed: {sorted(WEBHOOK_EVENTS)}")
        return list(dict.fromkeys(events))

    async def fire_event(self, organization_id: uuid.UUID, event_type: str, data: dict) -> int:
        """Queue + attempt delivery of an AI event to every subscribed webhook.

        Never raises: an outbound webhook problem must not fail the API call
        that produced the event.
        """
        try:
            hooks = (await self.db.execute(select(AIWebhook).filter(
                AIWebhook.organization_id == organization_id, AIWebhook.is_active == True,
                AIWebhook.is_deleted == False))).scalars().all()
            targets = [h for h in hooks if not h.events or event_type in h.events]
            for h in targets:
                d = await self._queue_delivery(h, event_type, data)
                await self._attempt_delivery(h, d)
            return len(targets)
        except Exception:
            return 0

    async def _queue_delivery(self, webhook: AIWebhook, event_type: str, data: dict) -> AIWebhookDelivery:
        payload = {"id": str(uuid.uuid4()), "type": event_type,
                   "created_at": _now().isoformat(),
                   "api_version": CURRENT_VERSION, "data": data}
        d = AIWebhookDelivery(organization_id=webhook.organization_id, webhook_id=webhook.id,
                              event_type=event_type, payload=payload, status="pending",
                              attempts=0, next_retry_at=_now())
        self.db.add(d)
        await self.db.flush()
        return d

    async def _attempt_delivery(self, webhook: AIWebhook, d: AIWebhookDelivery) -> bool:
        """One signed POST. Schedules the next backoff retry on failure, and
        dead-letters once max_attempts is spent."""
        body = json.dumps(d.payload, separators=(",", ":"), sort_keys=True)
        d.attempts = (d.attempts or 0) + 1
        started = time.monotonic()
        ok, code, err = False, None, None
        try:
            import httpx
            headers = {"Content-Type": "application/json",
                       SIGNATURE_HEADER: build_signature_header(webhook.secret, body),
                       "X-CRM-AI-Event": d.event_type,
                       "X-CRM-AI-Delivery": str(d.id),
                       "X-API-Version": CURRENT_VERSION,
                       "User-Agent": f"crm-ai-webhooks/{CURRENT_VERSION}"}
            async with httpx.AsyncClient(timeout=8.0) as client:
                resp = await client.post(webhook.url, content=body, headers=headers)
            code = resp.status_code
            ok = 200 <= resp.status_code < 300
            if not ok:
                err = f"HTTP {resp.status_code}"
        except Exception as e:  # network error, DNS, timeout…
            err = str(e)[:500]
        d.duration_ms = int((time.monotonic() - started) * 1000)
        d.response_code = code
        d.error = err
        if ok:
            d.status = "success"
            d.delivered_at = _now()
            d.next_retry_at = None
            webhook.delivered_count = (webhook.delivered_count or 0) + 1
            webhook.last_status = "success"
        elif d.attempts >= (webhook.max_attempts or 5):
            d.status = "dead_letter"
            d.next_retry_at = None
            webhook.failed_count = (webhook.failed_count or 0) + 1
            webhook.last_status = "dead_letter"
        else:
            d.status = "failed"
            idx = min(d.attempts - 1, len(RETRY_BACKOFF_MINUTES) - 1)
            d.next_retry_at = _now() + timedelta(minutes=RETRY_BACKOFF_MINUTES[idx])
            webhook.failed_count = (webhook.failed_count or 0) + 1
            webhook.last_status = "failed"
        webhook.last_delivery_at = _now()
        self.db.add_all([d, webhook])
        await self.db.flush()
        return ok

    async def retry_due_deliveries(self, organization_id: uuid.UUID | None = None, limit: int = 100) -> dict:
        """Cron step: re-attempt failed deliveries whose backoff has elapsed."""
        q = select(AIWebhookDelivery).filter(
            AIWebhookDelivery.status == "failed", AIWebhookDelivery.is_deleted == False,
            AIWebhookDelivery.next_retry_at != None)
        if organization_id:
            q = q.filter(AIWebhookDelivery.organization_id == organization_id)
        rows = (await self.db.execute(q.order_by(AIWebhookDelivery.next_retry_at.asc())
                                      .limit(limit))).scalars().all()
        now = _now()
        due = [d for d in rows if (_aware(d.next_retry_at) or now) <= now]
        delivered = dead = 0
        for d in due:
            w = (await self.db.execute(select(AIWebhook).filter(
                AIWebhook.id == d.webhook_id, AIWebhook.is_deleted == False))).scalars().first()
            if not w or not w.is_active:
                d.status = "dead_letter"
                d.next_retry_at = None
                self.db.add(d)
                dead += 1
                continue
            if await self._attempt_delivery(w, d):
                delivered += 1
            elif d.status == "dead_letter":
                dead += 1
        await self.db.flush()
        return {"attempted": len(due), "delivered": delivered, "dead_lettered": dead}

    async def deliveries(self, actor: User, *, webhook_id: uuid.UUID | None = None,
                         status_filter: str | None = None, limit: int = 100) -> list[dict]:
        self._require_manager(actor)
        q = select(AIWebhookDelivery).filter(
            AIWebhookDelivery.organization_id == actor.organization_id,
            AIWebhookDelivery.is_deleted == False)
        if webhook_id:
            q = q.filter(AIWebhookDelivery.webhook_id == webhook_id)
        if status_filter:
            q = q.filter(AIWebhookDelivery.status == status_filter)
        rows = (await self.db.execute(q.order_by(AIWebhookDelivery.created_at.desc())
                                      .limit(limit))).scalars().all()
        return [self._ser_delivery(d) for d in rows]

    async def replay_delivery(self, actor: User, delivery_id: uuid.UUID) -> dict:
        """Re-send a failed or dead-lettered delivery immediately."""
        self._require_manager(actor)
        d = (await self.db.execute(select(AIWebhookDelivery).filter(
            AIWebhookDelivery.id == delivery_id,
            AIWebhookDelivery.organization_id == actor.organization_id,
            AIWebhookDelivery.is_deleted == False))).scalars().first()
        if not d:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Delivery not found")
        w = await self._webhook_row(actor, d.webhook_id)
        await self._attempt_delivery(w, d)
        return self._ser_delivery(d)

    # ================= documentation / SDK / examples =================
    @staticmethod
    def endpoints(base_url: str) -> list[dict]:
        """Reference for the public, key-authenticated surface."""
        return [
            {"method": "POST", "path": "/generate", "scope": "ai:generate",
             "summary": "Create a completion",
             "description": "One-shot generation. Accepts a prompt, a message list or a "
                            "template_key with variables. Provider/model are optional hints — "
                            "omit them to use the organization's configured fallback chain.",
             "request": {"prompt": "string", "messages": "[{role, content}]", "task_type": "string",
                         "template_key": "string", "variables": "object", "provider": "string",
                         "model": "string", "temperature": "number", "max_tokens": "integer"},
             "response": {"text": "string", "provider": "string", "model": "string",
                          "tokens": "integer", "cost_usd": "number", "cached": "boolean"}},
            {"method": "POST", "path": "/chat", "scope": "ai:chat",
             "summary": "Multi-turn chat",
             "description": "Chat with server-side conversation memory. Pass the returned "
                            "conversation_id on the next turn to continue the thread.",
             "request": {"message": "string", "conversation_id": "uuid", "title": "string",
                         "context_type": "string", "context_id": "string"},
             "response": {"text": "string", "conversation_id": "uuid", "provider": "string",
                          "model": "string", "tokens": "integer"}},
            {"method": "POST", "path": "/stream", "scope": "ai:stream",
             "summary": "Stream a completion (SSE)",
             "description": "text/event-stream of 'data: {\"delta\": \"…\"}' frames, terminated "
                            "by 'data: [DONE]'.",
             "request": {"prompt": "string", "messages": "[{role, content}]", "provider": "string",
                         "model": "string"},
             "response": {"delta": "string"}},
            {"method": "GET", "path": "/models", "scope": "ai:models",
             "summary": "List routable providers and models",
             "description": "Reflects the organization's configured providers and the key's "
                            "allowlists — no provider is ever assumed.",
             "request": {}, "response": {"providers": "[{provider, name, models}]",
                                         "fallback_chain": "[string]"}},
            {"method": "GET", "path": "/templates", "scope": "ai:templates",
             "summary": "List approved prompt templates",
             "description": "Approved Prompt Studio templates callable via template_key. "
                            "Drafts and templates pending review are never exposed.",
             "request": {}, "response": {"key": "string", "name": "string", "variables": "[string]"}},
            {"method": "GET", "path": "/usage", "scope": "ai:usage",
             "summary": "Usage and remaining quota for this key",
             "request": {"days": "integer (1-365)"},
             "response": {"requests": "integer", "tokens": "integer", "cost_usd": "number",
                          "rate_limit": "object"}},
            {"method": "GET", "path": "/version", "scope": None,
             "summary": "Version discovery",
             "description": "Current version, supported versions and sunset dates. "
                            "Unauthenticated.",
             "request": {}, "response": {"current_version": "string", "versions": "[object]"}},
            {"method": "GET", "path": "/openapi.json", "scope": None,
             "summary": "OpenAPI 3.1 spec for this public surface",
             "description": f"Import into Postman/Insomnia or generate a client. Served from {base_url}.",
             "request": {}, "response": {"openapi": "3.1.0"}},
        ]

    def docs(self, base_url: str | None = None) -> dict:
        base = (base_url or DEFAULT_BASE_URL).rstrip("/")
        return {
            "title": "CRM AI API",
            "version": CURRENT_VERSION,
            "base_url": base,
            "authentication": {
                "schemes": ["Authorization: Bearer <api_key>", "X-API-Key: <api_key>"],
                "key_format": "crm_<environment>_<secret>",
                "notes": "Keys are hashed at rest and shown once at creation. A key acts as the "
                         "user who created it, so it inherits that user's role, downline scope and "
                         "AI governance policy.",
            },
            "rate_limits": {
                "per_minute": "Configured per key (default 60).",
                "daily_quota": "Configured per key (default 1000).",
                "headers": ["X-RateLimit-Limit", "X-RateLimit-Remaining", "X-RateLimit-Reset",
                            "X-Quota-Limit", "X-Quota-Remaining", "Retry-After (on 429)"],
            },
            "versioning": {"current": CURRENT_VERSION, "versions": API_VERSIONS,
                           "header": "X-API-Version", "policy":
                               "Additive changes ship in place; breaking changes ship as a new "
                               "version with at least 90 days of overlap before sunset."},
            "scopes": [{"key": k, "description": v} for k, v in SCOPES.items()],
            "endpoints": self.endpoints(base),
            "webhooks": {
                "events": [{"key": k, "description": v} for k, v in WEBHOOK_EVENTS.items()],
                "signature_header": SIGNATURE_HEADER,
                "signature_scheme": "t=<unix timestamp>,v1=<hex HMAC-SHA256 of \"<t>.<raw body>\">",
                "retry_backoff_minutes": RETRY_BACKOFF_MINUTES,
                "headers": [SIGNATURE_HEADER, "X-CRM-AI-Event", "X-CRM-AI-Delivery"],
            },
            "errors": [
                {"status": 400, "meaning": "Malformed request body or unknown parameter."},
                {"status": 401, "meaning": "Missing, invalid, revoked or expired API key."},
                {"status": 403, "meaning": "Key lacks the required scope, model/provider or IP allowance."},
                {"status": 429, "meaning": "Rate limit or daily quota exhausted — honour Retry-After."},
                {"status": 500, "meaning": "Unexpected server error; safe to retry with backoff."},
            ],
            "sdks": _sdk_languages(),
        }

    def openapi_spec(self, base_url: str | None = None) -> dict:
        base = (base_url or DEFAULT_BASE_URL).rstrip("/")
        paths: dict = {}
        for ep in self.endpoints(base):
            op = {
                "summary": ep["summary"],
                "description": ep.get("description", ""),
                "operationId": ep["path"].strip("/").replace("/", "_").replace(".", "_") + "_" + ep["method"].lower(),
                "security": [] if ep["scope"] is None else [{"ApiKeyAuth": []}, {"BearerAuth": []}],
                "responses": {
                    "200": {"description": "Success",
                            "content": {"application/json": {"schema": {"type": "object"}}}},
                    "401": {"description": "Missing or invalid API key"},
                    "403": {"description": "Insufficient scope"},
                    "429": {"description": "Rate limit or quota exceeded"},
                },
            }
            if ep["method"] == "POST":
                op["requestBody"] = {
                    "required": True,
                    "content": {"application/json": {"schema": {
                        "type": "object",
                        "properties": {k: {"type": "string", "description": v}
                                       for k, v in ep["request"].items()}}}},
                }
            paths.setdefault(ep["path"], {})[ep["method"].lower()] = op
        return {
            "openapi": "3.1.0",
            "info": {"title": "CRM AI API", "version": CURRENT_VERSION,
                     "description": "Provider-agnostic AI endpoints for the CRM platform. "
                                    "Model routing is configured server-side."},
            "servers": [{"url": base}],
            "security": [{"ApiKeyAuth": []}],
            "components": {"securitySchemes": {
                "ApiKeyAuth": {"type": "apiKey", "in": "header", "name": "X-API-Key"},
                "BearerAuth": {"type": "http", "scheme": "bearer"},
            }},
            "paths": paths,
        }

    def sdk(self, language: str, base_url: str | None = None) -> dict:
        from app.services.ai_sdk_templates import SDK_LANGUAGES, render_sdk
        if language not in SDK_LANGUAGES:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND,
                                detail=f"No SDK for '{language}'. Available: {sorted(SDK_LANGUAGES)}")
        meta = SDK_LANGUAGES[language]
        base = (base_url or DEFAULT_BASE_URL).rstrip("/")
        return {**meta, "key": language, "version": CURRENT_VERSION, "base_url": base,
                "source": render_sdk(language, base, CURRENT_VERSION)}

    def examples(self, base_url: str | None = None) -> list[dict]:
        from app.services.ai_sdk_templates import render_examples
        return render_examples((base_url or DEFAULT_BASE_URL).rstrip("/"))

    # ================= developer portal + analytics =================
    async def portal(self, actor: User, base_url: str | None = None) -> dict:
        """Everything the Developer Portal page needs in one call."""
        self._require_manager(actor)
        org = actor.organization_id
        keys = (await self.db.execute(select(AIApiKey).filter(
            AIApiKey.organization_id == org, AIApiKey.is_deleted == False))).scalars().all()
        hooks = (await self.db.execute(select(AIWebhook).filter(
            AIWebhook.organization_id == org, AIWebhook.is_deleted == False))).scalars().all()
        since = _now() - timedelta(days=30)
        reqs = (await self.db.execute(select(AIApiRequest).filter(
            AIApiRequest.organization_id == org, AIApiRequest.created_at >= since))).scalars().all()
        failed = [r for r in reqs if r.status_code >= 400]
        throttled = [r for r in reqs if r.status_code == 429]
        dead = (await self.db.execute(select(func.count(AIWebhookDelivery.id)).filter(
            AIWebhookDelivery.organization_id == org,
            AIWebhookDelivery.status == "dead_letter"))).scalar() or 0
        return {
            "base_url": (base_url or DEFAULT_BASE_URL).rstrip("/"),
            "current_version": CURRENT_VERSION,
            "versions": API_VERSIONS,
            "keys_total": len(keys),
            "keys_active": len([k for k in keys if k.is_active and k.revoked_at is None]),
            "webhooks_total": len(hooks),
            "webhooks_active": len([h for h in hooks if h.is_active]),
            "requests_30d": len(reqs),
            "failed_30d": len(failed),
            "throttled_30d": len(throttled),
            "tokens_30d": sum(int(r.tokens or 0) for r in reqs),
            "cost_30d": round(sum(float(r.cost_usd or 0) for r in reqs), 4),
            "success_rate": round(100 * (len(reqs) - len(failed)) / len(reqs), 1) if reqs else 100.0,
            "dead_letter_deliveries": int(dead),
            "sdk_languages": _sdk_languages(),
            "scopes": [{"key": k, "description": v} for k, v in SCOPES.items()],
            "webhook_events": [{"key": k, "description": v} for k, v in WEBHOOK_EVENTS.items()],
            "keys": [self._ser_key(k) for k in
                     sorted(keys, key=lambda x: _aware(x.created_at) or _now(), reverse=True)[:10]],
        }

    async def analytics(self, actor: User, days: int = 30) -> dict:
        self._require_manager(actor)
        since = _now() - timedelta(days=days)
        rows = (await self.db.execute(select(AIApiRequest).filter(
            AIApiRequest.organization_id == actor.organization_id,
            AIApiRequest.created_at >= since))).scalars().all()
        keys = {k.id: k for k in (await self.db.execute(select(AIApiKey).filter(
            AIApiKey.organization_id == actor.organization_id))).scalars().all()}
        by_endpoint: dict[str, dict] = {}
        by_key: dict[str, dict] = {}
        by_day: dict[str, int] = {}
        by_status: dict[str, int] = {}
        for r in rows:
            e = by_endpoint.setdefault(r.endpoint, {"requests": 0, "errors": 0, "tokens": 0, "latency": []})
            e["requests"] += 1
            e["tokens"] += int(r.tokens or 0)
            e["latency"].append(int(r.latency_ms or 0))
            if r.status_code >= 400:
                e["errors"] += 1
            name = keys[r.api_key_id].name if r.api_key_id in keys else "(deleted key)"
            k = by_key.setdefault(name, {"requests": 0, "errors": 0, "tokens": 0, "cost_usd": 0.0})
            k["requests"] += 1
            k["tokens"] += int(r.tokens or 0)
            k["cost_usd"] = round(k["cost_usd"] + float(r.cost_usd or 0), 6)
            if r.status_code >= 400:
                k["errors"] += 1
            day = (_aware(r.created_at) or _now()).date().isoformat()
            by_day[day] = by_day.get(day, 0) + 1
            by_status[str(r.status_code)] = by_status.get(str(r.status_code), 0) + 1
        for e in by_endpoint.values():
            lat = e.pop("latency")
            e["avg_latency_ms"] = int(sum(lat) / len(lat)) if lat else 0
        latencies = sorted(int(r.latency_ms or 0) for r in rows if r.status_code < 400)
        return {
            "window_days": days, "requests": len(rows),
            "errors": len([r for r in rows if r.status_code >= 400]),
            "throttled": len([r for r in rows if r.status_code == 429]),
            "tokens": sum(int(r.tokens or 0) for r in rows),
            "cost_usd": round(sum(float(r.cost_usd or 0) for r in rows), 6),
            "p50_latency_ms": latencies[len(latencies) // 2] if latencies else 0,
            "p95_latency_ms": latencies[int(len(latencies) * 0.95)] if latencies else 0,
            "by_endpoint": by_endpoint,
            "by_key": dict(sorted(by_key.items(), key=lambda kv: kv[1]["requests"], reverse=True)),
            "by_day": dict(sorted(by_day.items())),
            "by_status": by_status,
        }

    async def requests_log(self, actor: User, *, key_id: uuid.UUID | None = None,
                           limit: int = 100) -> list[dict]:
        self._require_manager(actor)
        q = select(AIApiRequest).filter(AIApiRequest.organization_id == actor.organization_id)
        if key_id:
            q = q.filter(AIApiRequest.api_key_id == key_id)
        rows = (await self.db.execute(q.order_by(AIApiRequest.created_at.desc())
                                      .limit(limit))).scalars().all()
        return [{"id": str(r.id), "api_key_id": str(r.api_key_id) if r.api_key_id else None,
                 "endpoint": r.endpoint, "method": r.method, "api_version": r.api_version,
                 "status_code": r.status_code, "latency_ms": r.latency_ms, "tokens": r.tokens,
                 "cost_usd": float(r.cost_usd or 0), "provider": r.provider, "model": r.model,
                 "error": r.error, "created_at": _iso(r.created_at)} for r in rows]

    async def export_csv(self, actor: User, days: int = 30) -> str:
        self._require_manager(actor)
        data = await self.analytics(actor, days=days)
        buf = io.StringIO()
        w = csv.writer(buf)
        w.writerow(["Section", "Key", "Requests", "Errors", "Tokens", "Cost USD", "Avg latency ms"])
        for name, v in data["by_key"].items():
            w.writerow(["key", name, v["requests"], v["errors"], v["tokens"], v["cost_usd"], ""])
        for name, v in data["by_endpoint"].items():
            w.writerow(["endpoint", name, v["requests"], v["errors"], v["tokens"], "", v["avg_latency_ms"]])
        for day, count in data["by_day"].items():
            w.writerow(["day", day, count, "", "", "", ""])
        return buf.getvalue()

    # ================= helpers =================
    async def _audit(self, actor: User, action: str, resource_id, meta: dict):
        try:
            await self.audit.log_event(
                organization_id=actor.organization_id, actor_user_id=actor.id, action=action,
                resource_type="ai_api", resource_id=str(resource_id), action_metadata=meta)
        except Exception:
            pass

    @staticmethod
    def _ser_key(k: AIApiKey) -> dict:
        return {"id": str(k.id), "name": k.name, "environment": k.environment,
                "key_prefix": k.key_prefix, "masked_key": f"{k.key_prefix}…",
                "scopes": k.scopes or list(DEFAULT_SCOPES),
                "rate_limit_per_min": k.rate_limit_per_min, "daily_quota": k.daily_quota,
                "allowed_providers": k.allowed_providers or [],
                "allowed_models": k.allowed_models or [],
                "allowed_ips": k.allowed_ips or [],
                "expires_at": _iso(k.expires_at), "last_used_at": _iso(k.last_used_at),
                "use_count": k.use_count, "is_active": k.is_active,
                "revoked_at": _iso(k.revoked_at), "created_at": _iso(k.created_at)}

    @staticmethod
    def _ser_webhook(w: AIWebhook, reveal_secret: bool = False) -> dict:
        out = {"id": str(w.id), "name": w.name, "url": w.url,
               "events": w.events or list(WEBHOOK_EVENTS.keys()),
               "subscribes_all": not w.events, "is_active": w.is_active,
               "max_attempts": w.max_attempts, "delivered_count": w.delivered_count,
               "failed_count": w.failed_count, "last_status": w.last_status,
               "last_delivery_at": _iso(w.last_delivery_at), "created_at": _iso(w.created_at)}
        out["secret"] = w.secret if reveal_secret else f"{w.secret[:6]}…"
        return out

    @staticmethod
    def _ser_delivery(d: AIWebhookDelivery) -> dict:
        return {"id": str(d.id), "webhook_id": str(d.webhook_id), "event_type": d.event_type,
                "status": d.status, "attempts": d.attempts, "response_code": d.response_code,
                "error": d.error, "duration_ms": d.duration_ms,
                "next_retry_at": _iso(d.next_retry_at), "delivered_at": _iso(d.delivered_at),
                "payload": d.payload, "created_at": _iso(d.created_at)}


def _total_tokens(out: dict) -> int:
    """The gateway returns tokens as {prompt, completion, total}."""
    t = out.get("tokens")
    if isinstance(t, dict):
        return int(t.get("total") or 0)
    return int(t or 0)


def _sdk_languages() -> list[dict]:
    from app.services.ai_sdk_templates import SDK_LANGUAGES
    return [{"key": k, **v} for k, v in SDK_LANGUAGES.items()]
