import React from 'react';
import { UserPlus, Video, ListChecks, BellRing } from 'lucide-react';
import { DashboardSummaryResponse } from '../../services/dashboardApi';

interface TodayAgendaWidgetProps {
  summary: DashboardSummaryResponse | null;
  isLoading: boolean;
}

export const TodayAgendaWidget: React.FC<TodayAgendaWidgetProps> = ({ summary, isLoading }) => {
  const today = summary?.today;

  const items = [
    { label: "Today's Leads", value: today?.leads_created ?? 0, icon: UserPlus, color: 'text-brand-400 bg-brand-500/5 border-brand-500/10' },
    { label: "Today's Meetings", value: today?.meetings_due ?? 0, icon: Video, color: 'text-indigo-400 bg-indigo-500/5 border-indigo-500/10' },
    { label: "Today's Tasks", value: today?.tasks_due ?? 0, icon: ListChecks, color: 'text-emerald-400 bg-emerald-500/5 border-emerald-500/10' },
    { label: 'Follow-ups Due', value: today?.follow_ups_due ?? 0, icon: BellRing, color: 'text-amber-400 bg-amber-500/5 border-amber-500/10' },
  ];

  return (
    <div className="glass-panel p-6 rounded-2xl border border-slate-800/80">
      <h3 className="text-sm font-bold text-slate-100 mb-4">Today's Agenda</h3>
      {isLoading ? (
        <div className="grid grid-cols-2 gap-4 animate-pulse">
          {Array.from({ length: 4 }).map((_, i) => (
            <div key={i} className="h-16 bg-slate-900/60 rounded-xl" />
          ))}
        </div>
      ) : (
        <div className="grid grid-cols-2 gap-4">
          {items.map((item) => (
            <div key={item.label} className={`flex items-center gap-3 p-3 rounded-xl border ${item.color}`}>
              <item.icon className="w-5 h-5 shrink-0" />
              <div>
                <p className="text-lg font-extrabold text-slate-100 leading-tight">{item.value}</p>
                <p className="text-[10px] text-slate-400 font-medium">{item.label}</p>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
};
