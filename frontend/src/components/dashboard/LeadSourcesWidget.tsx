import React from 'react';
import { Radar } from 'lucide-react';
import { DashboardSummaryResponse } from '../../services/dashboardApi';

interface LeadSourcesWidgetProps {
  summary: DashboardSummaryResponse | null;
  isLoading: boolean;
}

const COLORS = ['bg-brand-500', 'bg-indigo-500', 'bg-emerald-500', 'bg-amber-500', 'bg-violet-500', 'bg-sky-500', 'bg-rose-500'];

export const LeadSourcesWidget: React.FC<LeadSourcesWidgetProps> = ({ summary, isLoading }) => {
  const sources = Object.entries(summary?.leads_by_source ?? {}).sort((a, b) => b[1] - a[1]);
  const total = sources.reduce((sum, [, count]) => sum + count, 0);

  return (
    <div className="glass-panel p-6 rounded-2xl border border-slate-800/80">
      <h3 className="text-sm font-bold text-slate-100 mb-4 flex items-center gap-2">
        <Radar className="w-4 h-4 text-brand-400" />
        Lead Sources
      </h3>
      {isLoading ? (
        <div className="space-y-2 animate-pulse">
          {Array.from({ length: 3 }).map((_, i) => (
            <div key={i} className="h-5 bg-slate-900/60 rounded-lg" />
          ))}
        </div>
      ) : sources.length === 0 ? (
        <p className="text-xs text-slate-500 text-center py-6">No lead source data yet.</p>
      ) : (
        <div className="space-y-2.5">
          {sources.map(([source, count], idx) => (
            <div key={source} className="flex items-center gap-2.5">
              <span className={`w-2 h-2 rounded-full shrink-0 ${COLORS[idx % COLORS.length]}`} />
              <span className="text-xs text-slate-300 flex-1 truncate">{source}</span>
              <span className="text-xs font-bold text-slate-100">{count}</span>
              <span className="text-[10px] text-slate-500 w-10 text-right">
                {total > 0 ? Math.round((count / total) * 100) : 0}%
              </span>
            </div>
          ))}
        </div>
      )}
    </div>
  );
};
