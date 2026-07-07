import React from 'react';
import { GitBranch } from 'lucide-react';
import { DashboardSummaryResponse } from '../../services/dashboardApi';

interface PipelineWidgetProps {
  summary: DashboardSummaryResponse | null;
  isLoading: boolean;
}

export const PipelineWidget: React.FC<PipelineWidgetProps> = ({ summary, isLoading }) => {
  const stages = summary?.leads_by_stage ?? [];
  const maxCount = Math.max(1, ...stages.map((s) => s.count));

  return (
    <div className="glass-panel p-6 rounded-2xl border border-slate-800/80">
      <div className="flex items-center justify-between mb-4">
        <h3 className="text-sm font-bold text-slate-100 flex items-center gap-2">
          <GitBranch className="w-4 h-4 text-brand-400" />
          Pipeline by Stage
        </h3>
        {summary && summary.conversion_rate !== null ? (
          <span className="text-xs font-bold text-emerald-400">{summary.conversion_rate}% converted</span>
        ) : (
          <span className="text-[10px] text-slate-500" title='Add a pipeline stage named "Converted" to track this'>
            Conversion rate not configured
          </span>
        )}
      </div>

      {isLoading ? (
        <div className="space-y-3 animate-pulse">
          {Array.from({ length: 4 }).map((_, i) => (
            <div key={i} className="h-6 bg-slate-900/60 rounded-lg" />
          ))}
        </div>
      ) : stages.length === 0 ? (
        <p className="text-xs text-slate-500 text-center py-6">No pipeline stages configured yet.</p>
      ) : (
        <div className="space-y-3">
          {stages.map((stage) => (
            <div key={stage.stage_id}>
              <div className="flex items-center justify-between text-xs mb-1">
                <span className="font-medium text-slate-300">{stage.stage_name}</span>
                <span className="text-slate-400">{stage.count}</span>
              </div>
              <div className="w-full h-2 bg-slate-900 rounded-full overflow-hidden">
                <div
                  className={`h-full rounded-full ${stage.stage_name === 'Converted' ? 'bg-emerald-500' : 'bg-gradient-to-r from-brand-500 to-indigo-500'}`}
                  style={{ width: `${(stage.count / maxCount) * 100}%` }}
                />
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
};
