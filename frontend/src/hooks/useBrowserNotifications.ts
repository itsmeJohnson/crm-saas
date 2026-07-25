import { useEffect, useRef } from 'react';
import { useNavigate } from 'react-router-dom';
import { notificationApi } from '../services/notificationApi';

const POLL_MS = 60_000; // aligns with the backend's 60s reminder-dispatch loop

/**
 * Surfaces new in-app notifications (reminders, follow-ups, escalations) as
 * desktop/browser notifications while the CRM tab is open — the delivery
 * surface the Notification Center couldn't provide on its own. It reuses the
 * existing unread feed; it does NOT create a second notification system.
 *
 * On the first poll it records what's already unread WITHOUT notifying, so a
 * user who logs in to a stack of reminders isn't blasted with a dozen popups —
 * only notifications that arrive AFTER the session started are shown.
 */
export function useBrowserNotifications(enabled: boolean): void {
  const navigate = useNavigate();
  const seen = useRef<Set<string>>(new Set());
  const primed = useRef(false);

  useEffect(() => {
    if (!enabled) return;
    if (typeof window === 'undefined' || !('Notification' in window)) return;

    // Ask once, best-effort. If the user denies, we simply never pop anything.
    if (Notification.permission === 'default') {
      Notification.requestPermission().catch(() => { /* ignore */ });
    }

    let cancelled = false;

    const tick = async () => {
      try {
        const items = await notificationApi.list({ unread_only: true, limit: 15 });
        if (cancelled) return;

        if (!primed.current) {
          items.forEach((n) => seen.current.add(n.id));
          primed.current = true;
          return;
        }
        if (Notification.permission !== 'granted') return;

        // Newest last so popups arrive in chronological order.
        for (const n of [...items].reverse()) {
          if (seen.current.has(n.id)) continue;
          seen.current.add(n.id);
          const notif = new Notification(n.title || 'Reminder', {
            body: n.body || '',
            tag: n.id, // collapses duplicates for the same notification
          });
          notif.onclick = () => {
            window.focus();
            if (n.link_url) navigate(n.link_url);
            notif.close();
          };
        }
      } catch {
        /* transient poll failure — try again next tick */
      }
    };

    tick();
    const timer = window.setInterval(tick, POLL_MS);
    return () => {
      cancelled = true;
      window.clearInterval(timer);
    };
  }, [enabled, navigate]);
}
