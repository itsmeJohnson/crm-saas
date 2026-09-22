import React, { useEffect, useRef, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { MessageCircle, X } from 'lucide-react';
import { useAuthStore } from '../../store/authStore';
import { whatsappRealtime } from '../../services/whatsappRealtime';

interface Popup {
  key: string;
  conversationId: string;
  name: string;
  body: string;
}

const AUTO_DISMISS_MS = 9000;

/**
 * Global WhatsApp inbound notifier. Mounted once in the app layout, it listens
 * on the shared realtime socket and, whenever a customer message arrives on ANY
 * page, raises a desktop notification and an in-app popup that opens the chat.
 *
 * It keys off the broadcast the backend sends on every inbound message
 * (`type: "whatsapp_message"`, `message.direction === "INBOUND"`).
 */
export const WhatsAppLiveNotifier: React.FC = () => {
  const user = useAuthStore((s) => s.user);
  const navigate = useNavigate();
  const [popups, setPopups] = useState<Popup[]>([]);
  const seen = useRef<Set<string>>(new Set());

  useEffect(() => {
    if (!user) return;

    // Ask for desktop-notification permission once (best-effort).
    if (typeof window !== 'undefined' && 'Notification' in window && Notification.permission === 'default') {
      Notification.requestPermission().catch(() => { /* ignore */ });
    }

    whatsappRealtime.connect(user.id);

    const open = (conversationId: string) => {
      navigate(`/whatsapp?conversationId=${conversationId}`);
    };

    const unsubscribe = whatsappRealtime.subscribe((data) => {
      if (!data || data.type !== 'whatsapp_message') return;
      const message = data.message || {};
      if (message.direction !== 'INBOUND') return;

      // De-dupe: the same message id can arrive if the socket reconnects.
      const msgId = message.id;
      if (msgId) {
        if (seen.current.has(msgId)) return;
        seen.current.add(msgId);
      }

      const conversationId: string = data.conversation_id;
      const name: string = data.display_name || data.from_number || 'WhatsApp contact';
      const body: string = message.body || (message.media_type ? '📎 Attachment' : 'New message');

      // Desktop notification.
      try {
        if ('Notification' in window && Notification.permission === 'granted') {
          const n = new Notification(`WhatsApp · ${name}`, {
            body,
            tag: `wa-${conversationId}`,
          });
          n.onclick = () => {
            window.focus();
            open(conversationId);
            n.close();
          };
        }
      } catch {
        /* notifications unsupported / blocked — the in-app popup still shows */
      }

      // In-app popup (works even when desktop notifications are denied).
      const key = `${conversationId}-${msgId || Date.now()}`;
      setPopups((prev) => [{ key, conversationId, name, body }, ...prev].slice(0, 4));
      window.setTimeout(() => {
        setPopups((prev) => prev.filter((p) => p.key !== key));
      }, AUTO_DISMISS_MS);
    });

    return () => {
      unsubscribe();
    };
  }, [user, navigate]);

  if (popups.length === 0) return null;

  return (
    <div
      style={{
        position: 'fixed',
        right: 'max(16px, env(safe-area-inset-right, 0px))',
        bottom: 'max(16px, env(safe-area-inset-bottom, 0px))',
        zIndex: 9999,
        display: 'flex',
        flexDirection: 'column',
        gap: 10,
        maxWidth: 'calc(100vw - 32px)',
      }}
    >
      {popups.map((p) => (
        <div
          key={p.key}
          role="button"
          tabIndex={0}
          onClick={() => {
            navigate(`/whatsapp?conversationId=${p.conversationId}`);
            setPopups((prev) => prev.filter((x) => x.key !== p.key));
          }}
          onKeyDown={(e) => {
            if (e.key === 'Enter' || e.key === ' ') {
              navigate(`/whatsapp?conversationId=${p.conversationId}`);
              setPopups((prev) => prev.filter((x) => x.key !== p.key));
            }
          }}
          style={{
            width: 320,
            cursor: 'pointer',
            background: 'var(--bg-surface, #ffffff)',
            color: 'var(--text-primary, #111827)',
            border: '1px solid var(--border-color, #e5e7eb)',
            borderLeft: '4px solid #25D366',
            borderRadius: 12,
            boxShadow: '0 12px 32px -14px rgba(0,0,0,.4)',
            padding: '12px 14px',
          }}
        >
          <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 4 }}>
            <MessageCircle style={{ width: 16, height: 16, color: '#25D366', flexShrink: 0 }} />
            <strong style={{ fontSize: 13, flex: 1, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
              {p.name}
            </strong>
            <X
              style={{ width: 14, height: 14, opacity: 0.6 }}
              onClick={(e) => {
                e.stopPropagation();
                setPopups((prev) => prev.filter((x) => x.key !== p.key));
              }}
            />
          </div>
          <div
            style={{
              fontSize: 13,
              color: 'var(--text-secondary, #4b5563)',
              overflow: 'hidden',
              textOverflow: 'ellipsis',
              whiteSpace: 'nowrap',
            }}
          >
            {p.body}
          </div>
          <div style={{ fontSize: 11, color: '#25D366', marginTop: 6, fontWeight: 600 }}>
            Click to open chat →
          </div>
        </div>
      ))}
    </div>
  );
};
