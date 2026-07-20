"""AI Lead Intelligence.

A per-lead intelligence layer that unifies the CRM's existing lead signals into
one scored, explained, actionable view — reusing rather than re-implementing:

* lead scoring  → lead_scoring.compute_score (the rule-based 0-100 score)
* conversion prediction + factor breakdown, next-best-action, opportunity/risk
  → PredictiveService's engineered lead features and heuristic probability
* AI lead summary → the AI Platform gateway (multi-provider, cost-tracked)

On top it derives temperature (hot/warm/cold), quality grade, data completeness,
fuzzy duplicate suggestions and enrichment hints, and rolls the whole cohort up
into a dashboard and a distribution report. NO new tables, no cron, no AI
hardcoding — a bounded read aggregator. Scoped to the caller's downline; any
active user gets intelligence on the leads they can see (managers/admins the
whole org). Every AI summary flows through the gateway's logging/permissions.
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
from app.services.predictive_service import PredictiveService, _clamp, _days_since
from app.services.lead_scoring import compute_score

MAX_LEADS = 5000
COMPLETENESS_FIELDS = ("email", "phone", "company_name", "city", "source", "value", "score")
TEMPERATURES = ("hot", "warm", "cold")
QUALITY_GRADES = ("A", "B", "C", "D")


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _num(v) -> float:
    try:
        return float(v)
    except (TypeError, ValueError):
        return 0.0


class LeadIntelligenceService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.pred = PredictiveService(db)

    # ---------- scope ----------
    async def _scope_ids(self, actor: User) -> set | None:
        if actor.role in ("SuperAdmin", "OrgAdmin"):
            return None
        ids = {actor.id}
        if actor.role == "Manager":
            rows = (await self.db.execute(select(User.id).filter(
                User.organization_id == actor.organization_id, User.is_deleted == False,
                User.reporting_to_id == actor.id))).scalars().all()
            ids |= set(rows)
        return ids

    # ---------- derived signals ----------
    @staticmethod
    def _score_grade(score: int) -> str:
        return "A" if score >= 75 else "B" if score >= 50 else "C" if score >= 25 else "D"

    @staticmethod
    def _temperature(probability: float, days_since_activity, age_days: int) -> str:
        if probability >= 60 and (days_since_activity is None or days_since_activity <= 14):
            return "hot"
        if probability < 30 or (days_since_activity is not None and days_since_activity > 30) or age_days > 60:
            return "cold"
        return "warm"

    def _completeness(self, lead: Lead) -> dict:
        present, missing = [], []
        for f in COMPLETENESS_FIELDS:
            v = getattr(lead, f, None)
            if v not in (None, "", 0):
                present.append(f)
            else:
                missing.append(f)
        pct = round(len(present) * 100 / len(COMPLETENESS_FIELDS), 1)
        return {"pct": pct, "present": present, "missing": missing}

    @staticmethod
    def _quality_grade(score: int, completeness_pct: float, probability: float, activities: int) -> str:
        composite = score * 0.4 + completeness_pct * 0.25 + probability * 0.25 + min(activities, 10) * 1.0
        return "A" if composite >= 75 else "B" if composite >= 55 else "C" if composite >= 35 else "D"

    def _opportunity_score(self, value: float, probability: float) -> float:
        """0-100 blend of expected value (log-damped) and conversion likelihood."""
        import math
        value_factor = _clamp(math.log10(value + 1) / 6 * 100, 0, 100) if value > 0 else 0
        return round(value_factor * 0.5 + probability * 0.5, 1)

    @staticmethod
    def _risk_score(f: dict) -> tuple[float, list[str]]:
        risk, reasons = 0.0, []
        dsl = f["days_since_last_activity"]
        if f["activities_total"] == 0 and f["age_days"] > 7:
            risk += 35
            reasons.append("Never contacted")
        elif dsl is not None and dsl > 21:
            risk += 25
            reasons.append(f"No activity in {dsl} days")
        if f["age_days"] > 60:
            risk += 20
            reasons.append("Lead older than 60 days")
        if not f["has_email"] and not f["has_phone"]:
            risk += 20
            reasons.append("No contact channel on file")
        if f["score"] < 25:
            risk += 10
            reasons.append("Low lead score")
        return round(_clamp(risk, 0, 100), 1), reasons

    def _insights(self, lead: Lead, f: dict, prob: float, completeness: dict, temp: str) -> list[str]:
        out = []
        if temp == "hot":
            out.append(f"🔥 Hot lead — {prob}% conversion likelihood; prioritize outreach.")
        elif temp == "cold":
            out.append("🧊 Cold lead — low likelihood or gone quiet.")
        if f["calls"] >= 2:
            out.append(f"Strong engagement: {f['calls']} calls logged.")
        if f["activities_total"] == 0:
            out.append("No activity yet — first touch is overdue.")
        if completeness["missing"]:
            out.append(f"Missing data: {', '.join(completeness['missing'])}.")
        if _num(lead.value) >= 10000:
            out.append(f"High-value opportunity (₹{_num(lead.value):,.0f}).")
        return out

    def _next_best_action(self, f: dict, prob: float, temp: str) -> dict:
        if f["activities_total"] == 0 and f["age_days"] >= 1:
            return {"action": "Make first contact", "priority": "high",
                    "reason": f"Never contacted — created {f['age_days']} day(s) ago."}
        if prob >= 60:
            return {"action": "Push to close", "priority": "high",
                    "reason": f"{prob}% conversion likelihood — engage while warm."}
        dsl = f["days_since_last_activity"]
        if f["score"] >= 50 and dsl is not None and dsl > 7:
            return {"action": "Follow up", "priority": "medium",
                    "reason": f"Score {f['score']} lead idle for {dsl} day(s)."}
        if temp == "cold":
            return {"action": "Qualify or archive", "priority": "low",
                    "reason": "Low likelihood — decide whether to keep nurturing."}
        return {"action": "Nurture", "priority": "medium", "reason": "Keep the lead moving through the pipeline."}

    # ---------- fuzzy duplicate suggestions ----------
    async def _duplicate_suggestions(self, actor: User, lead: Lead) -> list[dict]:
        conds = []
        if lead.email:
            conds.append(func.lower(Lead.email) == lead.email.lower())
        if lead.phone:
            conds.append(Lead.phone == lead.phone)
        # fuzzy: same last name + company, or same company_name
        if lead.last_name:
            conds.append(func.lower(Lead.last_name) == lead.last_name.lower())
        if lead.company_name:
            conds.append(func.lower(Lead.company_name) == lead.company_name.lower())
        if not conds:
            return []
        q = select(Lead).filter(Lead.organization_id == actor.organization_id, Lead.is_deleted == False,
                                Lead.id != lead.id, or_(*conds)).limit(10)
        rows = (await self.db.execute(q)).scalars().all()
        out = []
        for c in rows:
            reasons = []
            if lead.email and c.email and c.email.lower() == lead.email.lower():
                reasons.append("same email")
            if lead.phone and c.phone == lead.phone:
                reasons.append("same phone")
            if lead.last_name and c.last_name and c.last_name.lower() == lead.last_name.lower():
                reasons.append("same last name")
            if lead.company_name and c.company_name and c.company_name.lower() == lead.company_name.lower():
                reasons.append("same company")
            confidence = "high" if ({"same email", "same phone"} & set(reasons)) else "medium" if len(reasons) >= 2 else "low"
            out.append({"lead_id": str(c.id), "name": f"{c.first_name or ''} {c.last_name}".strip(),
                        "email": c.email, "phone": c.phone, "status": c.status,
                        "match_on": reasons, "confidence": confidence})
        out.sort(key=lambda r: {"high": 0, "medium": 1, "low": 2}[r["confidence"]])
        return out

    def _enrichment(self, lead: Lead, completeness: dict) -> list[dict]:
        hints = {
            "email": "Add an email to enable outreach and raise the score (+15).",
            "phone": "Add a phone number for calling (+15).",
            "company_name": "Identify the company for firmographic context (+10).",
            "city": "Add the city to route by territory.",
            "source": "Set the lead source to measure channel ROI.",
            "value": "Estimate deal value to compute opportunity score.",
        }
        return [{"field": f, "suggestion": hints.get(f, f"Populate {f}.")}
                for f in completeness["missing"] if f in hints]

    # ---------- per-lead intelligence ----------
    async def _get_lead(self, actor: User, lead_id: uuid.UUID) -> Lead:
        lead = (await self.db.execute(select(Lead).filter(
            Lead.id == lead_id, Lead.organization_id == actor.organization_id,
            Lead.is_deleted == False))).scalars().first()
        if not lead:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Lead not found")
        scope = await self._scope_ids(actor)
        if scope is not None and lead.assigned_user_id not in scope:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Lead not found")
        return lead

    def _intelligence(self, lead: Lead, f: dict) -> dict:
        # a live rule-based score (independent of any stored value); feed it into
        # the probability model so scoring and prediction stay consistent.
        score = compute_score(email=lead.email, phone=lead.phone, company_name=lead.company_name,
                              value=lead.value, source=lead.source, priority=lead.priority)
        f = {**f, "score": score}
        prob, factors = self.pred._lead_probability(f)
        completeness = self._completeness(lead)
        temp = self._temperature(prob, f["days_since_last_activity"], f["age_days"])
        risk, risk_reasons = self._risk_score(f)
        opportunity = self._opportunity_score(_num(lead.value), prob)
        quality = self._quality_grade(score, completeness["pct"], prob, f["activities_total"])
        return {
            "lead_id": str(lead.id), "name": f["name"], "status": lead.status,
            "value": _num(lead.value), "assigned_user_id": str(lead.assigned_user_id) if lead.assigned_user_id else None,
            "score": score, "score_grade": self._score_grade(score),
            "conversion_probability": prob, "conversion_factors": factors,
            "temperature": temp, "quality_grade": quality,
            "completeness": completeness, "opportunity_score": opportunity,
            "risk_score": risk, "risk_reasons": risk_reasons,
            "recommended_priority": ("High" if temp == "hot" else "Low" if temp == "cold" else "Medium"),
            "next_best_action": self._next_best_action(f, prob, temp),
            "insights": self._insights(lead, f, prob, completeness, temp),
            "enrichment_suggestions": self._enrichment(lead, completeness),
            "age_days": f["age_days"], "activities": f["activities_total"],
            "method": "heuristic_v1", "ai_ready": True,
        }

    async def lead_intelligence(self, actor: User, lead_id: uuid.UUID) -> dict:
        lead = await self._get_lead(actor, lead_id)
        stats = await self.pred._lead_activity_stats(actor.organization_id)
        f = self.pred._lead_features(lead, stats)
        intel = self._intelligence(lead, f)
        intel["duplicate_suggestions"] = await self._duplicate_suggestions(actor, lead)
        return intel

    async def lead_summary(self, actor: User, lead_id: uuid.UUID) -> dict:
        """AI-generated narrative summary — routed through the AI Platform gateway
        (multi-provider, logged, cost-tracked)."""
        lead = await self._get_lead(actor, lead_id)
        from app.services.ai_gateway_service import AIGatewayService
        return await AIGatewayService(self.db).crm_summarize(actor, "lead", str(lead.id))

    async def duplicates(self, actor: User, lead_id: uuid.UUID) -> list[dict]:
        lead = await self._get_lead(actor, lead_id)
        return await self._duplicate_suggestions(actor, lead)

    # ---------- cohort (dashboard / list / report) ----------
    async def _cohort(self, actor: User) -> list[dict]:
        scope = await self._scope_ids(actor)
        q = select(Lead).filter(Lead.organization_id == actor.organization_id, Lead.is_deleted == False)
        if scope is not None:
            q = q.filter(Lead.assigned_user_id.in_(list(scope)))
        leads = list((await self.db.execute(q.order_by(Lead.created_at.desc()).limit(MAX_LEADS))).scalars().all())
        stats = await self.pred._lead_activity_stats(actor.organization_id)
        out = []
        for lead in leads:
            f = self.pred._lead_features(lead, stats)
            out.append(self._intelligence(lead, f))
        return out

    async def list_leads(self, actor: User, *, temperature: str | None = None, quality: str | None = None,
                         sort: str = "opportunity", limit: int = 100) -> dict:
        rows = await self._cohort(actor)
        if temperature:
            rows = [r for r in rows if r["temperature"] == temperature]
        if quality:
            rows = [r for r in rows if r["quality_grade"] == quality]
        key = {"opportunity": "opportunity_score", "score": "score", "risk": "risk_score",
               "probability": "conversion_probability"}.get(sort, "opportunity_score")
        rows.sort(key=lambda r: -r[key])
        return {"total": len(rows), "rows": rows[:min(limit, 500)]}

    async def dashboard(self, actor: User) -> dict:
        rows = await self._cohort(actor)
        open_rows = [r for r in rows if r["status"] not in ("Won", "Converted", "Customer", "Lost")]
        total = len(rows)
        by_temp = {t: sum(1 for r in rows if r["temperature"] == t) for t in TEMPERATURES}
        by_quality = {g: sum(1 for r in rows if r["quality_grade"] == g) for g in QUALITY_GRADES}
        avg_score = round(sum(r["score"] for r in rows) / total, 1) if total else 0.0
        avg_completeness = round(sum(r["completeness"]["pct"] for r in rows) / total, 1) if total else 0.0
        avg_prob = round(sum(r["conversion_probability"] for r in rows) / total, 1) if total else 0.0
        hot = sorted([r for r in open_rows if r["temperature"] == "hot"],
                     key=lambda r: -r["opportunity_score"])[:5]
        at_risk = sorted([r for r in open_rows if r["risk_score"] >= 50],
                         key=lambda r: -r["risk_score"])[:5]
        needs_data = sorted([r for r in open_rows if r["completeness"]["missing"]],
                            key=lambda r: r["completeness"]["pct"])[:5]
        return {"total": total, "by_temperature": by_temp, "by_quality": by_quality,
                "avg_score": avg_score, "avg_completeness": avg_completeness,
                "avg_conversion_probability": avg_prob,
                "hot_leads": hot, "at_risk_leads": at_risk, "needs_enrichment": needs_data,
                "method": "heuristic_v1", "ai_ready": True}

    async def report(self, actor: User) -> dict:
        rows = await self._cohort(actor)
        def dist(key, buckets):
            return {b: sum(1 for r in rows if r[key] == b) for b in buckets}
        by_owner: dict = {}
        for r in rows:
            oid = r["assigned_user_id"] or "unassigned"
            b = by_owner.setdefault(oid, {"count": 0, "hot": 0, "avg_score_sum": 0, "opportunity_sum": 0.0})
            b["count"] += 1
            b["hot"] += 1 if r["temperature"] == "hot" else 0
            b["avg_score_sum"] += r["score"]
            b["opportunity_sum"] += r["opportunity_score"]
        names: dict = {}
        uids = [uuid.UUID(o) for o in by_owner if o != "unassigned"]
        if uids:
            urows = (await self.db.execute(select(User).filter(User.id.in_(uids)))).scalars().all()
            names = {str(u.id): f"{u.first_name} {u.last_name}".strip() for u in urows}
        owner_rows = [{"owner_id": o, "owner_name": names.get(o, "Unassigned" if o == "unassigned" else "—"),
                       "count": b["count"], "hot": b["hot"],
                       "avg_score": round(b["avg_score_sum"] / b["count"], 1) if b["count"] else 0,
                       "avg_opportunity": round(b["opportunity_sum"] / b["count"], 1) if b["count"] else 0}
                      for o, b in by_owner.items()]
        owner_rows.sort(key=lambda r: -r["avg_opportunity"])
        return {"total": len(rows), "by_temperature": dist("temperature", TEMPERATURES),
                "by_quality": dist("quality_grade", QUALITY_GRADES),
                "by_score_grade": dist("score_grade", QUALITY_GRADES), "by_owner": owner_rows}

    async def export_csv(self, actor: User) -> str:
        rows = await self._cohort(actor)
        rows.sort(key=lambda r: -r["opportunity_score"])
        buf = io.StringIO()
        w = csv.writer(buf)
        w.writerow(["lead_id", "name", "status", "value", "score", "score_grade", "quality_grade",
                    "temperature", "conversion_probability", "opportunity_score", "risk_score",
                    "completeness_pct", "next_best_action"])
        for r in rows:
            w.writerow([r["lead_id"], r["name"], r["status"], r["value"], r["score"], r["score_grade"],
                        r["quality_grade"], r["temperature"], r["conversion_probability"],
                        r["opportunity_score"], r["risk_score"], r["completeness"]["pct"],
                        r["next_best_action"]["action"]])
        return buf.getvalue()
