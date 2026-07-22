"""AI Recommendation Engine — a unified, personalized recommendation layer with
a feedback loop.

COMPOSES the existing intelligence stack rather than reimplementing it:
  * PredictiveService        → lead features / probability, at-risk customers,
    employee-performance dataset.
  * LeadIntelligenceService  → next-best-action decision logic + downline scope.
  * SalesIntelligenceService → upsell / cross-sell product recommendations.
  * WorkflowAssistantService → recommended workflows to automate.
  * PredictionEngineService  → recommended campaigns (best predicted ROI).
  * KnowledgeBaseService     → recommended knowledge articles (semantic search).
  * CommunicationAnalyticsService → best call-time window (activity heatmap).

Adds what none of them had: a unified feed, three NEW generators (recommended
AGENT, FOLLOW-UP, CALL-TIME), a per-user personalization re-rank, and a
persisted FEEDBACK LOOP (accept / dismiss / snooze / complete) that both stops
dismissed items re-surfacing and feeds recommendation analytics.

Deterministic throughout; ONE new table (recommendation_feedback).
"""
import csv
import io
import uuid
from datetime import datetime, timezone, timedelta

from fastapi import HTTPException, status
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User
from app.models.lead import Lead
from app.models.recommendation import RecommendationFeedback
from app.services.audit_service import AuditService
from app.services.predictive_service import PredictiveService
from app.services.lead_intelligence_service import LeadIntelligenceService

MANAGER_ROLES = ("SuperAdmin", "OrgAdmin", "Manager")
REC_TYPES = ("next_best_action", "follow_up", "call_time", "agent", "product",
             "workflow", "campaign", "knowledge")
ACTIONS = ("pending", "accepted", "dismissed", "snoozed", "completed")
CLOSED_ACTIONS = ("dismissed", "completed")  # never re-surface these
PRIORITY_BASE = {"high": 70.0, "medium": 45.0, "low": 25.0}
WEEKDAYS = ("Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday")


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _aware(dt):
    if dt is None:
        return None
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


class RecommendationEngineService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.audit = AuditService(db)
        self.pred = PredictiveService(db)
        self.lead_intel = LeadIntelligenceService(db)

    # ---------- scope ----------
    async def _scope_ids(self, actor: User) -> set | None:
        """None = whole org (admins); otherwise the actor + direct reports."""
        if actor.role in ("SuperAdmin", "OrgAdmin"):
            return None
        ids = {actor.id}
        if actor.role == "Manager":
            rows = (await self.db.execute(select(User.id).filter(
                User.organization_id == actor.organization_id, User.is_deleted == False,
                User.reporting_to_id == actor.id))).scalars().all()
            ids |= set(rows)
        return ids

    async def _scoped_leads(self, actor: User):
        leads, stats = await self.pred._leads(actor.organization_id)
        scope = await self._scope_ids(actor)
        if scope is not None:
            leads = [l for l in leads if l.assigned_user_id in scope]
        return leads, stats

    # ---------- personalization (the feedback loop's learning) ----------
    async def _multipliers(self, actor: User) -> dict:
        """Per-rec-type score multiplier learned from this user's feedback:
        Laplace-smoothed acceptance rate mapped to ~[0.5, 1.5]. No history → 1.0."""
        rows = (await self.db.execute(select(
            RecommendationFeedback.rec_type, RecommendationFeedback.action).filter(
            RecommendationFeedback.user_id == actor.id,
            RecommendationFeedback.is_deleted == False))).all()
        acc: dict = {}
        for rec_type, action in rows:
            b = acc.setdefault(rec_type, {"pos": 0, "neg": 0})
            if action in ("accepted", "completed"):
                b["pos"] += 1
            elif action == "dismissed":
                b["neg"] += 1
        mult = {}
        for t in REC_TYPES:
            b = acc.get(t, {"pos": 0, "neg": 0})
            rate = (b["pos"] + 1) / (b["pos"] + b["neg"] + 2)  # Laplace, default 0.5
            mult[t] = round(0.5 + rate, 3)  # 0.5 .. 1.5
        return mult

    async def _suppressed_keys(self, actor: User) -> dict:
        """rec_key → action for keys the user already resolved (dismiss/complete)
        or is currently snoozing — these are filtered out of a fresh feed."""
        rows = (await self.db.execute(select(RecommendationFeedback).filter(
            RecommendationFeedback.user_id == actor.id,
            RecommendationFeedback.is_deleted == False))).scalars().all()
        now = _now()
        out = {}
        for r in rows:
            if r.action in CLOSED_ACTIONS:
                out[r.rec_key] = r.action
            elif r.action == "snoozed" and r.snooze_until and _aware(r.snooze_until) > now:
                out[r.rec_key] = "snoozed"
        return out

    # ================= generators (each returns list of rec dicts) ==========
    async def next_best_actions(self, actor: User, limit: int = 20) -> list[dict]:
        leads, stats = await self._scoped_leads(actor)
        out = []
        for l in leads:
            f = self.pred._lead_features(l, stats)
            if f["converted"] is not None:
                continue
            prob, _ = self.pred._lead_probability(f)
            temp = self.lead_intel._temperature(prob, f["days_since_last_activity"], f["age_days"])
            nba = self.lead_intel._next_best_action(f, prob, temp)
            out.append(self._rec("next_best_action", f"next_best_action:lead:{f['lead_id']}",
                                 title=f"{nba['action']}: {f['name']}", reason=nba["reason"],
                                 priority=nba["priority"], target_type="lead", target_id=f["lead_id"],
                                 payload={"action": nba["action"], "conversion_probability": prob,
                                          "value": f["value"], "temperature": temp}))
        return self._top(out, limit)

    async def follow_ups(self, actor: User, limit: int = 20) -> list[dict]:
        """Leads/customers overdue for a touch: idle open leads + at-risk customers."""
        leads, stats = await self._scoped_leads(actor)
        out = []
        for l in leads:
            f = self.pred._lead_features(l, stats)
            if f["converted"] is not None:
                continue
            dsl = f["days_since_last_activity"]
            if dsl is not None and dsl >= 7:
                pr = "high" if dsl >= 21 else "medium"
                out.append(self._rec("follow_up", f"follow_up:lead:{f['lead_id']}",
                                     title=f"Follow up with {f['name']}",
                                     reason=f"No activity for {dsl} day(s).", priority=pr,
                                     target_type="lead", target_id=f["lead_id"],
                                     payload={"days_since_last_activity": dsl, "value": f["value"]}))
            elif f["activities_total"] == 0 and f["age_days"] >= 2:
                out.append(self._rec("follow_up", f"follow_up:lead:{f['lead_id']}",
                                     title=f"First touch for {f['name']}",
                                     reason=f"Never contacted — {f['age_days']} day(s) old.",
                                     priority="high", target_type="lead", target_id=f["lead_id"],
                                     payload={"age_days": f["age_days"]}))
        # at-risk customers with overdue balances (admins/managers see customers)
        if actor.role in MANAGER_ROLES:
            for c in await self.pred._customers(actor.organization_id):
                if c["overdue_invoices"] > 0:
                    out.append(self._rec("follow_up", f"follow_up:customer:{c['customer_id']}",
                                         title=f"Chase payment: {c['customer_name']}",
                                         reason=f"{c['overdue_invoices']} overdue invoice(s).",
                                         priority="high", target_type="customer",
                                         target_id=c["customer_id"],
                                         payload={"overdue_invoices": c["overdue_invoices"]}))
        return self._top(out, limit)

    async def call_times(self, actor: User, limit: int = 10) -> list[dict]:
        """Best call windows from the org's contact-activity heatmap, plus a
        per-lead nudge for hot leads that should be called in that window."""
        from app.services.communication_analytics_service import CommunicationAnalyticsService
        heat = await CommunicationAnalyticsService(self.db).heatmap(actor)
        peak = heat.get("peak", {})
        out = []
        if peak.get("count", 0) > 0:
            wd = WEEKDAYS[peak["weekday"]] if 0 <= peak["weekday"] < 7 else "?"
            hr = peak["hour"]
            window = f"{hr:02d}:00–{(hr + 1) % 24:02d}:00"
            out.append(self._rec("call_time", "call_time:org:peak",
                                 title=f"Best time to call: {wd} {window}",
                                 reason=f"Your team's contacts respond most around this window "
                                        f"({peak['count']} interactions).",
                                 priority="medium", target_type="org", target_id=None,
                                 payload={"weekday": wd, "hour": hr, "window": window,
                                          "sample": peak["count"]}))
        # hot open leads worth calling
        leads, stats = await self._scoped_leads(actor)
        hot = []
        for l in leads:
            f = self.pred._lead_features(l, stats)
            if f["converted"] is not None:
                continue
            prob, _ = self.pred._lead_probability(f)
            if prob >= 55 and f["has_phone"]:
                hot.append((prob, f))
        for prob, f in sorted(hot, key=lambda x: -x[0])[:limit]:
            out.append(self._rec("call_time", f"call_time:lead:{f['lead_id']}",
                                 title=f"Call {f['name']} today",
                                 reason=f"{prob}% conversion likelihood and reachable by phone.",
                                 priority="high", target_type="lead", target_id=f["lead_id"],
                                 payload={"conversion_probability": prob}))
        return self._top(out, limit + 1)

    async def agents(self, actor: User, lead_id: uuid.UUID | None = None, limit: int = 5) -> list[dict]:
        """Recommended agent(s) to hand work to: best recent performers with the
        lightest current open-lead load, within the actor's scope."""
        self._require_manager(actor)
        perf = await self.pred._ds_employee_performance(actor)
        scope = await self._scope_ids(actor)
        # current open-lead load per user
        q = select(Lead.assigned_user_id, func.count(Lead.id)).filter(
            Lead.organization_id == actor.organization_id, Lead.is_deleted == False,
            Lead.status.notin_(("Converted", "Lost", "Closed", "Dead")),
            Lead.assigned_user_id != None).group_by(Lead.assigned_user_id)
        load = {str(uid): n for uid, n in (await self.db.execute(q)).all()}
        out = []
        for p in perf:
            if scope is not None and uuid.UUID(p["user_id"]) not in scope:
                continue
            if p["role"] not in ("Employee", "Manager"):
                continue
            open_load = load.get(p["user_id"], 0)
            # ranking score: performance up, load down
            rank_score = round(p["score_30d"] - open_load * 3, 2)
            reason = (f"Performance score {p['score_30d']} (trend {p['trend_pct']}%), "
                      f"{open_load} open lead(s).")
            rec = self._rec("agent", f"agent:{p['user_id']}" + (f":{lead_id}" if lead_id else ""),
                            title=f"Assign to {p['user_name']}", reason=reason,
                            priority="high" if rank_score > 20 else "medium",
                            target_type="user", target_id=p["user_id"],
                            payload={"score_30d": p["score_30d"], "open_load": open_load,
                                     "trend_pct": p["trend_pct"],
                                     "for_lead": str(lead_id) if lead_id else None})
            rec["_rank_score"] = rank_score
            out.append(rec)
        out.sort(key=lambda r: r.pop("_rank_score"), reverse=True)
        return out[:limit]

    async def products(self, actor: User, limit: int = 20) -> list[dict]:
        self._require_manager(actor)
        from app.services.sales_intelligence_service import SalesIntelligenceService
        data = await SalesIntelligenceService(self.db).upsell_suggestions(actor)
        out = []
        for u in data.get("upsell", []):
            out.append(self._rec("product", f"product:upsell:{u['customer_id']}",
                                 title=f"Upsell {u['customer_name']}", reason=u["reason"],
                                 priority=u.get("priority", "medium"), target_type="customer",
                                 target_id=u["customer_id"], payload={"kind": "upsell",
                                 "total_paid": u.get("total_paid")}))
        for c in data.get("cross_sell", []):
            out.append(self._rec("product", f"product:cross:{c['customer_id']}",
                                 title=f"Cross-sell {c['customer_name']}", reason=c["reason"],
                                 priority=c.get("priority", "medium"), target_type="customer",
                                 target_id=c["customer_id"], payload={"kind": "cross_sell"}))
        return self._top(out, limit)

    async def workflows(self, actor: User, limit: int = 10) -> list[dict]:
        self._require_manager(actor)
        from app.services.workflow_assistant_service import WorkflowAssistantService
        data = await WorkflowAssistantService(self.db).suggestions(actor)
        out = []
        for s in data.get("suggestions", []):
            if s.get("already_covered"):
                continue
            out.append(self._rec("workflow", f"workflow:{s['key']}", title=s["title"],
                                 reason=s["reason"], priority=s.get("impact", "medium"),
                                 target_type="workflow", target_id=None,
                                 payload={"trigger_event": s.get("trigger_event"),
                                          "draft_graph": s.get("draft_graph")}))
        return self._top(out, limit)

    async def campaigns(self, actor: User, limit: int = 10) -> list[dict]:
        self._require_manager(actor)
        from app.services.prediction_engine_service import PredictionEngineService
        data = await PredictionEngineService(self.db).campaign_predictions(actor, limit=limit)
        out = []
        for c in data.get("predictions", []):
            roi = c["predicted"].get("roi_pct")
            if roi is None:
                continue
            out.append(self._rec("campaign", f"campaign:{c['campaign_id']}",
                                 title=f"Launch '{c['name']}' ({c['channel']})",
                                 reason=f"Predicted ROI {roi}% on {c['audience_size']} recipients.",
                                 priority="high" if roi >= 100 else "medium",
                                 target_type="campaign", target_id=c["campaign_id"],
                                 payload={"roi_pct": roi, "channel": c["channel"],
                                          "expected_revenue": c["predicted"].get("revenue")}))
        return self._top(out, limit)

    async def knowledge(self, actor: User, query: str, limit: int = 5) -> list[dict]:
        from app.services.knowledge_base_service import KnowledgeBaseService
        res = await KnowledgeBaseService(self.db).search(actor, query, limit=limit, log=False)
        out = []
        for r in res.get("results", []):
            out.append(self._rec("knowledge", f"knowledge:{r['article_id']}",
                                 title=r["title"], reason=r.get("excerpt", "")[:200],
                                 priority="low", target_type="article", target_id=r["article_id"],
                                 payload={"score": r.get("score"), "article_type": r.get("article_type")}))
        return out

    # ================= unified + personalized feed =================
    async def feed(self, actor: User, *, limit: int = 25, persist: bool = True) -> dict:
        """The unified 'Next Best Action' feed: candidates from every generator,
        personalized re-rank, dismissed items suppressed, top N persisted."""
        mult = await self._multipliers(actor)
        suppressed = await self._suppressed_keys(actor)
        candidates: list[dict] = []
        candidates += await self.next_best_actions(actor, limit=15)
        candidates += await self.follow_ups(actor, limit=15)
        candidates += await self.call_times(actor, limit=6)
        candidates += await self.knowledge(actor, self._context_query(actor), limit=3)
        if actor.role in MANAGER_ROLES:
            candidates += await self.products(actor, limit=8)
            candidates += await self.workflows(actor, limit=5)
            candidates += await self.campaigns(actor, limit=5)
        # dedup by rec_key, drop suppressed, apply personalization
        seen, ranked = set(), []
        for c in candidates:
            if c["rec_key"] in seen or c["rec_key"] in suppressed:
                continue
            seen.add(c["rec_key"])
            c["personalized_score"] = round(c["score"] * mult.get(c["rec_type"], 1.0), 2)
            ranked.append(c)
        ranked.sort(key=lambda r: r["personalized_score"], reverse=True)
        top = ranked[:limit]
        if persist:
            await self._persist(actor, top)
        return {"generated_at": _now().isoformat(), "count": len(top),
                "personalization": mult, "recommendations": top,
                "types_present": sorted({r["rec_type"] for r in top})}

    async def personalized(self, actor: User, limit: int = 25) -> dict:
        """Personalized suggestions — the feed plus an explanation of how the
        user's own feedback shaped the ranking."""
        f = await self.feed(actor, limit=limit)
        mult = f["personalization"]
        boosted = sorted(mult.items(), key=lambda kv: kv[1], reverse=True)
        f["explanation"] = {
            "boosted_types": [t for t, m in boosted if m > 1.0],
            "muted_types": [t for t, m in boosted if m < 1.0],
            "note": "Types you accept are up-weighted; types you dismiss are down-weighted.",
        }
        return f

    def _context_query(self, actor: User) -> str:
        return "sales follow up objection pricing onboarding"

    # ================= feedback loop =================
    async def record_feedback(self, actor: User, *, action: str,
                              feedback_id: uuid.UUID | None = None,
                              rec_key: str | None = None, rec_type: str | None = None,
                              title: str | None = None, reason: str | None = None,
                              target_type: str | None = None, target_id: str | None = None,
                              payload: dict | None = None, snooze_hours: int | None = None) -> dict:
        if action not in ACTIONS:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST,
                                detail=f"action must be one of {list(ACTIONS)}")
        row = None
        if feedback_id:
            row = (await self.db.execute(select(RecommendationFeedback).filter(
                RecommendationFeedback.id == feedback_id,
                RecommendationFeedback.organization_id == actor.organization_id,
                RecommendationFeedback.is_deleted == False))).scalars().first()
            if not row:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Recommendation not found")
            if row.user_id != actor.id and actor.role not in ("SuperAdmin", "OrgAdmin"):
                raise HTTPException(status_code=status.HTTP_403_FORBIDDEN,
                                    detail="You can only act on your own recommendations")
        elif rec_key:
            row = (await self.db.execute(select(RecommendationFeedback).filter(
                RecommendationFeedback.user_id == actor.id,
                RecommendationFeedback.rec_key == rec_key,
                RecommendationFeedback.is_deleted == False))).scalars().first()
            if not row:
                if not (rec_type and title):
                    raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST,
                                        detail="New feedback needs rec_type and title")
                if rec_type not in REC_TYPES:
                    raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST,
                                        detail=f"rec_type must be one of {list(REC_TYPES)}")
                row = RecommendationFeedback(organization_id=actor.organization_id, user_id=actor.id,
                                             rec_type=rec_type, rec_key=rec_key, title=title,
                                             reason=reason, target_type=target_type, target_id=target_id,
                                             payload=payload or {}, action="pending")
                self.db.add(row)
        else:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST,
                                detail="Provide feedback_id or rec_key")
        row.action = action
        row.acted_at = _now()
        if action == "snoozed":
            row.snooze_until = _now() + timedelta(hours=max(1, min(int(snooze_hours or 24), 720)))
        await self.db.flush()
        await self.audit.log_event(actor.organization_id, actor_user_id=actor.id,
                                   action="RECOMMENDATION_FEEDBACK", resource_type="recommendation",
                                   resource_id=str(row.id),
                                   action_metadata={"rec_type": row.rec_type, "response": action})
        await self.db.commit()
        await self.db.refresh(row)
        return self._row_dict(row)

    # ================= analytics =================
    async def analytics(self, actor: User) -> dict:
        self._require_manager(actor)
        scope = await self._scope_ids(actor)
        q = select(RecommendationFeedback).filter(
            RecommendationFeedback.organization_id == actor.organization_id,
            RecommendationFeedback.is_deleted == False)
        if scope is not None:
            q = q.filter(RecommendationFeedback.user_id.in_(list(scope)))
        rows = (await self.db.execute(q)).scalars().all()
        by_type: dict = {}
        totals = {"shown": 0, "accepted": 0, "dismissed": 0, "snoozed": 0,
                  "completed": 0, "pending": 0}
        for r in rows:
            totals["shown"] += 1
            totals[r.action] = totals.get(r.action, 0) + 1
            b = by_type.setdefault(r.rec_type, {"shown": 0, "accepted": 0, "dismissed": 0,
                                                "completed": 0, "snoozed": 0, "pending": 0})
            b["shown"] += 1
            b[r.action] = b.get(r.action, 0) + 1
        def acc_rate(b):
            acted = b["accepted"] + b["completed"] + b["dismissed"]
            return round((b["accepted"] + b["completed"]) * 100 / acted, 1) if acted else None
        per_type = [{"rec_type": t, **b, "acceptance_rate": acc_rate(b)}
                    for t, b in sorted(by_type.items(), key=lambda kv: -kv[1]["shown"])]
        accepted_rows = [r for r in rows if r.action in ("accepted", "completed")]
        top_accepted = [{"title": r.title, "rec_type": r.rec_type,
                         "acted_at": _aware(r.acted_at).isoformat() if r.acted_at else None}
                        for r in sorted(accepted_rows, key=lambda r: _aware(r.acted_at) or _now(),
                                        reverse=True)[:10]]
        return {"totals": totals, "overall_acceptance_rate": acc_rate(totals),
                "by_type": per_type, "top_accepted": top_accepted}

    # ================= dashboard / report / export =================
    async def dashboard(self, actor: User) -> dict:
        feed = await self.feed(actor, limit=8, persist=False)
        pending = (await self.db.execute(select(func.count(RecommendationFeedback.id)).filter(
            RecommendationFeedback.user_id == actor.id,
            RecommendationFeedback.is_deleted == False,
            RecommendationFeedback.action == "pending"))).scalar() or 0
        accepted = (await self.db.execute(select(func.count(RecommendationFeedback.id)).filter(
            RecommendationFeedback.user_id == actor.id,
            RecommendationFeedback.is_deleted == False,
            RecommendationFeedback.action.in_(("accepted", "completed"))))).scalar() or 0
        return {"top_recommendations": feed["recommendations"][:6],
                "types_present": feed["types_present"], "total": feed["count"],
                "my_pending": int(pending), "my_accepted": int(accepted)}

    async def report(self, actor: User) -> dict:
        self._require_manager(actor)
        feed = await self.feed(actor, limit=50, persist=False)
        analytics = await self.analytics(actor)
        counts: dict = {}
        for r in feed["recommendations"]:
            counts[r["rec_type"]] = counts.get(r["rec_type"], 0) + 1
        return {"generated_at": _now().isoformat(),
                "summary": {"live_recommendations": feed["count"], "by_type": counts,
                            "overall_acceptance_rate": analytics["overall_acceptance_rate"],
                            "feedback_shown": analytics["totals"]["shown"]},
                "recommendations": feed["recommendations"], "analytics": analytics}

    async def export_csv(self, actor: User) -> str:
        self._require_manager(actor)
        feed = await self.feed(actor, limit=200, persist=False)
        buf = io.StringIO()
        w = csv.writer(buf)
        w.writerow(["rec_type", "title", "priority", "score", "personalized_score",
                    "target_type", "target_id", "reason"])
        for r in feed["recommendations"]:
            w.writerow([r["rec_type"], r["title"], r["priority"], r["score"],
                        r["personalized_score"], r.get("target_type"), r.get("target_id"),
                        (r.get("reason") or "")[:200]])
        await self.audit.log_event(actor.organization_id, actor_user_id=actor.id,
                                   action="RECOMMENDATIONS_EXPORTED", resource_type="recommendation",
                                   action_metadata={"rows": feed["count"]})
        await self.db.commit()
        return buf.getvalue()

    def catalog(self) -> dict:
        return {"rec_types": list(REC_TYPES), "actions": list(ACTIONS)}

    # ================= helpers =================
    def _require_manager(self, actor: User):
        if actor.role not in MANAGER_ROLES:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN,
                                detail="Manager or admin role required")

    def _rec(self, rec_type: str, rec_key: str, *, title: str, reason: str, priority: str,
             target_type: str | None, target_id: str | None, payload: dict) -> dict:
        return {"rec_type": rec_type, "rec_key": rec_key, "title": title, "reason": reason,
                "priority": priority, "score": PRIORITY_BASE.get(priority, 30.0),
                "target_type": target_type, "target_id": target_id, "payload": payload}

    def _top(self, recs: list[dict], limit: int) -> list[dict]:
        recs.sort(key=lambda r: r["score"], reverse=True)
        return recs[:limit]

    async def _persist(self, actor: User, recs: list[dict]):
        """Upsert each surfaced rec as a feedback row (idempotent per user+key),
        preserving any prior action; new ones start pending. Attaches `id`."""
        keys = [r["rec_key"] for r in recs]
        existing = {}
        if keys:
            rows = (await self.db.execute(select(RecommendationFeedback).filter(
                RecommendationFeedback.user_id == actor.id,
                RecommendationFeedback.rec_key.in_(keys),
                RecommendationFeedback.is_deleted == False))).scalars().all()
            existing = {r.rec_key: r for r in rows}
        for rank, r in enumerate(recs, 1):
            row = existing.get(r["rec_key"])
            if row is None:
                row = RecommendationFeedback(
                    organization_id=actor.organization_id, user_id=actor.id,
                    rec_type=r["rec_type"], rec_key=r["rec_key"], title=r["title"],
                    reason=r["reason"], target_type=r["target_type"], target_id=r["target_id"],
                    score=r["personalized_score"], rank=rank, payload=r["payload"], action="pending")
                self.db.add(row)
                await self.db.flush()
            else:
                row.score = r["personalized_score"]
                row.rank = rank
            r["id"] = str(row.id)
            r["action"] = row.action
        await self.db.commit()

    def _row_dict(self, r: RecommendationFeedback) -> dict:
        return {"id": str(r.id), "rec_type": r.rec_type, "rec_key": r.rec_key,
                "title": r.title, "reason": r.reason, "priority": None,
                "target_type": r.target_type, "target_id": r.target_id,
                "action": r.action, "score": r.score, "rank": r.rank,
                "payload": r.payload or {},
                "acted_at": _aware(r.acted_at).isoformat() if r.acted_at else None,
                "snooze_until": _aware(r.snooze_until).isoformat() if r.snooze_until else None}
