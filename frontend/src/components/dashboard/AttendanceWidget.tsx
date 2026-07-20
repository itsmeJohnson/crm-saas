import React, { useCallback, useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { attendanceApi, MyToday, AttendanceDashboard } from '../../services/attendanceApi';
import { Clock, LogIn, LogOut, Coffee, Loader2, UserCheck } from 'lucide-react';

const fmtTime = (iso: string | null) => iso ? new Date(iso).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }) : '—';

export const AttendanceWidget: React.FC = () => {
  const [today, setToday] = useState<MyToday | null>(null);
  const [dash, setDash] = useState<AttendanceDashboard | null>(null);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const navigate = useNavigate();

  const load = useCallback(() => {
    Promise.all([attendanceApi.myToday(), attendanceApi.dashboard().catch(() => null)])
      .then(([t, d]) => { setToday(t); setDash(d); })
      .catch(() => {})
      .finally(() => setLoading(false));
  }, []);
  useEffect(() => { load(); }, [load]);

  const rec = today?.record;
  const clockedIn = !!rec?.clock_in_at && !rec?.clock_out_at;
  const done = !!rec?.clock_out_at;

  const act = async (fn: () => Promise<any>) => {
    setBusy(true);
    try { await fn(); load(); } catch { /* surfaced on the full page */ } finally { setBusy(false); }
  };

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
              <p className="text-sm font-bold text-slate-100">{clockedIn ? 'Clocked in' : done ? 'Shift complete' : 'Not clocked in'}</p>
              <p className="text-[11px] text-slate-500 mt-0.5 flex items-center gap-2">
                <span className="inline-flex items-center gap-1"><LogIn className="w-3 h-3" /> {fmtTime(rec?.clock_in_at || null)}</span>
                <span className="inline-flex items-center gap-1"><LogOut className="w-3 h-3" /> {fmtTime(rec?.clock_out_at || null)}</span>
              </p>
            </div>
            {!clockedIn && !done && (
              <button disabled={busy} onClick={() => act(() => attendanceApi.clockIn())} className="inline-flex items-center gap-1.5 bg-emerald-500/90 text-white text-xs font-medium py-1.5 px-3 rounded-lg cursor-pointer disabled:opacity-40"><LogIn className="w-3.5 h-3.5" /> Clock in</button>
            )}
            {clockedIn && (
              <button disabled={busy} onClick={() => act(() => attendanceApi.clockOut())} className="inline-flex items-center gap-1.5 bg-red-500/90 text-white text-xs font-medium py-1.5 px-3 rounded-lg cursor-pointer disabled:opacity-40"><LogOut className="w-3.5 h-3.5" /> Clock out</button>
            )}
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
