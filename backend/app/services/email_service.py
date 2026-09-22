import logging
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from pathlib import Path
from jinja2 import Environment, FileSystemLoader

from app.core.config import settings

logger = logging.getLogger(__name__)

# RFC 2606 / RFC 6761 reserved TLDs and second-level domains — never deliverable.
# Sends to these are dropped at the choke point below so bogus test/seed
# recipients don't generate an endless stream of MAILER-DAEMON bounces.
_RESERVED_TLDS = (".test", ".example", ".invalid", ".localhost")
_RESERVED_DOMAINS = ("example.com", "example.net", "example.org")


def _is_suppressed_recipient(to_email: str) -> bool:
    """True when `to_email` must never receive real mail: a malformed address, an
    RFC-reserved test domain/TLD, or an operator-configured suppressed domain
    (settings.EMAIL_SUPPRESSED_DOMAINS). Matching is case-insensitive and covers
    subdomains. Prevents provisioned test/seed accounts (e.g. bob@boblogistics.com)
    from being re-emailed on a loop by recurring crons and bouncing every run."""
    domain = (to_email or "").rsplit("@", 1)[-1].strip().lower().rstrip(".")
    if not domain or "." not in domain:
        return True  # malformed / no usable domain — nothing to deliver to
    if domain.endswith(_RESERVED_TLDS):
        return True

    def _matches(blocked: str) -> bool:
        blocked = blocked.strip().lower()
        return bool(blocked) and (domain == blocked or domain.endswith("." + blocked))

    if any(_matches(b) for b in _RESERVED_DOMAINS):
        return True
    if any(_matches(b) for b in settings.EMAIL_SUPPRESSED_DOMAINS):
        return True
    return False


TEMPLATE_DIR = Path(__file__).resolve().parent.parent / "templates" / "emails"

# Ensure directory exists
TEMPLATE_DIR.mkdir(parents=True, exist_ok=True)

jinja_env = Environment(loader=FileSystemLoader(str(TEMPLATE_DIR)))

def send_email(to_email: str, subject: str, template_name: str, context: dict) -> None:
    """
    Renders an HTML email template and sends it via SMTP if configured,
    otherwise logs the email content to stdout/logger.
    """
    # Root guard: NEVER send real mail from the test environment, even when
    # SMTP_HOST is populated. The test suite creates users with placeholder
    # addresses (new_manager@crm.com, new_employee@org-a.com, …) and does not
    # mock this function; if a scheduled/CI test run inherits a real SMTP_HOST it
    # would fire welcome emails to those dead addresses and generate nightly
    # MAILER-DAEMON bounces. Gating on ENVIRONMENT (conftest sets it to "testing")
    # is correct because the mock-mode check below only triggers on an *empty*
    # SMTP_HOST, which is not guaranteed under test.
    if settings.is_testing:
        logger.info("[EMAIL MOCK - testing env] Suppressed real send to %r (subject=%r)", to_email, subject)
        return

    # Guard: never attempt delivery to reserved/test or operator-suppressed
    # domains. Test/seed accounts (e.g. bob@boblogistics.com) provisioned against
    # a live DB would otherwise be re-emailed by recurring crons and bounce on
    # every run. Drop silently (log, don't raise) so callers are unaffected.
    if _is_suppressed_recipient(to_email):
        logger.warning(
            "[EMAIL SUPPRESSED] Skipping non-deliverable recipient %r (subject=%r)",
            to_email, subject,
        )
        return

    try:
        # Load and render template
        template = jinja_env.get_template(template_name)
        html_content = template.render(context)
    except Exception as e:
        logger.error(f"Failed to render email template {template_name}: {e}")
        # Simple fallback text context
        html_content = f"<h3>Email notification</h3><p>{subject}</p><p>{context}</p>"

    # Check if SMTP is configured
    if not settings.SMTP_HOST:
        logger.info(f"[EMAIL MOCK] Sending email to {to_email}")
        logger.info(f"Subject: {subject}")
        logger.info(f"Body (HTML): {html_content[:500]}...")
        return

    # Determine effective from address (SMTP_FROM_* overrides EMAILS_FROM_*)
    from_email = getattr(settings, 'SMTP_FROM_EMAIL', None) or settings.EMAILS_FROM_EMAIL
    from_name = getattr(settings, 'SMTP_FROM_NAME', None) or settings.EMAILS_FROM_NAME

    # Construct MIME message
    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = f"{from_name} <{from_email}>"
    msg["To"] = to_email

    # Attach HTML body
    msg.attach(MIMEText(html_content, "html"))

    try:

        # Determine SSL mode:
        # - Port 465: SMTP_SSL=True or SMTP_USE_TLS=True → use SMTP_SSL class
        # - Port 587: use SMTP + STARTTLS
        use_ssl = settings.SMTP_SSL or getattr(settings, 'SMTP_USE_TLS', False)
        port = settings.SMTP_PORT
        if use_ssl and port == 587:
            port = 465  # Auto-correct if SSL flag set with wrong port

        if use_ssl:
            server = smtplib.SMTP_SSL(settings.SMTP_HOST, port)
        else:
            server = smtplib.SMTP(settings.SMTP_HOST, port)
            if settings.SMTP_TLS:
                server.starttls()

        if settings.SMTP_USER and settings.SMTP_PASSWORD:
            server.login(settings.SMTP_USER, settings.SMTP_PASSWORD)
        server.sendmail(from_email, [to_email], msg.as_string())
        server.quit()
        logger.info(f"Successfully sent email to {to_email}")
    except Exception as e:
        logger.error(f"Failed to send email to {to_email} via SMTP: {e}")
        # Don't raise so the main flow isn't blocked by email failure
