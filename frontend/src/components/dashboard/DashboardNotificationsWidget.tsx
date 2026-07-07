import React, { useEffect } from 'react';
import { Link } from 'react-router-dom';
import { Bell } from 'lucide-react';
import { useNotificationStore } from '../../store/notificationStore';

export const DashboardNotificationsWidget: React.FC = () => {
  const { notifications, isLoading, fetchNotifications, markRead } = useNotificationStore();

  useEffect(() => {
    fetchNotifications();
  }, [fetchNotifications]);

  const recent = notifications.slice(0, 5);

  return (
    <div className="glass-panel p-6 rounded-2xl border border-slate-800/80">
      <h3 className="text-sm font-bold text-slate-100 mb-4 flex items-center gap-2">
        <Bell className="w-4 h-4 text-brand-400" />
        Recent Notifications
      </h3>
      {isLoading ? (
        <div className="space-y-2 animate-pulse">
          {Array.from({ length: 3 }).map((_, i) => (
            <div key={i} className="h-10 bg-slate-900/60 rounded-lg" />
          ))}
        </div>
      ) : recent.length === 0 ? (
        <p className="text-xs text-slate-500 text-center py-6">You're all caught up.</p>
      ) : (
        <div className="space-y-1">
          {recent.map((n) => (
            <Link
              key={n.id}
              to={n.link_url || '#'}
              onClick={() => !n.is_read && markRead(n.id)}
              className={`flex items-start gap-2 px-2 py-2 rounded-lg hover:bg-slate-900/40 transition-colors ${!n.is_read ? 'bg-brand-500/5' : ''}`}
            >
              {!n.is_read && <span className="mt-1.5 w-1.5 h-1.5 rounded-full bg-brand-400 shrink-0" />}
              <div className={`min-w-0 ${n.is_read ? 'pl-3.5' : ''}`}>
                <p className="text-xs font-semibold text-slate-200 truncate">{n.title}</p>
                <p className="text-[11px] text-slate-500 truncate">{n.body}</p>
              </div>
            </Link>
          ))}
        </div>
      )}
    </div>
  );
};
