"""Web Push provider seam.

Mirrors the other messaging modules: a Mock sender that logs in dev/CI, and a
real Web Push sender (VAPID) used when server keys are configured. Delivery is
best-effort — a failure never blocks the notification write.
"""
import logging

logger = logging.getLogger("app.push")


class MockPushSender:
    name = "mock"

    def send(self, *, subscription: dict, title: str, body: str, url: str | None = None) -> bool:
        logger.info("[PUSH MOCK] endpoint=%s title=%r", (subscription or {}).get("endpoint", "")[:60], title[:60])
        return True


class WebPushSender:
    """Real Web Push via the `pywebpush` library + VAPID keys (server-side).
    Not wired by default — instantiated only when VAPID keys are configured."""
    name = "webpush"

    def __init__(self, vapid_private_key: str, vapid_claims: dict):
        self.vapid_private_key = vapid_private_key
        self.vapid_claims = vapid_claims

    def send(self, *, subscription: dict, title: str, body: str, url: str | None = None) -> bool:
        try:
            from pywebpush import webpush  # optional dependency
            import json
            webpush(
                subscription_info={
                    "endpoint": subscription.get("endpoint"),
                    "keys": {"p256dh": subscription.get("p256dh"), "auth": subscription.get("auth")},
                },
                data=json.dumps({"title": title, "body": body, "url": url}),
                vapid_private_key=self.vapid_private_key,
                vapid_claims=dict(self.vapid_claims),
            )
            return True
        except Exception as e:
            logger.warning("Web push failed: %s", e)
            return False


def get_push_sender():
    """Resolve a push sender. Uses the Mock sender unless VAPID keys are set."""
    try:
        from app.core.config import settings
        priv = getattr(settings, "VAPID_PRIVATE_KEY", None)
        sub = getattr(settings, "VAPID_SUBJECT", None)
        if priv and sub:
            return WebPushSender(priv, {"sub": sub})
    except Exception:
        pass
    return MockPushSender()


# ---- Native mobile push (FCM / APNS) ----

class MockNativePushSender:
    """Simulates native push in dev/CI; logs and reports success."""
    name = "mock-native"

    def send(self, *, token: str, platform: str, title: str, body: str, url: str | None = None) -> bool:
        logger.info("[PUSH NATIVE MOCK] platform=%s token=%s title=%r", platform, (token or "")[:12], title[:60])
        return True


class FcmPushSender:
    """Real Firebase Cloud Messaging HTTP v1 sender. Handles both Android (FCM)
    and iOS (APNS-via-FCM) tokens with one credential. Config-gated — only used
    when FCM_CREDENTIALS_JSON is set; best-effort like every other channel."""
    name = "fcm"

    def __init__(self, credentials_json: str):
        self.credentials_json = credentials_json

    def send(self, *, token: str, platform: str, title: str, body: str, url: str | None = None) -> bool:
        try:
            # firebase-admin is an optional dependency, mirroring pywebpush above.
            import firebase_admin
            from firebase_admin import credentials, messaging
            if not firebase_admin._apps:
                import json
                cred = credentials.Certificate(json.loads(self.credentials_json))
                firebase_admin.initialize_app(cred)
            messaging.send(messaging.Message(
                token=token,
                notification=messaging.Notification(title=title, body=body),
                data={"url": url or ""},
            ))
            return True
        except Exception as e:
            logger.warning("FCM push failed (%s): %s", platform, e)
            return False


def get_native_push_sender():
    """Resolve a native push sender. Mock unless FCM credentials are configured."""
    try:
        from app.core.config import settings
        creds = getattr(settings, "FCM_CREDENTIALS_JSON", None)
        if creds:
            return FcmPushSender(creds)
    except Exception:
        pass
    return MockNativePushSender()
