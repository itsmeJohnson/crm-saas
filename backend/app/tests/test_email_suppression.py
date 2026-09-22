"""Regression tests for the outbound-mail suppression guard.

Background: test/seed fixtures (e.g. bob@boblogistics.com) provisioned against a
live DB were being re-emailed by the subscription/trial crons on every run,
producing a stream of MAILER-DAEMON bounces (Hostinger relays through
MailChannels). `send_email` now drops non-deliverable recipients at the choke
point. These tests pin that behaviour so it isn't regressed away.
"""
import pytest

from app.core.config import settings
from app.services import email_service
from app.services.email_service import _is_suppressed_recipient, send_email


@pytest.mark.parametrize("addr", [
    "bob@boblogistics.com",          # the original culprit (configured list)
    "BOB@BobLogistics.COM",          # case-insensitive
    "alice@sub.boblogistics.com",    # subdomain of a suppressed domain
    "x@example.com",                 # RFC 2606 reserved domain
    "x@example.org",
    "x@example.net",
    "x@thing.test",                  # RFC reserved TLD
    "x@host.localhost",
    "x@a.invalid",
    "malformed-no-at",               # no domain at all
    "noatdomain@",                   # empty domain
])
def test_suppressed_recipients(addr):
    assert _is_suppressed_recipient(addr) is True


@pytest.mark.parametrize("addr", [
    "real@johnsonsoftwares.com",
    "admin@acme.co.in",
    "owner@some-real-company.com",
])
def test_deliverable_recipients(addr):
    assert _is_suppressed_recipient(addr) is False


def test_send_email_short_circuits_for_suppressed(monkeypatch):
    """send_email must not touch SMTP for a suppressed recipient, even when
    SMTP is configured."""
    # Configure SMTP so the guard is the only thing that can stop delivery.
    monkeypatch.setattr(settings, "SMTP_HOST", "smtp.example-relay.test", raising=False)

    called = {"smtp": False}

    class _Boom:
        def __init__(self, *a, **k):
            called["smtp"] = True
            raise AssertionError("SMTP must not be constructed for a suppressed recipient")

    monkeypatch.setattr(email_service.smtplib, "SMTP", _Boom, raising=True)
    monkeypatch.setattr(email_service.smtplib, "SMTP_SSL", _Boom, raising=True)

    # Should return quietly without raising and without opening SMTP.
    send_email(
        to_email="bob@boblogistics.com",
        subject="Your Free Trial is Ending Soon",
        template_name="trial_ending_soon.html",
        context={},
    )
    assert called["smtp"] is False


def test_configured_domain_is_respected(monkeypatch):
    monkeypatch.setattr(settings, "EMAIL_SUPPRESSED_DOMAINS", ["blocked.example-corp.com"], raising=False)
    assert _is_suppressed_recipient("someone@blocked.example-corp.com") is True
    assert _is_suppressed_recipient("someone@allowed-corp.com") is False
