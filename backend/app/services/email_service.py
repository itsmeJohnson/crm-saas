import logging
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from pathlib import Path
from jinja2 import Environment, FileSystemLoader

from app.core.config import settings

logger = logging.getLogger(__name__)

TEMPLATE_DIR = Path(__file__).resolve().parent.parent / "templates" / "emails"

# Ensure directory exists
TEMPLATE_DIR.mkdir(parents=True, exist_ok=True)

jinja_env = Environment(loader=FileSystemLoader(str(TEMPLATE_DIR)))

def send_email(to_email: str, subject: str, template_name: str, context: dict) -> None:
    """
    Renders an HTML email template and sends it via SMTP if configured,
    otherwise logs the email content to stdout/logger.
    """
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
