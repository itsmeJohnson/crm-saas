#!/usr/bin/env python3
"""Demo helper: fire a simulated inbound WhatsApp message into the LOCAL CRM so
the live incoming-notification popup appears on screen during a demo.

Usage:
    python3 demo_whatsapp_ping.py                 # random broking-client message
    python3 demo_whatsapp_ping.py "your message"  # custom message
    python3 demo_whatsapp_ping.py "msg" 919876543210   # custom message + number

Env overrides: CRM_BASE, CRM_EMAIL, CRM_PASS.
Stdlib only — no pip installs, no curl needed.
"""
import json
import os
import random
import sys
import urllib.request

BASE = os.environ.get("CRM_BASE", "http://localhost:8000")
EMAIL = os.environ.get("CRM_EMAIL", "admin@business-demo.com")
PASS = os.environ.get("CRM_PASS", "Demo@12345")

MESSAGES = [
    "Namaste, I want to open a demat account. What documents are needed?",
    "Is my KYC verified yet? I submitted my PAN yesterday.",
    "Hello, what are your brokerage charges for intraday trading?",
    "Please call me regarding F&O segment activation.",
    "I have transferred the amount — when will my trading account be active?",
    "Can you share the account opening link on WhatsApp?",
]


def _post(path, data, token=None):
    req = urllib.request.Request(BASE + path, data=json.dumps(data).encode(), method="POST")
    req.add_header("Content-Type", "application/json")
    if token:
        req.add_header("Authorization", "Bearer " + token)
    return json.loads(urllib.request.urlopen(req, timeout=8).read())


def _get(path, token):
    req = urllib.request.Request(BASE + path)
    req.add_header("Authorization", "Bearer " + token)
    return json.loads(urllib.request.urlopen(req, timeout=8).read())


def main():
    body = sys.argv[1] if len(sys.argv) > 1 else random.choice(MESSAGES)
    number = sys.argv[2] if len(sys.argv) > 2 else "919812345678"
    try:
        token = _post("/api/v1/auth/login", {"email": EMAIL, "password": PASS})["access_token"]
        webhook_token = _get("/api/v1/whatsapp/settings", token).get("webhook_token")
        if not webhook_token:
            print("✗ No WhatsApp webhook_token on this org — check WhatsApp settings.")
            return
        _post(
            "/api/v1/whatsapp/webhook/inbound",
            {"token": webhook_token, "from_number": number, "body": body},
        )
        print(f'📲 Sent demo WhatsApp from +{number}:\n   "{body}"')
        print("   → Watch the CRM: a popup should appear bottom-right on any page.")
    except Exception as exc:  # noqa: BLE001
        print(f"✗ Could not send (is the local CRM running at {BASE}?): {exc}")


if __name__ == "__main__":
    main()
