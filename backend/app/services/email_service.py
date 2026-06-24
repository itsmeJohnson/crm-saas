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

    # Construct MIME message
    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = f"{settings.EMAILS_FROM_NAME} <{settings.EMAILS_FROM_EMAIL}>"
    msg["To"] = to_email
    
    # Attach HTML body
    msg.attach(MIMEText(html_content, "html"))

    try:
        # Connect and send
        if settings.SMTP_SSL:
            server = smtplib.SMTP_SSL(settings.SMTP_HOST, settings.SMTP_PORT)
        else:
            server = smtplib.SMTP(settings.SMTP_HOST, settings.SMTP_PORT)
            if settings.SMTP_TLS:
                server.starttls()
        if settings.SMTP_USER and settings.SMTP_PASSWORD:
            server.login(settings.SMTP_USER, settings.SMTP_PASSWORD)
        server.sendmail(settings.EMAILS_FROM_EMAIL, [to_email], msg.as_string())
        server.quit()
        logger.info(f"Successfully sent email to {to_email}")
    except Exception as e:
        logger.error(f"Failed to send email to {to_email} via SMTP: {e}")
        # Don't raise so the main flow isn't blocked by email failure
