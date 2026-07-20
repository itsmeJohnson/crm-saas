import React from 'react';
import { useNavigate } from 'react-router-dom';
import { EmployeeSummary } from '../../services/dashboardApi';
import { CalendarDays, Phone, Users, Loader2 } from 'lucide-react';

const fmtTime = (iso: string | null) => iso ? new Date(iso).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }) : '';

export const TodayScheduleWidget: React.FC<{ data: EmployeeSummary | null; loading?: boolean }> = ({ data, loading }) => {
  const navigate = useNavigate();
  return (
    <div className="glass-panel border border-slate-800/85 rounded-2xl p-5">
      <div className="flex items-center justify-between mb-4">
        <h3 className="text-sm font-semibold text-slate-200 flex items-center gap-2"><CalendarDays className="w-4 h-4 text-brand-400" /> Today's Schedule</h3>
        <button onClick={() => navigate('/calendar')} className="text-xs text-brand-400 hover:text-brand-300 cursor-pointer">Calendar</button>
      </div>
      {loading ? (
        <div className="py-6 text-center text-slate-400"><Loader2 className="w-5 h-5 animate-spin inline" /></div>
      ) : !data ? (
        <p className="text-xs text-slate-500">No schedule.</p>
      ) : (
        <>
          <div className="grid grid-cols-2 gap-2">
            <div className="p-2.5 bg-slate-950/40 border border-slate-800/60 rounded-lg">
              <p className="text-[10px] font-semibold text-slate-500 uppercase tracking-wider flex items-center gap-1"><Phone className="w-3 h-3 text-brand-400" /> Calls today</p>
              <p className="text-lg font-bold text-slate-100 mt-0.5">{data.today_calls}</p>
            </div>
            <div className="p-2.5 bg-slate-950/40 border border-slate-800/60 rounded-lg">
              <p className="text-[10px] font-semibold text-slate-500 uppercase tracking-wider flex items-center gap-1"><Users className="w-3 h-3 text-emerald-400" /> Meetings</p>
              <p className="text-lg font-bold text-slate-100 mt-0.5">{data.today_meetings_count}</p>
            </div>
          </div>
          {data.today_meetings.length > 0 ? (
            <ul className="mt-3 space-y-1.5">
              {data.today_meetings.slice(0, 4).map((m) => (
                <li key={m.id} className="flex items-center justify-between text-xs">
                  <span className="text-slate-300 truncate">{m.title}</span>
                  <span className="text-slate-500 shrink-0">{fmtTime(m.start_at)}</span>
                </li>
              ))}
            </ul>
          ) : (
            <p className="text-[11px] text-slate-500 mt-3">No meetings scheduled today.</p>
          )}
        </>
      )}
    </div>
  );
};
