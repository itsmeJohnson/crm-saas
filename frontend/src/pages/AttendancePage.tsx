import React, { useCallback, useEffect, useState } from 'react';
import {
  Clock, LogIn, LogOut, Coffee, Loader2, Plus, X, Check, Trash2, Pencil, CalendarClock,
  UserCheck, ClipboardList, BarChart3, MapPin, AlarmClock, Play,
} from 'lucide-react';
import {
  attendanceApi, Shift, AttendanceRecord, MyToday, Correction, AttendanceDashboard, MonthlyReport,
} from '../services/attendanceApi';
import { userApi } from '../services/userApi';
import { useAuthStore } from '../store/authStore';
import { extractErrorMessage } from '../utils/errors';

const WEEKDAYS = ['mon', 'tue', 'wed', 'thu', 'fri', 'sat', 'sun'];
const F = "w-full bg-slate-800/70 border border-slate-700/70 text-slate-200 py-2 px-3 rounded-lg text-sm";

const StatusChip: React.FC<{ status: string }> = ({ status }) => {
  const tone = status === 'late' ? 'bg-amber-500/10 text-amber-400 border-amber-500/20'
    : status === 'present' ? 'bg-emerald-500/10 text-emerald-400 border-emerald-500/20'
      : status === 'half_day' ? 'bg-orange-500/10 text-orange-400 border-orange-500/20'
        : status === 'absent' ? 'bg-red-500/10 text-red-400 border-red-500/20'
          : 'bg-slate-700/40 text-slate-400 border-slate-600/40';
  return <span className={`px-2 py-0.5 text-[10px] font-semibold rounded-md border ${tone}`}>{status.replace('_', ' ')}</span>;
};

const fmtTime = (iso: string | null) => iso ? new Date(iso).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }) : '—';
const fmtMins = (m: number) => `${Math.floor(m / 60)}h ${m % 60}m`;
const getGeo = (): Promise<{ latitude?: number; longitude?: number }> =>
  new Promise((resolve) => {
    if (!navigator.geolocation) return resolve({});
    navigator.geolocation.getCurrentPosition(
      (p) => resolve({ latitude: p.coords.latitude, longitude: p.coords.longitude }),
      () => resolve({}), { timeout: 4000 });
  });

/* ── Clock panel ── */
const ClockPanel: React.FC<{ onChange: () => void }> = ({ onChange }) => {
  const [data, setData] = useState<MyToday | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(() => { attendanceApi.myToday().then(setData).catch(() => {}); }, []);
  useEffect(() => { load(); }, [load]);

  const act = async (fn: () => Promise<any>) => {
    setBusy(true); setError(null);
    try { await fn(); load(); onChange(); }
    catch (e: any) { setError(extractErrorMessage(e, 'Action failed')); } finally { setBusy(false); }
  };

  const rec = data?.record;
  const clockedIn = !!rec?.clock_in_at && !rec?.clock_out_at;
  const done = !!rec?.clock_out_at;

  return (
    <div className="glass-panel border border-slate-800/85 rounded-2xl p-5">
      {error && <div className="p-2.5 mb-3 bg-red-500/10 border border-red-500/20 text-red-400 rounded-lg text-xs">{error}</div>}
      <div className="flex flex-wrap items-center justify-between gap-4">
        <div>
          <p className="text-[11px] text-slate-500 uppercase tracking-wider">Today · {data?.work_date}</p>
          <div className="flex items-center gap-3 mt-1">
            <p className="text-2xl font-bold text-slate-100">{clockedIn ? 'Clocked in' : done ? 'Shift complete' : 'Not clocked in'}</p>
            {rec && <StatusChip status={rec.status} />}
          </div>
          <p className="text-xs text-slate-500 mt-1">
            {data?.shift ? <>Shift: <span className="text-slate-300">{data.shift.name} ({data.shift.start_time}–{data.shift.end_time})</span></> : 'No shift assigned'}
          </p>
          {rec && (
            <p className="text-xs text-slate-400 mt-2 flex items-center gap-3 flex-wrap">
              <span className="inline-flex items-center gap-1"><LogIn className="w-3.5 h-3.5" /> {fmtTime(rec.clock_in_at)}</span>
              <span className="inline-flex items-center gap-1"><LogOut className="w-3.5 h-3.5" /> {fmtTime(rec.clock_out_at)}</span>
              <span className="inline-flex items-center gap-1"><Clock className="w-3.5 h-3.5" /> {fmtMins(rec.worked_minutes)} worked</span>
              <span className="inline-flex items-center gap-1"><Coffee className="w-3.5 h-3.5" /> {fmtMins(rec.break_minutes)} break</span>
              {rec.is_late && <span className="text-amber-400">Late {rec.late_minutes}m</span>}
              {rec.is_early_logout && <span className="text-orange-400">Early {rec.early_minutes}m</span>}
            </p>
          )}
        </div>
        <div className="flex items-center gap-2">
          {!clockedIn && !done && (
            <button disabled={busy} onClick={() => act(async () => attendanceApi.clockIn(await getGeo()))}
                    className="inline-flex items-center gap-1.5 bg-gradient-to-r from-emerald-500 to-emerald-600 text-white text-sm font-medium py-2 px-4 rounded-lg disabled:opacity-40 cursor-pointer">
              {busy ? <Loader2 className="w-4 h-4 animate-spin" /> : <LogIn className="w-4 h-4" />} Clock in
            </button>
          )}
          {clockedIn && (
            <>
              {data?.on_break ? (
                <button disabled={busy} onClick={() => act(() => attendanceApi.breakEnd())} className="inline-flex items-center gap-1.5 border border-amber-500/40 text-amber-300 text-sm py-2 px-3 rounded-lg cursor-pointer"><Play className="w-4 h-4" /> End break</button>
              ) : (
                <button disabled={busy} onClick={() => act(() => attendanceApi.breakStart())} className="inline-flex items-center gap-1.5 border border-slate-700 text-slate-300 text-sm py-2 px-3 rounded-lg cursor-pointer"><Coffee className="w-4 h-4" /> Break</button>
              )}
              <button disabled={busy} onClick={() => act(async () => attendanceApi.clockOut(await getGeo()))}
                      className="inline-flex items-center gap-1.5 bg-gradient-to-r from-red-500 to-red-600 text-white text-sm font-medium py-2 px-4 rounded-lg disabled:opacity-40 cursor-pointer">
                {busy ? <Loader2 className="w-4 h-4 animate-spin" /> : <LogOut className="w-4 h-4" />} Clock out
              </button>
            </>
          )}
          {done && <span className="text-xs text-slate-500 inline-flex items-center gap-1"><Check className="w-4 h-4 text-emerald-400" /> Done for today</span>}
        </div>
      </div>
      {data?.on_break && <p className="text-xs text-amber-400/80 mt-3 flex items-center gap-1.5"><Coffee className="w-3.5 h-3.5" /> On break…</p>}
    </div>
  );
};

/* ── Shift modal ── */
const ShiftModal: React.FC<{ initial?: Shift | null; onClose: () => void; onSaved: () => void }> = ({ initial, onClose, onSaved }) => {
  const [f, setF] = useState<any>(initial ? {
    ...initial, working_days: initial.working_days,
  } : { name: '', code: '', start_time: '09:00', end_time: '18:00', break_minutes: 60, grace_minutes: 10, working_days: ['mon', 'tue', 'wed', 'thu', 'fri'], status: 'active' });
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const toggleDay = (d: string) => {
    const set = new Set(f.working_days || []);
    set.has(d) ? set.delete(d) : set.add(d);
    setF({ ...f, working_days: WEEKDAYS.filter((x) => set.has(x)) });
  };
  const save = async () => {
    if (!f.name?.trim()) { setError('Name is required'); return; }
    setBusy(true); setError(null);
    try {
      const payload = {
        name: f.name, code: f.code || undefined, start_time: f.start_time, end_time: f.end_time,
        break_minutes: Number(f.break_minutes) || 0, grace_minutes: Number(f.grace_minutes) || 0,
        working_days: f.working_days, status: f.status,
      };
      if (initial) await attendanceApi.updateShift(initial.id, payload);
      else await attendanceApi.createShift(payload);
      onSaved();
    } catch (e: any) { setError(extractErrorMessage(e, 'Failed to save')); } finally { setBusy(false); }
  };
  return (
    <div className="fixed inset-0 z-40 flex items-center justify-center bg-black/50 backdrop-blur-sm p-4">
      <div className="glass-panel border border-slate-800/85 rounded-2xl w-full max-w-md bg-slate-900 max-h-[90vh] overflow-y-auto">
        <div className="flex items-center justify-between p-4 border-b border-slate-800/60">
          <h3 className="text-sm font-semibold text-slate-200 flex items-center gap-2"><CalendarClock className="w-4 h-4 text-brand-400" /> {initial ? 'Edit' : 'New'} shift</h3>
          <button onClick={onClose} className="p-1 text-slate-500 hover:text-slate-300 cursor-pointer"><X className="w-4 h-4" /></button>
        </div>
        <div className="p-4 space-y-3">
          {error && <div className="p-2.5 bg-red-500/10 border border-red-500/20 text-red-400 rounded-lg text-xs">{error}</div>}
          <div className="grid grid-cols-2 gap-2">
            <input value={f.name} onChange={(e) => setF({ ...f, name: e.target.value })} placeholder="Name" className={F} />
            <input value={f.code || ''} onChange={(e) => setF({ ...f, code: e.target.value })} placeholder="Code" className={F} />
          </div>
          <div className="grid grid-cols-2 gap-2">
            <label className="text-xs text-slate-400">Start<input type="time" value={f.start_time} onChange={(e) => setF({ ...f, start_time: e.target.value })} className={F} /></label>
            <label className="text-xs text-slate-400">End<input type="time" value={f.end_time} onChange={(e) => setF({ ...f, end_time: e.target.value })} className={F} /></label>
          </div>
          <div className="grid grid-cols-2 gap-2">
            <label className="text-xs text-slate-400">Break (min)<input type="number" value={f.break_minutes} onChange={(e) => setF({ ...f, break_minutes: e.target.value })} className={F} /></label>
            <label className="text-xs text-slate-400">Grace (min)<input type="number" value={f.grace_minutes} onChange={(e) => setF({ ...f, grace_minutes: e.target.value })} className={F} /></label>
          </div>
          <div>
            <p className="text-xs text-slate-400 mb-1">Working days</p>
            <div className="flex gap-1 flex-wrap">
              {WEEKDAYS.map((d) => (
                <button key={d} onClick={() => toggleDay(d)} className={`px-2 py-1 text-[11px] rounded-md border cursor-pointer capitalize ${(f.working_days || []).includes(d) ? 'bg-brand-500/15 text-brand-300 border-brand-500/30' : 'bg-slate-800/40 text-slate-500 border-slate-700/40'}`}>{d}</button>
              ))}
            </div>
          </div>
          <button onClick={save} disabled={busy} className="w-full inline-flex items-center justify-center gap-2 bg-gradient-to-r from-brand-500 to-indigo-500 text-white font-medium py-2 px-4 rounded-lg text-sm disabled:opacity-40 cursor-pointer">
            {busy ? <Loader2 className="w-4 h-4 animate-spin" /> : <Check className="w-4 h-4" />} {initial ? 'Save' : 'Create'}
          </button>
        </div>
      </div>
    </div>
  );
};

/* ── Assign shift modal ── */
const AssignModal: React.FC<{ shifts: Shift[]; users: any[]; onClose: () => void; onSaved: () => void }> = ({ shifts, users, onClose, onSaved }) => {
  const [shiftId, setShiftId] = useState(shifts[0]?.id || '');
  const [pick, setPick] = useState<Set<string>>(new Set());
  const [start, setStart] = useState('');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const save = async () => {
    if (!shiftId || !pick.size) { setError('Pick a shift and at least one user'); return; }
    setBusy(true); setError(null);
    try { await attendanceApi.assignShift({ shift_id: shiftId, user_ids: [...pick], start_date: start || undefined }); onSaved(); }
    catch (e: any) { setError(extractErrorMessage(e, 'Failed to assign')); } finally { setBusy(false); }
  };
  return (
    <div className="fixed inset-0 z-40 flex items-center justify-center bg-black/50 backdrop-blur-sm p-4">
      <div className="glass-panel border border-slate-800/85 rounded-2xl w-full max-w-md bg-slate-900 max-h-[90vh] overflow-y-auto">
        <div className="flex items-center justify-between p-4 border-b border-slate-800/60">
          <h3 className="text-sm font-semibold text-slate-200 flex items-center gap-2"><UserCheck className="w-4 h-4 text-brand-400" /> Assign shift</h3>
          <button onClick={onClose} className="p-1 text-slate-500 hover:text-slate-300 cursor-pointer"><X className="w-4 h-4" /></button>
        </div>
        <div className="p-4 space-y-3">
          {error && <div className="p-2.5 bg-red-500/10 border border-red-500/20 text-red-400 rounded-lg text-xs">{error}</div>}
          <select value={shiftId} onChange={(e) => setShiftId(e.target.value)} className={F}>
            {shifts.map((s) => <option key={s.id} value={s.id}>{s.name} ({s.start_time}–{s.end_time})</option>)}
          </select>
          <label className="text-xs text-slate-400 block">Start date (optional)<input type="date" value={start} onChange={(e) => setStart(e.target.value)} className={F} /></label>
          <div className="max-h-52 overflow-y-auto space-y-1 border border-slate-800/60 rounded-lg p-2">
            {users.map((u) => (
              <label key={u.id} className="flex items-center gap-2 text-xs text-slate-300 cursor-pointer">
                <input type="checkbox" checked={pick.has(u.id)} onChange={(e) => { const s = new Set(pick); e.target.checked ? s.add(u.id) : s.delete(u.id); setPick(s); }} />
                {`${u.first_name || ''} ${u.last_name || ''}`.trim() || u.email} <span className="text-slate-600">({u.role})</span>
              </label>
            ))}
          </div>
          <button onClick={save} disabled={busy} className="w-full inline-flex items-center justify-center gap-2 bg-gradient-to-r from-brand-500 to-indigo-500 text-white font-medium py-2 px-4 rounded-lg text-sm disabled:opacity-40 cursor-pointer">
            {busy ? <Loader2 className="w-4 h-4 animate-spin" /> : <Check className="w-4 h-4" />} Assign {pick.size ? `(${pick.size})` : ''}
          </button>
        </div>
      </div>
    </div>
  );
};

/* ── Correction modal ── */
const CorrectionModal: React.FC<{ onClose: () => void; onSaved: () => void }> = ({ onClose, onSaved }) => {
  const [f, setF] = useState({ work_date: '', reason: '', clock_in_at: '', clock_out_at: '', status: '' });
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const save = async () => {
    if (!f.work_date || !f.reason.trim()) { setError('Date and reason are required'); return; }
    setBusy(true); setError(null);
    try {
      const proposed: any = {};
      if (f.clock_in_at) proposed.clock_in_at = new Date(`${f.work_date}T${f.clock_in_at}`).toISOString();
      if (f.clock_out_at) proposed.clock_out_at = new Date(`${f.work_date}T${f.clock_out_at}`).toISOString();
      if (f.status) proposed.status = f.status;
      await attendanceApi.requestCorrection({ work_date: f.work_date, reason: f.reason, proposed: Object.keys(proposed).length ? proposed : undefined });
      onSaved();
    } catch (e: any) { setError(extractErrorMessage(e, 'Failed to submit')); } finally { setBusy(false); }
  };
  return (
    <div className="fixed inset-0 z-40 flex items-center justify-center bg-black/50 backdrop-blur-sm p-4">
      <div className="glass-panel border border-slate-800/85 rounded-2xl w-full max-w-md bg-slate-900">
        <div className="flex items-center justify-between p-4 border-b border-slate-800/60">
          <h3 className="text-sm font-semibold text-slate-200 flex items-center gap-2"><ClipboardList className="w-4 h-4 text-brand-400" /> Request correction</h3>
          <button onClick={onClose} className="p-1 text-slate-500 hover:text-slate-300 cursor-pointer"><X className="w-4 h-4" /></button>
        </div>
        <div className="p-4 space-y-3">
          {error && <div className="p-2.5 bg-red-500/10 border border-red-500/20 text-red-400 rounded-lg text-xs">{error}</div>}
          <label className="text-xs text-slate-400 block">Date<input type="date" value={f.work_date} onChange={(e) => setF({ ...f, work_date: e.target.value })} className={F} /></label>
          <div className="grid grid-cols-2 gap-2">
            <label className="text-xs text-slate-400">Clock in<input type="time" value={f.clock_in_at} onChange={(e) => setF({ ...f, clock_in_at: e.target.value })} className={F} /></label>
            <label className="text-xs text-slate-400">Clock out<input type="time" value={f.clock_out_at} onChange={(e) => setF({ ...f, clock_out_at: e.target.value })} className={F} /></label>
          </div>
          <select value={f.status} onChange={(e) => setF({ ...f, status: e.target.value })} className={F}>
            <option value="">Keep status</option>
            {['present', 'late', 'half_day', 'on_leave', 'absent'].map((s) => <option key={s} value={s}>{s}</option>)}
          </select>
          <textarea value={f.reason} onChange={(e) => setF({ ...f, reason: e.target.value })} rows={2} placeholder="Reason" className={F} />
          <button onClick={save} disabled={busy} className="w-full inline-flex items-center justify-center gap-2 bg-gradient-to-r from-brand-500 to-indigo-500 text-white font-medium py-2 px-4 rounded-lg text-sm disabled:opacity-40 cursor-pointer">
            {busy ? <Loader2 className="w-4 h-4 animate-spin" /> : <Check className="w-4 h-4" />} Submit
          </button>
        </div>
      </div>
    </div>
  );
};

/* ── Page ── */
export const AttendancePage: React.FC = () => {
  const { user } = useAuthStore();
  const isManager = user?.role === 'OrgAdmin' || user?.role === 'Manager';
  const isAdmin = user?.role === 'OrgAdmin';

  const [tab, setTab] = useState<'today' | 'history' | 'corrections' | 'shifts' | 'report'>('today');
  const [dash, setDash] = useState<AttendanceDashboard | null>(null);
  const [records, setRecords] = useState<AttendanceRecord[]>([]);
  const [shifts, setShifts] = useState<Shift[]>([]);
  const [corrections, setCorrections] = useState<Correction[]>([]);
  const [report, setReport] = useState<MonthlyReport | null>(null);
  const [users, setUsers] = useState<any[]>([]);
  const [shiftModal, setShiftModal] = useState<Shift | null | 'new'>(null);
  const [assignOpen, setAssignOpen] = useState(false);
  const [corrOpen, setCorrOpen] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const now = new Date();
  const [ym, setYm] = useState({ year: now.getFullYear(), month: now.getMonth() + 1 });

  const loadDash = useCallback(() => { attendanceApi.dashboard().then(setDash).catch(() => {}); }, []);
  useEffect(() => { loadDash(); }, [loadDash]);
  useEffect(() => { if (isAdmin) userApi.getUsers({ is_active: true, limit: 200 }).then(setUsers).catch(() => {}); }, [isAdmin]);

  const loadTab = useCallback(() => {
    setError(null);
    if (tab === 'history') attendanceApi.records({}).then((r) => setRecords(r.items)).catch((e) => setError(extractErrorMessage(e, 'Failed')));
    if (tab === 'shifts') attendanceApi.listShifts({}).then(setShifts).catch(() => {});
    if (tab === 'corrections') attendanceApi.listCorrections({}).then(setCorrections).catch(() => {});
    if (tab === 'report') attendanceApi.monthlyReport(ym.year, ym.month).then(setReport).catch(() => {});
  }, [tab, ym]);
  useEffect(() => { loadTab(); }, [loadTab]);
  // shifts list is also needed for the assign modal
  useEffect(() => { if (isAdmin) attendanceApi.listShifts({}).then(setShifts).catch(() => {}); }, [isAdmin]);

  const review = async (c: Correction, approve: boolean) => {
    try { await attendanceApi.reviewCorrection(c.id, approve); loadTab(); loadDash(); }
    catch (e: any) { setError(extractErrorMessage(e, 'Review failed')); }
  };
  const removeShift = async (s: Shift) => {
    if (!window.confirm(`Delete shift "${s.name}"?`)) return;
    try { await attendanceApi.deleteShift(s.id); loadTab(); } catch (e: any) { setError(extractErrorMessage(e, 'Delete failed')); }
  };

  return (
    <div className="p-4 sm:p-6 space-y-4">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <h1 className="text-lg font-bold text-slate-100 flex items-center gap-2"><Clock className="w-5 h-5 text-brand-400" /> Attendance</h1>
      </div>

      {dash && (
        <div className="grid grid-cols-3 sm:grid-cols-6 gap-2">
          {[
            { label: 'Present', value: dash.present, icon: UserCheck },
            { label: 'Absent', value: dash.absent, icon: X },
            { label: 'Late', value: dash.late, icon: AlarmClock },
            { label: 'On break', value: dash.on_break, icon: Coffee },
            { label: 'Working', value: dash.still_working, icon: Play },
            { label: 'Pending', value: dash.pending_corrections, icon: ClipboardList },
          ].map((s) => (
            <div key={s.label} className="glass-panel border border-slate-800/85 rounded-xl p-3">
              <p className="text-[10px] font-semibold text-slate-500 uppercase tracking-wider flex items-center gap-1"><s.icon className="w-3 h-3 text-brand-400" /> {s.label}</p>
              <p className="text-xl font-bold text-slate-100 mt-0.5">{s.value}</p>
            </div>
          ))}
        </div>
      )}

      {error && <div className="p-3 bg-red-500/10 border border-red-500/20 text-red-400 rounded-lg text-xs">{error}</div>}

      <div className="flex gap-1 border-b border-slate-800/60 flex-wrap">
        {([['today', 'Today', Clock], ['history', 'My History', CalendarClock], ['corrections', isManager ? 'Corrections & Approvals' : 'Corrections', ClipboardList], ...(isAdmin ? [['shifts', 'Shifts', CalendarClock]] as const : []), ['report', 'Monthly Report', BarChart3]] as const).map(([key, label, Icon]) => (
          <button key={key} onClick={() => setTab(key as any)}
                  className={`px-3 py-1.5 text-xs font-medium inline-flex items-center gap-1.5 border-b-2 -mb-px cursor-pointer ${tab === key ? 'border-brand-500 text-brand-300' : 'border-transparent text-slate-500 hover:text-slate-300'}`}>
            <Icon className="w-3.5 h-3.5" /> {label}
          </button>
        ))}
      </div>

      {tab === 'today' && <ClockPanel onChange={loadDash} />}

      {tab === 'history' && (
        <div className="overflow-x-auto">
          <table className="w-full text-xs">
            <thead><tr className="text-left text-[10px] text-slate-500 uppercase">
              <th className="py-2 pr-2">Date</th><th className="py-2 pr-2">In</th><th className="py-2 pr-2">Out</th><th className="py-2 pr-2">Worked</th><th className="py-2 pr-2">Break</th><th className="py-2 pr-2">Status</th><th className="py-2">Flags</th>
            </tr></thead>
            <tbody>
              {records.map((r) => (
                <tr key={r.id} className="border-t border-slate-800/50 text-slate-300">
                  <td className="py-1.5 pr-2">{r.work_date}</td>
                  <td className="py-1.5 pr-2">{fmtTime(r.clock_in_at)}</td>
                  <td className="py-1.5 pr-2">{fmtTime(r.clock_out_at)}</td>
                  <td className="py-1.5 pr-2">{fmtMins(r.worked_minutes)}</td>
                  <td className="py-1.5 pr-2">{fmtMins(r.break_minutes)}</td>
                  <td className="py-1.5 pr-2"><StatusChip status={r.status} /></td>
                  <td className="py-1.5 text-[11px]">{r.is_late && <span className="text-amber-400 mr-1">late {r.late_minutes}m</span>}{r.is_early_logout && <span className="text-orange-400">early {r.early_minutes}m</span>}{r.in_latitude != null && <MapPin className="w-3 h-3 inline text-slate-500" />}</td>
                </tr>
              ))}
            </tbody>
          </table>
          {!records.length && <p className="text-xs text-slate-500 py-6 text-center">No attendance records yet.</p>}
        </div>
      )}

      {tab === 'corrections' && (
        <div className="space-y-3">
          <button onClick={() => setCorrOpen(true)} className="inline-flex items-center gap-1.5 bg-gradient-to-r from-brand-500 to-indigo-500 text-white text-xs font-medium py-1.5 px-3 rounded-lg cursor-pointer"><Plus className="w-3.5 h-3.5" /> Request correction</button>
          <div className="space-y-2">
            {corrections.map((c) => (
              <div key={c.id} className="p-3 rounded-xl border border-slate-800/85 bg-slate-950/30">
                <div className="flex items-center justify-between gap-2">
                  <p className="text-sm text-slate-200">{c.user_name} · <span className="text-slate-400">{c.work_date}</span></p>
                  <div className="flex items-center gap-2">
                    <StatusChip status={c.status} />
                    {isManager && c.status === 'pending' && (
                      <>
                        <button onClick={() => review(c, true)} className="text-xs text-emerald-400 cursor-pointer inline-flex items-center gap-1"><Check className="w-3.5 h-3.5" /> Approve</button>
                        <button onClick={() => review(c, false)} className="text-xs text-red-400 cursor-pointer inline-flex items-center gap-1"><X className="w-3.5 h-3.5" /> Reject</button>
                      </>
                    )}
                  </div>
                </div>
                <p className="text-[11px] text-slate-500 mt-1">{c.reason}{c.reviewed_by_name ? ` · reviewed by ${c.reviewed_by_name}` : ''}</p>
              </div>
            ))}
            {!corrections.length && <p className="text-xs text-slate-500 py-4 text-center">No corrections.</p>}
          </div>
        </div>
      )}

      {tab === 'shifts' && isAdmin && (
        <div className="space-y-3">
          <div className="flex items-center gap-2">
            <button onClick={() => setShiftModal('new')} className="inline-flex items-center gap-1.5 bg-gradient-to-r from-brand-500 to-indigo-500 text-white text-xs font-medium py-1.5 px-3 rounded-lg cursor-pointer"><Plus className="w-3.5 h-3.5" /> New shift</button>
            <button onClick={() => setAssignOpen(true)} className="inline-flex items-center gap-1.5 border border-slate-800 text-slate-300 text-xs py-1.5 px-3 rounded-lg cursor-pointer"><UserCheck className="w-3.5 h-3.5" /> Assign shift</button>
          </div>
          <div className="space-y-2">
            {shifts.map((s) => (
              <div key={s.id} className="p-3 rounded-xl border border-slate-800/85 bg-slate-950/30 flex items-center justify-between gap-2">
                <div>
                  <p className="text-sm text-slate-200 font-medium">{s.name} {s.code && <span className="text-[10px] text-slate-600">{s.code}</span>}</p>
                  <p className="text-[11px] text-slate-500 mt-0.5">{s.start_time}–{s.end_time} · {s.break_minutes}m break · {s.grace_minutes}m grace · {(s.working_days || []).join(', ')}</p>
                </div>
                <div className="flex items-center gap-1">
                  <button onClick={() => setShiftModal(s)} className="p-1.5 text-slate-500 hover:text-slate-300 cursor-pointer"><Pencil className="w-4 h-4" /></button>
                  <button onClick={() => removeShift(s)} className="p-1.5 text-slate-500 hover:text-red-400 cursor-pointer"><Trash2 className="w-4 h-4" /></button>
                </div>
              </div>
            ))}
            {!shifts.length && <p className="text-xs text-slate-500 py-4 text-center">No shifts yet.</p>}
          </div>
        </div>
      )}

      {tab === 'report' && (
        <div className="space-y-3">
          <div className="flex items-center gap-2">
            <input type="number" value={ym.year} onChange={(e) => setYm({ ...ym, year: Number(e.target.value) })} className="bg-slate-800/70 border border-slate-700/70 text-slate-200 py-1.5 px-2 rounded-lg text-xs w-24" />
            <select value={ym.month} onChange={(e) => setYm({ ...ym, month: Number(e.target.value) })} className="bg-slate-800/70 border border-slate-700/70 text-slate-200 py-1.5 px-2 rounded-lg text-xs">
              {Array.from({ length: 12 }, (_, i) => i + 1).map((m) => <option key={m} value={m}>{new Date(2000, m - 1).toLocaleString('default', { month: 'long' })}</option>)}
            </select>
          </div>
          <div className="overflow-x-auto">
            <table className="w-full text-xs">
              <thead><tr className="text-left text-[10px] text-slate-500 uppercase">
                <th className="py-2 pr-2">Employee</th><th className="py-2 pr-2">Present</th><th className="py-2 pr-2">Late</th><th className="py-2 pr-2">Early</th><th className="py-2 pr-2">Half</th><th className="py-2 pr-2">Leave</th><th className="py-2">Hours</th>
              </tr></thead>
              <tbody>
                {report?.rows.map((r) => (
                  <tr key={r.user_id} className="border-t border-slate-800/50 text-slate-300">
                    <td className="py-1.5 pr-2">{r.name}</td>
                    <td className="py-1.5 pr-2">{r.present_days}</td>
                    <td className="py-1.5 pr-2">{r.late_days}</td>
                    <td className="py-1.5 pr-2">{r.early_days}</td>
                    <td className="py-1.5 pr-2">{r.half_days}</td>
                    <td className="py-1.5 pr-2">{r.leave_days}</td>
                    <td className="py-1.5">{r.worked_hours}h</td>
                  </tr>
                ))}
              </tbody>
            </table>
            {!report?.rows.length && <p className="text-xs text-slate-500 py-6 text-center">No data for this month.</p>}
          </div>
        </div>
      )}

      {shiftModal && <ShiftModal initial={shiftModal === 'new' ? null : shiftModal} onClose={() => setShiftModal(null)} onSaved={() => { setShiftModal(null); loadTab(); }} />}
      {assignOpen && <AssignModal shifts={shifts} users={users} onClose={() => setAssignOpen(false)} onSaved={() => { setAssignOpen(false); loadDash(); }} />}
      {corrOpen && <CorrectionModal onClose={() => setCorrOpen(false)} onSaved={() => { setCorrOpen(false); loadTab(); loadDash(); }} />}
    </div>
  );
};
