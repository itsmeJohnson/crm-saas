import React, { useCallback, useEffect, useState } from 'react';
import {
  CheckCircle2, Plus, Loader2, X, Check, Trash2, Clock, Inbox, GitBranch, UserCheck,
  History as HistoryIcon, BarChart3, AlertTriangle, Send,
} from 'lucide-react';
import {
  approvalApi, Chain, ApprovalRequest, HistoryRow, Delegation, ApprovalDashboard, ApprovalReport,
  APPROVAL_TYPES, APPROVER_ROLES,
} from '../services/approvalApi';
import { userApi } from '../services/userApi';
import { useAuthStore } from '../store/authStore';
import { extractErrorMessage } from '../utils/errors';

const F = "w-full bg-slate-800/70 border border-slate-700/70 text-slate-200 py-2 px-3 rounded-lg text-sm";
const StatusChip: React.FC<{ s: string }> = ({ s }) => {
  const tone = s === 'approved' ? 'bg-emerald-500/10 text-emerald-400 border-emerald-500/20'
    : s === 'pending' ? 'bg-amber-500/10 text-amber-400 border-amber-500/20'
      : s === 'rejected' ? 'bg-red-500/10 text-red-400 border-red-500/20'
        : 'bg-slate-700/40 text-slate-400 border-slate-600/40';
  return <span className={`px-2 py-0.5 text-[10px] font-semibold rounded-md border ${tone}`}>{s}</span>;
};

/* ── New request modal ── */
const RequestModal: React.FC<{ onClose: () => void; onSaved: () => void }> = ({ onClose, onSaved }) => {
  const [f, setF] = useState<any>({ request_type: 'expense', title: '', description: '', amount: '' });
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const save = async () => {
    if (!f.title.trim()) { setError('Title is required'); return; }
    setBusy(true); setError(null);
    try {
      await approvalApi.create({ request_type: f.request_type, title: f.title, description: f.description || undefined, amount: f.amount ? Number(f.amount) : undefined });
      onSaved();
    } catch (e: any) { setError(extractErrorMessage(e, 'Failed to submit')); } finally { setBusy(false); }
  };
  return (
    <div className="fixed inset-0 z-40 flex items-center justify-center bg-black/50 backdrop-blur-sm p-4">
      <div className="glass-panel border border-slate-800/85 rounded-2xl w-full max-w-md bg-slate-900">
        <div className="flex items-center justify-between p-4 border-b border-slate-800/60">
          <h3 className="text-sm font-semibold text-slate-200 flex items-center gap-2"><Send className="w-4 h-4 text-brand-400" /> New approval request</h3>
          <button onClick={onClose} className="p-1 text-slate-500 hover:text-slate-300 cursor-pointer"><X className="w-4 h-4" /></button>
        </div>
        <div className="p-4 space-y-3">
          {error && <div className="p-2.5 bg-red-500/10 border border-red-500/20 text-red-400 rounded-lg text-xs">{error}</div>}
          <select value={f.request_type} onChange={(e) => setF({ ...f, request_type: e.target.value })} className={F}>
            {APPROVAL_TYPES.map((t) => <option key={t} value={t} className="capitalize">{t}</option>)}
          </select>
          <input value={f.title} onChange={(e) => setF({ ...f, title: e.target.value })} placeholder="Title" className={F} />
          <input type="number" value={f.amount} onChange={(e) => setF({ ...f, amount: e.target.value })} placeholder="Amount (optional)" className={F} />
          <textarea value={f.description} onChange={(e) => setF({ ...f, description: e.target.value })} rows={2} placeholder="Details" className={F} />
          <button onClick={save} disabled={busy} className="w-full inline-flex items-center justify-center gap-2 bg-gradient-to-r from-brand-500 to-indigo-500 text-white font-medium py-2 px-4 rounded-lg text-sm disabled:opacity-40 cursor-pointer">
            {busy ? <Loader2 className="w-4 h-4 animate-spin" /> : <Check className="w-4 h-4" />} Submit
          </button>
        </div>
      </div>
    </div>
  );
};

/* ── Chain modal (multi-level) ── */
const ChainModal: React.FC<{ initial?: Chain | null; users: any[]; onClose: () => void; onSaved: () => void }> = ({ initial, users, onClose, onSaved }) => {
  const [f, setF] = useState<any>(initial
    ? { name: initial.name, request_type: initial.request_type, min_amount: initial.min_amount, escalation_hours: initial.escalation_hours || '', is_active: initial.is_active, steps: initial.steps.map((s) => ({ approver_role: s.approver_role || '', approver_user_id: s.approver_user_id || '' })) }
    : { name: '', request_type: 'expense', min_amount: 0, escalation_hours: '', is_active: true, steps: [{ approver_role: 'Manager', approver_user_id: '' }] });
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const setStep = (i: number, patch: any) => setF({ ...f, steps: f.steps.map((s: any, j: number) => j === i ? { ...s, ...patch } : s) });
  const addStep = () => setF({ ...f, steps: [...f.steps, { approver_role: 'OrgAdmin', approver_user_id: '' }] });
  const rmStep = (i: number) => setF({ ...f, steps: f.steps.filter((_: any, j: number) => j !== i) });
  const save = async () => {
    if (!f.name.trim()) { setError('Name is required'); return; }
    setBusy(true); setError(null);
    try {
      const payload = {
        name: f.name, request_type: f.request_type, min_amount: Number(f.min_amount) || 0,
        escalation_hours: f.escalation_hours ? Number(f.escalation_hours) : undefined, is_active: !!f.is_active,
        steps: f.steps.map((s: any) => ({ approver_role: s.approver_user_id ? null : (s.approver_role || null), approver_user_id: s.approver_user_id || null })),
      };
      if (initial) await approvalApi.updateChain(initial.id, payload);
      else await approvalApi.createChain(payload);
      onSaved();
    } catch (e: any) { setError(extractErrorMessage(e, 'Failed to save')); } finally { setBusy(false); }
  };
  return (
    <div className="fixed inset-0 z-40 flex items-center justify-center bg-black/50 backdrop-blur-sm p-4">
      <div className="glass-panel border border-slate-800/85 rounded-2xl w-full max-w-lg bg-slate-900 max-h-[90vh] overflow-y-auto">
        <div className="flex items-center justify-between p-4 border-b border-slate-800/60">
          <h3 className="text-sm font-semibold text-slate-200 flex items-center gap-2"><GitBranch className="w-4 h-4 text-brand-400" /> {initial ? 'Edit' : 'New'} approval chain</h3>
          <button onClick={onClose} className="p-1 text-slate-500 hover:text-slate-300 cursor-pointer"><X className="w-4 h-4" /></button>
        </div>
        <div className="p-4 space-y-3">
          {error && <div className="p-2.5 bg-red-500/10 border border-red-500/20 text-red-400 rounded-lg text-xs">{error}</div>}
          <div className="grid grid-cols-2 gap-2">
            <input value={f.name} onChange={(e) => setF({ ...f, name: e.target.value })} placeholder="Chain name" className={F} />
            <select value={f.request_type} disabled={!!initial} onChange={(e) => setF({ ...f, request_type: e.target.value })} className={`${F} disabled:opacity-50`}>
              {APPROVAL_TYPES.map((t) => <option key={t} value={t} className="capitalize">{t}</option>)}
            </select>
          </div>
          <div className="grid grid-cols-2 gap-2">
            <label className="text-xs text-slate-400">Min amount (tier)<input type="number" value={f.min_amount} onChange={(e) => setF({ ...f, min_amount: e.target.value })} className={F} /></label>
            <label className="text-xs text-slate-400">Escalate after (h)<input type="number" value={f.escalation_hours} onChange={(e) => setF({ ...f, escalation_hours: e.target.value })} className={F} /></label>
          </div>
          <div>
            <p className="text-xs text-slate-400 mb-1">Approval levels (in order)</p>
            <div className="space-y-2">
              {f.steps.map((s: any, i: number) => (
                <div key={i} className="flex items-center gap-2">
                  <span className="text-[10px] text-slate-500 w-8">L{i + 1}</span>
                  <select value={s.approver_role} onChange={(e) => setStep(i, { approver_role: e.target.value, approver_user_id: '' })} className="flex-1 bg-slate-800/70 border border-slate-700/70 text-slate-200 py-1.5 px-2 rounded-lg text-xs">
                    <option value="">— specific user —</option>
                    {APPROVER_ROLES.map((r) => <option key={r} value={r}>{r}</option>)}
                  </select>
                  {!s.approver_role && (
                    <select value={s.approver_user_id} onChange={(e) => setStep(i, { approver_user_id: e.target.value })} className="flex-1 bg-slate-800/70 border border-slate-700/70 text-slate-200 py-1.5 px-2 rounded-lg text-xs">
                      <option value="">Pick user…</option>
                      {users.map((u) => <option key={u.id} value={u.id}>{`${u.first_name || ''} ${u.last_name || ''}`.trim() || u.email}</option>)}
                    </select>
                  )}
                  {f.steps.length > 1 && <button onClick={() => rmStep(i)} className="text-slate-600 hover:text-red-400 cursor-pointer"><X className="w-3.5 h-3.5" /></button>}
                </div>
              ))}
            </div>
            <button onClick={addStep} className="mt-2 text-xs text-brand-400 cursor-pointer inline-flex items-center gap-1"><Plus className="w-3.5 h-3.5" /> Add level</button>
          </div>
          <button onClick={save} disabled={busy} className="w-full inline-flex items-center justify-center gap-2 bg-gradient-to-r from-brand-500 to-indigo-500 text-white font-medium py-2 px-4 rounded-lg text-sm disabled:opacity-40 cursor-pointer">
            {busy ? <Loader2 className="w-4 h-4 animate-spin" /> : <Check className="w-4 h-4" />} {initial ? 'Save' : 'Create'}
          </button>
        </div>
      </div>
    </div>
  );
};

/* ── Delegation modal ── */
const DelegationModal: React.FC<{ users: any[]; onClose: () => void; onSaved: () => void }> = ({ users, onClose, onSaved }) => {
  const [f, setF] = useState<any>({ delegate_id: '', request_type: '', start_date: '', end_date: '' });
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const save = async () => {
    if (!f.delegate_id) { setError('Pick a delegate'); return; }
    setBusy(true); setError(null);
    try {
      await approvalApi.createDelegation({ delegate_id: f.delegate_id, request_type: f.request_type || undefined, start_date: f.start_date || undefined, end_date: f.end_date || undefined });
      onSaved();
    } catch (e: any) { setError(extractErrorMessage(e, 'Failed to delegate')); } finally { setBusy(false); }
  };
  return (
    <div className="fixed inset-0 z-40 flex items-center justify-center bg-black/50 backdrop-blur-sm p-4">
      <div className="glass-panel border border-slate-800/85 rounded-2xl w-full max-w-md bg-slate-900">
        <div className="flex items-center justify-between p-4 border-b border-slate-800/60">
          <h3 className="text-sm font-semibold text-slate-200 flex items-center gap-2"><UserCheck className="w-4 h-4 text-brand-400" /> Delegate approvals</h3>
          <button onClick={onClose} className="p-1 text-slate-500 hover:text-slate-300 cursor-pointer"><X className="w-4 h-4" /></button>
        </div>
        <div className="p-4 space-y-3">
          {error && <div className="p-2.5 bg-red-500/10 border border-red-500/20 text-red-400 rounded-lg text-xs">{error}</div>}
          <select value={f.delegate_id} onChange={(e) => setF({ ...f, delegate_id: e.target.value })} className={F}>
            <option value="">Delegate to…</option>
            {users.map((u) => <option key={u.id} value={u.id}>{`${u.first_name || ''} ${u.last_name || ''}`.trim() || u.email}</option>)}
          </select>
          <select value={f.request_type} onChange={(e) => setF({ ...f, request_type: e.target.value })} className={F}>
            <option value="">All types</option>
            {APPROVAL_TYPES.map((t) => <option key={t} value={t} className="capitalize">{t}</option>)}
          </select>
          <div className="grid grid-cols-2 gap-2">
            <label className="text-xs text-slate-400">From<input type="date" value={f.start_date} onChange={(e) => setF({ ...f, start_date: e.target.value })} className={F} /></label>
            <label className="text-xs text-slate-400">Until<input type="date" value={f.end_date} onChange={(e) => setF({ ...f, end_date: e.target.value })} className={F} /></label>
          </div>
          <button onClick={save} disabled={busy} className="w-full inline-flex items-center justify-center gap-2 bg-gradient-to-r from-brand-500 to-indigo-500 text-white font-medium py-2 px-4 rounded-lg text-sm disabled:opacity-40 cursor-pointer">
            {busy ? <Loader2 className="w-4 h-4 animate-spin" /> : <Check className="w-4 h-4" />} Delegate
          </button>
        </div>
      </div>
    </div>
  );
};

/* ── Page ── */
export const ApprovalsPage: React.FC = () => {
  const { user } = useAuthStore();
  const isManager = user?.role === 'OrgAdmin' || user?.role === 'Manager';
  const isAdmin = user?.role === 'OrgAdmin';

  const [tab, setTab] = useState<'mine' | 'pending' | 'chains' | 'delegations' | 'reports'>('mine');
  const [dash, setDash] = useState<ApprovalDashboard | null>(null);
  const [mine, setMine] = useState<ApprovalRequest[]>([]);
  const [pending, setPending] = useState<ApprovalRequest[]>([]);
  const [chains, setChains] = useState<Chain[]>([]);
  const [delegations, setDelegations] = useState<Delegation[]>([]);
  const [report, setReport] = useState<ApprovalReport | null>(null);
  const [history, setHistory] = useState<Record<string, HistoryRow[]>>({});
  const [users, setUsers] = useState<any[]>([]);
  const [reqOpen, setReqOpen] = useState(false);
  const [chainModal, setChainModal] = useState<Chain | null | 'new'>(null);
  const [delegOpen, setDelegOpen] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const loadDash = useCallback(() => { approvalApi.dashboard().then(setDash).catch(() => {}); }, []);
  useEffect(() => { loadDash(); }, [loadDash]);
  useEffect(() => { if (isManager) userApi.getUsers({ is_active: true, limit: 200 }).then(setUsers).catch(() => {}); }, [isManager]);

  const loadTab = useCallback(() => {
    setError(null);
    if (tab === 'mine') approvalApi.list({ box: 'mine' }).then((r) => setMine(r.items)).catch((e) => setError(extractErrorMessage(e, 'Failed')));
    if (tab === 'pending') approvalApi.list({ box: 'pending' }).then((r) => setPending(r.items)).catch(() => {});
    if (tab === 'chains') approvalApi.listChains({}).then(setChains).catch(() => {});
    if (tab === 'delegations') approvalApi.listDelegations().then(setDelegations).catch(() => {});
    if (tab === 'reports') approvalApi.report({}).then(setReport).catch(() => {});
  }, [tab]);
  useEffect(() => { loadTab(); }, [loadTab]);

  const act = async (r: ApprovalRequest, approve: boolean) => {
    try { await approvalApi.act(r.id, approve); loadTab(); loadDash(); }
    catch (e: any) { setError(extractErrorMessage(e, 'Action failed')); }
  };
  const cancel = async (r: ApprovalRequest) => {
    try { await approvalApi.cancel(r.id); loadTab(); loadDash(); }
    catch (e: any) { setError(extractErrorMessage(e, 'Cancel failed')); }
  };
  const toggleHistory = async (r: ApprovalRequest) => {
    if (history[r.id]) { setHistory((h) => { const n = { ...h }; delete n[r.id]; return n; }); return; }
    const rows = await approvalApi.history(r.id);
    setHistory((h) => ({ ...h, [r.id]: rows }));
  };
  const escalate = async () => {
    try { const r = await approvalApi.escalateOverdue(); window.alert(`${r.escalated} request(s) escalated.`); loadTab(); }
    catch (e: any) { setError(extractErrorMessage(e, 'Failed')); }
  };

  const RequestCard: React.FC<{ r: ApprovalRequest; actions?: React.ReactNode }> = ({ r, actions }) => (
    <div className="p-3 rounded-xl border border-slate-800/85 bg-slate-950/30">
      <div className="flex items-center justify-between gap-2">
        <div className="min-w-0">
          <p className="text-sm text-slate-200 truncate">
            <span className="capitalize text-slate-400">{r.request_type}</span> · {r.title}
            {r.amount != null && <span className="text-slate-500"> · ₹{Math.round(r.amount).toLocaleString()}</span>}
          </p>
          <p className="text-[11px] text-slate-500">by {r.requested_by_name} · level {r.current_level}/{r.total_levels}{r.escalated ? ' · escalated' : ''}</p>
        </div>
        <div className="flex items-center gap-2 shrink-0">
          <StatusChip s={r.status} />
          <button onClick={() => toggleHistory(r)} title="History" className="text-slate-500 hover:text-slate-300 cursor-pointer"><HistoryIcon className="w-3.5 h-3.5" /></button>
          {actions}
        </div>
      </div>
      {history[r.id] && (
        <ul className="mt-2 space-y-1 border-t border-slate-800/50 pt-2">
          {history[r.id].map((h) => (
            <li key={h.id} className="text-[11px] text-slate-500">
              <span className="capitalize text-slate-400">{h.action}</span>{h.level ? ` (L${h.level})` : ''} · {h.actor_name}{h.on_behalf_of_name ? ` for ${h.on_behalf_of_name}` : ''}{h.note ? ` — ${h.note}` : ''}
            </li>
          ))}
        </ul>
      )}
    </div>
  );

  return (
    <div className="p-4 sm:p-6 space-y-4">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <h1 className="text-lg font-bold text-slate-100 flex items-center gap-2"><CheckCircle2 className="w-5 h-5 text-brand-400" /> Approvals</h1>
        <div className="flex items-center gap-2">
          {isManager && <button onClick={() => setDelegOpen(true)} className="inline-flex items-center gap-1.5 border border-slate-800 text-slate-300 text-xs py-1.5 px-3 rounded-lg cursor-pointer"><UserCheck className="w-3.5 h-3.5" /> Delegate</button>}
          <button onClick={() => setReqOpen(true)} className="inline-flex items-center gap-1.5 bg-gradient-to-r from-brand-500 to-indigo-500 text-white text-xs font-medium py-1.5 px-3 rounded-lg cursor-pointer"><Plus className="w-3.5 h-3.5" /> New request</button>
        </div>
      </div>

      {dash && (
        <div className="grid grid-cols-3 sm:grid-cols-6 gap-2">
          {[
            { label: 'My pending', value: dash.my_pending, icon: Clock },
            { label: 'To action', value: dash.awaiting_my_action, icon: Inbox },
            { label: 'Approved', value: dash.approved, icon: Check },
            { label: 'Rejected', value: dash.rejected, icon: X },
            { label: 'Pending', value: dash.pending, icon: Clock },
            { label: 'Total', value: dash.total, icon: BarChart3 },
          ].map((s) => (
            <div key={s.label} className="glass-panel border border-slate-800/85 rounded-xl p-3">
              <p className="text-[10px] font-semibold text-slate-500 uppercase tracking-wider flex items-center gap-1"><s.icon className="w-3 h-3 text-brand-400" /> {s.label}</p>
              <p className="text-lg font-bold text-slate-100 mt-0.5">{s.value}</p>
            </div>
          ))}
        </div>
      )}

      {error && <div className="p-3 bg-red-500/10 border border-red-500/20 text-red-400 rounded-lg text-xs">{error}</div>}

      <div className="flex gap-1 border-b border-slate-800/60 flex-wrap">
        {([['mine', 'My Requests', Send], ['pending', 'Pending My Action', Inbox], ...(isAdmin ? [['chains', 'Approval Chains', GitBranch]] as const : []), ['delegations', 'Delegations', UserCheck], ...(isManager ? [['reports', 'Reports', BarChart3]] as const : [])] as const).map(([key, lbl, Icon]) => (
          <button key={key} onClick={() => setTab(key as any)} className={`px-3 py-1.5 text-xs font-medium inline-flex items-center gap-1.5 border-b-2 -mb-px cursor-pointer ${tab === key ? 'border-brand-500 text-brand-300' : 'border-transparent text-slate-500 hover:text-slate-300'}`}>
            <Icon className="w-3.5 h-3.5" /> {lbl}
          </button>
        ))}
      </div>

      {tab === 'mine' && (
        <div className="space-y-2">
          {mine.map((r) => <RequestCard key={r.id} r={r} actions={r.status === 'pending' ? <button onClick={() => cancel(r)} className="text-xs text-red-400 cursor-pointer">Cancel</button> : undefined} />)}
          {!mine.length && <p className="text-xs text-slate-500 py-6 text-center">No requests yet.</p>}
        </div>
      )}

      {tab === 'pending' && (
        <div className="space-y-2">
          {pending.map((r) => (
            <RequestCard key={r.id} r={r} actions={
              <>
                <button onClick={() => act(r, true)} className="text-xs text-emerald-400 cursor-pointer inline-flex items-center gap-1"><Check className="w-3.5 h-3.5" /> Approve</button>
                <button onClick={() => act(r, false)} className="text-xs text-red-400 cursor-pointer inline-flex items-center gap-1"><X className="w-3.5 h-3.5" /> Reject</button>
              </>
            } />
          ))}
          {!pending.length && <p className="text-xs text-slate-500 py-6 text-center">Nothing awaiting your action.</p>}
        </div>
      )}

      {tab === 'chains' && isAdmin && (
        <div className="space-y-3">
          <div className="flex items-center gap-2">
            <button onClick={() => setChainModal('new')} className="inline-flex items-center gap-1.5 bg-gradient-to-r from-brand-500 to-indigo-500 text-white text-xs font-medium py-1.5 px-3 rounded-lg cursor-pointer"><Plus className="w-3.5 h-3.5" /> New chain</button>
            <button onClick={escalate} className="inline-flex items-center gap-1.5 border border-slate-800 text-slate-300 text-xs py-1.5 px-3 rounded-lg cursor-pointer"><AlertTriangle className="w-3.5 h-3.5" /> Escalate overdue</button>
          </div>
          <div className="space-y-2">
            {chains.map((c) => (
              <div key={c.id} className="p-3 rounded-xl border border-slate-800/85 bg-slate-950/30 flex items-center justify-between gap-2">
                <div>
                  <p className="text-sm text-slate-200 font-medium capitalize">{c.name} <span className="text-[10px] text-slate-600">{c.request_type}{c.min_amount ? ` ≥ ₹${c.min_amount}` : ''}</span></p>
                  <p className="text-[11px] text-slate-500 mt-0.5">{c.steps.map((s, i) => `L${i + 1}:${s.approver_role || 'user'}`).join(' → ')}{c.escalation_hours ? ` · escalate ${c.escalation_hours}h` : ''}{c.is_active ? '' : ' · inactive'}</p>
                </div>
                <div className="flex items-center gap-1">
                  <button onClick={() => setChainModal(c)} className="p-1.5 text-slate-500 hover:text-slate-300 cursor-pointer"><GitBranch className="w-4 h-4" /></button>
                  <button onClick={async () => { if (window.confirm('Delete chain?')) { try { await approvalApi.deleteChain(c.id); loadTab(); } catch (e: any) { setError(extractErrorMessage(e, 'Delete failed')); } } }} className="p-1.5 text-slate-500 hover:text-red-400 cursor-pointer"><Trash2 className="w-4 h-4" /></button>
                </div>
              </div>
            ))}
            {!chains.length && <p className="text-xs text-slate-500 py-6 text-center">No chains — without one, requests go straight to an OrgAdmin.</p>}
          </div>
        </div>
      )}

      {tab === 'delegations' && (
        <div className="space-y-2">
          {delegations.map((d) => (
            <div key={d.id} className="p-3 rounded-xl border border-slate-800/85 bg-slate-950/30 flex items-center justify-between gap-2">
              <p className="text-xs text-slate-300">{d.delegator_id === user?.id ? 'You' : 'A user'} → delegate · <span className="capitalize">{d.request_type || 'all'}</span> · {d.start_date}{d.end_date ? ` → ${d.end_date}` : ''} {d.is_active ? '' : '· revoked'}</p>
              {d.is_active && (d.delegator_id === user?.id || user?.role === 'OrgAdmin') && (
                <button onClick={async () => { await approvalApi.revokeDelegation(d.id); loadTab(); }} className="text-xs text-red-400 cursor-pointer">Revoke</button>
              )}
            </div>
          ))}
          {!delegations.length && <p className="text-xs text-slate-500 py-6 text-center">No delegations.</p>}
        </div>
      )}

      {tab === 'reports' && isManager && report && (
        <div className="overflow-x-auto">
          <table className="w-full text-xs">
            <thead><tr className="text-left text-[10px] text-slate-500 uppercase">
              <th className="py-2 pr-2">Type</th><th className="py-2 pr-2">Total</th><th className="py-2 pr-2">Approved</th><th className="py-2 pr-2">Rejected</th><th className="py-2 pr-2">Pending</th><th className="py-2">Avg decision (h)</th>
            </tr></thead>
            <tbody>
              {report.rows.map((r) => (
                <tr key={r.request_type} className="border-t border-slate-800/50 text-slate-300">
                  <td className="py-1.5 pr-2 capitalize">{r.request_type}</td>
                  <td className="py-1.5 pr-2">{r.total}</td>
                  <td className="py-1.5 pr-2">{r.approved}</td>
                  <td className="py-1.5 pr-2">{r.rejected}</td>
                  <td className="py-1.5 pr-2">{r.pending}</td>
                  <td className="py-1.5">{r.avg_decision_hours ?? '—'}</td>
                </tr>
              ))}
            </tbody>
          </table>
          {!report.rows.length && <p className="text-xs text-slate-500 py-6 text-center">No approval data yet.</p>}
        </div>
      )}

      {reqOpen && <RequestModal onClose={() => setReqOpen(false)} onSaved={() => { setReqOpen(false); loadTab(); loadDash(); }} />}
      {chainModal && <ChainModal initial={chainModal === 'new' ? null : chainModal} users={users} onClose={() => setChainModal(null)} onSaved={() => { setChainModal(null); loadTab(); }} />}
      {delegOpen && <DelegationModal users={users} onClose={() => setDelegOpen(false)} onSaved={() => { setDelegOpen(false); loadTab(); }} />}
    </div>
  );
};
