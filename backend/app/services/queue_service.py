"""Background Queue service.

A durable, Postgres-backed job queue with a poll-based async worker — no external
broker, matching the app's single-scheduler + redis-lock architecture. Provides
named queues (email/sms/whatsapp/report/export/ai/default) with priority
ordering, retry → dead-letter, scheduled `run_at`, cancellation, job history,
worker heartbeats and monitoring.

Handlers reuse existing services (report generation, exports, notifications) and
a Mock AI seam; existing synchronous sends are untouched — the queue is the new
opt-in async path. `process_once` runs one job and is the unit the worker loop
and the tests both drive, so behaviour is deterministic without a live worker.
"""
from __future__ import annotations
import csv
import io
import time
import uuid
from datetime import datetime, timezone, timedelta
from fastapi import HTTPException, status
from sqlalchemy import select, func, and_
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User
from app.models.queue import QueueJob, QueueWorker

QUEUES = ("email", "sms", "whatsapp", "report", "export", "ai", "default")
JOB_STATUSES = ("queued", "running", "succeeded", "failed", "dead_letter", "cancelled")
# default queue for each job_type
QUEUE_FOR_TYPE = {
    "send_email": "email", "send_sms": "sms", "send_whatsapp": "whatsapp",
    "generate_report": "report", "generate_export": "export", "ai_task": "ai",
    "notify": "default", "noop": "default", "always_fail": "default",
}
JOB_TYPES = tuple(QUEUE_FOR_TYPE.keys())
WORKER_STALE_SECONDS = 90


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _aware(dt: datetime | None) -> datetime | None:
    if dt is None:
        return None
    return dt if dt.tzinfo is not None else dt.replace(tzinfo=timezone.utc)


class QueueService:
    def __init__(self, db: AsyncSession):
        self.db = db

    # ---------- permissions ----------
    def _require_manager(self, actor: User):
        if actor.role not in ("SuperAdmin", "OrgAdmin", "Manager"):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN,
                                detail="Only managers and admins can manage the queue.")

    @staticmethod
    def catalog() -> dict:
        return {"queues": list(QUEUES), "job_types": list(JOB_TYPES),
                "statuses": list(JOB_STATUSES), "queue_for_type": QUEUE_FOR_TYPE}

    # ================= enqueue =================
    async def enqueue(self, *, organization_id: uuid.UUID, job_type: str, payload: dict | None = None,
                      queue: str | None = None, priority: int = 5, max_attempts: int = 3,
                      run_at: datetime | None = None, created_by: uuid.UUID | None = None) -> QueueJob:
        if job_type not in QUEUE_FOR_TYPE:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST,
                                detail=f"Unknown job_type. Allowed: {sorted(JOB_TYPES)}")
        q = queue or QUEUE_FOR_TYPE.get(job_type, "default")
        if q not in QUEUES:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Unknown queue. Allowed: {list(QUEUES)}")
        job = QueueJob(organization_id=organization_id, queue=q, job_type=job_type,
                       priority=int(priority), payload=payload, status="queued", attempts=0,
                       max_attempts=max(1, min(int(max_attempts), 10)), run_at=run_at or _now(),
                       created_by=created_by)
        self.db.add(job)
        await self.db.flush()
        return job

    async def enqueue_api(self, actor: User, data: dict) -> dict:
        self._require_manager(actor)
        run_at = data.get("run_at")
        job = await self.enqueue(organization_id=actor.organization_id, job_type=data["job_type"],
                                 payload=data.get("payload"), queue=data.get("queue"),
                                 priority=int(data.get("priority", 5)), max_attempts=int(data.get("max_attempts", 3)),
                                 run_at=run_at, created_by=actor.id)
        return self._job_dict(job)

    # ================= claim + execute (worker step) =================
    async def claim_next(self, *, organization_id: uuid.UUID | None = None,
                         queues: list[str] | None = None, worker_id: uuid.UUID | None = None) -> QueueJob | None:
        """Claim the highest-priority due job (priority DESC, then earliest run_at)."""
        q = select(QueueJob).filter(QueueJob.status == "queued", QueueJob.is_deleted == False,
                                    QueueJob.run_at <= _now())
        if organization_id is not None:
            q = q.filter(QueueJob.organization_id == organization_id)
        if queues:
            q = q.filter(QueueJob.queue.in_(queues))
        q = q.order_by(QueueJob.priority.desc(), QueueJob.run_at.asc(), QueueJob.created_at.asc()).limit(1)
        job = (await self.db.execute(q)).scalars().first()
        if not job:
            return None
        job.status = "running"
        job.started_at = _now()
        job.worker_id = worker_id
        job.attempts = (job.attempts or 0) + 1
        self.db.add(job)
        await self.db.flush()
        return job

    async def process_once(self, *, organization_id: uuid.UUID | None = None,
                           queues: list[str] | None = None, worker_id: uuid.UUID | None = None) -> dict | None:
        """Claim + run one job. Returns the job dict, or None if nothing was due."""
        job = await self.claim_next(organization_id=organization_id, queues=queues, worker_id=worker_id)
        if job is None:
            return None
        await self._execute(job)
        return self._job_dict(job)

    async def _execute(self, job: QueueJob):
        started = time.monotonic()
        try:
            result = await self._run_handler(job)
            job.status = "succeeded"
            job.result = result if isinstance(result, dict) else {"result": result}
            job.error = None
        except Exception as e:
            err = f"{type(e).__name__}: {e}"
            if job.attempts >= job.max_attempts:
                job.status = "dead_letter"   # retry exhausted → DLQ
            else:
                job.status = "queued"        # back on the queue for another attempt
                job.run_at = _now() + timedelta(seconds=min(60, 2 ** job.attempts))  # simple backoff
                job.started_at = None
                job.worker_id = None
            job.error = err
        job.finished_at = _now() if job.status in ("succeeded", "dead_letter") else None
        job.duration_ms = int((time.monotonic() - started) * 1000)
        self.db.add(job)
        await self.db.flush()

    # ---------- handlers (reuse existing services) ----------
    async def _run_handler(self, job: QueueJob) -> dict:
        p = job.payload or {}
        jt = job.job_type
        if jt == "noop":
            return {"ok": True}
        if jt == "always_fail":
            raise RuntimeError(p.get("reason") or "intentional failure")
        if jt == "ai_task":
            # Routed through the AI Platform gateway (provider abstraction,
            # fallback chain, cost tracking, usage logs). With no provider
            # configured the gateway's Mock provider answers — same dev/CI
            # behavior as the original mock seam.
            from app.services.ai_gateway_service import AIGatewayService
            return await AIGatewayService(self.db).run_automation_task(job.organization_id, p)
        if jt == "generate_report":
            from app.services.automation_service import AutomationService
            data = await AutomationService(self.db)._generate_report(
                job.organization_id, p.get("report_type") or "lead_summary")
            return {"summary": data["summary"], "data": data["data"]}
        if jt == "generate_export":
            return await self._export(job.organization_id, p.get("entity") or "leads")
        if jt == "notify":
            from app.services.notification_service import NotificationService
            uid = p.get("user_id") or (str(job.created_by) if job.created_by else None)
            if not uid:
                raise ValueError("notify requires user_id")
            await NotificationService(self.db).create_notification(
                organization_id=job.organization_id, user_id=uuid.UUID(str(uid)), category="system",
                title=p.get("title") or "Queued notification", body=p.get("body") or "",
                link_url=p.get("link_url"))
            return {"notified": str(uid)}
        if jt in ("send_email", "send_sms", "send_whatsapp"):
            return await self._send_message(job, jt, p)
        raise ValueError(f"No handler for job_type {jt}")

    async def _send_message(self, job: QueueJob, jt: str, p: dict) -> dict:
        """Route to the existing messaging module services. Best-effort — provider
        errors raise, which drives the retry/DLQ machinery."""
        actor = await self.db.get(User, job.created_by) if job.created_by else None
        if actor is None:
            raise ValueError("send job requires a valid created_by user")
        if jt == "send_sms":
            from app.services.sms_service import SmsService
            await SmsService(self.db).send(actor, {"body": p.get("body"), "to_number": p.get("to_number"),
                                                   "lead_id": p.get("lead_id")}, _skip_cap=True)
            return {"channel": "sms", "to": p.get("to_number")}
        if jt == "send_whatsapp":
            from app.services.whatsapp_service import WhatsAppService
            if p.get("message_id") and p.get("action") != "download_media":
                res = await WhatsAppService(self.db).process_outbox_send(
                    uuid.UUID(p["message_id"]),
                    language=p.get("language", "en_US"),
                    variables=p.get("variables")
                )
                return {"channel": "whatsapp", "message_id": p["message_id"], "result": res}
            elif p.get("action") == "download_media" and p.get("message_id"):
                await WhatsAppService(self.db).download_and_persist_media(
                    uuid.UUID(p["message_id"]),
                    p["media_id"],
                    p["file_name"]
                )
                return {"channel": "whatsapp", "action": "download_media", "media_id": p["media_id"]}
            else:
                await WhatsAppService(self.db).send_text(actor, {"body": p.get("body"),
                                                                 "to_number": p.get("to_number"), "lead_id": p.get("lead_id")})
                return {"channel": "whatsapp", "to": p.get("to_number")}
        from app.services.email_service_module import EmailModuleService
        await EmailModuleService(self.db).send(actor, {"subject": p.get("subject") or "Message",
                                                       "body": p.get("body"), "to": p.get("to"), "lead_id": p.get("lead_id")})
        return {"channel": "email", "to": p.get("to")}

    async def _export(self, org_id: uuid.UUID, entity: str) -> dict:
        """Produce a small CSV export as the job result (Export Queue)."""
        buf = io.StringIO()
        w = csv.writer(buf)
        if entity == "leads":
            from app.models.lead import Lead
            rows = (await self.db.execute(select(Lead.title, Lead.status, Lead.value).filter(
                Lead.organization_id == org_id, Lead.is_deleted == False).limit(1000))).all()
            w.writerow(["title", "status", "value"])
            for t, s, v in rows:
                w.writerow([t, s, float(v) if v is not None else ""])
        else:
            w.writerow(["entity"]); w.writerow([entity])
        content = buf.getvalue()
        return {"entity": entity, "rows": content.count("\n") - 1, "bytes": len(content), "csv": content[:5000]}

    # ================= job management =================
    async def _get(self, actor: User, job_id: uuid.UUID) -> QueueJob:
        job = (await self.db.execute(select(QueueJob).filter(
            QueueJob.id == job_id, QueueJob.organization_id == actor.organization_id,
            QueueJob.is_deleted == False))).scalars().first()
        if not job:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job not found.")
        return job

    async def get(self, actor: User, job_id: uuid.UUID) -> dict:
        return self._job_dict(await self._get(actor, job_id))

    async def list_jobs(self, actor: User, queue: str | None = None, status_filter: str | None = None,
                        scheduled: bool | None = None, limit: int = 50) -> list[dict]:
        q = select(QueueJob).filter(QueueJob.organization_id == actor.organization_id, QueueJob.is_deleted == False)
        if queue:
            q = q.filter(QueueJob.queue == queue)
        if status_filter:
            q = q.filter(QueueJob.status == status_filter)
        if scheduled:
            q = q.filter(QueueJob.status == "queued", QueueJob.run_at > _now())
        q = q.order_by(QueueJob.created_at.desc()).limit(min(limit, 200))
        return [self._job_dict(j) for j in (await self.db.execute(q)).scalars().all()]

    async def cancel(self, actor: User, job_id: uuid.UUID) -> dict:
        self._require_manager(actor)
        job = await self._get(actor, job_id)
        if job.status not in ("queued",):
            raise HTTPException(status_code=status.HTTP_409_CONFLICT,
                                detail=f"Only queued jobs can be cancelled (status={job.status}).")
        job.status = "cancelled"
        job.finished_at = _now()
        self.db.add(job)
        await self.db.flush()
        return self._job_dict(job)

    async def retry(self, actor: User, job_id: uuid.UUID) -> dict:
        """Requeue a failed / dead-lettered / cancelled job for another run."""
        self._require_manager(actor)
        job = await self._get(actor, job_id)
        if job.status not in ("failed", "dead_letter", "cancelled"):
            raise HTTPException(status_code=status.HTTP_409_CONFLICT,
                                detail=f"Only failed/dead-letter/cancelled jobs can be retried (status={job.status}).")
        job.status = "queued"
        job.run_at = _now()
        job.attempts = 0
        job.error = None
        job.started_at = job.finished_at = job.worker_id = None
        self.db.add(job)
        await self.db.flush()
        return self._job_dict(job)

    async def dead_letter(self, actor: User, limit: int = 50) -> list[dict]:
        rows = (await self.db.execute(select(QueueJob).filter(
            QueueJob.organization_id == actor.organization_id, QueueJob.status == "dead_letter",
            QueueJob.is_deleted == False).order_by(QueueJob.finished_at.desc()).limit(min(limit, 200)))).scalars().all()
        return [self._job_dict(j) for j in rows]

    async def purge(self, actor: User, status_filter: str) -> dict:
        """Soft-delete completed/cancelled jobs to keep history tidy."""
        self._require_manager(actor)
        if status_filter not in ("succeeded", "cancelled", "dead_letter"):
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Can only purge succeeded/cancelled/dead_letter.")
        rows = (await self.db.execute(select(QueueJob).filter(
            QueueJob.organization_id == actor.organization_id, QueueJob.status == status_filter,
            QueueJob.is_deleted == False))).scalars().all()
        for j in rows:
            j.is_deleted = True
            self.db.add(j)
        await self.db.flush()
        return {"purged": len(rows)}

    # ================= workers =================
    async def register_worker(self, name: str, queues: list[str] | None = None) -> QueueWorker:
        w = (await self.db.execute(select(QueueWorker).filter(QueueWorker.name == name))).scalars().first()
        if w is None:
            w = QueueWorker(name=name, status="idle", queues=",".join(queues) if queues else None)
            self.db.add(w)
        w.last_heartbeat = _now()
        w.status = "idle"
        self.db.add(w)
        await self.db.flush()
        return w

    async def heartbeat(self, worker_id: uuid.UUID, *, status_val: str = "idle",
                        current_job_id: uuid.UUID | None = None, processed_delta: int = 0):
        w = await self.db.get(QueueWorker, worker_id)
        if w is None:
            return
        w.last_heartbeat = _now()
        w.status = status_val
        w.current_job_id = current_job_id
        if processed_delta:
            w.jobs_processed = (w.jobs_processed or 0) + processed_delta
        self.db.add(w)
        await self.db.flush()

    async def list_workers(self, actor: User) -> list[dict]:
        rows = (await self.db.execute(select(QueueWorker).filter(
            QueueWorker.is_deleted == False).order_by(QueueWorker.last_heartbeat.desc().nullslast()))).scalars().all()
        out = []
        for w in rows:
            hb = _aware(w.last_heartbeat)
            stale = hb is None or (_now() - hb).total_seconds() > WORKER_STALE_SECONDS
            out.append({"id": str(w.id), "name": w.name,
                        "status": "offline" if stale else w.status,
                        "last_heartbeat": w.last_heartbeat.isoformat() if w.last_heartbeat else None,
                        "jobs_processed": w.jobs_processed,
                        "current_job_id": str(w.current_job_id) if w.current_job_id else None,
                        "queues": w.queues})
        return out

    # ================= monitoring / reports =================
    async def dashboard(self, actor: User) -> dict:
        org = actor.organization_id
        counts = dict((s, c) for s, c in (await self.db.execute(
            select(QueueJob.status, func.count(QueueJob.id)).filter(
                QueueJob.organization_id == org, QueueJob.is_deleted == False
            ).group_by(QueueJob.status))).all())
        pending = counts.get("queued", 0)
        workers = await self.list_workers(actor)
        active_workers = sum(1 for w in workers if w["status"] != "offline")
        recent = await self.list_jobs(actor, limit=5)
        return {"pending": pending, "running": counts.get("running", 0),
                "succeeded": counts.get("succeeded", 0), "failed": counts.get("failed", 0),
                "dead_letter": counts.get("dead_letter", 0), "workers": active_workers,
                "recent": recent}

    async def report(self, actor: User) -> dict:
        org = actor.organization_id
        by_queue = {}
        rows = (await self.db.execute(select(QueueJob.queue, QueueJob.status, func.count(QueueJob.id)).filter(
            QueueJob.organization_id == org, QueueJob.is_deleted == False
        ).group_by(QueueJob.queue, QueueJob.status))).all()
        for q, s, c in rows:
            by_queue.setdefault(q, {"queued": 0, "running": 0, "succeeded": 0, "failed": 0, "dead_letter": 0, "cancelled": 0})
            by_queue[q][s] = c
        total = (await self.db.execute(select(func.count(QueueJob.id)).filter(
            QueueJob.organization_id == org, QueueJob.is_deleted == False))).scalar() or 0
        done = (await self.db.execute(select(func.count(QueueJob.id)).filter(
            QueueJob.organization_id == org, QueueJob.is_deleted == False,
            QueueJob.status.in_(["succeeded", "failed", "dead_letter"])))).scalar() or 0
        succeeded = (await self.db.execute(select(func.count(QueueJob.id)).filter(
            QueueJob.organization_id == org, QueueJob.is_deleted == False,
            QueueJob.status == "succeeded"))).scalar() or 0
        avg_ms = (await self.db.execute(select(func.avg(QueueJob.duration_ms)).filter(
            QueueJob.organization_id == org, QueueJob.is_deleted == False,
            QueueJob.duration_ms.isnot(None)))).scalar()
        return {"total": total, "by_queue": by_queue,
                "success_rate": round(succeeded / done * 100, 1) if done else 100.0,
                "avg_duration_ms": round(float(avg_ms), 1) if avg_ms else 0.0}

    # ---------- serialize ----------
    def _job_dict(self, j: QueueJob) -> dict:
        return {"id": str(j.id), "queue": j.queue, "job_type": j.job_type, "priority": j.priority,
                "status": j.status, "attempts": j.attempts, "max_attempts": j.max_attempts,
                "payload": j.payload, "result": j.result, "error": j.error,
                "run_at": j.run_at.isoformat() if j.run_at else None,
                "started_at": j.started_at.isoformat() if j.started_at else None,
                "finished_at": j.finished_at.isoformat() if j.finished_at else None,
                "duration_ms": j.duration_ms,
                "created_at": j.created_at.isoformat() if j.created_at else None}
