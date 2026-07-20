"""AI Communication Intelligence.

Turns raw communication records (Call / Email / WhatsApp / SMS activities, plus
call transcripts and meeting notes) into structured intelligence: sentiment,
intent, action items, follow-up suggestions, language detection and — for the
narrative pieces (call/email/meeting summaries, translation) — the AI Platform
gateway. The linguistic analysis (sentiment lexicon, intent patterns, action-
item extraction, language/script detection) is deterministic, so it works with
the Mock provider and never depends on one model; anything generative routes
through AIGatewayService (multi-provider, logged, cost-tracked). NO new tables,
no cron — a bounded read aggregator over Activity, scoped like Communication
Analytics (managers see all, reps their own). Transcription support = the
pipeline accepts transcript text (from the recording flow or an external STT)
and analyzes it the same way; translation is "ready" via the gateway.
"""
from __future__ import annotations
import csv
import io
import re
import uuid
from datetime import datetime, timedelta, timezone
from fastapi import HTTPException, status
from sqlalchemy import select, or_
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User
from app.models.activity import Activity

CHANNELS = ("Call", "SMS", "WhatsApp", "Email")

# ---- sentiment lexicon (small, transparent; a model can replace it later) ----
POSITIVE = {"great", "good", "excellent", "happy", "thanks", "thank", "interested", "love",
            "perfect", "awesome", "yes", "agree", "confirmed", "excited", "wonderful", "pleased",
            "appreciate", "satisfied", "helpful", "resolved", "keen", "definitely", "sounds good"}
NEGATIVE = {"bad", "poor", "unhappy", "angry", "disappointed", "problem", "issue", "complaint",
            "cancel", "refund", "expensive", "delay", "delayed", "no", "not interested", "frustrated",
            "terrible", "worst", "broken", "failed", "annoyed", "unacceptable", "wrong", "never",
            "waste", "confused", "concern", "concerned"}

# ---- intent patterns (ordered; multiple may match) ----
INTENT_PATTERNS = {
    "pricing": r"\b(price|pricing|cost|quote|quotation|discount|budget|how much)\b",
    "scheduling": r"\b(schedule|meeting|call back|available|calendar|appointment|book|reschedule|when can)\b",
    "complaint": r"\b(complaint|issue|problem|not working|broken|refund|angry|disappointed|unacceptable)\b",
    "interest": r"\b(interested|keen|would like|want to|looking for|tell me more|demo|trial)\b",
    "objection": r"\b(too expensive|not sure|think about|competitor|already have|no budget|not now)\b",
    "support": r"\b(help|support|how do i|how to|not able|error|reset|configure)\b",
    "cancellation": r"\b(cancel|unsubscribe|stop|terminate|close account|opt out)\b",
    "question": r"\?|\b(what|when|where|why|how|can you|could you|do you)\b",
}

# ---- action-item / follow-up cue patterns ----
ACTION_CUES = [
    r"\bi will\b", r"\bwe will\b", r"\bi'll\b", r"\bwe'll\b", r"\bwill send\b", r"\bwill share\b",
    r"\bfollow[- ]?up\b", r"\bget back to you\b", r"\bnext step\b", r"\bneed to\b", r"\bhave to\b",
    r"\bplease\b", r"\bcan you\b", r"\bcould you\b", r"\blet's\b", r"\baction item\b", r"\bto[- ]?do\b",
    r"\bsend (?:me|us|the|over)\b", r"\bschedule\b", r"\bcall (?:me|back)\b", r"\bremind\b",
]

# ---- language detection: script + common-word heuristics ----
LANG_WORDS = {
    "hi": {"hai", "kya", "aap", "nahi", "kar", "mera", "kaise", "acha", "theek", "namaste", "dhanyavaad"},
    "es": {"hola", "gracias", "por", "favor", "que", "como", "usted", "bueno", "precio", "quiero"},
    "fr": {"bonjour", "merci", "vous", "comment", "prix", "oui", "non", "je", "nous", "s'il"},
    "de": {"hallo", "danke", "bitte", "wie", "preis", "ja", "nein", "ich", "wir", "und"},
}


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _aware(dt):
    if dt is None:
        return None
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


def _sentences(text: str) -> list[str]:
    return [s.strip() for s in re.split(r"(?<=[.!?])\s+|\n+", text or "") if s.strip()]


def detect_language(text: str) -> dict:
    t = (text or "").lower()
    if re.search(r"[ऀ-ॿ]", text or ""):  # Devanagari script
        return {"code": "hi", "name": "Hindi", "confidence": "high", "script": "Devanagari"}
    if re.search(r"[؀-ۿ]", text or ""):
        return {"code": "ar", "name": "Arabic", "confidence": "high", "script": "Arabic"}
    if re.search(r"[一-鿿]", text or ""):
        return {"code": "zh", "name": "Chinese", "confidence": "high", "script": "Han"}
    words = set(re.findall(r"[a-z']+", t))
    best, hits = "en", 0
    for code, vocab in LANG_WORDS.items():
        n = len(words & vocab)
        if n > hits:
            best, hits = code, n
    names = {"hi": "Hindi", "es": "Spanish", "fr": "French", "de": "German", "en": "English"}
    return {"code": best, "name": names.get(best, "English"),
            "confidence": "medium" if hits >= 2 else "low", "script": "Latin"}


def analyze_sentiment(text: str) -> dict:
    t = (text or "").lower()
    pos = sum(1 for w in POSITIVE if w in t)
    neg = sum(1 for w in NEGATIVE if w in t)
    score = round((pos - neg) / (pos + neg + 1), 3)
    label = "positive" if score > 0.15 else "negative" if score < -0.15 else "neutral"
    return {"label": label, "score": score, "positive_hits": pos, "negative_hits": neg}


def detect_intents(text: str) -> list[str]:
    t = (text or "").lower()
    return [name for name, pat in INTENT_PATTERNS.items() if re.search(pat, t)]


def extract_action_items(text: str) -> list[str]:
    items = []
    for s in _sentences(text):
        low = s.lower()
        if any(re.search(cue, low) for cue in ACTION_CUES):
            items.append(s[:200])
    # de-dup preserving order
    seen, out = set(), []
    for i in items:
        if i.lower() not in seen:
            seen.add(i.lower())
            out.append(i)
    return out[:10]


def follow_up_suggestions(intents: list[str], sentiment: dict, action_items: list[str]) -> list[str]:
    out = []
    if sentiment["label"] == "negative":
        out.append("Address the raised concern promptly and confirm resolution.")
    if "pricing" in intents:
        out.append("Send a pricing breakdown or quote.")
    if "scheduling" in intents:
        out.append("Propose 2–3 meeting slots and confirm a time.")
    if "interest" in intents:
        out.append("Share a demo or trial and move toward the next step.")
    if "complaint" in intents:
        out.append("Escalate the complaint and set a follow-up deadline.")
    if "objection" in intents:
        out.append("Prepare objection-handling material and re-engage.")
    if "cancellation" in intents:
        out.append("Trigger a retention conversation before processing any cancellation.")
    if not out and action_items:
        out.append("Complete the committed action items and log the outcome.")
    if not out:
        out.append("Send a brief recap and confirm the next step.")
    return out


class CommIntelligenceService:
    def __init__(self, db: AsyncSession):
        self.db = db

    def _privileged(self, actor: User) -> bool:
        return actor.role in ("SuperAdmin", "OrgAdmin", "Manager")

    def _scoped(self, q):
        return q

    def _base(self, actor: User, channel=None, days: int | None = None):
        q = select(Activity).filter(Activity.organization_id == actor.organization_id,
                                    Activity.is_deleted == False, Activity.activity_type.in_(CHANNELS))
        if not self._privileged(actor):
            q = q.filter(or_(Activity.assigned_user_id == actor.id, Activity.created_by == actor.id))
        if channel:
            q = q.filter(Activity.activity_type == channel)
        if days:
            q = q.filter(Activity.created_at >= _now() - timedelta(days=days))
        return q

    # ---------- text analysis (deterministic, no AI) ----------
    def analyze_text(self, text: str, *, channel: str | None = None) -> dict:
        text = text or ""
        sentiment = analyze_sentiment(text)
        intents = detect_intents(text)
        action_items = extract_action_items(text)
        language = detect_language(text)
        return {"channel": channel, "chars": len(text), "words": len(text.split()),
                "language": language, "sentiment": sentiment, "intents": intents,
                "primary_intent": intents[0] if intents else "general",
                "action_items": action_items,
                "follow_up_suggestions": follow_up_suggestions(intents, sentiment, action_items),
                "translation_ready": language["code"] != "en"}

    async def analyze(self, actor: User, data: dict) -> dict:
        text = (data.get("text") or "").strip()
        if not text:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="text is required.")
        return self.analyze_text(text, channel=data.get("channel"))

    # ---------- per-activity intelligence ----------
    async def _get_activity(self, actor: User, activity_id: uuid.UUID) -> Activity:
        a = (await self.db.execute(select(Activity).filter(
            Activity.id == activity_id, Activity.organization_id == actor.organization_id,
            Activity.is_deleted == False))).scalars().first()
        if not a:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Communication not found")
        if not self._privileged(actor) and a.assigned_user_id != actor.id and a.created_by != actor.id:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Communication not found")
        return a

    @staticmethod
    def _activity_text(a: Activity) -> str:
        return f"{a.subject or ''}\n{a.description or ''}".strip()

    async def activity_intelligence(self, actor: User, activity_id: uuid.UUID) -> dict:
        a = await self._get_activity(actor, activity_id)
        intel = self.analyze_text(self._activity_text(a), channel=a.activity_type)
        return {"activity_id": str(a.id), "channel": a.activity_type,
                "direction": a.call_direction, "subject": a.subject,
                "duration": a.call_duration, "disposition": a.call_disposition,
                "created_at": _aware(a.created_at).isoformat() if a.created_at else None, **intel}

    async def activity_summary(self, actor: User, activity_id: uuid.UUID) -> dict:
        """AI narrative summary of one communication — via the AI Platform gateway."""
        a = await self._get_activity(actor, activity_id)
        from app.services.ai_gateway_service import AIGatewayService
        label = {"Call": "call", "Email": "email", "SMS": "SMS", "WhatsApp": "WhatsApp"}.get(a.activity_type, "message")
        return await AIGatewayService(self.db).generate(
            actor, task_type="communication", template_key="text_summary",
            variables={"text": f"{label} — {self._activity_text(a)}"[:6000], "length": 4})

    # ---------- transcription support ----------
    async def analyze_transcript(self, actor: User, data: dict) -> dict:
        """Transcription support: accept transcript text (from the call-recording
        flow or an external STT service) and run the full analysis pipeline,
        optionally attaching it to a call activity for context."""
        transcript = (data.get("transcript") or "").strip()
        if not transcript:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="transcript is required.")
        intel = self.analyze_text(transcript, channel="Call")
        out = {"source": "transcript", **intel}
        if data.get("activity_id"):
            a = await self._get_activity(actor, uuid.UUID(str(data["activity_id"])))
            out["activity_id"] = str(a.id)
            out["duration"] = a.call_duration
        return out

    # ---------- translation-ready ----------
    async def translate(self, actor: User, data: dict) -> dict:
        text = (data.get("text") or "").strip()
        target = (data.get("target_lang") or "en").strip()
        if not text:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="text is required.")
        source = detect_language(text)
        from app.services.ai_gateway_service import AIGatewayService
        res = await AIGatewayService(self.db).generate(
            actor, task_type="communication",
            prompt=f"Translate the following text to {target}. Return only the translation.\n\n{text}"[:6000])
        return {"source_language": source, "target_lang": target,
                "original": text, "translation": res["text"], "provider": res.get("provider")}

    # ---------- conversation analysis ----------
    async def conversation(self, actor: User, *, lead_id: uuid.UUID | None = None,
                           contact_id: uuid.UUID | None = None) -> dict:
        if not lead_id and not contact_id:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST,
                                detail="Provide lead_id or contact_id.")
        q = self._base(actor)
        q = q.filter(Activity.lead_id == lead_id) if lead_id else q.filter(Activity.contact_id == contact_id)
        acts = list((await self.db.execute(q.order_by(Activity.created_at.asc()).limit(200))).scalars().all())
        if not acts:
            return {"messages": 0, "timeline": [], "overall_sentiment": "neutral",
                    "intents": [], "action_items": [], "follow_up_suggestions": [],
                    "languages": []}
        timeline, sent_scores, all_intents, action_items, langs = [], [], {}, [], {}
        by_channel: dict[str, int] = {}
        for a in acts:
            text = self._activity_text(a)
            s = analyze_sentiment(text)
            intents = detect_intents(text)
            lang = detect_language(text)
            sent_scores.append(s["score"])
            for it in intents:
                all_intents[it] = all_intents.get(it, 0) + 1
            action_items += extract_action_items(text)
            langs[lang["code"]] = langs.get(lang["code"], 0) + 1
            by_channel[a.activity_type] = by_channel.get(a.activity_type, 0) + 1
            timeline.append({"activity_id": str(a.id), "channel": a.activity_type,
                             "direction": a.call_direction, "subject": (a.subject or "")[:80],
                             "sentiment": s["label"], "sentiment_score": s["score"],
                             "created_at": _aware(a.created_at).isoformat() if a.created_at else None})
        avg = round(sum(sent_scores) / len(sent_scores), 3)
        overall = "positive" if avg > 0.15 else "negative" if avg < -0.15 else "neutral"
        ranked_intents = sorted(all_intents.items(), key=lambda x: -x[1])
        # de-dup action items
        seen, uniq = set(), []
        for i in action_items:
            if i.lower() not in seen:
                seen.add(i.lower()); uniq.append(i)
        return {"messages": len(acts), "by_channel": by_channel, "timeline": timeline,
                "overall_sentiment": overall, "avg_sentiment_score": avg,
                "sentiment_trend": "improving" if len(sent_scores) >= 2 and sent_scores[-1] > sent_scores[0]
                                   else "declining" if len(sent_scores) >= 2 and sent_scores[-1] < sent_scores[0]
                                   else "steady",
                "intents": [{"intent": k, "count": v} for k, v in ranked_intents],
                "primary_intent": ranked_intents[0][0] if ranked_intents else "general",
                "action_items": uniq[:15],
                "follow_up_suggestions": follow_up_suggestions([k for k, _ in ranked_intents],
                                                               {"label": overall}, uniq),
                "languages": [{"code": k, "count": v} for k, v in sorted(langs.items(), key=lambda x: -x[1])]}

    async def meeting_summary(self, actor: User, data: dict) -> dict:
        """Meeting summary: summarize supplied meeting notes/transcript + extract
        decisions and action items. Narrative via the gateway; action items
        deterministically."""
        notes = (data.get("notes") or data.get("transcript") or "").strip()
        if not notes:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="notes or transcript is required.")
        from app.services.ai_gateway_service import AIGatewayService
        summary = await AIGatewayService(self.db).generate(
            actor, task_type="communication", template_key="text_summary",
            variables={"text": f"Meeting notes:\n{notes}"[:6000], "length": 5})
        return {"summary": summary["text"], "action_items": extract_action_items(notes),
                "sentiment": analyze_sentiment(notes), "intents": detect_intents(notes),
                "language": detect_language(notes)}

    # ---------- dashboard & report ----------
    async def _cohort_analyzed(self, actor: User, days: int = 30) -> list[dict]:
        acts = list((await self.db.execute(
            self._base(actor, days=days).order_by(Activity.created_at.desc()).limit(3000))).scalars().all())
        out = []
        for a in acts:
            intel = self.analyze_text(self._activity_text(a), channel=a.activity_type)
            out.append({"channel": a.activity_type, "sentiment": intel["sentiment"]["label"],
                        "primary_intent": intel["primary_intent"],
                        "action_items": len(intel["action_items"]),
                        "language": intel["language"]["code"]})
        return out

    async def dashboard(self, actor: User, days: int = 30) -> dict:
        rows = await self._cohort_analyzed(actor, days=days)
        total = len(rows)
        sentiment = {k: sum(1 for r in rows if r["sentiment"] == k) for k in ("positive", "neutral", "negative")}
        intents: dict[str, int] = {}
        channels: dict[str, int] = {}
        languages: dict[str, int] = {}
        action_items = 0
        for r in rows:
            intents[r["primary_intent"]] = intents.get(r["primary_intent"], 0) + 1
            channels[r["channel"]] = channels.get(r["channel"], 0) + 1
            languages[r["language"]] = languages.get(r["language"], 0) + 1
            action_items += r["action_items"]
        pos_rate = round(sentiment["positive"] * 100 / total, 1) if total else 0.0
        return {"days": days, "total": total, "sentiment": sentiment, "positive_rate": pos_rate,
                "action_items": action_items,
                "by_intent": [{"intent": k, "count": v} for k, v in sorted(intents.items(), key=lambda x: -x[1])],
                "by_channel": channels,
                "languages": [{"code": k, "count": v} for k, v in sorted(languages.items(), key=lambda x: -x[1])],
                "method": "heuristic_v1", "ai_ready": True}

    async def report(self, actor: User, days: int = 30) -> dict:
        rows = await self._cohort_analyzed(actor, days=days)
        by_channel: dict[str, dict] = {}
        for r in rows:
            b = by_channel.setdefault(r["channel"], {"channel": r["channel"], "total": 0,
                                                     "positive": 0, "negative": 0, "action_items": 0})
            b["total"] += 1
            if r["sentiment"] == "positive":
                b["positive"] += 1
            if r["sentiment"] == "negative":
                b["negative"] += 1
            b["action_items"] += r["action_items"]
        return {"days": days, "total": len(rows), "by_channel": list(by_channel.values())}

    async def export_csv(self, actor: User, days: int = 30) -> str:
        rows = await self._cohort_analyzed(actor, days=days)
        buf = io.StringIO()
        w = csv.writer(buf)
        w.writerow(["channel", "sentiment", "primary_intent", "action_items", "language"])
        for r in rows:
            w.writerow([r["channel"], r["sentiment"], r["primary_intent"], r["action_items"], r["language"]])
        return buf.getvalue()
