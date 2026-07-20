"""Pluggable email transport layer.

Mirrors the other messaging modules: a Mock transport that simulates SMTP send
and IMAP fetch in dev/CI without credentials, plus real SMTP (smtplib) and IMAP
(imaplib) transports used when an org configures a mailbox. OAuth (Gmail /
Microsoft 365) is represented in EmailSettings; when access tokens are present a
real transport would authenticate via XOAUTH2 — the seam lives here.

A send never raises for a business failure: it returns an EmailSendResult with
status='failed' so the caller can persist the error instead of 500-ing.
"""
import email as email_lib
import imaplib
import logging
import smtplib
import uuid
from dataclasses import dataclass, field
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.utils import parseaddr

logger = logging.getLogger("app.email")


@dataclass
class EmailSendResult:
    status: str                       # sent|failed
    message_id: str | None = None
    error: str | None = None


@dataclass
class FetchedEmail:
    from_addr: str
    to_addr: str
    subject: str
    body: str
    message_id: str | None = None
    in_reply_to: str | None = None


def _make_message_id(domain: str = "crm.local") -> str:
    return f"<{uuid.uuid4()}@{domain}>"


class MockEmailTransport:
    """Simulates SMTP/IMAP: logs sends, returns a synthetic Message-ID; fetches nothing."""
    name = "mock"

    def send(self, *, from_addr: str, to_addrs: list[str], cc_addrs: list[str], subject: str,
             html_body: str, message_id: str | None = None, in_reply_to: str | None = None,
             attachments: list | None = None) -> EmailSendResult:
        if not to_addrs:
            return EmailSendResult(status="failed", error="No recipient")
        mid = message_id or _make_message_id()
        logger.info("[EMAIL MOCK] to=%s subject=%r id=%s", to_addrs, subject[:60], mid)
        return EmailSendResult(status="sent", message_id=mid)

    def fetch(self, *, limit: int = 25) -> list[FetchedEmail]:
        return []


class SmtpEmailTransport:
    """Real SMTP send via smtplib. Per-org host/port/creds from EmailSettings."""
    name = "smtp"

    def __init__(self, host: str, port: int, username: str | None, password: str | None, use_tls: bool = True):
        self.host = host
        self.port = port or 587
        self.username = username
        self.password = password
        self.use_tls = use_tls

    def send(self, *, from_addr: str, to_addrs: list[str], cc_addrs: list[str], subject: str,
             html_body: str, message_id: str | None = None, in_reply_to: str | None = None,
             attachments: list | None = None) -> EmailSendResult:
        if not self.host:
            return EmailSendResult(status="failed", error="SMTP host not configured")
        if not to_addrs:
            return EmailSendResult(status="failed", error="No recipient")
        mid = message_id or _make_message_id((parseaddr(from_addr)[1] or "crm.local").split("@")[-1])
        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"] = from_addr
        msg["To"] = ", ".join(to_addrs)
        if cc_addrs:
            msg["Cc"] = ", ".join(cc_addrs)
        msg["Message-ID"] = mid
        if in_reply_to:
            msg["In-Reply-To"] = in_reply_to
            msg["References"] = in_reply_to
        msg.attach(MIMEText(html_body, "html"))
        # File attachments: dicts with base64 content ({filename, content_b64, mime})
        # are attached as real MIME parts; legacy URL/metadata attachments are ignored
        # here (they only annotate the Activity record).
        for att in (attachments or []):
            if not isinstance(att, dict) or not att.get("content_b64"):
                continue
            try:
                from email.mime.application import MIMEApplication
                import base64 as _b64
                part = MIMEApplication(_b64.b64decode(att["content_b64"]))
                part.add_header("Content-Disposition", "attachment",
                                filename=str(att.get("filename") or "attachment"))
                msg.attach(part)
            except Exception as e:
                logger.warning("Skipping bad email attachment %r: %s", att.get("filename"), e)
        recipients = list(to_addrs) + list(cc_addrs or [])
        try:
            if self.use_tls and self.port == 465:
                server = smtplib.SMTP_SSL(self.host, self.port, timeout=15)
            else:
                server = smtplib.SMTP(self.host, self.port, timeout=15)
                if self.use_tls:
                    server.starttls()
            if self.username and self.password:
                server.login(self.username, self.password)
            server.sendmail(parseaddr(from_addr)[1], recipients, msg.as_string())
            server.quit()
            return EmailSendResult(status="sent", message_id=mid)
        except Exception as e:
            logger.error("SMTP send failed: %s", e)
            return EmailSendResult(status="failed", error=str(e)[:500])


class ImapEmailFetcher:
    """Real IMAP fetch via imaplib — pulls UNSEEN messages from INBOX."""
    name = "imap"

    def __init__(self, host: str, port: int, username: str, password: str, use_ssl: bool = True):
        self.host = host
        self.port = port or (993 if use_ssl else 143)
        self.username = username
        self.password = password
        self.use_ssl = use_ssl

    def fetch(self, *, limit: int = 25) -> list[FetchedEmail]:
        if not (self.host and self.username):
            return []
        out: list[FetchedEmail] = []
        try:
            conn = imaplib.IMAP4_SSL(self.host, self.port) if self.use_ssl else imaplib.IMAP4(self.host, self.port)
            conn.login(self.username, self.password)
            conn.select("INBOX")
            typ, data = conn.search(None, "UNSEEN")
            ids = (data[0].split() if data and data[0] else [])[:limit]
            for num in ids:
                typ, msg_data = conn.fetch(num, "(RFC822)")
                if not msg_data or not msg_data[0]:
                    continue
                msg = email_lib.message_from_bytes(msg_data[0][1])
                out.append(FetchedEmail(
                    from_addr=parseaddr(msg.get("From", ""))[1],
                    to_addr=parseaddr(msg.get("To", ""))[1],
                    subject=msg.get("Subject", ""),
                    body=_extract_body(msg),
                    message_id=msg.get("Message-ID"),
                    in_reply_to=msg.get("In-Reply-To"),
                ))
            conn.close()
            conn.logout()
        except Exception as e:
            logger.error("IMAP fetch failed: %s", e)
        return out


def _extract_body(msg) -> str:
    if msg.is_multipart():
        for part in msg.walk():
            if part.get_content_type() == "text/html":
                try:
                    return part.get_payload(decode=True).decode(errors="replace")
                except Exception:
                    continue
        for part in msg.walk():
            if part.get_content_type() == "text/plain":
                try:
                    return part.get_payload(decode=True).decode(errors="replace")
                except Exception:
                    continue
        return ""
    try:
        return msg.get_payload(decode=True).decode(errors="replace")
    except Exception:
        return str(msg.get_payload())


def get_transport(settings):
    """Resolve a send transport from EmailSettings. Falls back to Mock when the row
    is missing/inactive or SMTP isn't configured (OAuth without a real client too)."""
    if not settings or not settings.is_active:
        return MockEmailTransport()
    if (settings.provider or "mock").lower() == "smtp" and settings.smtp_host:
        return SmtpEmailTransport(settings.smtp_host, settings.smtp_port, settings.smtp_username,
                                  settings.smtp_password, settings.smtp_use_tls)
    return MockEmailTransport()


def get_fetcher(settings):
    """Resolve an inbound fetcher from EmailSettings. Mock unless IMAP is configured."""
    if not settings or not settings.is_active:
        return MockEmailTransport()
    if settings.imap_host and settings.imap_username:
        return ImapEmailFetcher(settings.imap_host, settings.imap_port, settings.imap_username,
                                settings.imap_password, settings.imap_use_ssl)
    return MockEmailTransport()
