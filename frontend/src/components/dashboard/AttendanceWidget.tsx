import React, { useCallback, useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { attendanceApi, MyToday, AttendanceDashboard } from '../../services/attendanceApi';
import { Clock, LogIn, LogOut, Coffee, Loader2, UserCheck } from 'lucide-react';

const fmtTime = (iso: string | null) => iso ? new Date(iso).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }) : '—';

export const AttendanceWidget: React.FC = () => {
  const [today, setToday] = useState<MyToday | null>(null);
  const [dash, setDash] = useState<AttendanceDashboard | null>(null);
  const [loading, setLoading] = useState(true);
  const navigate = useNavigate();

  const load = useCallback(() => {
    Promise.all([attendanceApi.myToday(), attendanceApi.dashboard().catch(() => null)])
      .then(([t, d]) => { setToday(t); setDash(d); })
      .catch(() => {})
      .finally(() => setLoading(false));
  }, []);
  useEffect(() => { load(); }, [load]);

  useEffect(() => {
    const handleSync = () => load();
    window.addEventListener('attendance-updated', handleSync);
    return () => window.removeEventListener('attendance-updated', handleSync);
  }, [load]);

  const rec = today?.record;
  const clockedIn = !!rec?.clock_in_at && !rec?.clock_out_at;
  const done = !!rec?.clock_out_at;

  return (
    <div className="glass-panel border border-slate-800/85 rounded-2xl p-5">
      <div className="flex items-center justify-between mb-4">
        <h3 className="text-sm font-semibold text-slate-200 flex items-center gap-2"><Clock className="w-4 h-4 text-brand-400" /> Attendance</h3>
        <button onClick={() => navigate('/attendance')} className="text-xs text-brand-400 hover:text-brand-300 cursor-pointer">Open</button>
      </div>
      {loading ? (
        <div className="py-6 text-center text-slate-400"><Loader2 className="w-5 h-5 animate-spin inline" /></div>
      ) : (
        <>
          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm font-bold text-slate-100">{clockedIn ? 'Punched In' : done ? 'Punched Out (Shift Ended)' : 'Not Punched In'}</p>
              <p className="text-[11px] text-slate-500 mt-0.5 flex items-center gap-2">
                <span className="inline-flex items-center gap-1"><LogIn className="w-3 h-3 text-emerald-400" /> {fmtTime(rec?.clock_in_at || null)}</span>
                <span className="inline-flex items-center gap-1"><LogOut className="w-3 h-3 text-rose-400" /> {fmtTime(rec?.clock_out_at || null)}</span>
              </p>
            </div>
            <div>
              {clockedIn ? (
                <span className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-semibold bg-emerald-500/15 text-emerald-400 border border-emerald-500/30">
                  <span className="w-2 h-2 rounded-full bg-emerald-400 animate-pulse" />
                  On Duty
                </span>
              ) : done ? (
                <span className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-semibold bg-slate-500/15 text-slate-400 border border-slate-500/30">
                  <LogOut className="w-3.5 h-3.5 text-rose-400" />
                  Shift Ended
                </span>
              ) : (
                <span className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-semibold bg-amber-500/15 text-amber-400 border border-amber-500/30">
                  <Clock className="w-3.5 h-3.5 text-amber-400" />
                  Off Duty
                </span>
              )}
            </div>
          </div>
          {today?.on_break && <p className="text-[11px] text-amber-400/80 mt-2 flex items-center gap-1"><Coffee className="w-3 h-3" /> On break</p>}
          {dash && (
            <div className="grid grid-cols-3 gap-2 mt-3 pt-3 border-t border-slate-800/60">
              <div><p className="text-[10px] text-slate-500 uppercase flex items-center gap-1"><UserCheck className="w-3 h-3" /> Present</p><p className="text-sm font-bold text-slate-100">{dash.present}/{dash.headcount}</p></div>
              <div><p className="text-[10px] text-slate-500 uppercase">Late</p><p className="text-sm font-bold text-amber-400">{dash.late}</p></div>
              <div><p className="text-[10px] text-slate-500 uppercase">Pending</p><p className="text-sm font-bold text-slate-100">{dash.pending_corrections}</p></div>
            </div>
          )}
        </>
      )}
    </div>
  );
};
