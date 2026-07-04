import React, { useCallback, useEffect, useState } from 'react';
import {
  CalendarDays, Plus, Loader2, X, Check, Trash2, Pencil, Plane, Home, ClipboardCheck,
  CalendarRange, Umbrella, BarChart3, Wallet,
} from 'lucide-react';
import { leaveApi, LeaveType, BalanceRow, LeaveRequest, LeaveCalendarItem, LeaveDashboard, LeaveReport } from '../services/leaveApi';
import { calendarApi, Holiday } from '../services/calendarApi';
import { useAuthStore } from '../store/authStore';
import { extractErrorMessage } from '../utils/errors';

const F = "w-full bg-slate-800/70 border border-slate-700/70 text-slate-200 py-2 px-3 rounded-lg text-sm";
const StatusChip: React.FC<{ status: string }> = ({ status }) => {
  const tone = status === 'approved' ? 'bg-emerald-500/10 text-emerald-400 border-emerald-500/20'
    : status === 'pending' ? 'bg-amber-500/10 text-amber-400 border-amber-500/20'
      : status === 'rejected' ? 'bg-red-500/10 text-red-400 border-red-500/20'
        : status === 'holiday' ? 'bg-indigo-500/10 text-indigo-300 border-indigo-500/20'
          : 'bg-slate-700/40 text-slate-400 border-slate-600/40';
  return <span className={`px-2 py-0.5 text-[10px] font-semibold rounded-md border ${tone}`}>{status}</span>;
};

/* ── Apply modal ── */
const ApplyModal: React.FC<{ types: LeaveType[]; onClose: () => void; onSaved: () => void }> = ({ types, onClose, onSaved }) => {
  const [f, setF] = useState<any>({ request_type: 'leave', leave_type_id: types[0]?.id || '', start_date: '', end_date: '', is_half_day: false, half_day_period: 'first_half', reason: '' });
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const save = async () => {
    if (!f.start_date || !f.end_date) { setError('Start and end dates are required'); return; }
    if (f.request_type === 'leave' && !f.leave_type_id) { setError('Select a leave type'); return; }
    setBusy(true); setError(null);
    try {
      await leaveApi.apply({
        request_type: f.request_type,
        leave_type_id: f.request_type === 'leave' ? f.leave_type_id : undefined,
        start_date: f.start_date, end_date: f.is_half_day ? f.start_date : f.end_date,
        is_half_day: f.is_half_day, half_day_period: f.is_half_day ? f.half_day_period : undefined,
        reason: f.reason || undefined,
      });
      onSaved();
    } catch (e: any) { setError(extractErrorMessage(e, 'Failed to apply')); } finally { setBusy(false); }
  };
  return (
    <div className="fixed inset-0 z-40 flex items-center justify-center bg-black/50 backdrop-blur-sm p-4">
      <div className="glass-panel border border-slate-800/85 rounded-2xl w-full max-w-md bg-slate-900 max-h-[90vh] overflow-y-auto">
        <div className="flex items-center justify-between p-4 border-b border-slate-800/60">
          <h3 className="text-sm font-semibold text-slate-200 flex items-center gap-2"><Plane className="w-4 h-4 text-brand-400" /> Apply {f.request_type === 'wfh' ? 'WFH' : 'leave'}</h3>
          <button onClick={onClose} className="p-1 text-slate-500 hover:text-slate-300 cursor-pointer"><X className="w-4 h-4" /></button>
        </div>
        <div className="p-4 space-y-3">
          {error && <div className="p-2.5 bg-red-500/10 border border-red-500/20 text-red-400 rounded-lg text-xs">{error}</div>}
          <div className="flex gap-2">
            {(['leave', 'wfh'] as const).map((rt) => (
              <button key={rt} onClick={() => setF({ ...f, request_type: rt })} className={`flex-1 py-1.5 text-xs rounded-lg border cursor-pointer inline-flex items-center justify-center gap-1.5 ${f.request_type === rt ? 'bg-brand-500/15 text-brand-300 border-brand-500/30' : 'bg-slate-800/40 text-slate-400 border-slate-700/40'}`}>
                {rt === 'leave' ? <Plane className="w-3.5 h-3.5" /> : <Home className="w-3.5 h-3.5" />} {rt === 'leave' ? 'Leave' : 'Work from home'}
              </button>
            ))}
          </div>
          {f.request_type === 'leave' && (
            <select value={f.leave_type_id} onChange={(e) => setF({ ...f, leave_type_id: e.target.value })} className={F}>
              <option value="">Select leave type…</option>
              {types.map((t) => <option key={t.id} value={t.id}>{t.name}{t.is_paid ? '' : ' (unpaid)'}</option>)}
            </select>
          )}
          <label className="flex items-center gap-2 text-xs text-slate-300 cursor-pointer">
            <input type="checkbox" checked={f.is_half_day} onChange={(e) => setF({ ...f, is_half_day: e.target.checked })} /> Half day
          </label>
          <div className="grid grid-cols-2 gap-2">
            <label className="text-xs text-slate-400">Start<input type="date" value={f.start_date} onChange={(e) => setF({ ...f, start_date: e.target.value })} className={F} /></label>
            {!f.is_half_day
              ? <label className="text-xs text-slate-400">End<input type="date" value={f.end_date} onChange={(e) => setF({ ...f, end_date: e.target.value })} className={F} /></label>
              : <label className="text-xs text-slate-400">Period<select value={f.half_day_period} onChange={(e) => setF({ ...f, half_day_period: e.target.value })} className={F}><option value="first_half">First half</option><option value="second_half">Second half</option></select></label>}
          </div>
          <textarea value={f.reason} onChange={(e) => setF({ ...f, reason: e.target.value })} rows={2} placeholder="Reason" className={F} />
          <button onClick={save} disabled={busy} className="w-full inline-flex items-center justify-center gap-2 bg-gradient-to-r from-brand-500 to-indigo-500 text-white font-medium py-2 px-4 rounded-lg text-sm disabled:opacity-40 cursor-pointer">
            {busy ? <Loader2 className="w-4 h-4 animate-spin" /> : <Check className="w-4 h-4" />} Submit
          </button>
        </div>
      </div>
    </div>
  );
};

/* ── Leave type modal ── */
const TypeModal: React.FC<{ initial?: LeaveType | null; onClose: () => void; onSaved: () => void }> = ({ initial, onClose, onSaved }) => {
  const [f, setF] = useState<any>(initial ? { ...initial } : {
    name: '', code: '', annual_quota: 12, is_paid: true, allow_half_day: true, requires_approval: true, deducts_balance: true, max_consecutive_days: '', color: '', status: 'active',
  });
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const save = async () => {
    if (!f.name?.trim()) { setError('Name is required'); return; }
    setBusy(true); setError(null);
    try {
      const payload = {
        name: f.name, code: f.code || undefined, is_paid: !!f.is_paid, annual_quota: Number(f.annual_quota) || 0,
        allow_half_day: !!f.allow_half_day, requires_approval: !!f.requires_approval, deducts_balance: !!f.deducts_balance,
        max_consecutive_days: f.max_consecutive_days ? Number(f.max_consecutive_days) : null, color: f.color || undefined, status: f.status,
      };
      if (initial) await leaveApi.updateType(initial.id, payload);
      else await leaveApi.createType(payload);
      onSaved();
    } catch (e: any) { setError(extractErrorMessage(e, 'Failed to save')); } finally { setBusy(false); }
  };
  return (
    <div className="fixed inset-0 z-40 flex items-center justify-center bg-black/50 backdrop-blur-sm p-4">
      <div className="glass-panel border border-slate-800/85 rounded-2xl w-full max-w-md bg-slate-900 max-h-[90vh] overflow-y-auto">
        <div className="flex items-center justify-between p-4 border-b border-slate-800/60">
          <h3 className="text-sm font-semibold text-slate-200 flex items-center gap-2"><CalendarDays className="w-4 h-4 text-brand-400" /> {initial ? 'Edit' : 'New'} leave type</h3>
          <button onClick={onClose} className="p-1 text-slate-500 hover:text-slate-300 cursor-pointer"><X className="w-4 h-4" /></button>
        </div>
        <div className="p-4 space-y-3">
          {error && <div className="p-2.5 bg-red-500/10 border border-red-500/20 text-red-400 rounded-lg text-xs">{error}</div>}
          <div className="grid grid-cols-2 gap-2">
            <input value={f.name} onChange={(e) => setF({ ...f, name: e.target.value })} placeholder="Name" className={F} />
            <input value={f.code || ''} onChange={(e) => setF({ ...f, code: e.target.value })} placeholder="Code" className={F} />
          </div>
          <div className="grid grid-cols-2 gap-2">
            <label className="text-xs text-slate-400">Annual quota (days)<input type="number" value={f.annual_quota} onChange={(e) => setF({ ...f, annual_quota: e.target.value })} className={F} /></label>
            <label className="text-xs text-slate-400">Max consecutive<input type="number" value={f.max_consecutive_days || ''} onChange={(e) => setF({ ...f, max_consecutive_days: e.target.value })} className={F} /></label>
          </div>
          <div className="space-y-1.5">
            {[['is_paid', 'Paid'], ['allow_half_day', 'Allow half day'], ['requires_approval', 'Requires approval'], ['deducts_balance', 'Deducts balance']].map(([k, label]) => (
              <label key={k} className="flex items-center gap-2 text-xs text-slate-300 cursor-pointer">
                <input type="checkbox" checked={!!f[k]} onChange={(e) => setF({ ...f, [k]: e.target.checked })} /> {label}
              </label>
            ))}
          </div>
          <button onClick={save} disabled={busy} className="w-full inline-flex items-center justify-center gap-2 bg-gradient-to-r from-brand-500 to-indigo-500 text-white font-medium py-2 px-4 rounded-lg text-sm disabled:opacity-40 cursor-pointer">
            {busy ? <Loader2 className="w-4 h-4 animate-spin" /> : <Check className="w-4 h-4" />} {initial ? 'Save' : 'Create'}
          </button>
        </div>
      </div>
    </div>
  );
};

/* ── Holiday tab (reuses calendarApi) ── */
const HolidayPanel: React.FC<{ canManage: boolean }> = ({ canManage }) => {
  const [rows, setRows] = useState<Holiday[]>([]);
  const [f, setF] = useState({ name: '', holiday_date: '', recurring_annual: false });
  const [error, setError] = useState<string | null>(null);
  const load = useCallback(() => { calendarApi.listHolidays().then(setRows).catch(() => {}); }, []);
  useEffect(() => { load(); }, [load]);
  const add = async () => {
    if (!f.name.trim() || !f.holiday_date) { setError('Name and date are required'); return; }
    setError(null);
    try { await calendarApi.createHoliday(f); setF({ name: '', holiday_date: '', recurring_annual: false }); load(); }
    catch (e: any) { setError(extractErrorMessage(e, 'Failed to add holiday')); }
  };
  return (
    <div className="space-y-3">
      {error && <div className="p-2.5 bg-red-500/10 border border-red-500/20 text-red-400 rounded-lg text-xs">{error}</div>}
      {canManage && (
        <div className="p-2 bg-slate-950/40 border border-slate-800/60 rounded-lg grid grid-cols-4 gap-2">
          <input value={f.name} onChange={(e) => setF({ ...f, name: e.target.value })} placeholder="Holiday name" className="bg-slate-800/70 border border-slate-700/70 text-slate-200 py-1.5 px-2 rounded-lg text-xs col-span-2" />
          <input type="date" value={f.holiday_date} onChange={(e) => setF({ ...f, holiday_date: e.target.value })} className="bg-slate-800/70 border border-slate-700/70 text-slate-200 py-1.5 px-2 rounded-lg text-xs" />
          <button onClick={add} className="text-xs text-emerald-400 cursor-pointer inline-flex items-center justify-center gap-1"><Plus className="w-3.5 h-3.5" /> Add</button>
          <label className="flex items-center gap-1.5 text-[11px] text-slate-400 cursor-pointer col-span-4"><input type="checkbox" checked={f.recurring_annual} onChange={(e) => setF({ ...f, recurring_annual: e.target.checked })} /> Repeats every year</label>
        </div>
      )}
      <ul className="space-y-1.5">
        {rows.map((h) => (
          <li key={h.id} className="flex items-center justify-between p-2 bg-slate-950/40 border border-slate-800/60 rounded-lg text-xs">
            <span className="text-slate-200 flex items-center gap-2"><Umbrella className="w-3.5 h-3.5 text-indigo-300" /> {h.name} <span className="text-slate-500">{h.holiday_date}{h.recurring_annual ? ' · annual' : ''}</span></span>
            {canManage && <button onClick={async () => { await calendarApi.deleteHoliday(h.id); load(); }} className="text-slate-600 hover:text-red-400 cursor-pointer"><Trash2 className="w-3.5 h-3.5" /></button>}
          </li>
        ))}
        {!rows.length && <p className="text-xs text-slate-500 py-4 text-center">No holidays configured.</p>}
      </ul>
    </div>
  );
};

/* ── Page ── */
export const LeavePage: React.FC = () => {
  const { user } = useAuthStore();
  const isManager = user?.role === 'OrgAdmin' || user?.role === 'Manager';
  const isAdmin = user?.role === 'OrgAdmin';

  const [tab, setTab] = useState<'my' | 'approvals' | 'calendar' | 'holidays' | 'types' | 'report'>('my');
  const [dash, setDash] = useState<LeaveDashboard | null>(null);
  const [types, setTypes] = useState<LeaveType[]>([]);
  const [balances, setBalances] = useState<BalanceRow[]>([]);
  const [myRequests, setMyRequests] = useState<LeaveRequest[]>([]);
  const [approvals, setApprovals] = useState<LeaveRequest[]>([]);
  const [calItems, setCalItems] = useState<LeaveCalendarItem[]>([]);
  const [report, setReport] = useState<LeaveReport | null>(null);
  const [applyOpen, setApplyOpen] = useState(false);
  const [typeModal, setTypeModal] = useState<LeaveType | null | 'new'>(null);
  const [error, setError] = useState<string | null>(null);

  const loadDash = useCallback(() => { leaveApi.dashboard().then(setDash).catch(() => {}); }, []);
  useEffect(() => { loadDash(); leaveApi.listTypes({ status: 'active' }).then(setTypes).catch(() => {}); }, [loadDash]);

  const loadTab = useCallback(() => {
    setError(null);
    if (tab === 'my') {
      leaveApi.balances().then(setBalances).catch(() => {});
      leaveApi.listRequests({ scope: 'mine' }).then((r) => setMyRequests(r.items)).catch((e) => setError(extractErrorMessage(e, 'Failed')));
    }
    if (tab === 'approvals') leaveApi.listRequests({ scope: 'team', status: 'pending' }).then((r) => setApprovals(r.items)).catch(() => {});
    if (tab === 'types') leaveApi.listTypes({}).then(setTypes).catch(() => {});
    if (tab === 'calendar') {
      const from = new Date(); from.setDate(1);
      const to = new Date(from.getFullYear(), from.getMonth() + 1, 0);
      leaveApi.calendar(from.toISOString().slice(0, 10), to.toISOString().slice(0, 10)).then(setCalItems).catch(() => {});
    }
    if (tab === 'report') leaveApi.report(new Date().getFullYear()).then(setReport).catch(() => {});
  }, [tab]);
  useEffect(() => { loadTab(); }, [loadTab]);

  const review = async (r: LeaveRequest, approve: boolean) => {
    try { await leaveApi.review(r.id, approve); loadTab(); loadDash(); }
    catch (e: any) { setError(extractErrorMessage(e, 'Review failed')); }
  };
  const cancel = async (r: LeaveRequest) => {
    if (!window.confirm('Cancel this request?')) return;
    try { await leaveApi.cancel(r.id); loadTab(); loadDash(); }
    catch (e: any) { setError(extractErrorMessage(e, 'Cancel failed')); }
  };
  const removeType = async (t: LeaveType) => {
    if (!window.confirm(`Delete leave type "${t.name}"?`)) return;
    try { await leaveApi.deleteType(t.id); loadTab(); }
    catch (e: any) { setError(extractErrorMessage(e, 'Delete failed')); }
  };

  const RequestRow: React.FC<{ r: LeaveRequest; showUser?: boolean; actions?: React.ReactNode }> = ({ r, showUser, actions }) => (
    <div className="p-3 rounded-xl border border-slate-800/85 bg-slate-950/30">
      <div className="flex items-center justify-between gap-2">
        <div className="flex items-center gap-2 min-w-0">
          {r.request_type === 'wfh' ? <Home className="w-3.5 h-3.5 text-brand-400 shrink-0" /> : <Plane className="w-3.5 h-3.5 text-brand-400 shrink-0" />}
          <p className="text-sm text-slate-200 truncate">
            {showUser ? `${r.user_name} · ` : ''}{r.request_type === 'wfh' ? 'WFH' : r.leave_type_name}
            <span className="text-slate-500"> · {r.start_date}{r.end_date !== r.start_date ? ` → ${r.end_date}` : ''}{r.is_half_day ? ' (½)' : ''} · {r.day_count}d</span>
          </p>
        </div>
        <div className="flex items-center gap-2 shrink-0">
          <StatusChip status={r.status} />
          {actions}
        </div>
      </div>
      {r.reason && <p className="text-[11px] text-slate-500 mt-1">{r.reason}</p>}
    </div>
  );

  return (
    <div className="p-4 sm:p-6 space-y-4">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <h1 className="text-lg font-bold text-slate-100 flex items-center gap-2"><CalendarDays className="w-5 h-5 text-brand-400" /> Leave</h1>
        <button onClick={() => setApplyOpen(true)} className="inline-flex items-center gap-1.5 bg-gradient-to-r from-brand-500 to-indigo-500 text-white text-xs font-medium py-1.5 px-3 rounded-lg cursor-pointer"><Plus className="w-3.5 h-3.5" /> Apply</button>
      </div>

      {dash && (
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-2">
          {[
            { label: 'Available days', value: dash.my_available_days, icon: Wallet },
            { label: 'My pending', value: dash.my_pending, icon: CalendarRange },
            ...(isManager ? [{ label: 'To approve', value: dash.pending_approvals, icon: ClipboardCheck }] : []),
            { label: 'On leave today', value: dash.on_leave_today.length, icon: Plane },
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
        {([['my', 'My Leave', CalendarDays], ...(isManager ? [['approvals', 'Approvals', ClipboardCheck]] as const : []), ['calendar', 'Leave Calendar', CalendarRange], ['holidays', 'Holiday Calendar', Umbrella], ...(isAdmin ? [['types', 'Leave Types', CalendarDays]] as const : []), ['report', 'Reports', BarChart3]] as const).map(([key, label, Icon]) => (
          <button key={key} onClick={() => setTab(key as any)}
                  className={`px-3 py-1.5 text-xs font-medium inline-flex items-center gap-1.5 border-b-2 -mb-px cursor-pointer ${tab === key ? 'border-brand-500 text-brand-300' : 'border-transparent text-slate-500 hover:text-slate-300'}`}>
            <Icon className="w-3.5 h-3.5" /> {label}
          </button>
        ))}
      </div>

      {tab === 'my' && (
        <div className="space-y-4">
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-2">
            {balances.map((b) => (
              <div key={b.leave_type_id} className="glass-panel border border-slate-800/85 rounded-xl p-3">
                <div className="flex items-center justify-between">
                  <p className="text-xs font-semibold text-slate-200">{b.leave_type_name}</p>
                  <span className="text-[10px] text-slate-500">{b.year}</span>
                </div>
                <p className="text-2xl font-bold text-slate-100 mt-1">{b.available}<span className="text-xs text-slate-500"> / {b.allocated + b.carried_forward}</span></p>
                <p className="text-[10px] text-slate-500 mt-0.5">{b.used} used · {b.pending} pending</p>
              </div>
            ))}
            {!balances.length && <p className="text-xs text-slate-500">No leave balances allocated yet.</p>}
          </div>
          <div className="space-y-2">
            {myRequests.map((r) => (
              <RequestRow key={r.id} r={r} actions={['pending', 'approved'].includes(r.status)
                ? <button onClick={() => cancel(r)} className="text-xs text-red-400 cursor-pointer">Cancel</button> : undefined} />
            ))}
            {!myRequests.length && <p className="text-xs text-slate-500 py-4 text-center">No requests yet.</p>}
          </div>
        </div>
      )}

      {tab === 'approvals' && (
        <div className="space-y-2">
          {approvals.map((r) => (
            <RequestRow key={r.id} r={r} showUser actions={
              <>
                <button onClick={() => review(r, true)} className="text-xs text-emerald-400 cursor-pointer inline-flex items-center gap-1"><Check className="w-3.5 h-3.5" /> Approve</button>
                <button onClick={() => review(r, false)} className="text-xs text-red-400 cursor-pointer inline-flex items-center gap-1"><X className="w-3.5 h-3.5" /> Reject</button>
              </>
            } />
          ))}
          {!approvals.length && <p className="text-xs text-slate-500 py-6 text-center">No pending approvals.</p>}
        </div>
      )}

      {tab === 'calendar' && (
        <div className="space-y-1.5">
          {calItems.map((i) => (
            <div key={i.id} className="flex items-center justify-between p-2 bg-slate-950/40 border border-slate-800/60 rounded-lg text-xs">
              <span className="text-slate-200 flex items-center gap-2">
                {i.type === 'holiday' ? <Umbrella className="w-3.5 h-3.5 text-indigo-300" /> : i.request_type === 'wfh' ? <Home className="w-3.5 h-3.5 text-brand-400" /> : <Plane className="w-3.5 h-3.5 text-brand-400" />}
                {i.type === 'holiday' ? i.leave_type_name || 'Holiday' : `${i.user_name} · ${i.request_type === 'wfh' ? 'WFH' : i.leave_type_name}`}
                <span className="text-slate-500">{i.start_date}{i.end_date !== i.start_date ? ` → ${i.end_date}` : ''}</span>
              </span>
              <StatusChip status={i.status} />
            </div>
          ))}
          {!calItems.length && <p className="text-xs text-slate-500 py-6 text-center">Nothing this month.</p>}
        </div>
      )}

      {tab === 'holidays' && <HolidayPanel canManage={isManager} />}

      {tab === 'types' && isAdmin && (
        <div className="space-y-3">
          <button onClick={() => setTypeModal('new')} className="inline-flex items-center gap-1.5 bg-gradient-to-r from-brand-500 to-indigo-500 text-white text-xs font-medium py-1.5 px-3 rounded-lg cursor-pointer"><Plus className="w-3.5 h-3.5" /> New leave type</button>
          <div className="space-y-2">
            {types.map((t) => (
              <div key={t.id} className="p-3 rounded-xl border border-slate-800/85 bg-slate-950/30 flex items-center justify-between gap-2">
                <div>
                  <p className="text-sm text-slate-200 font-medium">{t.name} {t.code && <span className="text-[10px] text-slate-600">{t.code}</span>} {!t.is_paid && <span className="text-[10px] text-amber-400">unpaid</span>}</p>
                  <p className="text-[11px] text-slate-500 mt-0.5">{t.annual_quota} days/yr · {t.allow_half_day ? 'half-day ok' : 'full days'} · {t.requires_approval ? 'needs approval' : 'auto-approved'} · {t.status}</p>
                </div>
                <div className="flex items-center gap-1">
                  <button onClick={() => setTypeModal(t)} className="p-1.5 text-slate-500 hover:text-slate-300 cursor-pointer"><Pencil className="w-4 h-4" /></button>
                  <button onClick={() => removeType(t)} className="p-1.5 text-slate-500 hover:text-red-400 cursor-pointer"><Trash2 className="w-4 h-4" /></button>
                </div>
              </div>
            ))}
            {!types.length && <p className="text-xs text-slate-500 py-4 text-center">No leave types yet.</p>}
          </div>
        </div>
      )}

      {tab === 'report' && (
        <div className="overflow-x-auto">
          <table className="w-full text-xs">
            <thead><tr className="text-left text-[10px] text-slate-500 uppercase">
              <th className="py-2 pr-2">Employee</th><th className="py-2 pr-2">Used</th><th className="py-2 pr-2">Pending</th><th className="py-2">Available</th>
            </tr></thead>
            <tbody>
              {report?.rows.map((r) => (
                <tr key={r.user_id} className="border-t border-slate-800/50 text-slate-300">
                  <td className="py-1.5 pr-2">{r.name}</td>
                  <td className="py-1.5 pr-2">{r.used}</td>
                  <td className="py-1.5 pr-2">{r.pending}</td>
                  <td className="py-1.5">{r.available}</td>
                </tr>
              ))}
            </tbody>
          </table>
          {!report?.rows.length && <p className="text-xs text-slate-500 py-6 text-center">No data for this year.</p>}
        </div>
      )}

      {applyOpen && <ApplyModal types={types.filter((t) => t.status === 'active')} onClose={() => setApplyOpen(false)} onSaved={() => { setApplyOpen(false); loadTab(); loadDash(); }} />}
      {typeModal && <TypeModal initial={typeModal === 'new' ? null : typeModal} onClose={() => setTypeModal(null)} onSaved={() => { setTypeModal(null); loadTab(); }} />}
    </div>
  );
};
