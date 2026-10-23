/**
 * Shared WhatsApp / telephony real-time WebSocket.
 *
 * The backend ConnectionManager keys exactly one socket per user, so multiple
 * independent `new WebSocket(...)` connections for the same user would evict one
 * another. This singleton owns ONE connection and multiplexes every incoming
 * message to all subscribers, letting both the WhatsApp page and the global
 * inbound notifier listen at the same time.
 */
type RealtimeHandler = (data: any) => void;

let socket: WebSocket | null = null;
let currentUserId: string | null = null;
let reconnectTimer: ReturnType<typeof setTimeout> | null = null;
let intentionalClose = false;
const handlers = new Set<RealtimeHandler>();

let reconnectAttempts = 0;
let pingInterval: ReturnType<typeof setInterval> | null = null;

function buildUrl(userId: string): string {
  const proto = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
  return `${proto}//${window.location.host}/api/v1/telephony/ws/${userId}`;
}

function stopPing(): void {
  if (pingInterval) {
    clearInterval(pingInterval);
    pingInterval = null;
  }
}

function startPing(): void {
  stopPing();
  pingInterval = setInterval(() => {
    if (socket && socket.readyState === WebSocket.OPEN) {
      try {
        socket.send(JSON.stringify({ type: 'ping' }));
      } catch {}
    }
  }, 25000);
}

function scheduleReconnect(): void {
  if (intentionalClose || !currentUserId) return;
  if (reconnectTimer) clearTimeout(reconnectTimer);

  // Exponential backoff with jitter: 1s, 2s, 4s, 8s, max 15s
  const delay = Math.min(1000 * Math.pow(1.5, reconnectAttempts), 15000) + Math.random() * 500;
  reconnectAttempts++;
  reconnectTimer = setTimeout(() => {
    open();
  }, delay);
}

function open(): void {
  if (!currentUserId) return;
  if (
    socket &&
    (socket.readyState === WebSocket.OPEN || socket.readyState === WebSocket.CONNECTING)
  ) {
    return;
  }
  intentionalClose = false;
  socket = new WebSocket(buildUrl(currentUserId));

  socket.onopen = () => {
    reconnectAttempts = 0;
    startPing();
  };

  socket.onmessage = (event) => {
    let data: any;
    try {
      data = JSON.parse(event.data);
    } catch {
      return;
    }
    // Ignore ping/pong acknowledgments
    if (data?.type === 'pong' || data?.type === 'ping') return;

    handlers.forEach((handler) => {
      try {
        handler(data);
      } catch (err) {
        console.error('whatsappRealtime handler error', err);
      }
    });
  };

  socket.onclose = () => {
    stopPing();
    socket = null;
    scheduleReconnect();
  };

  socket.onerror = () => {
    try {
      socket?.close();
    } catch {
      /* ignore */
    }
  };
}

// Window & Network level active recovery listeners
if (typeof window !== 'undefined') {
  window.addEventListener('online', () => {
    if (!intentionalClose && currentUserId) {
      reconnectAttempts = 0;
      open();
    }
  });

  document.addEventListener('visibilitychange', () => {
    if (document.visibilityState === 'visible' && !intentionalClose && currentUserId) {
      if (!socket || socket.readyState !== WebSocket.OPEN) {
        reconnectAttempts = 0;
        open();
      }
    }
  });
}

export const whatsappRealtime = {
  /** Ensure the shared connection is open for this user (idempotent). */
  connect(userId: string): void {
    if (currentUserId && currentUserId !== userId) {
      this.reset();
    }
    currentUserId = userId;
    open();
  },

  /** Register a handler; returns an unsubscribe function. */
  subscribe(handler: RealtimeHandler): () => void {
    handlers.add(handler);
    open(); // keep the connection alive while there are listeners
    return () => {
      handlers.delete(handler);
    };
  },

  /** Tear down the connection (e.g. on logout or user switch). */
  reset(): void {
    intentionalClose = true;
    if (reconnectTimer) {
      clearTimeout(reconnectTimer);
      reconnectTimer = null;
    }
    currentUserId = null;
    if (socket) {
      try {
        socket.close();
      } catch {
        /* ignore */
      }
      socket = null;
    }
  },
};
