import React from 'react';
import { Phone, Users, Mail, CheckSquare, ChevronLeft, ChevronRight, AlertCircle } from 'lucide-react';
import { RecentActivityItem } from '../../services/dashboardApi';

interface RecentActivitiesWidgetProps {
  activities: RecentActivityItem[];
  total: number;
  page: number;
  limit: number;
  isLoading: boolean;
  onPageChange: (page: number) => void;
}

const TYPE_ICONS: Record<string, any> = {
  Call: Phone,
  Meeting: Users,
  Email: Mail,
  Task: CheckSquare
};

const TYPE_COLORS: Record<string, string> = {
  Call: 'bg-emerald-500/10 text-emerald-400 border-emerald-500/25',
  Meeting: 'bg-indigo-500/10 text-indigo-400 border-indigo-500/25',
  Email: 'bg-sky-500/10 text-sky-400 border-sky-500/25',
  Task: 'bg-amber-500/10 text-amber-400 border-amber-500/25',
  Unknown: 'bg-slate-500/10 text-slate-400 border-slate-500/25'
};

export const RecentActivitiesWidget: React.FC<RecentActivitiesWidgetProps> = ({
  activities,
  total,
  page,
  limit,
  isLoading,
  onPageChange
}) => {
  const hasMore = total > page * limit;

  const formatDate = (dateStr: string) => {
    const d = new Date(dateStr);
    return d.toLocaleDateString('en-US', {
      month: 'short',
      day: 'numeric',
      hour: '2-digit',
      minute: '2-digit'
    });
  };

  if (isLoading) {
    return (
      <div className="glass-panel p-6 rounded-2xl border border-slate-800/80 bg-slate-950/20 space-y-4 min-h-[400px] flex flex-col justify-between">
        <div>
          <div className="h-5 bg-slate-800 rounded w-1/3 animate-pulse"></div>
          <div className="h-3 bg-slate-800 rounded w-1/4 animate-pulse mt-2"></div>
        </div>
        <div className="flex-1 space-y-4 mt-6">
          {Array.from({ length: 4 }).map((_, i) => (
            <div key={i} className="flex gap-3 animate-pulse">
              <div className="w-9 h-9 rounded-xl bg-slate-800"></div>
              <div className="flex-1 space-y-2">
                <div className="h-4 bg-slate-800 rounded w-1/2"></div>
                <div className="h-3 bg-slate-800 rounded w-1/3"></div>
              </div>
            </div>
          ))}
        </div>
      </div>
    );
  }

  return (
    <div className="glass-panel p-6 rounded-2xl border border-slate-800/80 bg-slate-950/20 flex flex-col justify-between min-h-[400px]">
      <div>
        <h3 className="text-sm font-semibold text-slate-300">Recent Activities</h3>
        <p className="text-xs text-slate-500 mt-0.5">Timeline of recent logged activities across the team</p>
      </div>

      <div className="flex-1 mt-6 space-y-4.5">
        {activities.length === 0 ? (
          <div className="flex flex-col items-center justify-center text-slate-500 py-12">
            <AlertCircle className="w-8 h-8 mb-2 opacity-60" />
            <p className="text-sm font-medium">No recent activities</p>
            <p className="text-xs text-slate-600 mt-0.5">Team activities will display here once logged</p>
          </div>
        ) : (
          <div className="relative border-l border-slate-800/60 ml-4.5 pl-6 space-y-6">
            {activities.map((act) => {
              const Icon = TYPE_ICONS[act.activity_type] || TYPE_ICONS.Task;
              const colorClass = TYPE_COLORS[act.activity_type] || TYPE_COLORS.Unknown;
              return (
                <div key={act.id} className="relative">
                  {/* Icon Timeline Bullet */}
                  <span className={`absolute -left-[42px] top-0.5 w-9 h-9 rounded-xl border flex items-center justify-center ${colorClass}`}>
                    <Icon className="w-4 h-4" />
                  </span>

                  <div>
                    <div className="flex items-center justify-between gap-4">
                      <p className="text-sm font-semibold text-slate-200">
                        {act.subject}
                      </p>
                      <span className="text-[10px] font-medium text-slate-500 shrink-0">
                        {formatDate(act.created_at)}
                      </span>
                    </div>
                    {act.description && (
                      <p className="text-xs text-slate-400 mt-1 font-medium line-clamp-2">
                        {act.description}
                      </p>
                    )}
                    <div className="flex items-center gap-2 mt-1.5 text-[10px] text-slate-500 font-semibold">
                      <span className={`px-1.5 py-0.5 rounded-md border text-[9px] ${
                        act.status === 'Completed' ? 'bg-emerald-500/10 text-emerald-400 border-emerald-500/20' : 'bg-slate-800/50 text-slate-400 border-slate-800'
                      }`}>
                        {act.status}
                      </span>
                      <span>•</span>
                      <span>Assigned to: <strong className="text-slate-400 font-medium">{act.assigned_user_name}</strong></span>
                    </div>
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </div>

      {total > limit && (
        <div className="flex items-center justify-between border-t border-slate-800/60 pt-4 mt-6">
          <div className="text-xs text-slate-400">
            Showing Page <span className="font-semibold text-slate-200">{page}</span>
          </div>
          <div className="flex items-center gap-2">
            <button
              onClick={() => onPageChange(page - 1)}
              disabled={page === 1}
              className={`p-1.5 border rounded-xl transition-all cursor-pointer ${
                page === 1
                  ? 'border-slate-800 bg-slate-900/30 text-slate-600 cursor-not-allowed'
                  : 'border-slate-800 bg-slate-900 text-slate-300 hover:border-slate-700 hover:bg-slate-900/80 active:bg-slate-900/50'
              }`}
            >
              <ChevronLeft className="w-4 h-4" />
            </button>
            <button
              onClick={() => onPageChange(page + 1)}
              disabled={!hasMore}
              className={`p-1.5 border rounded-xl transition-all cursor-pointer ${
                !hasMore
                  ? 'border-slate-800 bg-slate-900/30 text-slate-600 cursor-not-allowed'
                  : 'border-slate-800 bg-slate-900 text-slate-300 hover:border-slate-700 hover:bg-slate-900/80 active:bg-slate-900/50'
              }`}
            >
              <ChevronRight className="w-4 h-4" />
            </button>
          </div>
        </div>
      )}
    </div>
  );
};
