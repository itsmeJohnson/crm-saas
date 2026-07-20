"""AI CRM Copilot.

A conversational orchestration layer on top of the AI Platform gateway — the
natural-language front door to the CRM. It does NOT re-implement AI: intent
routing is a deterministic parser (so it works with the Mock provider and never
depends on a specific model), and every draft/summary/answer that needs
language generation goes through AIGatewayService — the same multi-provider
gateway, memory, caching, cost tracking and logging. Copilot conversations
reuse the AI Platform's ai_conversations / ai_messages (task_type "copilot") —
no new tables.

Capabilities: chat, natural-language search (leads/contacts/companies/
customers), CRM questions (aggregate answers), report generation, record &
activity summaries, opportunity finding (reuses PredictiveService), message
drafting (email/WhatsApp/SMS), and CRM actions (create task, schedule meeting,
send message) that are proposed first and executed on explicit confirmation —
each execution audit-logged. Every reply carries a `speech` field so a
voice/TTS front end can read it aloud (voice-ready). Read actions respect the
caller's downline scope; write/send actions delegate to the owning service so
their own permissions, validation and notifications still fire.
"""
from __future__ import annotations
import re
import uuid
from datetime import datetime, timedelta, timezone
from fastapi import HTTPException, status
from sqlalchemy import select, func, or_
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User
from app.models.lead import Lead
from app.models.contact import Contact
from app.models.company import Company
from app.models.task import Task
from app.models.activity import Activity
from app.services.ai_gateway_service import AIGatewayService
from app.services.audit_service import AuditService

CONVERTED_LEAD_STATUSES = {"Won", "Converted", "Customer"}
ACTION_TYPES = ("create_task", "schedule_meeting", "send_email", "send_whatsapp", "send_sms")

CAPABILITIES = [
    {"intent": "search", "label": "Natural-language search",
     "examples": ["find leads in Mumbai", "show high priority leads", "search companies in retail"]},
    {"intent": "question", "label": "Ask CRM questions",
     "examples": ["how many open leads do I have", "what is my pipeline value", "conversion rate this month"]},
    {"intent": "report", "label": "Generate reports",
     "examples": ["generate a report of leads by status", "report on pipeline by owner"]},
    {"intent": "summarize", "label": "Summarize records & activity",
     "examples": ["summarize lead Ada Lovelace", "summarize customer Acme", "summarize recent activity"]},
    {"intent": "opportunities", "label": "Find opportunities",
     "examples": ["find opportunities", "who should I call today", "hottest leads"]},
    {"intent": "draft", "label": "Draft messages",
     "examples": ["draft an email to Ada about a demo", "draft a whatsapp to John", "draft an sms reminder to Acme"]},
    {"intent": "create_task", "label": "Create tasks",
     "examples": ["create a task follow up with Ada tomorrow", "remind me to call John"]},
    {"intent": "schedule_meeting", "label": "Schedule meetings",
     "examples": ["schedule a meeting with Ada tomorrow at 3pm", "book a call with Acme next monday"]},
]


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _clean(s: str) -> str:
    return (s or "").strip()


def _parse_when(text: str) -> datetime | None:
    """Very small natural-time parser: today/tomorrow/next <weekday> + optional
    'at Hpm/Ham'. Deterministic and timezone-aware (UTC). Good enough for the
    Copilot's propose-then-confirm flow — the user sees the resolved time."""
    t = text.lower()
    base = _now().replace(minute=0, second=0, microsecond=0)
    day = None
    if "tomorrow" in t:
        day = base + timedelta(days=1)
    elif "today" in t or "this afternoon" in t or "tonight" in t:
        day = base
    else:
        weekdays = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]
        for i, wd in enumerate(weekdays):
            if wd in t:
                ahead = (i - base.weekday()) % 7
                ahead = ahead or 7  # "monday" → next monday, not today
                day = base + timedelta(days=ahead)
                break
    if day is None and ("next week" in t):
        day = base + timedelta(days=7)
    if day is None:
        return None
    m = re.search(r"at\s+(\d{1,2})\s*(:(\d{2}))?\s*(am|pm)?", t)
    hour = 9
    if m:
        hour = int(m.group(1)) % 12
        if (m.group(4) or "") == "pm":
            hour += 12
        elif m.group(4) is None and int(m.group(1)) < 8:
            hour = int(m.group(1)) + 12  # bare "at 3" → afternoon
        minute = int(m.group(3) or 0)
        return day.replace(hour=hour, minute=minute)
    return day.replace(hour=9)


class CopilotService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.ai = AIGatewayService(db)
        self.audit = AuditService(db)

    # ---------- scope (downline for managers, own for reps) ----------
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

    def _scoped(self, q, model, scope):
        if scope is not None:
            q = q.filter(model.assigned_user_id.in_(list(scope)))
        return q

    # ---------- capabilities ----------
    def capabilities(self) -> dict:
        return {"capabilities": CAPABILITIES, "action_types": list(ACTION_TYPES),
                "voice_ready": True, "powered_by": "ai-platform-gateway"}

    # ================= intent parsing =================
    def parse_intent(self, message: str) -> dict:
        t = message.lower().strip()
        # draft (before search — "draft email to..." mustn't read as search)
        if re.search(r"\b(draft|write|compose)\b", t):
            channel = ("whatsapp" if "whatsapp" in t or "whats app" in t
                       else "sms" if "sms" in t or "text message" in t
                       else "email")
            goal = "follow up"
            gm = re.search(r"\babout\s+(.*)$", t)
            if gm:
                goal = _clean(gm.group(1))
            return {"intent": "draft", "channel": channel, "target": self._extract_target(message), "goal": goal}
        if re.search(r"\b(create|add|make)\b.*\btask\b", t) or re.search(r"\bremind me to\b", t):
            return {"intent": "create_task", "raw": message}
        if re.search(r"\b(schedule|book|set up|arrange)\b.*\b(meeting|call|demo|appointment)\b", t):
            return {"intent": "schedule_meeting", "raw": message}
        if re.search(r"(opportunit|who should i call|hot lead|best lead|next best)", t):
            return {"intent": "opportunities"}
        if re.search(r"\b(report|breakdown)\b", t):
            return {"intent": "report", "raw": message}
        if re.search(r"(summar|recap|brief me)", t):
            return {"intent": "summarize", "target": self._extract_target(message), "raw": message}
        if re.search(r"\b(how many|what is|what's|whats|count|total|average|conversion|pipeline value)\b", t):
            return {"intent": "question", "raw": message}
        if re.search(r"\b(find|search|show|list|get|lookup|look up)\b", t):
            entity = ("contacts" if "contact" in t else "companies" if ("compan" in t) else
                      "customers" if "customer" in t else "leads")
            return {"intent": "search", "entity": entity, "raw": message}
        return {"intent": "chat", "raw": message}

    @staticmethod
    def _extract_target(message: str) -> str | None:
        m = re.search(r"\b(?:to|for|with|about|lead|contact|customer|company|named)\s+([A-Z][\w'\-]*(?:\s+[A-Z][\w'\-]*){0,3})",
                      message)
        if m:
            return _clean(m.group(1))
        return None

    # ================= entity resolution =================
    async def _resolve_entity(self, actor: User, name: str | None):
        """Best-effort resolve a name to (context_type, id, display) across
        leads → contacts → companies. Returns None when unresolved."""
        if not name:
            return None
        scope = await self._scope_ids(actor)
        # match the whole phrase OR any of its word tokens against the name
        # columns, so "Ada Lovelace" resolves against first_name/last_name.
        tokens = [name.lower()] + [w for w in re.split(r"\s+", name.lower()) if len(w) >= 2]
        def _likes(*cols):
            conds = []
            for tok in tokens:
                like = f"%{tok}%"
                conds += [func.lower(c).like(like) for c in cols]
            return or_(*conds)
        lq = select(Lead).filter(Lead.organization_id == actor.organization_id, Lead.is_deleted == False,
                                 _likes(Lead.first_name, Lead.last_name, Lead.company_name))
        lead = (await self.db.execute(self._scoped(lq, Lead, scope).limit(1))).scalars().first()
        if lead:
            return ("lead", lead.id, f"{lead.first_name or ''} {lead.last_name}".strip())
        cq = select(Contact).filter(Contact.organization_id == actor.organization_id, Contact.is_deleted == False,
                                    _likes(Contact.first_name, Contact.last_name))
        contact = (await self.db.execute(self._scoped(cq, Contact, scope).limit(1))).scalars().first()
        if contact:
            return ("contact", contact.id, f"{contact.first_name or ''} {contact.last_name or ''}".strip())
        coq = select(Company).filter(Company.organization_id == actor.organization_id, Company.is_deleted == False,
                                     _likes(Company.name))
        company = (await self.db.execute(coq.limit(1))).scalars().first()
        if company:
            return ("company", company.id, company.name)
        return None

    # ================= handlers =================
    async def _reply(self, text: str, *, intent: str, data=None, pending_action=None,
                     conversation_id=None) -> dict:
        return {"reply": text, "speech": re.sub(r"[*_#`]", "", text), "intent": intent,
                "data": data, "pending_action": pending_action,
                "conversation_id": str(conversation_id) if conversation_id else None,
                "requires_confirmation": pending_action is not None}

    async def _handle_search(self, actor: User, parsed: dict) -> dict:
        entity = parsed.get("entity", "leads")
        msg = parsed["raw"]
        scope = await self._scope_ids(actor)
        rows, items = [], []
        # optional filters parsed from the phrase
        status_m = re.search(r"\b(new|contacted|qualified|converted|won|lost|open)\b", msg.lower())
        city_m = re.search(r"\bin\s+([A-Z][\w'\-]+)", msg)
        priority_m = re.search(r"\b(high|medium|low|urgent)\s+priority\b", msg.lower())
        name_m = re.search(r"\b(?:named|called)\s+([A-Za-z][\w'\-]+)", msg)
        if entity == "contacts":
            q = select(Contact).filter(Contact.organization_id == actor.organization_id, Contact.is_deleted == False)
            if name_m:
                like = f"%{name_m.group(1).lower()}%"
                q = q.filter(or_(func.lower(Contact.first_name).like(like), func.lower(Contact.last_name).like(like)))
            rows = (await self.db.execute(self._scoped(q, Contact, scope).order_by(Contact.created_at.desc()).limit(10))).scalars().all()
            items = [{"type": "contact", "id": str(c.id), "name": f"{c.first_name or ''} {c.last_name or ''}".strip(),
                      "email": c.email, "phone": c.phone, "title": c.job_title} for c in rows]
        elif entity in ("companies", "customers"):
            q = select(Company).filter(Company.organization_id == actor.organization_id, Company.is_deleted == False)
            if entity == "customers":
                q = q.filter(Company.company_type == "Customer")
            if name_m:
                q = q.filter(func.lower(Company.name).like(f"%{name_m.group(1).lower()}%"))
            rows = (await self.db.execute(q.order_by(Company.created_at.desc()).limit(10))).scalars().all()
            items = [{"type": "company", "id": str(c.id), "name": c.name, "industry": c.industry,
                      "company_type": c.company_type} for c in rows]
        else:
            q = select(Lead).filter(Lead.organization_id == actor.organization_id, Lead.is_deleted == False)
            if status_m:
                s = status_m.group(1)
                if s == "open":
                    q = q.filter(Lead.status.notin_(list(CONVERTED_LEAD_STATUSES) + ["Lost"]))
                else:
                    q = q.filter(func.lower(Lead.status) == s)
            if city_m:
                q = q.filter(func.lower(Lead.city) == city_m.group(1).lower())
            if priority_m:
                q = q.filter(func.lower(Lead.priority) == priority_m.group(1))
            if name_m:
                like = f"%{name_m.group(1).lower()}%"
                q = q.filter(or_(func.lower(Lead.first_name).like(like), func.lower(Lead.last_name).like(like),
                                 func.lower(Lead.company_name).like(like)))
            rows = (await self.db.execute(self._scoped(q, Lead, scope).order_by(Lead.score.desc(), Lead.created_at.desc()).limit(10))).scalars().all()
            items = [{"type": "lead", "id": str(l.id), "name": f"{l.first_name or ''} {l.last_name}".strip(),
                      "status": l.status, "value": float(l.value or 0), "score": l.score,
                      "email": l.email, "phone": l.phone, "city": l.city} for l in rows]
        label = entity
        text = (f"Found {len(items)} {label} matching your search."
                if items else f"No {label} matched that search.")
        return await self._reply(text, intent="search", data={"entity": entity, "results": items})

    async def _handle_question(self, actor: User, parsed: dict) -> dict:
        msg = parsed["raw"].lower()
        org = actor.organization_id
        scope = await self._scope_ids(actor)

        async def lead_count(*filters):
            q = select(func.count(Lead.id)).filter(Lead.organization_id == org, Lead.is_deleted == False, *filters)
            return (await self.db.execute(self._scoped(q, Lead, scope))).scalar() or 0

        total = await lead_count()
        converted = await lead_count(or_(Lead.status.in_(list(CONVERTED_LEAD_STATUSES)), Lead.converted_at.isnot(None)))
        answer, data = None, {}
        if "conversion" in msg:
            rate = round(converted * 100 / total, 1) if total else 0.0
            answer = f"Your lead conversion rate is {rate}% ({converted} converted of {total} leads)."
            data = {"conversion_rate": rate, "converted": converted, "total": total}
        elif "pipeline" in msg or "pipeline value" in msg:
            vq = select(func.coalesce(func.sum(Lead.value), 0)).filter(
                Lead.organization_id == org, Lead.is_deleted == False,
                Lead.status.notin_(list(CONVERTED_LEAD_STATUSES) + ["Lost"]))
            pipeline = float((await self.db.execute(self._scoped(vq, Lead, scope))).scalar() or 0)
            answer = f"Your open pipeline value is ₹{pipeline:,.0f}."
            data = {"pipeline_value": pipeline}
        elif "task" in msg:
            tq = select(func.count(Task.id)).filter(Task.organization_id == org, Task.is_deleted == False,
                                                    Task.status != "Done")
            if scope is not None:
                tq = tq.filter(Task.assigned_user_id.in_(list(scope)))
            open_tasks = (await self.db.execute(tq)).scalar() or 0
            overdue_q = tq.filter(Task.due_date < _now())
            overdue = (await self.db.execute(overdue_q)).scalar() or 0
            answer = f"You have {open_tasks} open task(s), {overdue} of them overdue."
            data = {"open_tasks": open_tasks, "overdue": overdue}
        else:
            open_leads = await lead_count(Lead.status.notin_(list(CONVERTED_LEAD_STATUSES) + ["Lost"]))
            answer = f"You have {total} lead(s) total — {open_leads} open, {converted} converted."
            data = {"total": total, "open": open_leads, "converted": converted}
        return await self._reply(answer, intent="question", data=data)

    async def _handle_opportunities(self, actor: User) -> dict:
        from app.services.predictive_service import PredictiveService
        dash = await PredictiveService(self.db).dashboard(actor)
        hot = dash.get("hot_leads", [])[:5]
        recs = dash.get("top_recommendations", [])[:5]
        if hot:
            top = hot[0]
            text = (f"Your hottest opportunity is {top['name']} "
                    f"({top.get('conversion_probability', 0)}% likely, ₹{top.get('value', 0):,.0f}). "
                    f"{len(hot)} strong open leads and {len(recs)} recommended actions right now.")
        else:
            text = "No standout open opportunities right now — pipeline is quiet."
        return await self._reply(text, intent="opportunities",
                                 data={"hot_leads": hot, "recommendations": recs,
                                       "expected_pipeline_value": dash.get("expected_pipeline_value", 0)})

    async def _handle_report(self, actor: User, parsed: dict) -> dict:
        from app.services.report_builder_service import ReportBuilderService
        rb = ReportBuilderService(self.db)
        msg = parsed["raw"].lower()
        # pick a dataset + grouping from the phrase, default leads-by-status
        dataset, group = "leads", "status"
        if "owner" in msg:
            group = "owner.first_name"
        elif "source" in msg:
            group = "source"
        elif "priority" in msg:
            group = "priority"
        definition = {"dataset": dataset, "columns": [{"field": "value", "agg": "sum"}],
                      "group_by": [group], "sort": [{"field": group, "dir": "asc"}]}
        try:
            res = await rb.run_definition(actor, definition, limit=50)
        except HTTPException:
            raise
        keys = [c["key"] for c in res["columns"]]
        table = "\n".join([" | ".join(keys)] +
                          [" | ".join(str(r.get(k, "")) for k in keys) for r in res["rows"][:30]])
        narrative = await self.ai.generate(actor, task_type="report", template_key="report_narrative",
                                           variables={"report_name": f"{dataset} by {group}", "table": table[:5000]})
        return await self._reply(narrative["text"], intent="report",
                                 data={"columns": res["columns"], "rows": res["rows"],
                                       "chart": {"type": "bar", "group": group}})

    async def _handle_summarize(self, actor: User, parsed: dict) -> dict:
        target = parsed.get("target")
        if not target or re.search(r"\b(activit|recent)\b", parsed["raw"].lower()):
            # summarize recent activity across the workspace
            scope = await self._scope_ids(actor)
            aq = select(Activity).filter(Activity.organization_id == actor.organization_id,
                                         Activity.is_deleted == False)
            if scope is not None:
                aq = aq.filter(Activity.assigned_user_id.in_(list(scope)))
            acts = (await self.db.execute(aq.order_by(Activity.created_at.desc()).limit(20))).scalars().all()
            lines = [f"- {a.activity_type}: {(a.subject or '')[:80]}" for a in acts]
            out = await self.ai.generate(actor, task_type="document", template_key="text_summary",
                                         variables={"text": "\n".join(lines) or "(no recent activity)", "length": 5})
            return await self._reply(out["text"], intent="summarize", data={"activities": len(acts)})
        resolved = await self._resolve_entity(actor, target)
        if not resolved:
            return await self._reply(f"I couldn't find anyone or any company called \"{target}\".",
                                     intent="summarize")
        ctype, cid, display = resolved
        out = await self.ai.crm_summarize(actor, ctype, str(cid))
        return await self._reply(out["text"], intent="summarize",
                                 data={"context_type": ctype, "context_id": str(cid), "name": display})

    async def _handle_draft(self, actor: User, parsed: dict) -> dict:
        channel = parsed.get("channel", "email")
        resolved = await self._resolve_entity(actor, parsed.get("target"))
        if not resolved:
            return await self._reply(
                f"Who should I draft this {channel} to? I couldn't identify the recipient.", intent="draft")
        ctype, cid, display = resolved
        goal = parsed.get("goal") or "follow up"
        if channel == "email":
            out = await self.ai.crm_draft_email(actor, ctype, str(cid), goal)
            action = {"type": "send_email", "context_type": ctype, "context_id": str(cid), "body": out["text"]}
        else:
            record = await self.ai.build_context(actor, ctype, str(cid))
            style = ("a short, friendly WhatsApp message (max 3 sentences, emojis ok)"
                     if channel == "whatsapp" else "a concise SMS under 160 characters")
            out = await self.ai.generate(
                actor, task_type="communication",
                prompt=f"Write {style} to {display}. Goal: {goal}.\n\nContext:\n{record}")
            action = {"type": f"send_{channel}", "context_type": ctype, "context_id": str(cid), "body": out["text"]}
        return await self._reply(
            f"Here's a draft {channel} for {display}:\n\n{out['text']}",
            intent="draft", data={"channel": channel, "draft": out["text"], "name": display},
            pending_action=action)

    async def _handle_create_task(self, actor: User, parsed: dict) -> dict:
        msg = parsed["raw"]
        title = re.sub(r"^\s*(create|add|make)\s+(a\s+)?task\s*(to|:)?\s*", "", msg, flags=re.I)
        title = re.sub(r"^\s*remind me to\s*", "", title, flags=re.I).strip() or "Follow up"
        when = _parse_when(msg)
        # strip trailing time phrase from the title
        title = re.sub(r"\b(today|tomorrow|next week|monday|tuesday|wednesday|thursday|friday|saturday|sunday)\b.*$",
                       "", title, flags=re.I).strip(" .,-") or "Follow up"
        target = self._extract_target(msg)
        linked = await self._resolve_entity(actor, target) if target else None
        action = {"type": "create_task", "title": title[:150],
                  "due_date": when.isoformat() if when else None}
        if linked:
            action[f"{linked[0]}_id"] = str(linked[1])
        due_txt = f" due {when.strftime('%a %d %b %H:%M')}" if when else ""
        link_txt = f" (linked to {linked[2]})" if linked else ""
        return await self._reply(
            f"I'll create the task \"{title}\"{due_txt}{link_txt}. Confirm to proceed.",
            intent="create_task", pending_action=action)

    async def _handle_schedule(self, actor: User, parsed: dict) -> dict:
        msg = parsed["raw"]
        when = _parse_when(msg) or _now().replace(hour=9, minute=0, second=0, microsecond=0) + timedelta(days=1)
        target = self._extract_target(msg)
        linked = await self._resolve_entity(actor, target) if target else None
        who = linked[2] if linked else (target or "the customer")
        title = f"Meeting with {who}"
        action = {"type": "schedule_meeting", "title": title,
                  "start_at": when.isoformat(), "end_at": (when + timedelta(minutes=30)).isoformat()}
        if linked:
            action[f"{linked[0]}_id"] = str(linked[1])
        return await self._reply(
            f"I'll schedule \"{title}\" for {when.strftime('%a %d %b %H:%M')} (30 min). Confirm to proceed.",
            intent="schedule_meeting", pending_action=action)

    async def _handle_chat(self, actor: User, parsed: dict, conversation_id) -> dict:
        out = await self.ai.generate(actor, prompt=parsed["raw"], task_type="copilot",
                                     conversation_id=conversation_id)
        return await self._reply(out["text"], intent="chat", conversation_id=conversation_id)

    # ================= public entrypoints =================
    async def ask(self, actor: User, data: dict) -> dict:
        message = _clean(data.get("message"))
        if not message:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="message is required.")
        # conversation history (reuse AI Platform); create on first turn
        conversation_id = data.get("conversation_id")
        if conversation_id:
            convo = await self.ai._conversation(actor, uuid.UUID(str(conversation_id)))
        else:
            convo = await self.ai._conversation(
                actor, uuid.UUID(str((await self.ai.create_conversation(
                    actor, {"title": message[:60]}))["id"])))
        # log the user turn so history/voice replay works for every intent
        await self.ai._append_message(convo, "user", message)

        parsed = self.parse_intent(message)
        intent = parsed["intent"]
        if intent == "search":
            res = await self._handle_search(actor, parsed)
        elif intent == "question":
            res = await self._handle_question(actor, parsed)
        elif intent == "opportunities":
            res = await self._handle_opportunities(actor)
        elif intent == "report":
            res = await self._handle_report(actor, parsed)
        elif intent == "summarize":
            res = await self._handle_summarize(actor, parsed)
        elif intent == "draft":
            res = await self._handle_draft(actor, parsed)
        elif intent == "create_task":
            res = await self._handle_create_task(actor, parsed)
        elif intent == "schedule_meeting":
            res = await self._handle_schedule(actor, parsed)
        else:
            # free chat already persisted assistant turn via the gateway
            res = await self._handle_chat(actor, parsed, convo.id)
            res["conversation_id"] = str(convo.id)
            return res
        # persist the assistant reply for non-chat intents
        await self.ai._append_message(convo, "assistant", res["reply"])
        res["conversation_id"] = str(convo.id)
        return res

    async def execute(self, actor: User, action: dict) -> dict:
        """Perform a confirmed CRM action. Delegates to the owning service so its
        validation, permissions and notifications fire; audit-logs the result."""
        atype = action.get("type")
        if atype not in ACTION_TYPES:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST,
                                detail=f"type must be one of {list(ACTION_TYPES)}")

        def _uid(key):
            v = action.get(key)
            try:
                return uuid.UUID(str(v)) if v else None
            except (ValueError, TypeError):
                return None

        result: dict
        if atype == "create_task":
            from app.services.task_service import TaskService
            payload = {"title": action.get("title") or "Follow up",
                       "assigned_user_id": actor.id,
                       "lead_id": _uid("lead_id"), "contact_id": _uid("contact_id"),
                       "company_id": _uid("company_id")}
            if action.get("due_date"):
                payload["due_date"] = datetime.fromisoformat(action["due_date"])
            task = await TaskService(self.db).create_task(actor, payload)
            result = {"created": "task", "id": str(task.id), "title": task.title}
        elif atype == "schedule_meeting":
            from app.services.calendar_service import CalendarService
            payload = {"title": action.get("title") or "Meeting", "event_type": "Meeting",
                       "start_at": datetime.fromisoformat(action["start_at"]),
                       "end_at": datetime.fromisoformat(action["end_at"]),
                       "lead_id": _uid("lead_id"), "contact_id": _uid("contact_id"),
                       "company_id": _uid("company_id")}
            ev = await CalendarService(self.db).create_event(actor, payload)
            result = {"created": "calendar_event", "id": str(ev.id), "title": ev.title,
                      "start_at": action["start_at"]}
        elif atype == "send_email":
            from app.services.email_service_module import EmailModuleService
            ctype = action.get("context_type")
            link = {f"{ctype}_id": _uid("context_id")} if ctype in ("lead", "contact", "company") else {}
            act = await EmailModuleService(self.db).send(
                actor, {"subject": action.get("subject") or "Following up", "body": action.get("body") or "", **link})
            result = {"sent": "email", "id": str(act.id)}
        elif atype == "send_whatsapp":
            from app.services.whatsapp_service import WhatsAppService
            link = self._msg_link(action)
            act = await WhatsAppService(self.db).send_text(actor, {"body": action.get("body") or "", **link})
            result = {"sent": "whatsapp", "id": str(act.id)}
        else:  # send_sms
            from app.services.sms_service import SmsService
            link = self._msg_link(action)
            act = await SmsService(self.db).send(actor, {"body": action.get("body") or "", **link})
            result = {"sent": "sms", "id": str(act.id)}
        await self.audit.log_event(
            organization_id=actor.organization_id, actor_user_id=actor.id,
            action="COPILOT_ACTION_EXECUTED", resource_type="copilot",
            resource_id=result.get("id"),
            action_metadata={"action_type": atype, **{k: v for k, v in result.items() if k != "id"}})
        return {"status": "done", "action_type": atype, "result": result,
                "reply": self._done_message(atype, result),
                "speech": self._done_message(atype, result)}

    @staticmethod
    def _msg_link(action: dict) -> dict:
        ctype, cid = action.get("context_type"), action.get("context_id")
        try:
            cid = uuid.UUID(str(cid)) if cid else None
        except (ValueError, TypeError):
            cid = None
        if ctype == "lead":
            return {"lead_id": cid}
        if ctype == "contact":
            return {"contact_id": cid}
        return {}

    @staticmethod
    def _done_message(atype: str, result: dict) -> str:
        if atype == "create_task":
            return f"Task \"{result.get('title')}\" created."
        if atype == "schedule_meeting":
            return f"Meeting \"{result.get('title')}\" scheduled."
        return f"{atype.replace('send_', '').upper()} sent."

    # ---------- history ----------
    async def conversations(self, actor: User) -> list[dict]:
        return await self.ai.list_conversations(actor)

    async def messages(self, actor: User, conversation_id: uuid.UUID) -> list[dict]:
        return await self.ai.conversation_messages(actor, conversation_id)
