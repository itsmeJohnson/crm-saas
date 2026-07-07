import React, { useCallback, useEffect, useState } from 'react';
import {
  Clock, Plus, Loader2, X, Check, Trash2, Pencil, Sparkles, RefreshCw, CalendarRange,
  BarChart3, UserCheck, Sun, Sunset, Moon, Timer, Users,
} from 'lucide-react';
import {
  shiftApi, Shift, Rotation, RotationMember, ShiftCalendarItem, ShiftReportRow, ShiftDashboard,
} from '../services/shiftApi';
import { userApi } from '../services/userApi';
import { useAuthStore } from '../store/authStore';
import { extractErrorMessage } from '../utils/errors';

const WEEKDAYS = ['mon', 'tue', 'wed', 'thu', 'fri', 'sat', 'sun'];
const SHIFT_TYPES = ['general', 'morning', 'evening', 'night', 'flexible'];
const F = "w-full bg-slate-800/70 border border-slate-700/70 text-slate-200 py-2 px-3 rounded-lg text-sm";

const typeIcon = (t: string) => t === 'morning' ? <Sun className="w-3.5 h-3.5 text-amber-400" />
  : t === 'evening' ? <Sunset className="w-3.5 h-3.5 text-orange-400" />
    : t === 'night' ? <Moon className="w-3.5 h-3.5 text-indigo-300" />
      : t === 'flexible' ? <Timer className="w-3.5 h-3.5 text-emerald-400" />
        : <Clock className="w-3.5 h-3.5 text-brand-400" />;

const StateChip: React.FC<{ state: string }> = ({ state }) => {
  const tone = state === 'working' ? 'bg-emerald-500/10 text-emerald-400 border-emerald-500/20'
    : state === 'weekly_off' ? 'bg-slate-700/40 text-slate-400 border-slate-600/40'
      : 'bg-indigo-500/10 text-indigo-300 border-indigo-500/20';
  return <span className={`px-2 py-0.5 text-[10px] font-semibold rounded-md border ${tone}`}>{state.replace('_', ' ')}</span>;
};

/* ── Shift modal ── */
const ShiftModal: React.FC<{ initial?: Shift | null; onClose: () => void; onSaved: () => void }> = ({ initial, onClose, onSaved }) => {
  const [f, setF] = useState<any>(initial ? { ...initial } : {
    name: '', code: '', shift_type: 'general', start_time: '09:00', end_time: '18:00',
    break_minutes: 60, grace_minutes: 10, working_days: ['mon', 'tue', 'wed', 'thu', 'fri'],
    is_flexible: false, works_on_holidays: false, status: 'active',
  });
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
        name: f.name, code: f.code || undefined, shift_type: f.shift_type,
        start_time: f.start_time, end_time: f.end_time, break_minutes: Number(f.break_minutes) || 0,
        grace_minutes: Number(f.grace_minutes) || 0, working_days: f.working_days,
        is_flexible: f.shift_type === 'flexible' ? true : !!f.is_flexible,
        works_on_holidays: !!f.works_on_holidays, status: f.status,
      };
      if (initial) await shiftApi.update(initial.id, payload);
      else await shiftApi.create(payload);
      onSaved();
    } catch (e: any) { setError(extractErrorMessage(e, 'Failed to save')); } finally { setBusy(false); }
  };
  return (
    <div className="fixed inset-0 z-40 flex items-center justify-center bg-black/50 backdrop-blur-sm p-4">
      <div className="glass-panel border border-slate-800/85 rounded-2xl w-full max-w-md bg-slate-900 max-h-[90vh] overflow-y-auto">
        <div className="flex items-center justify-between p-4 border-b border-slate-800/60">
          <h3 className="text-sm font-semibold text-slate-200 flex items-center gap-2"><Clock className="w-4 h-4 text-brand-400" /> {initial ? 'Edit' : 'New'} shift</h3>
          <button onClick={onClose} className="p-1 text-slate-500 hover:text-slate-300 cursor-pointer"><X className="w-4 h-4" /></button>
        </div>
        <div className="p-4 space-y-3">
          {error && <div className="p-2.5 bg-red-500/10 border border-red-500/20 text-red-400 rounded-lg text-xs">{error}</div>}
          <div className="grid grid-cols-2 gap-2">
            <input value={f.name} onChange={(e) => setF({ ...f, name: e.target.value })} placeholder="Name" className={F} />
            <input value={f.code || ''} onChange={(e) => setF({ ...f, code: e.target.value })} placeholder="Code" className={F} />
          </div>
          <select value={f.shift_type} onChange={(e) => setF({ ...f, shift_type: e.target.value })} className={F}>
            {SHIFT_TYPES.map((t) => <option key={t} value={t}>{t}</option>)}
          </select>
          <div className="grid grid-cols-2 gap-2">
            <label className="text-xs text-slate-400">Start<input type="time" value={f.start_time} onChange={(e) => setF({ ...f, start_time: e.target.value })} className={F} /></label>
            <label className="text-xs text-slate-400">End<input type="time" value={f.end_time} onChange={(e) => setF({ ...f, end_time: e.target.value })} className={F} /></label>
          </div>
          {f.shift_type === 'flexible' && <p className="text-[11px] text-emerald-400/80">Flexible shifts track hours only — no late/early flags.</p>}
          <div className="grid grid-cols-2 gap-2">
            <label className="text-xs text-slate-400">Break (min)<input type="number" value={f.break_minutes} onChange={(e) => setF({ ...f, break_minutes: e.target.value })} className={F} /></label>
            <label className="text-xs text-slate-400">Grace (min)<input type="number" value={f.grace_minutes} onChange={(e) => setF({ ...f, grace_minutes: e.target.value })} className={F} /></label>
          </div>
          <div>
            <p className="text-xs text-slate-400 mb-1">Working days <span className="text-slate-600">(unchecked = weekly off)</span></p>
            <div className="flex gap-1 flex-wrap">
              {WEEKDAYS.map((d) => (
                <button key={d} onClick={() => toggleDay(d)} className={`px-2 py-1 text-[11px] rounded-md border cursor-pointer capitalize ${(f.working_days || []).includes(d) ? 'bg-brand-500/15 text-brand-300 border-brand-500/30' : 'bg-slate-800/40 text-slate-500 border-slate-700/40'}`}>{d}</button>
              ))}
            </div>
          </div>
          <label className="flex items-center gap-2 text-xs text-slate-300 cursor-pointer"><input type="checkbox" checked={!!f.works_on_holidays} onChange={(e) => setF({ ...f, works_on_holidays: e.target.checked })} /> Works on holidays</label>
          <button onClick={save} disabled={busy} className="w-full inline-flex items-center justify-center gap-2 bg-gradient-to-r from-brand-500 to-indigo-500 text-white font-medium py-2 px-4 rounded-lg text-sm disabled:opacity-40 cursor-pointer">
            {busy ? <Loader2 className="w-4 h-4 animate-spin" /> : <Check className="w-4 h-4" />} {initial ? 'Save' : 'Create'}
          </button>
        </div>
      </div>
    </div>
  );
};

/* ── Assign shift modal ── */
const AssignModal: React.FC<{ title: string; users: any[]; onClose: () => void; onAssign: (userIds: string[], anchor: string) => Promise<void> }> = ({ title, users, onClose, onAssign }) => {
  const [pick, setPick] = useState<Set<string>>(new Set());
  const [anchor, setAnchor] = useState('');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const go = async () => {
    if (!pick.size) { setError('Pick at least one user'); return; }
    setBusy(true); setError(null);
    try { await onAssign([...pick], anchor); } catch (e: any) { setError(extractErrorMessage(e, 'Failed')); } finally { setBusy(false); }
  };
  return (
    <div className="fixed inset-0 z-40 flex items-center justify-center bg-black/50 backdrop-blur-sm p-4">
      <div className="glass-panel border border-slate-800/85 rounded-2xl w-full max-w-md bg-slate-900 max-h-[90vh] overflow-y-auto">
        <div className="flex items-center justify-between p-4 border-b border-slate-800/60">
          <h3 className="text-sm font-semibold text-slate-200 flex items-center gap-2"><UserCheck className="w-4 h-4 text-brand-400" /> {title}</h3>
          <button onClick={onClose} className="p-1 text-slate-500 hover:text-slate-300 cursor-pointer"><X className="w-4 h-4" /></button>
        </div>
        <div className="p-4 space-y-3">
          {error && <div className="p-2.5 bg-red-500/10 border border-red-500/20 text-red-400 rounded-lg text-xs">{error}</div>}
          <label className="text-xs text-slate-400 block">Start / anchor date (optional)<input type="date" value={anchor} onChange={(e) => setAnchor(e.target.value)} className={F} /></label>
          <div className="max-h-52 overflow-y-auto space-y-1 border border-slate-800/60 rounded-lg p-2">
            {users.map((u) => (
              <label key={u.id} className="flex items-center gap-2 text-xs text-slate-300 cursor-pointer">
                <input type="checkbox" checked={pick.has(u.id)} onChange={(e) => { const s = new Set(pick); e.target.checked ? s.add(u.id) : s.delete(u.id); setPick(s); }} />
                {`${u.first_name || ''} ${u.last_name || ''}`.trim() || u.email} <span className="text-slate-600">({u.role})</span>
              </label>
            ))}
          </div>
          <button onClick={go} disabled={busy} className="w-full inline-flex items-center justify-center gap-2 bg-gradient-to-r from-brand-500 to-indigo-500 text-white font-medium py-2 px-4 rounded-lg text-sm disabled:opacity-40 cursor-pointer">
            {busy ? <Loader2 className="w-4 h-4 animate-spin" /> : <Check className="w-4 h-4" />} Assign {pick.size ? `(${pick.size})` : ''}
          </button>
        </div>
      </div>
    </div>
  );
};

/* ── Rotation modal ── */
const RotationModal: React.FC<{ initial?: Rotation | null; shifts: Shift[]; onClose: () => void; onSaved: () => void }> = ({ initial, shifts, onClose, onSaved }) => {
  const [f, setF] = useState<any>(initial
    ? { name: initial.name, code: initial.code || '', description: initial.description || '', shift_sequence: initial.shift_sequence, rotation_days: initial.rotation_days, status: initial.status }
    : { name: '', code: '', description: '', shift_sequence: [], rotation_days: 7, status: 'active' });
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const toggleShift = (id: string) => {
    const seq = [...f.shift_sequence];
    const i = seq.indexOf(id);
    i >= 0 ? seq.splice(i, 1) : seq.push(id);
    setF({ ...f, shift_sequence: seq });
  };
  const save = async () => {
    if (!f.name?.trim()) { setError('Name is required'); return; }
    if (f.shift_sequence.length < 2) { setError('Pick at least two shifts to rotate through'); return; }
    setBusy(true); setError(null);
    try {
      const payload = { name: f.name, code: f.code || undefined, description: f.description || undefined, shift_sequence: f.shift_sequence, rotation_days: Number(f.rotation_days) || 7, status: f.status };
      if (initial) await shiftApi.updateRotation(initial.id, payload);
      else await shiftApi.createRotation(payload);
      onSaved();
    } catch (e: any) { setError(extractErrorMessage(e, 'Failed to save')); } finally { setBusy(false); }
  };
  return (
    <div className="fixed inset-0 z-40 flex items-center justify-center bg-black/50 backdrop-blur-sm p-4">
      <div className="glass-panel border border-slate-800/85 rounded-2xl w-full max-w-md bg-slate-900 max-h-[90vh] overflow-y-auto">
        <div className="flex items-center justify-between p-4 border-b border-slate-800/60">
          <h3 className="text-sm font-semibold text-slate-200 flex items-center gap-2"><RefreshCw className="w-4 h-4 text-brand-400" /> {initial ? 'Edit' : 'New'} rotation</h3>
          <button onClick={onClose} className="p-1 text-slate-500 hover:text-slate-300 cursor-pointer"><X className="w-4 h-4" /></button>
        </div>
        <div className="p-4 space-y-3">
          {error && <div className="p-2.5 bg-red-500/10 border border-red-500/20 text-red-400 rounded-lg text-xs">{error}</div>}
          <div className="grid grid-cols-2 gap-2">
            <input value={f.name} onChange={(e) => setF({ ...f, name: e.target.value })} placeholder="Name" className={F} />
            <input value={f.code} onChange={(e) => setF({ ...f, code: e.target.value })} placeholder="Code" className={F} />
          </div>
          <label className="text-xs text-slate-400 block">Days per shift before rotating<input type="number" min={1} value={f.rotation_days} onChange={(e) => setF({ ...f, rotation_days: e.target.value })} className={F} /></label>
          <div>
            <p className="text-xs text-slate-400 mb-1">Rotation sequence <span className="text-slate-600">(tap in order)</span></p>
            <div className="space-y-1 max-h-40 overflow-y-auto">
              {shifts.map((s) => {
                const idx = f.shift_sequence.indexOf(s.id);
                return (
                  <button key={s.id} onClick={() => toggleShift(s.id)} className={`w-full flex items-center justify-between px-2 py-1.5 text-xs rounded-lg border cursor-pointer ${idx >= 0 ? 'bg-brand-500/15 text-brand-200 border-brand-500/30' : 'bg-slate-800/40 text-slate-400 border-slate-700/40'}`}>
                    <span className="flex items-center gap-1.5">{typeIcon(s.shift_type)} {s.name}</span>
                    {idx >= 0 && <span className="text-[10px] bg-brand-500/30 rounded px-1.5">#{idx + 1}</span>}
                  </button>
                );
              })}
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

/* ── Page ── */
export const ShiftManagementPage: React.FC = () => {
  const { user } = useAuthStore();
  const isAdmin = user?.role === 'OrgAdmin';

  const [tab, setTab] = useState<'shifts' | 'rotations' | 'calendar' | 'reports'>('shifts');
  const [dash, setDash] = useState<ShiftDashboard | null>(null);
  const [shifts, setShifts] = useState<Shift[]>([]);
  const [rotations, setRotations] = useState<Rotation[]>([]);
  const [members, setMembers] = useState<Record<string, RotationMember[]>>({});
  const [cal, setCal] = useState<ShiftCalendarItem[]>([]);
  const [reports, setReports] = useState<ShiftReportRow[]>([]);
  const [users, setUsers] = useState<any[]>([]);
  const [shiftModal, setShiftModal] = useState<Shift | null | 'new'>(null);
  const [rotationModal, setRotationModal] = useState<Rotation | null | 'new'>(null);
  const [assignShift, setAssignShift] = useState<Shift | null>(null);
  const [assignRotation, setAssignRotation] = useState<Rotation | null>(null);
  const [error, setError] = useState<string | null>(null);

  const loadDash = useCallback(() => { shiftApi.dashboard().then(setDash).catch(() => {}); }, []);
  useEffect(() => { loadDash(); }, [loadDash]);
  useEffect(() => { if (isAdmin) userApi.getUsers({ is_active: true, limit: 200 }).then(setUsers).catch(() => {}); }, [isAdmin]);

  const loadTab = useCallback(() => {
    setError(null);
    if (tab === 'shifts') shiftApi.list({}).then(setShifts).catch((e) => setError(extractErrorMessage(e, 'Failed')));
    if (tab === 'rotations') { shiftApi.list({ status: 'active' }).then(setShifts).catch(() => {}); shiftApi.listRotations({}).then(setRotations).catch(() => {}); }
    if (tab === 'calendar') {
      const from = new Date();
      const to = new Date(Date.now() + 13 * 86400000);
      shiftApi.calendar(from.toISOString().slice(0, 10), to.toISOString().slice(0, 10)).then(setCal).catch(() => {});
    }
    if (tab === 'reports') {
      const from = new Date(); from.setDate(1);
      const to = new Date();
      shiftApi.reports(from.toISOString().slice(0, 10), to.toISOString().slice(0, 10)).then(setReports).catch(() => {});
    }
  }, [tab]);
  useEffect(() => { loadTab(); }, [loadTab]);

  const loadMembers = async (r: Rotation) => {
    const m = await shiftApi.rotationMembers(r.id);
    setMembers((prev) => ({ ...prev, [r.id]: m }));
  };
  const removeShift = async (s: Shift) => {
    if (!window.confirm(`Delete shift "${s.name}"?`)) return;
    try { await shiftApi.remove(s.id); loadTab(); loadDash(); } catch (e: any) { setError(extractErrorMessage(e, 'Delete failed')); }
  };
  const removeRotation = async (r: Rotation) => {
    if (!window.confirm(`Delete rotation "${r.name}"?`)) return;
    try { await shiftApi.removeRotation(r.id); loadTab(); loadDash(); } catch (e: any) { setError(extractErrorMessage(e, 'Delete failed')); }
  };
  const makePresets = async () => {
    try { const r = await shiftApi.createPresets(); window.alert(`${r.created} preset shift(s) created.`); loadTab(); loadDash(); }
    catch (e: any) { setError(extractErrorMessage(e, 'Failed')); }
  };

  // group calendar by date
  const calByDate: Record<string, ShiftCalendarItem[]> = {};
  cal.forEach((c) => { (calByDate[c.date] ||= []).push(c); });

  return (
    <div className="p-4 sm:p-6 space-y-4">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <h1 className="text-lg font-bold text-slate-100 flex items-center gap-2"><Clock className="w-5 h-5 text-brand-400" /> Shift Management</h1>
      </div>

      {dash && (
        <div className="grid grid-cols-2 sm:grid-cols-5 gap-2">
          {[
            { label: 'Shifts', value: dash.total_shifts },
            { label: 'Flexible', value: dash.flexible_shifts },
            { label: 'Night', value: dash.night_shifts },
            { label: 'Rotations', value: dash.active_rotations },
            { label: 'My shift today', value: dash.my_shift_today?.name || '—' },
          ].map((s) => (
            <div key={s.label} className="glass-panel border border-slate-800/85 rounded-xl p-3">
              <p className="text-[10px] font-semibold text-slate-500 uppercase tracking-wider">{s.label}</p>
              <p className="text-lg font-bold text-slate-100 mt-0.5 truncate">{s.value}</p>
            </div>
          ))}
        </div>
      )}

      {error && <div className="p-3 bg-red-500/10 border border-red-500/20 text-red-400 rounded-lg text-xs">{error}</div>}

      <div className="flex gap-1 border-b border-slate-800/60 flex-wrap">
        {([['shifts', 'Shifts', Clock], ['rotations', 'Rotations', RefreshCw], ['calendar', 'Shift Calendar', CalendarRange], ['reports', 'Reports', BarChart3]] as const).map(([key, label, Icon]) => (
          <button key={key} onClick={() => setTab(key)} className={`px-3 py-1.5 text-xs font-medium inline-flex items-center gap-1.5 border-b-2 -mb-px cursor-pointer ${tab === key ? 'border-brand-500 text-brand-300' : 'border-transparent text-slate-500 hover:text-slate-300'}`}>
            <Icon className="w-3.5 h-3.5" /> {label}
          </button>
        ))}
      </div>

      {tab === 'shifts' && (
        <div className="space-y-3">
          {isAdmin && (
            <div className="flex items-center gap-2">
              <button onClick={() => setShiftModal('new')} className="inline-flex items-center gap-1.5 bg-gradient-to-r from-brand-500 to-indigo-500 text-white text-xs font-medium py-1.5 px-3 rounded-lg cursor-pointer"><Plus className="w-3.5 h-3.5" /> New shift</button>
              <button onClick={makePresets} className="inline-flex items-center gap-1.5 border border-slate-800 text-slate-300 text-xs py-1.5 px-3 rounded-lg cursor-pointer"><Sparkles className="w-3.5 h-3.5" /> Create presets (Morning/Evening/Night/Flexible)</button>
            </div>
          )}
          <div className="space-y-2">
            {shifts.map((s) => (
              <div key={s.id} className="p-3 rounded-xl border border-slate-800/85 bg-slate-950/30 flex items-center justify-between gap-2">
                <div>
                  <p className="text-sm text-slate-200 font-medium flex items-center gap-1.5">{typeIcon(s.shift_type)} {s.name} {s.code && <span className="text-[10px] text-slate-600">{s.code}</span>}
                    {s.is_flexible && <span className="text-[10px] text-emerald-400">flexible</span>}
                    {s.status === 'archived' && <span className="text-[10px] text-slate-500">archived</span>}
                  </p>
                  <p className="text-[11px] text-slate-500 mt-0.5">{s.shift_type} · {s.start_time}–{s.end_time} · {s.break_minutes}m break · {s.grace_minutes}m grace · {(s.working_days || []).join(', ')}{s.works_on_holidays ? ' · works holidays' : ''}</p>
                </div>
                {isAdmin && (
                  <div className="flex items-center gap-1">
                    <button onClick={() => setAssignShift(s)} title="Assign" className="p-1.5 text-slate-500 hover:text-brand-300 cursor-pointer"><UserCheck className="w-4 h-4" /></button>
                    <button onClick={() => setShiftModal(s)} className="p-1.5 text-slate-500 hover:text-slate-300 cursor-pointer"><Pencil className="w-4 h-4" /></button>
                    <button onClick={() => removeShift(s)} className="p-1.5 text-slate-500 hover:text-red-400 cursor-pointer"><Trash2 className="w-4 h-4" /></button>
                  </div>
                )}
              </div>
            ))}
            {!shifts.length && <p className="text-xs text-slate-500 py-6 text-center">No shifts yet.</p>}
          </div>
        </div>
      )}

      {tab === 'rotations' && (
        <div className="space-y-3">
          {isAdmin && <button onClick={() => setRotationModal('new')} className="inline-flex items-center gap-1.5 bg-gradient-to-r from-brand-500 to-indigo-500 text-white text-xs font-medium py-1.5 px-3 rounded-lg cursor-pointer"><Plus className="w-3.5 h-3.5" /> New rotation</button>}
          <div className="space-y-2">
            {rotations.map((r) => (
              <div key={r.id} className="p-3 rounded-xl border border-slate-800/85 bg-slate-950/30">
                <div className="flex items-center justify-between gap-2">
                  <div>
                    <p className="text-sm text-slate-200 font-medium flex items-center gap-1.5"><RefreshCw className="w-3.5 h-3.5 text-brand-400" /> {r.name} <span className="text-[10px] text-slate-600">every {r.rotation_days}d</span></p>
                    <p className="text-[11px] text-slate-500 mt-0.5">{r.shift_names.join(' → ')} · {r.member_count} member(s)</p>
                  </div>
                  {isAdmin && (
                    <div className="flex items-center gap-1">
                      <button onClick={() => setAssignRotation(r)} title="Assign members" className="p-1.5 text-slate-500 hover:text-brand-300 cursor-pointer"><Users className="w-4 h-4" /></button>
                      <button onClick={() => loadMembers(r)} title="Show members" className="p-1.5 text-slate-500 hover:text-slate-300 cursor-pointer text-[10px]">members</button>
                      <button onClick={() => setRotationModal(r)} className="p-1.5 text-slate-500 hover:text-slate-300 cursor-pointer"><Pencil className="w-4 h-4" /></button>
                      <button onClick={() => removeRotation(r)} className="p-1.5 text-slate-500 hover:text-red-400 cursor-pointer"><Trash2 className="w-4 h-4" /></button>
                    </div>
                  )}
                </div>
                {members[r.id] && (
                  <ul className="mt-2 space-y-1 border-t border-slate-800/50 pt-2">
                    {members[r.id].map((m) => (
                      <li key={m.id} className="flex items-center justify-between text-[11px] text-slate-400">
                        <span>{m.user_name} <span className="text-slate-600">· from {m.anchor_date}</span></span>
                        {isAdmin && <button onClick={async () => { await shiftApi.removeRotationMember(r.id, m.user_id); loadMembers(r); loadTab(); }} className="text-slate-600 hover:text-red-400 cursor-pointer"><X className="w-3 h-3" /></button>}
                      </li>
                    ))}
                    {!members[r.id].length && <li className="text-[11px] text-slate-500">No members.</li>}
                  </ul>
                )}
              </div>
            ))}
            {!rotations.length && <p className="text-xs text-slate-500 py-6 text-center">No rotations yet.</p>}
          </div>
        </div>
      )}

      {tab === 'calendar' && (
        <div className="space-y-3">
          {Object.keys(calByDate).sort().map((d) => (
            <div key={d}>
              <p className="text-xs font-semibold text-slate-400 mb-1">{new Date(d).toLocaleDateString(undefined, { weekday: 'short', month: 'short', day: 'numeric' })}</p>
              <div className="space-y-1">
                {calByDate[d].map((c, i) => (
                  <div key={`${c.user_id}-${i}`} className="flex items-center justify-between p-2 bg-slate-950/40 border border-slate-800/60 rounded-lg text-xs">
                    <span className="text-slate-200 flex items-center gap-2">
                      {c.shift_type ? typeIcon(c.shift_type) : <Clock className="w-3.5 h-3.5 text-slate-500" />}
                      {c.user_name}{c.shift_name ? ` · ${c.shift_name} (${c.start_time}–${c.end_time})` : ''}
                    </span>
                    <StateChip state={c.state} />
                  </div>
                ))}
              </div>
            </div>
          ))}
          {!cal.length && <p className="text-xs text-slate-500 py-6 text-center">No scheduled shifts in the next two weeks.</p>}
        </div>
      )}

      {tab === 'reports' && (
        <div className="overflow-x-auto">
          <table className="w-full text-xs">
            <thead><tr className="text-left text-[10px] text-slate-500 uppercase">
              <th className="py-2 pr-2">Shift</th><th className="py-2 pr-2">Assigned</th><th className="py-2 pr-2">Records</th><th className="py-2 pr-2">Present</th><th className="py-2 pr-2">Late</th><th className="py-2 pr-2">Early</th><th className="py-2 pr-2">Leave</th><th className="py-2">Hours</th>
            </tr></thead>
            <tbody>
              {reports.map((r) => (
                <tr key={r.shift_id} className="border-t border-slate-800/50 text-slate-300">
                  <td className="py-1.5 pr-2 flex items-center gap-1.5">{typeIcon(r.shift_type)} {r.shift_name}</td>
                  <td className="py-1.5 pr-2">{r.assigned}</td>
                  <td className="py-1.5 pr-2">{r.records}</td>
                  <td className="py-1.5 pr-2">{r.present}</td>
                  <td className="py-1.5 pr-2">{r.late}</td>
                  <td className="py-1.5 pr-2">{r.early_logout}</td>
                  <td className="py-1.5 pr-2">{r.on_leave}</td>
                  <td className="py-1.5">{r.worked_hours}h</td>
                </tr>
              ))}
            </tbody>
          </table>
          {!reports.length && <p className="text-xs text-slate-500 py-6 text-center">No shift attendance this month.</p>}
        </div>
      )}

      {shiftModal && <ShiftModal initial={shiftModal === 'new' ? null : shiftModal} onClose={() => setShiftModal(null)} onSaved={() => { setShiftModal(null); loadTab(); loadDash(); }} />}
      {rotationModal && <RotationModal initial={rotationModal === 'new' ? null : rotationModal} shifts={shifts} onClose={() => setRotationModal(null)} onSaved={() => { setRotationModal(null); loadTab(); loadDash(); }} />}
      {assignShift && <AssignModal title={`Assign ${assignShift.name}`} users={users} onClose={() => setAssignShift(null)}
        onAssign={async (ids, anchor) => { await shiftApi.assign({ shift_id: assignShift.id, user_ids: ids, start_date: anchor || undefined }); setAssignShift(null); loadDash(); }} />}
      {assignRotation && <AssignModal title={`Assign to ${assignRotation.name}`} users={users} onClose={() => setAssignRotation(null)}
        onAssign={async (ids, anchor) => { await shiftApi.assignRotation(assignRotation.id, { user_ids: ids, anchor_date: anchor || undefined }); setAssignRotation(null); loadTab(); loadDash(); }} />}
    </div>
  );
};
