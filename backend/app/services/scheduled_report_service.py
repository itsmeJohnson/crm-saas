"""Scheduled Reports.

First-class scheduled delivery of user-built Report Builder reports: daily /
weekly / monthly / quarterly / yearly cycles, CSV / Excel / PDF artifacts, and
delivery over in-app notifications, email (real attachments via the org's email
transport) and WhatsApp (summary text via the org's provider). Every attempt is
recorded in report_delivery_logs (History); failed cycles are re-attempted on
the next daily tick up to max_retries, then the owner is notified. Reuses
ReportBuilderService.run_definition for data, the Email module's settings +
transports, the WhatsApp module's settings + providers, openpyxl and the
WeasyPrint/dummy-PDF seam. The Automation Engine's fixed-type scheduled_reports
and ReportDefinition's inline notification schedule are untouched.
"""
from __future__ import annotations
import base64
import calendar as _cal
import csv
import html as _html
import io
import uuid
from datetime import datetime, timedelta, timezone
from fastapi import HTTPException, status
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User
from app.models.report_builder import ReportDefinition
from app.models.scheduled_report import ReportSchedule, ReportDeliveryLog
from app.services.report_builder_service import ReportBuilderService
from app.services.notification_service import NotificationService

FREQUENCIES = ("daily", "weekly", "monthly", "quarterly", "yearly")
FORMATS = ("csv", "xlsx", "pdf")
CHANNELS = ("notification", "email", "whatsapp")
MAX_DELIVERY_ROWS = 2000  # rows included in generated artifacts


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _advance(frequency: str, base: datetime | None = None) -> datetime:
    """Next run after `base` for a frequency (calendar-safe month arithmetic)."""
    base = base or _now()
    if frequency == "daily":
        return base + timedelta(days=1)
    if frequency == "weekly":
        return base + timedelta(days=7)
    months = {"monthly": 1, "quarterly": 3, "yearly": 12}[frequency]
    y, m = base.year, base.month + months
    y += (m - 1) // 12
    m = (m - 1) % 12 + 1
    day = min(base.day, _cal.monthrange(y, m)[1])
    return base.replace(year=y, month=m, day=day)


class ScheduledReportService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.rb = ReportBuilderService(db)
        self.notifier = NotificationService(db)

    # ---------- meta ----------
    def meta(self) -> dict:
        return {"frequencies": list(FREQUENCIES), "formats": list(FORMATS), "channels": list(CHANNELS)}

    # ---------- CRUD ----------
    def _validate(self, data: dict):
        if data.get("frequency") and data["frequency"] not in FREQUENCIES:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"frequency must be one of {list(FREQUENCIES)}")
        for f in (data.get("formats") or []):
            if f not in FORMATS:
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"formats must be a subset of {list(FORMATS)}")
        for c in (data.get("channels") or []):
            if c not in CHANNELS:
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"channels must be a subset of {list(CHANNELS)}")

    async def _report(self, org_id: uuid.UUID, report_id: uuid.UUID) -> ReportDefinition:
        r = (await self.db.execute(select(ReportDefinition).filter(
            ReportDefinition.id == report_id, ReportDefinition.organization_id == org_id,
            ReportDefinition.is_deleted == False))).scalars().first()
        if not r:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Report not found")
        return r

    async def create(self, actor: User, data: dict) -> dict:
        self.rb._require_manager(actor)
        self._validate(data)
        report = await self._report(actor.organization_id, data["report_id"])
        s = ReportSchedule(
            organization_id=actor.organization_id, report_id=report.id, name=data["name"],
            frequency=data.get("frequency") or "weekly",
            formats=data.get("formats") or ["csv"], channels=data.get("channels") or ["notification"],
            recipients=data.get("recipients") or [], extra_emails=data.get("extra_emails"),
            is_active=bool(data.get("is_active", True)), max_retries=int(data.get("max_retries", 2)),
            next_run_at=_advance(data.get("frequency") or "weekly"), created_by=actor.id)
        self.db.add(s)
        await self.db.flush()
        await self.db.refresh(s)
        return await self._serialize(s)

    async def _get(self, actor: User, schedule_id: uuid.UUID) -> ReportSchedule:
        s = (await self.db.execute(select(ReportSchedule).filter(
            ReportSchedule.id == schedule_id, ReportSchedule.organization_id == actor.organization_id,
            ReportSchedule.is_deleted == False))).scalars().first()
        if not s:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Schedule not found")
        return s

    async def list_schedules(self, actor: User) -> list[dict]:
        self.rb._require_manager(actor)
        rows = (await self.db.execute(select(ReportSchedule).filter(
            ReportSchedule.organization_id == actor.organization_id, ReportSchedule.is_deleted == False)
            .order_by(ReportSchedule.created_at.desc()))).scalars().all()
        return [await self._serialize(s) for s in rows]

    async def update(self, actor: User, schedule_id: uuid.UUID, data: dict) -> dict:
        self.rb._require_manager(actor)
        self._validate(data)
        s = await self._get(actor, schedule_id)
        for f in ("name", "formats", "channels", "recipients", "extra_emails", "is_active", "max_retries"):
            if f in data and data[f] is not None:
                setattr(s, f, data[f])
        if data.get("frequency") and data["frequency"] != s.frequency:
            s.frequency = data["frequency"]
            s.next_run_at = _advance(s.frequency)
        self.db.add(s)
        await self.db.flush()
        return await self._serialize(s)

    async def delete(self, actor: User, schedule_id: uuid.UUID) -> None:
        self.rb._require_manager(actor)
        s = await self._get(actor, schedule_id)
        s.is_deleted = True
        self.db.add(s)
        await self.db.flush()

    # ---------- artifact generation ----------
    async def _run_report(self, report: ReportDefinition) -> tuple[dict, User | None]:
        owner = (await self.db.execute(select(User).filter(User.id == report.created_by))).scalars().first()
        if not owner:
            raise RuntimeError("Report owner not found")
        res = await self.rb.run_definition(owner, self.rb._serialize(report), limit=MAX_DELIVERY_ROWS)
        return res, owner

    @staticmethod
    def _csv_bytes(res: dict) -> bytes:
        buf = io.StringIO()
        w = csv.writer(buf)
        keys = [c["key"] for c in res["columns"]]
        w.writerow([c["label"] for c in res["columns"]])
        for r in res["rows"]:
            w.writerow([r.get(k) for k in keys])
        return buf.getvalue().encode("utf-8")

    @staticmethod
    def _xlsx_bytes(res: dict, title: str) -> bytes:
        import openpyxl
        wb = openpyxl.Workbook()
        ws = wb.active
        ws.title = (title or "Report")[:31]
        keys = [c["key"] for c in res["columns"]]
        ws.append([c["label"] for c in res["columns"]])
        for r in res["rows"]:
            ws.append([r.get(k) if isinstance(r.get(k), (int, float)) else
                       (str(r.get(k)) if r.get(k) is not None else "") for k in keys])
        out = io.BytesIO()
        wb.save(out)
        return out.getvalue()

    @staticmethod
    def _pdf_bytes(res: dict, title: str) -> bytes:
        from app.services.invoice_pdf import WEASYPRINT_AVAILABLE, DUMMY_PDF_BYTES
        if not WEASYPRINT_AVAILABLE:
            return DUMMY_PDF_BYTES
        import weasyprint
        keys = [c["key"] for c in res["columns"]]
        head = "".join(f"<th>{_html.escape(str(c['label']))}</th>" for c in res["columns"])
        body = "".join(
            "<tr>" + "".join(f"<td>{_html.escape('' if r.get(k) is None else str(r.get(k)))}</td>" for k in keys) + "</tr>"
            for r in res["rows"][:500])
        html_doc = f"""<!DOCTYPE html><html><head><meta charset="utf-8"><style>
            @page {{ size: A4 landscape; margin: 14mm; }}
            body {{ font-family: Arial, sans-serif; color: #1e293b; }}
            h1 {{ font-size: 16px; }} p {{ font-size: 10px; color: #64748b; }}
            table {{ width: 100%; border-collapse: collapse; font-size: 9px; }}
            th, td {{ border: 1px solid #cbd5e1; padding: 3px 5px; text-align: left; }}
            th {{ background: #f1f5f9; }}
            </style></head><body>
            <h1>{_html.escape(title)}</h1>
            <p>Generated {_now().strftime('%Y-%m-%d %H:%M UTC')} · {res.get('total', 0)} rows</p>
            <table><thead><tr>{head}</tr></thead><tbody>{body}</tbody></table>
            </body></html>"""
        return weasyprint.HTML(string=html_doc).write_pdf()

    def _artifacts(self, res: dict, formats: list, name: str) -> list[dict]:
        mimes = {"csv": "text/csv", "xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                 "pdf": "application/pdf"}
        out = []
        for fmt in formats or ["csv"]:
            if fmt == "csv":
                content = self._csv_bytes(res)
            elif fmt == "xlsx":
                content = self._xlsx_bytes(res, name)
            else:
                content = self._pdf_bytes(res, name)
            out.append({"filename": f"{name}.{fmt}", "mime": mimes[fmt],
                        "content_b64": base64.b64encode(content).decode(), "size": len(content)})
        return out

    # ---------- delivery ----------
    async def _resolve_users(self, org_id: uuid.UUID, s: ReportSchedule) -> list[User]:
        ids = []
        for x in (s.recipients or []):
            try:
                ids.append(uuid.UUID(str(x)))
            except ValueError:
                pass
        if not ids:
            ids = [s.created_by]
        rows = (await self.db.execute(select(User).filter(
            User.id.in_(ids), User.organization_id == org_id, User.is_deleted == False))).scalars().all()
        return list(rows)

    async def _deliver_email(self, owner: User, s: ReportSchedule, users: list[User],
                             artifacts: list[dict], summary: str) -> dict:
        from app.services.email_service_module import EmailModuleService
        from app.services.email_providers import get_transport
        addrs = [u.email for u in users if u.email] + list(s.extra_emails or [])
        if not addrs:
            return {"status": "failed", "error": "No recipient email addresses", "sent": 0}
        try:
            settings_row = await EmailModuleService(self.db).get_settings(owner, create=True)
            from_email = (settings_row.from_email if settings_row else None) or owner.email
            transport = get_transport(settings_row)
            result = transport.send(from_addr=from_email, to_addrs=addrs, cc_addrs=[],
                                    subject=f"Scheduled report: {s.name}",
                                    html_body=f"<p>{_html.escape(summary)}</p><p>The report is attached.</p>",
                                    attachments=artifacts)
            if result.status == "failed":
                return {"status": "failed", "error": result.error, "sent": 0}
            return {"status": "sent", "sent": len(addrs), "message_id": result.message_id}
        except Exception as e:
            return {"status": "failed", "error": str(e)[:300], "sent": 0}

    async def _deliver_whatsapp(self, owner: User, s: ReportSchedule, users: list[User], summary: str) -> dict:
        """Internal staff notification over the org's WhatsApp provider (direct
        provider send — not a customer conversation, so no 24h-window rules)."""
        from app.services.whatsapp_service import WhatsAppService
        from app.services.whatsapp_providers import get_provider
        phones = [u.phone for u in users if u.phone]
        if not phones:
            return {"status": "failed", "error": "No recipient phone numbers", "sent": 0}
        try:
            settings_row = await WhatsAppService(self.db).get_settings(owner, create=True)
            provider = get_provider(settings_row)
            sent, last_err = 0, None
            for p in phones:
                try:
                    r = await provider.send_text(to_number=p, body=summary)
                    if r.status != "failed":
                        sent += 1
                    else:
                        last_err = r.error
                except Exception as e:
                    last_err = str(e)[:200]
            if sent == 0:
                return {"status": "failed", "error": last_err or "All sends failed", "sent": 0}
            return {"status": "sent", "sent": sent, "error": last_err}
        except Exception as e:
            return {"status": "failed", "error": str(e)[:300], "sent": 0}

    async def _deliver_notification(self, s: ReportSchedule, users: list[User], summary: str) -> dict:
        sent = 0
        for u in users:
            try:
                await self.notifier.create_notification(
                    organization_id=s.organization_id, user_id=u.id, category="report",
                    title=f"Scheduled report: {s.name}", body=summary,
                    link_url="/scheduled-reports", action_metadata={"schedule_id": str(s.id)})
                sent += 1
            except Exception:
                pass
        return {"status": "sent" if sent else "failed", "sent": sent}

    async def deliver(self, s: ReportSchedule, *, triggered_by: str = "schedule", attempt: int = 1) -> ReportDeliveryLog:
        """Generate artifacts and deliver over every configured channel. Records a
        ReportDeliveryLog and returns it (never raises)."""
        log = ReportDeliveryLog(organization_id=s.organization_id, schedule_id=s.id, report_id=s.report_id,
                                status="pending", attempt=attempt, triggered_by=triggered_by,
                                frequency=s.frequency, formats=s.formats, channels=s.channels,
                                started_at=_now())
        detail: dict = {}
        try:
            report = await self._report(s.organization_id, s.report_id)
            res, owner = await self._run_report(report)
            users = await self._resolve_users(s.organization_id, s)
            artifacts = self._artifacts(res, s.formats, s.name.replace("/", "-"))
            summary = f'"{s.name}" is ready: {res.get("total", 0)} rows ({s.frequency}).'
            log.rows_count = int(res.get("total", 0))
            log.recipient_count = len(users) + len(s.extra_emails or [])
            detail["artifacts"] = [{"filename": a["filename"], "size": a["size"]} for a in artifacts]

            channels = s.channels or ["notification"]
            for ch in channels:
                if ch == "email":
                    detail["email"] = await self._deliver_email(owner, s, users, artifacts, summary)
                elif ch == "whatsapp":
                    detail["whatsapp"] = await self._deliver_whatsapp(owner, s, users, summary)
                elif ch == "notification":
                    detail["notification"] = await self._deliver_notification(s, users, summary)
            outcomes = [detail.get(ch, {}).get("status") for ch in channels]
            if all(o == "sent" for o in outcomes):
                log.status = "success"
            elif any(o == "sent" for o in outcomes):
                log.status = "partial"
            else:
                log.status = "failed"
                log.error = "; ".join(filter(None, (detail.get(ch, {}).get("error") for ch in channels)))[:500]
        except Exception as e:
            log.status = "failed"
            log.error = str(e)[:500]
        log.detail = detail
        log.finished_at = _now()
        self.db.add(log)
        await self.db.flush()
        return log

    async def run_now(self, actor: User, schedule_id: uuid.UUID) -> dict:
        self.rb._require_manager(actor)
        s = await self._get(actor, schedule_id)
        log = await self.deliver(s, triggered_by="manual")
        s.last_run_at = _now()
        s.last_status = log.status
        s.run_count = (s.run_count or 0) + 1
        self.db.add(s)
        await self.db.flush()
        return self._log_row(log)

    async def retry_delivery(self, actor: User, delivery_id: uuid.UUID) -> dict:
        self.rb._require_manager(actor)
        old = (await self.db.execute(select(ReportDeliveryLog).filter(
            ReportDeliveryLog.id == delivery_id, ReportDeliveryLog.organization_id == actor.organization_id,
            ReportDeliveryLog.is_deleted == False))).scalars().first()
        if not old:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Delivery not found")
        s = await self._get(actor, old.schedule_id)
        log = await self.deliver(s, triggered_by="retry", attempt=old.attempt + 1)
        s.last_status = log.status
        self.db.add(s)
        await self.db.flush()
        return self._log_row(log)

    # ---------- cron scan (with automatic retries) ----------
    async def scan(self, org_id: uuid.UUID) -> dict:
        """Daily tick: deliver due schedules. A failed cycle keeps the schedule
        due, so the next tick retries (attempt = fail_streak + 1) until
        max_retries is exhausted — then the owner is notified and the schedule
        advances to its next cycle."""
        due = (await self.db.execute(select(ReportSchedule).filter(
            ReportSchedule.organization_id == org_id, ReportSchedule.is_deleted == False,
            ReportSchedule.is_active == True, ReportSchedule.next_run_at.isnot(None),
            ReportSchedule.next_run_at <= _now()))).scalars().all()
        delivered = failed = 0
        for s in due:
            attempt = (s.fail_streak or 0) + 1
            log = await self.deliver(s, triggered_by="schedule" if attempt == 1 else "retry", attempt=attempt)
            s.last_run_at = _now()
            s.last_status = log.status
            s.run_count = (s.run_count or 0) + 1
            if log.status == "failed" and attempt <= (s.max_retries or 0):
                s.fail_streak = attempt  # stay due — next daily tick retries
                failed += 1
            else:
                if log.status == "failed":
                    failed += 1
                    try:
                        await self.notifier.create_notification(
                            organization_id=org_id, user_id=s.created_by, category="report",
                            title=f"Scheduled report failed: {s.name}",
                            body=f"Delivery failed after {attempt} attempt(s): {log.error or 'unknown error'}",
                            link_url="/scheduled-reports", priority="high",
                            action_metadata={"schedule_id": str(s.id)})
                    except Exception:
                        pass
                else:
                    delivered += 1
                s.fail_streak = 0
                s.next_run_at = _advance(s.frequency)
            self.db.add(s)
        await self.db.flush()
        return {"due": len(due), "delivered": delivered, "failed": failed}

    # ---------- history & dashboard ----------
    async def history(self, actor: User, schedule_id: uuid.UUID | None = None, limit: int = 100) -> list[dict]:
        self.rb._require_manager(actor)
        q = select(ReportDeliveryLog).filter(ReportDeliveryLog.organization_id == actor.organization_id,
                                             ReportDeliveryLog.is_deleted == False)
        if schedule_id:
            q = q.filter(ReportDeliveryLog.schedule_id == schedule_id)
        rows = (await self.db.execute(q.order_by(ReportDeliveryLog.created_at.desc())
                                      .limit(min(limit, 300)))).scalars().all()
        names = {s.id: s.name for s in (await self.db.execute(select(ReportSchedule).filter(
            ReportSchedule.organization_id == actor.organization_id))).scalars().all()}
        return [self._log_row(l, names.get(l.schedule_id)) for l in rows]

    async def dashboard(self, actor: User) -> dict:
        self.rb._require_manager(actor)
        schedules = (await self.db.execute(select(ReportSchedule).filter(
            ReportSchedule.organization_id == actor.organization_id,
            ReportSchedule.is_deleted == False))).scalars().all()
        active = [s for s in schedules if s.is_active]
        by_status = {}
        total_logs = (await self.db.execute(select(func.count(ReportDeliveryLog.id)).filter(
            ReportDeliveryLog.organization_id == actor.organization_id,
            ReportDeliveryLog.is_deleted == False))).scalar() or 0
        for st in ("success", "partial", "failed"):
            by_status[st] = (await self.db.execute(select(func.count(ReportDeliveryLog.id)).filter(
                ReportDeliveryLog.organization_id == actor.organization_id,
                ReportDeliveryLog.is_deleted == False, ReportDeliveryLog.status == st))).scalar() or 0
        success_rate = round(by_status["success"] * 100 / total_logs, 1) if total_logs else 0.0
        upcoming = sorted([s for s in active if s.next_run_at], key=lambda s: s.next_run_at)[:5]
        return {"schedules": len(schedules), "active": len(active), "deliveries": total_logs,
                "by_status": by_status, "success_rate": success_rate,
                "upcoming": [await self._serialize(s) for s in upcoming]}

    # ---------- serialize ----------
    async def _serialize(self, s: ReportSchedule) -> dict:
        report = (await self.db.execute(select(ReportDefinition).filter(
            ReportDefinition.id == s.report_id))).scalars().first()
        return {"id": str(s.id), "report_id": str(s.report_id), "report_name": report.name if report else "—",
                "name": s.name, "frequency": s.frequency, "formats": s.formats or [],
                "channels": s.channels or [], "recipients": s.recipients or [],
                "extra_emails": s.extra_emails or [], "is_active": s.is_active,
                "max_retries": s.max_retries, "fail_streak": s.fail_streak,
                "next_run_at": s.next_run_at.isoformat() if s.next_run_at else None,
                "last_run_at": s.last_run_at.isoformat() if s.last_run_at else None,
                "last_status": s.last_status, "run_count": s.run_count,
                "created_at": s.created_at.isoformat() if s.created_at else None}

    @staticmethod
    def _log_row(l: ReportDeliveryLog, schedule_name: str | None = None) -> dict:
        return {"id": str(l.id), "schedule_id": str(l.schedule_id), "schedule_name": schedule_name,
                "status": l.status, "attempt": l.attempt, "triggered_by": l.triggered_by,
                "frequency": l.frequency, "formats": l.formats or [], "channels": l.channels or [],
                "recipient_count": l.recipient_count, "rows_count": l.rows_count,
                "detail": l.detail, "error": l.error,
                "started_at": l.started_at.isoformat() if l.started_at else None,
                "finished_at": l.finished_at.isoformat() if l.finished_at else None}
