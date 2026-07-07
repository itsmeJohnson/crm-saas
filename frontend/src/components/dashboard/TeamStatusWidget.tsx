import React, { useEffect, useState } from 'react';
import { Radio } from 'lucide-react';
import { dashboardApi, TeamStatusMember } from '../../services/dashboardApi';

const STATE_META: Record<TeamStatusMember['state'], { label: string; dot: string; text: string }> = {
  IDLE: { label: 'Idle', dot: 'bg-slate-500', text: 'text-slate-400' },
  ACTIVE_CALLING: { label: 'On Call', dot: 'bg-emerald-400 animate-pulse', text: 'text-emerald-400' },
  BREAK: { label: 'On Break', dot: 'bg-amber-400', text: 'text-amber-400' },
};

const POLL_INTERVAL_MS = 20_000;

export const TeamStatusWidget: React.FC = () => {
  const [members, setMembers] = useState<TeamStatusMember[]>([]);
  const [isLoading, setIsLoading] = useState(true);

  useEffect(() => {
    let cancelled = false;
    const load = async () => {
      try {
        const data = await dashboardApi.getTeamStatus();
        if (!cancelled) setMembers(data);
      } catch {
        // Non-fatal — the rest of the dashboard still works without this widget.
      } finally {
        if (!cancelled) setIsLoading(false);
      }
    };
    load();
    const interval = setInterval(load, POLL_INTERVAL_MS);
    return () => {
      cancelled = true;
      clearInterval(interval);
    };
  }, []);

  if (!isLoading && members.length === 0) return null;

  return (
    <div className="glass-panel p-6 rounded-2xl border border-slate-800/80">
      <h3 className="text-sm font-bold text-slate-100 mb-4 flex items-center gap-2">
        <Radio className="w-4 h-4 text-brand-400" />
        Live Team Status
      </h3>
      {isLoading ? (
        <div className="space-y-2 animate-pulse">
          {Array.from({ length: 3 }).map((_, i) => (
            <div key={i} className="h-8 bg-slate-900/60 rounded-lg" />
          ))}
        </div>
      ) : (
        <div className="space-y-1.5 max-h-64 overflow-y-auto">
          {members.map((member) => {
            const meta = STATE_META[member.state] || STATE_META.IDLE;
            return (
              <div key={member.user_id} className="flex items-center justify-between px-2 py-1.5 rounded-lg hover:bg-slate-900/40">
                <span className="text-xs text-slate-300 truncate">{member.user_name}</span>
                <span className={`flex items-center gap-1.5 text-[10px] font-semibold ${meta.text}`}>
                  <span className={`w-1.5 h-1.5 rounded-full ${meta.dot}`} />
                  {meta.label}
                </span>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
};
