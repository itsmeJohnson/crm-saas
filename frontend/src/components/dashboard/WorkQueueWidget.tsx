import React, { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { dashboardApi, WorkQueue } from '../../services/dashboardApi';
import { ListChecks, AlertTriangle, CalendarClock, MapPin, Flame, Loader2, ChevronRight } from 'lucide-react';

const SECTION_ICON: Record<string, any> = {
  overdue_follow_ups: AlertTriangle, todays_follow_ups: CalendarClock,
  meetings: CalendarClock, site_visits: MapPin, hot_leads: Flame,
};
const SECTION_TONE: Record<string, string> = {
  overdue_follow_ups: 'text-red-400', todays_follow_ups: 'text-amber-400',
  meetings: 'text-sky-400', site_visits: 'text-emerald-400', hot_leads: 'text-orange-400',
};

export const WorkQueueWidget: React.FC = () => {
  const [data, setData] = useState<WorkQueue | null>(null);
  const [loading, setLoading] = useState(true);
  const navigate = useNavigate();

  useEffect(() => {
    dashboardApi.getWorkQueue(5).then(setData).catch(() => {}).finally(() => setLoading(false));
  }, []);

  const topSections = (data?.sections || []).filter(s => s.count > 0).slice(0, 5);
  const overdue = data?.counts?.overdue_follow_ups || 0;
  const todays = data?.counts?.todays_follow_ups || 0;

  return (
    <div className="glass-panel border border-slate-800/85 rounded-2xl p-5">
      <div className="flex items-center justify-between mb-4">
        <h3 className="text-sm font-semibold text-slate-200 flex items-center gap-2">
          <ListChecks className="w-4 h-4 text-brand-400" /> My Work Queue
        </h3>
        <button onClick={() => navigate('/leads')} className="text-xs text-brand-400 hover:text-brand-300 cursor-pointer">Open</button>
      </div>
      {loading ? (
        <div className="py-6 text-center text-slate-400"><Loader2 className="w-5 h-5 animate-spin inline" /></div>
      ) : !data ? (
        <p className="text-xs text-slate-500">No work-queue data.</p>
      ) : (
        <>
          <div className="grid grid-cols-2 gap-2 mb-3">
            <div className={`p-2.5 rounded-lg border ${overdue > 0 ? 'bg-red-500/10 border-red-500/30' : 'bg-slate-950/40 border-slate-800/60'}`}>
              <p className="text-[10px] font-semibold text-slate-500 uppercase flex items-center gap-1"><AlertTriangle className="w-3 h-3 text-red-400" /> Overdue</p>
              <p className={`text-base font-bold mt-0.5 ${overdue > 0 ? 'text-red-400' : 'text-slate-100'}`}>{overdue}</p>
            </div>
            <div className="p-2.5 bg-slate-950/40 border border-slate-800/60 rounded-lg">
              <p className="text-[10px] font-semibold text-slate-500 uppercase flex items-center gap-1"><CalendarClock className="w-3 h-3 text-amber-400" /> Today</p>
              <p className="text-base font-bold text-slate-100 mt-0.5">{todays}</p>
            </div>
          </div>
          {data.next_action && (
            <div onClick={() => data.next_action?.lead_id ? navigate(`/leads?id=${data.next_action.lead_id}`) : navigate('/leads')}
                 className="mb-2 p-2 bg-brand-500/10 border border-brand-500/20 rounded-lg cursor-pointer hover:border-brand-500/40">
              <p className="text-[10px] font-bold text-brand-300 uppercase">Do next</p>
              <p className="text-xs text-slate-200 truncate">{data.next_action.title}</p>
            </div>
          )}
          <div className="space-y-1">
            {topSections.length === 0 ? <p className="text-xs text-slate-500">You're all caught up 🎉</p> :
              topSections.map(s => {
                const Icon = SECTION_ICON[s.key] || ChevronRight;
                return (
                  <div key={s.key} className="flex items-center justify-between text-xs py-1 border-b border-slate-800/50 last:border-0">
                    <span className="flex items-center gap-1.5 text-slate-300"><Icon className={`w-3.5 h-3.5 ${SECTION_TONE[s.key] || 'text-slate-500'}`} /> {s.label}</span>
                    <span className="text-slate-400 font-semibold">{s.count}</span>
                  </div>
                );
              })}
          </div>
        </>
      )}
    </div>
  );
};
