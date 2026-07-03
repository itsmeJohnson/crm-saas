import React, { useEffect, useRef, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { Bell, CheckCheck, Loader2 } from 'lucide-react';
import { useNotificationStore } from '../../store/notificationStore';

const POLL_INTERVAL_MS = 30_000;

export const NotificationBell: React.FC = () => {
  const [open, setOpen] = useState(false);
  const containerRef = useRef<HTMLDivElement>(null);
  const navigate = useNavigate();

  const { notifications, unreadCount, isLoading, fetchNotifications, fetchUnreadCount, markRead, markAllRead } =
    useNotificationStore();

  useEffect(() => {
    fetchUnreadCount();
    const interval = setInterval(fetchUnreadCount, POLL_INTERVAL_MS);
    return () => clearInterval(interval);
  }, [fetchUnreadCount]);

  useEffect(() => {
    if (open) fetchNotifications();
  }, [open, fetchNotifications]);

  useEffect(() => {
    const handleClickOutside = (e: MouseEvent) => {
      if (containerRef.current && !containerRef.current.contains(e.target as Node)) {
        setOpen(false);
      }
    };
    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, []);

  const handleNotificationClick = async (id: string, isRead: boolean, linkUrl: string | null) => {
    if (!isRead) await markRead(id);
    setOpen(false);
    if (linkUrl) navigate(linkUrl);
  };

  const formatTime = (iso: string) => {
    const date = new Date(iso);
    const diffMs = Date.now() - date.getTime();
    const diffMins = Math.floor(diffMs / 60000);
    if (diffMins < 1) return 'just now';
    if (diffMins < 60) return `${diffMins}m ago`;
    const diffHours = Math.floor(diffMins / 60);
    if (diffHours < 24) return `${diffHours}h ago`;
    return date.toLocaleDateString();
  };

  return (
    <div ref={containerRef} className="relative">
      <button
        onClick={() => setOpen((o) => !o)}
        className="relative p-2 rounded-lg text-slate-400 hover:text-slate-200 hover:bg-slate-800/60 transition-colors cursor-pointer"
        title="Notifications"
      >
        <Bell className="w-4.5 h-4.5" />
        {unreadCount > 0 && (
          <span className="absolute -top-0.5 -right-0.5 min-w-[16px] h-4 px-1 flex items-center justify-center rounded-full bg-red-500 text-white text-[9px] font-bold leading-none">
            {unreadCount > 99 ? '99+' : unreadCount}
          </span>
        )}
      </button>

      {open && (
        <div className="absolute right-0 mt-2 w-80 max-h-[28rem] flex flex-col glass-panel border border-slate-800 rounded-2xl shadow-2xl z-50 bg-slate-950 overflow-hidden">
          <div className="flex items-center justify-between px-4 py-3 border-b border-slate-800/60">
            <span className="text-sm font-bold text-slate-100">Notifications</span>
            {unreadCount > 0 && (
              <button
                onClick={() => markAllRead()}
                className="flex items-center gap-1 text-[11px] font-semibold text-brand-400 hover:text-brand-300 cursor-pointer"
              >
                <CheckCheck className="w-3.5 h-3.5" />
                Mark all read
              </button>
            )}
          </div>

          <div className="flex-1 overflow-y-auto">
            {isLoading ? (
              <div className="flex items-center justify-center py-10">
                <Loader2 className="w-5 h-5 animate-spin text-slate-500" />
              </div>
            ) : notifications.length === 0 ? (
              <div className="py-10 text-center text-xs text-slate-500">You're all caught up.</div>
            ) : (
              notifications.map((n) => (
                <button
                  key={n.id}
                  onClick={() => handleNotificationClick(n.id, n.is_read, n.link_url)}
                  className={`w-full text-left px-4 py-3 border-b border-slate-900/60 hover:bg-slate-900/60 transition-colors cursor-pointer ${
                    !n.is_read ? 'bg-brand-500/5' : ''
                  }`}
                >
                  <div className="flex items-start gap-2">
                    {!n.is_read && <span className="mt-1.5 w-1.5 h-1.5 rounded-full bg-brand-400 shrink-0" />}
                    <div className={`min-w-0 flex-1 ${n.is_read ? 'pl-3.5' : ''}`}>
                      <p className="text-xs font-semibold text-slate-200 truncate">{n.title}</p>
                      <p className="text-[11px] text-slate-400 mt-0.5 line-clamp-2">{n.body}</p>
                      <p className="text-[10px] text-slate-600 mt-1">{formatTime(n.created_at)}</p>
                    </div>
                  </div>
                </button>
              ))
            )}
          </div>

          <button
            onClick={() => { setOpen(false); navigate('/notifications'); }}
            className="w-full text-center px-4 py-2.5 border-t border-slate-800/60 text-[11px] font-semibold text-brand-400 hover:text-brand-300 hover:bg-slate-900/60 cursor-pointer"
          >
            View all notifications
          </button>
        </div>
      )}
    </div>
  );
};
