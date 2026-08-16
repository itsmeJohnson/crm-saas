"""Integration Hub — one registry, one runtime, one health view.

What this module deliberately does NOT do: reimplement any channel that already
works. Payment gateways, SMS, WhatsApp, email, BI cloud storage and outbound
event webhooks keep their own tables, services and credentials. The hub
*discovers* them (`sync_managed()`) and shows them as read-only mirror rows so
there is a single inventory and a single health board.

What it adds:
  * CONNECTIONS   — per-org credentials + config for every category the platform
                    had no home for (ERP, accounting, HRMS, e-commerce,
                    marketing, social, CRM, identity/SSO/LDAP, calendar,
                    storage, generic API + webhook connectors).
  * RUNTIME       — one generic HTTP caller with per-connection timeout,
                    bounded exponential-backoff RETRY and transparent FALLBACK
                    to another connection.
  * HEALTH        — on-demand and cron health checks, consecutive-failure
                    tracking and a degraded/down rollup.
  * INBOUND       — token-authenticated webhook receipt with optional HMAC
                    verification, replay and Event Bus forwarding.
  * AUDIT         — every mutation through AuditService, every call in
                    integration_logs with credentials redacted.

Provider neutrality is absolute: everything routable is catalog data, and no
provider is assumed or hardcoded anywhere in the runtime.
"""
import asyncio
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
from app.models.integration import Integration, IntegrationLog, IntegrationEvent
from app.services.audit_service import AuditService
from app.services import integration_catalog as cat

MANAGER_ROLES = ("SuperAdmin", "OrgAdmin", "Manager")
ADMIN_ROLES = ("SuperAdmin", "OrgAdmin")

STATUSES = ("unconfigured", "healthy", "degraded", "down", "disabled")
ENVIRONMENTS = ("live", "sandbox")

# A connection is "degraded" from the first failure and "down" once it has
# failed this many checks in a row.
DOWN_AFTER_FAILURES = 3

SECRET_HINTS = ("key", "secret", "password", "token", "credential", "certificate")


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _aware(dt):
    """SQLite returns naive datetimes — normalise before any comparison."""
    if dt is None:
        return None
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


def _iso(dt):
    a = _aware(dt)
    return a.isoformat() if a else None


def mask_secrets(data: dict | None) -> dict:
    """Redact anything that looks like a credential. Used on every read and on
    every log row — secrets must never leave this service in the clear."""
    out = {}
    for k, v in (data or {}).items():
        if isinstance(v, str) and v and any(h in k.lower() for h in SECRET_HINTS):
            out[k] = f"{'*' * max(0, len(v) - 4)}{v[-4:]}" if len(v) > 4 else "****"
        elif isinstance(v, dict):
            out[k] = mask_secrets(v)
        else:
            out[k] = v
    return out


class IntegrationService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.audit = AuditService(db)

    # ================= guards =================
    def _require_manager(self, actor: User):
        if actor.role not in MANAGER_ROLES:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN,
                                detail="Only managers and administrators can view integrations.")

    def _require_admin(self, actor: User):
        """Credentials are admin-only — a Manager can see health, not secrets."""
        if actor.role not in ADMIN_ROLES:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN,
                                detail="Only organization administrators can configure integrations.")

    # ================= catalog =================
    @staticmethod
    def catalog() -> dict:
        return cat.catalog()

    # ================= connections =================
    async def create(self, actor: User, data: dict) -> dict:
        self._require_admin(actor)
        entry = cat.connector(data.get("provider"))
        if not entry:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST,
                                detail=f"Unknown connector '{data.get('provider')}'. See /integrations/catalog.")
        if entry["category"] in (c for c, v in cat.CATEGORIES.items() if v["managed_by"]):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"'{cat.CATEGORIES[entry['category']]['label']}' is configured in its own module; "
                       f"the hub mirrors it read-only.")
        env = data.get("environment") or "live"
        if env not in ENVIRONMENTS:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST,
                                detail=f"environment must be one of {list(ENVIRONMENTS)}")
        row = Integration(
            organization_id=actor.organization_id, category=entry["category"],
            provider=entry["key"], name=data.get("name") or entry["label"],
            environment=env, auth_type=entry["auth_type"],
            credentials=data.get("credentials") or {}, config=data.get("config") or {},
            is_enabled=data.get("is_enabled", True), is_managed_elsewhere=False,
            max_attempts=int(data.get("max_attempts") or 3),
            retry_backoff_seconds=int(data.get("retry_backoff_seconds") or 2),
            timeout_seconds=int(data.get("timeout_seconds") or 15),
            status="unconfigured", created_by=actor.id,
        )
        if entry["category"] == "webhook" and entry["key"] == "inbound_webhook":
            row.inbound_token = secrets.token_urlsafe(32)[:64]
            row.inbound_secret = secrets.token_urlsafe(32)[:64]
        self.db.add(row)
        await self.db.flush()
        await self._audit(actor, "INTEGRATION_CREATED", row.id,
                          {"provider": row.provider, "category": row.category, "name": row.name})
        return self._ser(row, reveal_inbound=True)

    async def list_connections(self, actor: User, *, category: str | None = None,
                   status_filter: str | None = None) -> list[dict]:
        self._require_manager(actor)
        q = select(Integration).filter(Integration.organization_id == actor.organization_id,
                                       Integration.is_deleted == False)
        if category:
            q = q.filter(Integration.category == category)
        if status_filter:
            q = q.filter(Integration.status == status_filter)
        rows = (await self.db.execute(q.order_by(Integration.category.asc(),
                                                 Integration.name.asc()))).scalars().all()
        return [self._ser(r) for r in rows]

    async def _row(self, actor: User, integration_id: uuid.UUID) -> Integration:
        r = (await self.db.execute(select(Integration).filter(
            Integration.id == integration_id,
            Integration.organization_id == actor.organization_id,
            Integration.is_deleted == False))).scalars().first()
        if not r:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Integration not found")
        return r

    async def get(self, actor: User, integration_id: uuid.UUID) -> dict:
        self._require_manager(actor)
        return self._ser(await self._row(actor, integration_id))

    async def update(self, actor: User, integration_id: uuid.UUID, data: dict) -> dict:
        self._require_admin(actor)
        r = await self._row(actor, integration_id)
        if r.is_managed_elsewhere:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST,
                                detail=f"This connection is owned by the {r.managed_by} module — edit it there.")
        # Credentials merge so a client can PATCH one field without resending all.
        if data.get("credentials"):
            r.credentials = {**(r.credentials or {}), **data["credentials"]}
        if data.get("config"):
            r.config = {**(r.config or {}), **data["config"]}
        for f in ("name", "environment", "is_enabled", "max_attempts",
                  "retry_backoff_seconds", "timeout_seconds"):
            if f in data and data[f] is not None:
                setattr(r, f, data[f])
        if "fallback_integration_id" in data:
            await self._set_fallback(actor, r, data["fallback_integration_id"])
        if r.is_enabled is False:
            r.status = "disabled"
        elif r.status == "disabled":
            r.status = "unconfigured"
        self.db.add(r)
        await self.db.flush()
        await self._audit(actor, "INTEGRATION_UPDATED", r.id, {"fields": sorted(data.keys())})
        return self._ser(r)

    async def _set_fallback(self, actor: User, row: Integration, target_id) -> None:
        """Assign a fallback target, rejecting self-reference and cycles — an
        unguarded chain would spin forever inside call_with_fallback()."""
        if target_id in (None, ""):
            row.fallback_integration_id = None
            return
        target_uuid = uuid.UUID(str(target_id))
        if target_uuid == row.id:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST,
                                detail="An integration cannot fall back to itself.")
        target = await self._row(actor, target_uuid)
        if target.category != row.category:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST,
                                detail="Fallback must be another connection in the same category.")
        # walk the existing chain looking for a cycle back to row
        seen = {row.id}
        cursor = target
        while cursor is not None:
            if cursor.id in seen:
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST,
                                    detail="That fallback would create a loop.")
            seen.add(cursor.id)
            nxt = cursor.fallback_integration_id
            cursor = (await self.db.execute(select(Integration).filter(
                Integration.id == nxt, Integration.is_deleted == False))).scalars().first() if nxt else None
        row.fallback_integration_id = target_uuid

    async def delete(self, actor: User, integration_id: uuid.UUID) -> None:
        self._require_admin(actor)
        r = await self._row(actor, integration_id)
        if r.is_managed_elsewhere:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST,
                                detail=f"This connection is owned by the {r.managed_by} module — remove it there.")
        r.is_deleted = True
        r.is_enabled = False
        self.db.add(r)
        # orphan any connection that used this one as its fallback
        dependents = (await self.db.execute(select(Integration).filter(
            Integration.fallback_integration_id == r.id,
            Integration.is_deleted == False))).scalars().all()
        for d in dependents:
            d.fallback_integration_id = None
            self.db.add(d)
        await self.db.flush()
        await self._audit(actor, "INTEGRATION_DELETED", r.id, {"name": r.name, "provider": r.provider})

    async def rotate_inbound_secret(self, actor: User, integration_id: uuid.UUID) -> dict:
        self._require_admin(actor)
        r = await self._row(actor, integration_id)
        if not r.inbound_token:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST,
                                detail="This connection has no inbound webhook endpoint.")
        r.inbound_token = secrets.token_urlsafe(32)[:64]
        r.inbound_secret = secrets.token_urlsafe(32)[:64]
        self.db.add(r)
        await self.db.flush()
        await self._audit(actor, "INTEGRATION_INBOUND_ROTATED", r.id, {"name": r.name})
        return self._ser(r, reveal_inbound=True)

    # ================= runtime: retry + fallback =================
    async def _http_attempt(self, row: Integration, method: str, url: str,
                            *, json_body=None, params=None, headers=None) -> tuple[int, str]:
        """One HTTP attempt. Returns (status_code, error_text). Never raises for
        a transport failure — the caller decides about retries."""
        import httpx
        hdrs = {"Accept": "application/json", **(row.config or {}).get("default_headers", {}), **(headers or {})}
        creds = row.credentials or {}
        auth = None
        if row.auth_type == "api_key" and creds.get("api_key"):
            hdrs[(row.config or {}).get("auth_header") or "X-API-Key"] = creds["api_key"]
        elif row.auth_type == "bearer" and creds.get("token"):
            hdrs["Authorization"] = f"Bearer {creds['token']}"
        elif row.auth_type == "oauth2" and creds.get("refresh_token"):
            hdrs["Authorization"] = f"Bearer {creds.get('access_token') or creds['refresh_token']}"
        elif row.auth_type == "basic" and creds.get("username"):
            auth = (creds.get("username", ""), creds.get("password", ""))
        try:
            async with httpx.AsyncClient(timeout=float(row.timeout_seconds or 15)) as client:
                resp = await client.request(method, url, json=json_body, params=params,
                                            headers=hdrs, auth=auth)
            if resp.status_code >= 400:
                return resp.status_code, f"HTTP {resp.status_code}: {resp.text[:200]}"
            return resp.status_code, ""
        except Exception as e:
            return 0, str(e)[:400]

    def _resolve_url(self, row: Integration, path: str | None) -> str:
        entry = cat.connector(row.provider) or {}
        base = (row.config or {}).get("base_url") or entry.get("base_url")
        if not base:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"'{row.name}' has no base_url. Set config.base_url before calling it.")
        return f"{base.rstrip('/')}/{(path or '').lstrip('/')}" if path else base

    async def call(self, actor: User | None, row: Integration, *, method: str = "GET",
                   path: str | None = None, json_body=None, params=None,
                   operation: str = "call", fallback_from: uuid.UUID | None = None) -> dict:
        """Execute one call with bounded exponential-backoff retry, then hand
        off to the fallback connection if every attempt failed."""
        if not row.is_enabled:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST,
                                detail=f"'{row.name}' is disabled.")
        url = self._resolve_url(row, path)
        attempts = max(1, min(int(row.max_attempts or 3), 10))
        base_backoff = max(0, int(row.retry_backoff_seconds or 2))
        started = time.monotonic()
        code, err = 0, "not attempted"
        for attempt in range(1, attempts + 1):
            code, err = await self._http_attempt(row, method, url, json_body=json_body, params=params)
            if not err:
                break
            # 4xx other than 408/429 is a caller error — retrying cannot help.
            if 400 <= code < 500 and code not in (408, 429):
                break
            if attempt < attempts:
                await asyncio.sleep(min(base_backoff * (2 ** (attempt - 1)), 30))
        latency = int((time.monotonic() - started) * 1000)
        ok = not err
        await self._record(row, operation=operation, method=method, endpoint=url,
                           ok=ok, status_code=code or None, attempts=attempt, latency_ms=latency,
                           error=err or None, actor=actor, fallback_from=fallback_from,
                           request_summary={"params": mask_secrets(params or {})})
        await self._apply_health(row, ok, latency, err)
        if ok:
            return {"ok": True, "status_code": code, "attempts": attempt, "latency_ms": latency,
                    "integration_id": str(row.id), "name": row.name,
                    "fell_back_from": str(fallback_from) if fallback_from else None}
        # ---- fallback ----
        if row.fallback_integration_id:
            target = (await self.db.execute(select(Integration).filter(
                Integration.id == row.fallback_integration_id,
                Integration.is_deleted == False))).scalars().first()
            if target and target.is_enabled:
                return await self.call(actor, target, method=method, path=path, json_body=json_body,
                                       params=params, operation=operation, fallback_from=row.id)
        return {"ok": False, "status_code": code, "attempts": attempt, "latency_ms": latency,
                "error": err, "integration_id": str(row.id), "name": row.name,
                "fell_back_from": str(fallback_from) if fallback_from else None}

    async def call_api(self, actor: User, integration_id: uuid.UUID, data: dict) -> dict:
        """Operator-invoked passthrough call — the API Connector surface."""
        self._require_manager(actor)
        row = await self._row(actor, integration_id)
        if row.is_managed_elsewhere:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST,
                                detail=f"Use the {row.managed_by} module to exercise this connection.")
        return await self.call(actor, row, method=(data.get("method") or "GET").upper(),
                               path=data.get("path"), json_body=data.get("body"),
                               params=data.get("params"), operation="call")

    # ================= health monitoring =================
    async def _apply_health(self, row: Integration, ok: bool, latency_ms: int, err: str | None):
        row.total_calls = (row.total_calls or 0) + 1
        row.last_check_at = _now()
        row.latency_ms = latency_ms
        if ok:
            row.consecutive_failures = 0
            row.last_success_at = _now()
            row.last_error = None
            row.status = "healthy"
        else:
            row.failed_calls = (row.failed_calls or 0) + 1
            row.consecutive_failures = (row.consecutive_failures or 0) + 1
            row.last_error = (err or "")[:500]
            row.status = "down" if row.consecutive_failures >= DOWN_AFTER_FAILURES else "degraded"
        self.db.add(row)
        await self.db.flush()

    async def health_check(self, actor: User | None, row: Integration) -> dict:
        """Ping the connector's health endpoint. A connection with no health
        path or no base URL stays 'unconfigured' rather than reporting a
        misleading green."""
        entry = cat.connector(row.provider) or {}
        if row.is_managed_elsewhere:
            return {"integration_id": str(row.id), "name": row.name, "status": row.status,
                    "checked": False, "reason": f"Owned by the {row.managed_by} module."}
        if not row.is_enabled:
            row.status = "disabled"
            self.db.add(row)
            await self.db.flush()
            return {"integration_id": str(row.id), "name": row.name, "status": "disabled", "checked": False}
        base = (row.config or {}).get("base_url") or entry.get("base_url")
        path = (row.config or {}).get("health_path") or entry.get("health_path")
        if not base:
            return {"integration_id": str(row.id), "name": row.name, "status": row.status,
                    "checked": False, "reason": "No base_url configured."}
        out = await self.call(actor, row, method="GET", path=path, operation="health_check")
        return {"integration_id": str(row.id), "name": row.name,
                "status": row.status, "checked": True, "ok": out["ok"],
                "latency_ms": out.get("latency_ms"), "error": out.get("error")}

    async def health_check_one(self, actor: User, integration_id: uuid.UUID) -> dict:
        self._require_manager(actor)
        return await self.health_check(actor, await self._row(actor, integration_id))

    async def health_check_all(self, organization_id: uuid.UUID, actor: User | None = None) -> dict:
        """Cron entry point: check every enabled, hub-owned connection."""
        rows = (await self.db.execute(select(Integration).filter(
            Integration.organization_id == organization_id, Integration.is_enabled == True,
            Integration.is_managed_elsewhere == False,
            Integration.is_deleted == False))).scalars().all()
        checked = healthy = failed = 0
        for r in rows:
            out = await self.health_check(actor, r)
            if out.get("checked"):
                checked += 1
                healthy += 1 if out.get("ok") else 0
                failed += 0 if out.get("ok") else 1
        return {"checked": checked, "healthy": healthy, "failed": failed}

    # ================= mirroring the modules that own their own credentials ==
    async def sync_managed(self, actor: User) -> dict:
        """Reflect the already-working channel modules into the hub as read-only
        rows so the inventory and health board are complete. Never writes to
        those modules and never copies their secrets."""
        self._require_manager(actor)
        org = actor.organization_id
        discovered: list[tuple[str, str, str, bool, str]] = []  # category, provider, name, configured, managed_by

        # --- SMS / WhatsApp / Email: per-org settings rows ---
        from app.models.sms_settings import SmsSettings
        from app.models.whatsapp import WhatsAppSettings
        from app.models.email_settings import EmailSettings
        for model, category, module in ((SmsSettings, "sms", "sms_settings"),
                                        (WhatsAppSettings, "whatsapp", "whatsapp_settings"),
                                        (EmailSettings, "email", "email_settings")):
            row = (await self.db.execute(select(model).filter(
                model.organization_id == org, model.is_deleted == False))).scalars().first()
            if row:
                prov = getattr(row, "provider", "mock") or "mock"
                discovered.append((category, prov, f"{cat.CATEGORIES[category]['label']} ({prov})",
                                   prov != "mock", module))

        # --- Payment gateways: platform-level, enabled ones only ---
        from app.models.payment_gateway import PaymentGateway
        gateways = (await self.db.execute(select(PaymentGateway).filter(
            PaymentGateway.is_enabled == True, PaymentGateway.is_deleted == False))).scalars().all()
        for g in gateways:
            discovered.append(("payment", g.name, g.display_name or g.name, True, "payment_gateways"))

        # --- BI cloud storage ---
        from app.models.bi_export import BISetting
        bi = (await self.db.execute(select(BISetting).filter(
            BISetting.organization_id == org, BISetting.is_deleted == False))).scalars().first()
        if bi:
            discovered.append(("storage", bi.storage_provider or "local",
                               f"BI Export Storage ({bi.storage_provider})",
                               (bi.storage_provider or "local") != "local", "bi_settings"))

        # --- Outbound event-bus webhooks ---
        from app.models.event import EventSubscription
        subs = (await self.db.execute(select(EventSubscription).filter(
            EventSubscription.organization_id == org, EventSubscription.subscriber_type == "webhook",
            EventSubscription.is_deleted == False))).scalars().all()
        for s in subs:
            discovered.append(("webhook", "outbound_webhook", f"Event Bus: {s.name}", True, "event_subscriptions"))

        created = updated = 0
        for category, provider, name, configured, module in discovered:
            existing = (await self.db.execute(select(Integration).filter(
                Integration.organization_id == org, Integration.category == category,
                Integration.name == name, Integration.is_managed_elsewhere == True,
                Integration.is_deleted == False))).scalars().first()
            new_status = "healthy" if configured else "unconfigured"
            if existing:
                if existing.status != new_status or existing.provider != provider:
                    existing.provider, existing.status = provider, new_status
                    self.db.add(existing)
                    updated += 1
                continue
            self.db.add(Integration(
                organization_id=org, category=category, provider=provider, name=name,
                environment="live", auth_type="none", credentials={}, config={},
                is_enabled=True, is_managed_elsewhere=True, managed_by=module,
                status=new_status, created_by=actor.id))
            created += 1
        await self.db.flush()
        return {"discovered": len(discovered), "created": created, "updated": updated}

    # ================= inbound webhook connector =================
    async def receive_inbound(self, token: str, payload: dict, *,
                              signature: str | None = None, raw_body: bytes | None = None) -> dict:
        """Token-authenticated inbound webhook. Verifies the HMAC when the caller
        sends one, stores the payload, and optionally forwards to the Event Bus."""
        row = (await self.db.execute(select(Integration).filter(
            Integration.inbound_token == token, Integration.is_deleted == False))).scalars().first()
        if not row:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Unknown webhook endpoint.")
        if not row.is_enabled:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="This endpoint is disabled.")
        sig_valid = None
        if signature and row.inbound_secret:
            expected = hmac.new(row.inbound_secret.encode(),
                                raw_body if raw_body is not None else json.dumps(payload).encode(),
                                hashlib.sha256).hexdigest()
            sig_valid = hmac.compare_digest(expected, signature.strip())
            if not sig_valid:
                await self._record(row, operation="inbound", method="POST", endpoint="(inbound)",
                                   ok=False, status_code=401, attempts=1, latency_ms=0,
                                   error="Invalid signature", actor=None, fallback_from=None,
                                   request_summary={})
                raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED,
                                    detail="Signature verification failed.")
        ev = IntegrationEvent(
            organization_id=row.organization_id, integration_id=row.id,
            event_type=(row.config or {}).get("event_type") or "inbound",
            payload=payload if isinstance(payload, dict) else {"body": payload},
            signature_valid=sig_valid, processed=False, received_at=_now())
        self.db.add(ev)
        await self.db.flush()

        if (row.config or {}).get("forward_to_event_bus"):
            try:
                from app.services.event_bus import EventBusService
                bus = EventBusService(self.db)
                published = await bus.publish(f"integration.{ev.event_type}",
                                              payload={"integration": row.name, "data": ev.payload},
                                              entity_type="integration", entity_id=str(row.id),
                                              source="system", organization_id=row.organization_id)
                ev.forwarded_event_id = getattr(published, "id", None)
                ev.processed = True
            except Exception as e:
                ev.error = str(e)[:500]
            self.db.add(ev)
            await self.db.flush()

        await self._record(row, operation="inbound", method="POST", endpoint="(inbound)",
                           ok=True, status_code=200, attempts=1, latency_ms=0, error=None,
                           actor=None, fallback_from=None, request_summary={})
        row.last_success_at = _now()
        row.status = "healthy"
        self.db.add(row)
        await self.db.flush()
        return {"received": True, "event_id": str(ev.id), "signature_valid": sig_valid,
                "forwarded": ev.processed}

    async def events(self, actor: User, *, integration_id: uuid.UUID | None = None,
                     limit: int = 100) -> list[dict]:
        self._require_manager(actor)
        q = select(IntegrationEvent).filter(IntegrationEvent.organization_id == actor.organization_id,
                                            IntegrationEvent.is_deleted == False)
        if integration_id:
            q = q.filter(IntegrationEvent.integration_id == integration_id)
        rows = (await self.db.execute(q.order_by(IntegrationEvent.received_at.desc())
                                      .limit(limit))).scalars().all()
        return [{"id": str(e.id), "integration_id": str(e.integration_id), "event_type": e.event_type,
                 "payload": e.payload, "signature_valid": e.signature_valid, "processed": e.processed,
                 "error": e.error, "received_at": _iso(e.received_at)} for e in rows]

    # ================= logs, dashboard, export =================
    async def _record(self, row: Integration, *, operation: str, method: str | None,
                      endpoint: str | None, ok: bool, status_code: int | None, attempts: int,
                      latency_ms: int, error: str | None, actor: User | None,
                      fallback_from: uuid.UUID | None, request_summary: dict):
        self.db.add(IntegrationLog(
            organization_id=row.organization_id, integration_id=row.id, operation=operation,
            method=method, endpoint=(endpoint or "")[:300],
            status=("fallback" if fallback_from else ("success" if ok else "failed")),
            status_code=status_code, attempts=attempts, latency_ms=latency_ms,
            error=error, fallback_from_id=fallback_from,
            request_summary=mask_secrets(request_summary), actor_user_id=actor.id if actor else None))
        await self.db.flush()

    async def logs(self, actor: User, *, integration_id: uuid.UUID | None = None,
                   status_filter: str | None = None, limit: int = 100) -> list[dict]:
        self._require_manager(actor)
        q = select(IntegrationLog).filter(IntegrationLog.organization_id == actor.organization_id)
        if integration_id:
            q = q.filter(IntegrationLog.integration_id == integration_id)
        if status_filter:
            q = q.filter(IntegrationLog.status == status_filter)
        rows = (await self.db.execute(q.order_by(IntegrationLog.created_at.desc())
                                      .limit(limit))).scalars().all()
        return [{"id": str(l.id), "integration_id": str(l.integration_id), "operation": l.operation,
                 "method": l.method, "endpoint": l.endpoint, "status": l.status,
                 "status_code": l.status_code, "attempts": l.attempts, "latency_ms": l.latency_ms,
                 "error": l.error, "fallback_from_id": str(l.fallback_from_id) if l.fallback_from_id else None,
                 "created_at": _iso(l.created_at)} for l in rows]

    async def dashboard(self, actor: User) -> dict:
        self._require_manager(actor)
        org = actor.organization_id
        rows = (await self.db.execute(select(Integration).filter(
            Integration.organization_id == org, Integration.is_deleted == False))).scalars().all()
        since = _now() - timedelta(days=7)
        logs = (await self.db.execute(select(IntegrationLog).filter(
            IntegrationLog.organization_id == org, IntegrationLog.created_at >= since))).scalars().all()
        by_category: dict[str, dict] = {}
        for r in rows:
            c = by_category.setdefault(r.category, {"total": 0, "healthy": 0, "down": 0, "degraded": 0})
            c["total"] += 1
            if r.status in ("healthy", "down", "degraded"):
                c[r.status] += 1
        failed = [l for l in logs if l.status == "failed"]
        fellback = [l for l in logs if l.status == "fallback"]
        retried = [l for l in logs if (l.attempts or 1) > 1]
        return {
            "total": len(rows),
            "active": len([r for r in rows if r.is_enabled and not r.is_managed_elsewhere]),
            "managed_elsewhere": len([r for r in rows if r.is_managed_elsewhere]),
            "healthy": len([r for r in rows if r.status == "healthy"]),
            "degraded": len([r for r in rows if r.status == "degraded"]),
            "down": len([r for r in rows if r.status == "down"]),
            "unconfigured": len([r for r in rows if r.status == "unconfigured"]),
            "categories_used": len(by_category),
            "categories_available": len(cat.CATEGORIES),
            "connectors_available": len(cat.CONNECTORS),
            "by_category": by_category,
            "calls_7d": len(logs), "failures_7d": len(failed),
            "retries_7d": len(retried), "fallbacks_7d": len(fellback),
            "success_rate": round(100 * (len(logs) - len(failed)) / len(logs), 1) if logs else 100.0,
            "needs_attention": [self._ser(r) for r in rows
                                if r.status in ("down", "degraded") and not r.is_managed_elsewhere][:10],
        }

    async def export_csv(self, actor: User) -> str:
        self._require_manager(actor)
        rows = await self.list_connections(actor)
        buf = io.StringIO()
        w = csv.writer(buf)
        w.writerow(["Category", "Provider", "Name", "Environment", "Enabled", "Owned by",
                    "Status", "Consecutive failures", "Last success", "Total calls", "Failed calls"])
        for r in rows:
            w.writerow([r["category"], r["provider"], r["name"], r["environment"], r["is_enabled"],
                        r["managed_by"] or "integration_hub", r["status"], r["consecutive_failures"],
                        r["last_success_at"] or "", r["total_calls"], r["failed_calls"]])
        await self._audit(actor, "INTEGRATION_EXPORTED", None, {"rows": len(rows)})
        return buf.getvalue()

    # ================= helpers =================
    async def _audit(self, actor: User, action: str, resource_id, meta: dict):
        try:
            await self.audit.log_event(
                organization_id=actor.organization_id, actor_user_id=actor.id, action=action,
                resource_type="integration", resource_id=str(resource_id) if resource_id else None,
                action_metadata=meta)
        except Exception:
            pass

    @staticmethod
    def _ser(r: Integration, reveal_inbound: bool = False) -> dict:
        entry = cat.connector(r.provider) or {}
        out = {
            "id": str(r.id), "category": r.category, "provider": r.provider,
            "provider_label": entry.get("label", r.provider), "name": r.name,
            "environment": r.environment, "auth_type": r.auth_type,
            "credentials": mask_secrets(r.credentials),
            "config": mask_secrets(r.config),
            "capabilities": entry.get("capabilities", []),
            "is_enabled": r.is_enabled, "is_managed_elsewhere": r.is_managed_elsewhere,
            "managed_by": r.managed_by, "status": r.status,
            "last_check_at": _iso(r.last_check_at), "last_success_at": _iso(r.last_success_at),
            "last_error": r.last_error, "consecutive_failures": r.consecutive_failures,
            "latency_ms": r.latency_ms, "max_attempts": r.max_attempts,
            "retry_backoff_seconds": r.retry_backoff_seconds, "timeout_seconds": r.timeout_seconds,
            "fallback_integration_id": str(r.fallback_integration_id) if r.fallback_integration_id else None,
            "total_calls": r.total_calls, "failed_calls": r.failed_calls,
            "has_inbound_endpoint": bool(r.inbound_token),
            "created_at": _iso(r.created_at),
        }
        if reveal_inbound and r.inbound_token:
            out["inbound_token"] = r.inbound_token
            out["inbound_secret"] = r.inbound_secret
        return out
