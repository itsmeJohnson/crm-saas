"""AI Analytics — the measurement layer over every AI call.

Pure aggregation: NO new tables. It reads what the platform already records and
adds the cuts the usage dashboard never had — per-user adoption, per-prompt
performance, per-MODEL (not just per-provider) performance, latency
percentiles, and a composite response-quality score.

COMPOSES:
  * AIUsageLog        → requests, tokens, cost, latency, status, cache,
    fallback, task_type, template_key, user_id (one row per gateway call).
  * AIPromptTemplate  → prompt names/categories for prompt performance.
  * AIGovernanceEvent → blocked/flagged rate feeding the quality score.
  * User              → org headcount for the adoption rate.

On "Response Quality": there is no human/LLM grader in the product, so this
does NOT claim semantic quality. It reports a transparent composite of the
operational signals that do exist — success, fallback-free, governance-clean
and within-SLA latency — with every component shown so the number is auditable.
"""
import csv
import io
import uuid
from datetime import datetime, timezone, timedelta

from fastapi import HTTPException, status
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User
from app.models.ai_platform import AIUsageLog, AIPromptTemplate
from app.services.audit_service import AuditService

MANAGER_ROLES = ("SuperAdmin", "OrgAdmin", "Manager")
MAX_ROWS = 20000
LATENCY_SLA_MS = 5000  # a call slower than this counts against the quality score

# quality composite weights (must sum to 1.0)
QUALITY_WEIGHTS = {"success": 0.40, "no_fallback": 0.20, "governance_clean": 0.20, "within_sla": 0.20}


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _aware(dt):
    if dt is None:
        return None
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


def _pct(part: int, whole: int) -> float:
    return round(part * 100 / whole, 1) if whole else 0.0


def percentile(values: list[float], p: float) -> float:
    """Nearest-rank percentile (deterministic, no numpy)."""
    if not values:
        return 0.0
    s = sorted(values)
    k = max(0, min(len(s) - 1, int(round((p / 100.0) * len(s) + 0.5)) - 1))
    return round(float(s[k]), 1)


class AIAnalyticsService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.audit = AuditService(db)

    def _require_manager(self, actor: User):
        if actor.role not in MANAGER_ROLES:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN,
                                detail="Manager or admin role required")

    async def _logs(self, org: uuid.UUID, days: int) -> list[AIUsageLog]:
        since = _now() - timedelta(days=max(1, min(int(days), 365)))
        rows = (await self.db.execute(select(AIUsageLog).filter(
            AIUsageLog.organization_id == org, AIUsageLog.is_deleted == False,
            AIUsageLog.created_at >= since)
            .order_by(AIUsageLog.created_at.desc()).limit(MAX_ROWS))).scalars().all()
        return list(rows)

    # ---------- overview (usage + tokens + cost + success/failure) ----------
    async def overview(self, actor: User, days: int = 30) -> dict:
        self._require_manager(actor)
        rows = await self._logs(actor.organization_id, days)
        total = len(rows)
        failed = sum(1 for r in rows if r.status == "failed")
        cached = sum(1 for r in rows if r.cache_hit)
        fallbacks = sum(1 for r in rows if r.fallback_from)
        billable = [r for r in rows if not r.cache_hit]
        prompt_tokens = sum(r.prompt_tokens for r in rows)
        completion_tokens = sum(r.completion_tokens for r in rows)
        cost = round(sum(float(r.cost_usd) for r in rows), 4)
        return {
            "days": days,
            "usage": {"requests": total, "billable_requests": len(billable),
                      "cached": cached, "cache_hit_rate": _pct(cached, total),
                      "fallbacks": fallbacks, "fallback_rate": _pct(fallbacks, total)},
            "tokens": {"prompt": prompt_tokens, "completion": completion_tokens,
                       "total": prompt_tokens + completion_tokens,
                       "avg_per_request": round((prompt_tokens + completion_tokens) / total, 1) if total else 0.0},
            "cost": {"total_usd": cost,
                     "avg_per_request_usd": round(cost / total, 6) if total else 0.0,
                     "cost_per_1k_tokens_usd": round(cost / ((prompt_tokens + completion_tokens) / 1000), 6)
                     if (prompt_tokens + completion_tokens) else 0.0},
            "reliability": {"success": total - failed, "failed": failed,
                            "success_rate": _pct(total - failed, total),
                            "failure_rate": _pct(failed, total)},
        }

    # ---------- latency (avg + percentiles + trend) ----------
    async def latency(self, actor: User, days: int = 30) -> dict:
        self._require_manager(actor)
        rows = await self._logs(actor.organization_id, days)
        live = [r for r in rows if r.status == "success" and not r.cache_hit]
        vals = [float(r.latency_ms) for r in live]
        by_day: dict = {}
        for r in live:
            d = _aware(r.created_at).date().isoformat() if r.created_at else "—"
            by_day.setdefault(d, []).append(float(r.latency_ms))
        by_model: dict = {}
        for r in live:
            by_model.setdefault(r.model, []).append(float(r.latency_ms))
        slowest = sorted(({"model": m, "avg_ms": round(sum(v) / len(v), 1),
                           "p95_ms": percentile(v, 95), "samples": len(v)}
                          for m, v in by_model.items()),
                         key=lambda x: -x["avg_ms"])[:10]
        return {"days": days, "samples": len(vals),
                "avg_ms": round(sum(vals) / len(vals), 1) if vals else 0.0,
                "p50_ms": percentile(vals, 50), "p95_ms": percentile(vals, 95),
                "p99_ms": percentile(vals, 99),
                "max_ms": round(max(vals), 1) if vals else 0.0,
                "sla_ms": LATENCY_SLA_MS,
                "within_sla_rate": _pct(sum(1 for v in vals if v <= LATENCY_SLA_MS), len(vals)),
                "slowest_models": slowest,
                "trend": [{"day": d, "avg_ms": round(sum(v) / len(v), 1), "p95_ms": percentile(v, 95),
                           "samples": len(v)} for d, v in sorted(by_day.items())]}

    # ---------- user adoption ----------
    async def user_adoption(self, actor: User, days: int = 30) -> dict:
        self._require_manager(actor)
        org = actor.organization_id
        rows = await self._logs(org, days)
        total_users = (await self.db.execute(select(func.count(User.id)).filter(
            User.organization_id == org, User.is_deleted == False,
            User.is_active == True))).scalar() or 0
        per_user: dict = {}
        for r in rows:
            if not r.user_id:
                continue
            u = per_user.setdefault(str(r.user_id), {"requests": 0, "tokens": 0, "cost": 0.0,
                                                     "failed": 0, "tasks": set(), "last": None})
            u["requests"] += 1
            u["tokens"] += r.total_tokens
            u["cost"] = round(u["cost"] + float(r.cost_usd), 4)
            u["failed"] += 1 if r.status == "failed" else 0
            u["tasks"].add(r.task_type)
            ts = _aware(r.created_at)
            if ts and (u["last"] is None or ts > u["last"]):
                u["last"] = ts
        names = {}
        if per_user:
            urows = (await self.db.execute(select(User).filter(
                User.id.in_([uuid.UUID(k) for k in per_user])))).scalars().all()
            names = {str(u.id): f"{u.first_name} {u.last_name}".strip() or u.email for u in urows}
        top = sorted(({"user_id": k, "user_name": names.get(k, "—"), "requests": v["requests"],
                       "tokens": v["tokens"], "cost_usd": v["cost"], "failed": v["failed"],
                       "features_used": len(v["tasks"]),
                       "last_used": v["last"].isoformat() if v["last"] else None}
                      for k, v in per_user.items()), key=lambda x: -x["requests"])
        active = len(per_user)
        return {"days": days, "total_active_users": total_users, "ai_users": active,
                "adoption_rate": _pct(active, total_users),
                "avg_requests_per_ai_user": round(len(rows) / active, 1) if active else 0.0,
                "top_users": top[:20],
                "non_adopters": max(0, total_users - active)}

    # ---------- feature adoption (by task type) ----------
    async def feature_adoption(self, actor: User, days: int = 30) -> dict:
        self._require_manager(actor)
        rows = await self._logs(actor.organization_id, days)
        total = len(rows)
        by_task: dict = {}
        for r in rows:
            b = by_task.setdefault(r.task_type, {"requests": 0, "tokens": 0, "cost": 0.0,
                                                 "failed": 0, "users": set()})
            b["requests"] += 1
            b["tokens"] += r.total_tokens
            b["cost"] = round(b["cost"] + float(r.cost_usd), 4)
            b["failed"] += 1 if r.status == "failed" else 0
            if r.user_id:
                b["users"].add(str(r.user_id))
        features = sorted(({"feature": k, "requests": v["requests"], "share_pct": _pct(v["requests"], total),
                            "tokens": v["tokens"], "cost_usd": v["cost"],
                            "unique_users": len(v["users"]),
                            "success_rate": _pct(v["requests"] - v["failed"], v["requests"])}
                           for k, v in by_task.items()), key=lambda x: -x["requests"])
        return {"days": days, "total_requests": total, "features_used": len(features),
                "features": features,
                "most_used": features[0]["feature"] if features else None,
                "least_used": features[-1]["feature"] if features else None}

    # ---------- prompt performance (per template) ----------
    async def prompt_performance(self, actor: User, days: int = 30) -> dict:
        self._require_manager(actor)
        org = actor.organization_id
        rows = [r for r in await self._logs(org, days) if r.template_key]
        by_key: dict = {}
        for r in rows:
            b = by_key.setdefault(r.template_key, {"requests": 0, "failed": 0, "tokens": 0,
                                                   "cost": 0.0, "lat": [], "cached": 0})
            b["requests"] += 1
            b["failed"] += 1 if r.status == "failed" else 0
            b["tokens"] += r.total_tokens
            b["cost"] = round(b["cost"] + float(r.cost_usd), 4)
            b["cached"] += 1 if r.cache_hit else 0
            if r.status == "success" and not r.cache_hit:
                b["lat"].append(float(r.latency_ms))
        meta = {}
        if by_key:
            trows = (await self.db.execute(select(AIPromptTemplate).filter(
                AIPromptTemplate.organization_id == org,
                AIPromptTemplate.key.in_(list(by_key)),
                AIPromptTemplate.is_deleted == False))).scalars().all()
            meta = {t.key: t for t in trows}
        out = []
        for k, v in by_key.items():
            t = meta.get(k)
            out.append({"template_key": k, "name": t.name if t else k,
                        "category": t.task_type if t else None,
                        "status": t.status if t else None,
                        "requests": v["requests"],
                        "success_rate": _pct(v["requests"] - v["failed"], v["requests"]),
                        "failure_rate": _pct(v["failed"], v["requests"]),
                        "cache_hit_rate": _pct(v["cached"], v["requests"]),
                        "tokens": v["tokens"],
                        "avg_tokens": round(v["tokens"] / v["requests"], 1) if v["requests"] else 0.0,
                        "cost_usd": v["cost"],
                        "avg_latency_ms": round(sum(v["lat"]) / len(v["lat"]), 1) if v["lat"] else 0.0,
                        "p95_latency_ms": percentile(v["lat"], 95)})
        out.sort(key=lambda x: -x["requests"])
        return {"days": days, "prompts_used": len(out), "prompts": out,
                "worst_by_failure": sorted(out, key=lambda x: -x["failure_rate"])[:5]}

    # ---------- model performance (per MODEL, not just provider) ----------
    async def model_performance(self, actor: User, days: int = 30) -> dict:
        self._require_manager(actor)
        rows = await self._logs(actor.organization_id, days)
        by_model: dict = {}
        by_provider: dict = {}
        for r in rows:
            key = f"{r.provider}:{r.model}"
            b = by_model.setdefault(key, {"provider": r.provider, "model": r.model, "requests": 0,
                                          "failed": 0, "tokens": 0, "cost": 0.0, "lat": [],
                                          "fallbacks": 0})
            b["requests"] += 1
            b["failed"] += 1 if r.status == "failed" else 0
            b["tokens"] += r.total_tokens
            b["cost"] = round(b["cost"] + float(r.cost_usd), 4)
            b["fallbacks"] += 1 if r.fallback_from else 0
            if r.status == "success" and not r.cache_hit:
                b["lat"].append(float(r.latency_ms))
            p = by_provider.setdefault(r.provider, {"requests": 0, "failed": 0, "cost": 0.0, "tokens": 0})
            p["requests"] += 1
            p["failed"] += 1 if r.status == "failed" else 0
            p["cost"] = round(p["cost"] + float(r.cost_usd), 4)
            p["tokens"] += r.total_tokens
        models = []
        for v in by_model.values():
            models.append({"provider": v["provider"], "model": v["model"], "requests": v["requests"],
                           "success_rate": _pct(v["requests"] - v["failed"], v["requests"]),
                           "failure_rate": _pct(v["failed"], v["requests"]),
                           "fallback_count": v["fallbacks"], "tokens": v["tokens"],
                           "cost_usd": v["cost"],
                           "cost_per_1k_tokens_usd": round(v["cost"] / (v["tokens"] / 1000), 6) if v["tokens"] else 0.0,
                           "avg_latency_ms": round(sum(v["lat"]) / len(v["lat"]), 1) if v["lat"] else 0.0,
                           "p95_latency_ms": percentile(v["lat"], 95)})
        models.sort(key=lambda x: -x["requests"])
        return {"days": days, "models_used": len(models), "models": models,
                "by_provider": [{"provider": k, **v, "success_rate": _pct(v["requests"] - v["failed"], v["requests"])}
                                for k, v in sorted(by_provider.items(), key=lambda kv: -kv[1]["requests"])]}

    # ---------- response quality (transparent composite) ----------
    async def quality(self, actor: User, days: int = 30) -> dict:
        self._require_manager(actor)
        org = actor.organization_id
        rows = await self._logs(org, days)
        total = len(rows)
        failed = sum(1 for r in rows if r.status == "failed")
        fallbacks = sum(1 for r in rows if r.fallback_from)
        live = [r for r in rows if r.status == "success" and not r.cache_hit]
        within_sla = sum(1 for r in live if float(r.latency_ms) <= LATENCY_SLA_MS)

        # governance cleanliness (blocked/flagged requests) — best-effort
        blocked = 0
        try:
            from app.models.ai_governance import AIGovernanceEvent
            since = _now() - timedelta(days=max(1, min(int(days), 365)))
            blocked = (await self.db.execute(select(func.count(AIGovernanceEvent.id)).filter(
                AIGovernanceEvent.organization_id == org,
                AIGovernanceEvent.is_deleted == False,
                AIGovernanceEvent.action_taken.in_(("blocked", "flagged")),
                AIGovernanceEvent.created_at >= since))).scalar() or 0
        except Exception:
            blocked = 0

        components = {
            "success": _pct(total - failed, total),
            "no_fallback": _pct(total - fallbacks, total),
            "governance_clean": _pct(max(0, total - blocked), total) if total else 100.0,
            "within_sla": _pct(within_sla, len(live)) if live else 100.0,
        }
        score = round(sum(components[k] * w for k, w in QUALITY_WEIGHTS.items()), 1)
        band = "excellent" if score >= 90 else "good" if score >= 75 else "fair" if score >= 60 else "poor"
        return {"days": days, "quality_score": score, "band": band,
                "components": components, "weights": QUALITY_WEIGHTS,
                "sample_size": total,
                "note": ("Operational quality composite (success, fallback-free, governance-clean, "
                         "within-SLA latency). It does not grade semantic accuracy — no human or "
                         "LLM grader is configured."),
                "signals": {"failed": failed, "fallbacks": fallbacks,
                            "governance_blocked_or_flagged": blocked,
                            "slow_calls": len(live) - within_sla}}

    # ---------- dashboard / report / export ----------
    async def dashboard(self, actor: User, days: int = 30) -> dict:
        self._require_manager(actor)
        ov = await self.overview(actor, days)
        lat = await self.latency(actor, days)
        q = await self.quality(actor, days)
        ua = await self.user_adoption(actor, days)
        fa = await self.feature_adoption(actor, days)
        mp = await self.model_performance(actor, days)
        return {"days": days,
                "requests": ov["usage"]["requests"], "tokens": ov["tokens"]["total"],
                "cost_usd": ov["cost"]["total_usd"],
                "success_rate": ov["reliability"]["success_rate"],
                "failure_rate": ov["reliability"]["failure_rate"],
                "avg_latency_ms": lat["avg_ms"], "p95_latency_ms": lat["p95_ms"],
                "quality_score": q["quality_score"], "quality_band": q["band"],
                "adoption_rate": ua["adoption_rate"], "ai_users": ua["ai_users"],
                "top_features": fa["features"][:5], "top_models": mp["models"][:5],
                "latency_trend": lat["trend"][-14:]}

    async def report(self, actor: User, days: int = 30) -> dict:
        self._require_manager(actor)
        return {"generated_at": _now().isoformat(), "days": days,
                "overview": await self.overview(actor, days),
                "latency": await self.latency(actor, days),
                "quality": await self.quality(actor, days),
                "user_adoption": await self.user_adoption(actor, days),
                "feature_adoption": await self.feature_adoption(actor, days),
                "prompt_performance": await self.prompt_performance(actor, days),
                "model_performance": await self.model_performance(actor, days)}

    async def export_csv(self, actor: User, days: int = 30) -> str:
        self._require_manager(actor)
        rep = await self.report(actor, days)
        buf = io.StringIO()
        w = csv.writer(buf)
        w.writerow(["section", "key", "requests", "success_rate", "tokens", "cost_usd", "avg_latency_ms"])
        ov = rep["overview"]
        w.writerow(["overview", "all", ov["usage"]["requests"], ov["reliability"]["success_rate"],
                    ov["tokens"]["total"], ov["cost"]["total_usd"], rep["latency"]["avg_ms"]])
        for m in rep["model_performance"]["models"]:
            w.writerow(["model", f'{m["provider"]}:{m["model"]}', m["requests"], m["success_rate"],
                        m["tokens"], m["cost_usd"], m["avg_latency_ms"]])
        for f in rep["feature_adoption"]["features"]:
            w.writerow(["feature", f["feature"], f["requests"], f["success_rate"], f["tokens"],
                        f["cost_usd"], ""])
        for p in rep["prompt_performance"]["prompts"]:
            w.writerow(["prompt", p["template_key"], p["requests"], p["success_rate"], p["tokens"],
                        p["cost_usd"], p["avg_latency_ms"]])
        for u in rep["user_adoption"]["top_users"]:
            w.writerow(["user", u["user_name"], u["requests"], "", u["tokens"], u["cost_usd"], ""])
        await self.audit.log_event(actor.organization_id, actor_user_id=actor.id,
                                   action="AI_ANALYTICS_EXPORTED", resource_type="ai_analytics",
                                   action_metadata={"days": days})
        await self.db.commit()
        return buf.getvalue()
