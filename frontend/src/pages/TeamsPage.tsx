import React, { useCallback, useEffect, useState } from 'react';
import {
  Users, Plus, Loader2, Search, X, Target, Archive, ArchiveRestore, Trash2, Pencil,
  Download, Upload, Check, Crown, UserPlus, Gauge, CalendarDays, TrendingUp, Send,
} from 'lucide-react';
import { teamApi, Team, TeamMember, TeamPerformance, TeamDashboard, TeamCalendarItem } from '../services/teamApi';
import { userApi } from '../services/userApi';
import { leadApi } from '../services/leadApi';
import { taskApi } from '../services/taskApi';
import { departmentApi, Department } from '../services/departmentApi';
import { useAuthStore } from '../store/authStore';
import { extractErrorMessage } from '../utils/errors';

const METRICS = ['leads_converted', 'calls_made', 'tasks_completed', 'revenue', 'activities', 'custom'];
const emptyForm = { name: '', code: '', description: '', team_leader_id: '', department_id: '', capacity: '', color: '', status: 'active' };

const StatusChip: React.FC<{ status: string }> = ({ status }) => (
  <span className={`px-2 py-0.5 text-[10px] font-semibold rounded-md border ${status === 'active' ? 'bg-emerald-500/10 text-emerald-400 border-emerald-500/20' : 'bg-slate-700/40 text-slate-400 border-slate-600/40'}`}>{status}</span>
);

/* ── Create / edit modal ── */
const TeamModal: React.FC<{ initial?: Team | null; users: any[]; depts: Department[]; canManage: boolean; onClose: () => void; onSaved: () => void }> =
  ({ initial, users, depts, canManage, onClose, onSaved }) => {
    const [form, setForm] = useState<any>(initial ? {
      name: initial.name, code: initial.code || '', description: initial.description || '',
      team_leader_id: initial.team_leader_id || '', department_id: initial.department_id || '',
      capacity: initial.capacity ?? '', color: initial.color || '', status: initial.status,
    } : emptyForm);
    const [busy, setBusy] = useState(false);
    const [error, setError] = useState<string | null>(null);

    const save = async () => {
      if (!form.name.trim()) { setError('Name is required'); return; }
      setBusy(true); setError(null);
      try {
        const payload: any = {
          name: form.name, code: form.code || undefined, description: form.description || undefined,
          department_id: form.department_id || null,
          capacity: form.capacity === '' ? null : parseInt(form.capacity, 10),
          color: form.color || undefined, status: form.status,
        };
        if (canManage) payload.team_leader_id = form.team_leader_id || null;
        if (initial) await teamApi.update(initial.id, payload);
        else await teamApi.create(payload);
        onSaved();
      } catch (e: any) { setError(extractErrorMessage(e, 'Failed to save')); } finally { setBusy(false); }
    };

    const F = "w-full bg-slate-800/70 border border-slate-700/70 text-slate-200 py-2 px-3 rounded-lg text-sm";
    return (
      <div className="fixed inset-0 z-40 flex items-center justify-center bg-black/50 backdrop-blur-sm p-4">
        <div className="glass-panel border border-slate-800/85 rounded-2xl w-full max-w-lg bg-slate-900 max-h-[90vh] overflow-y-auto">
          <div className="flex items-center justify-between p-4 border-b border-slate-800/60">
            <h3 className="text-sm font-semibold text-slate-200 flex items-center gap-2"><Users className="w-4 h-4 text-brand-400" /> {initial ? 'Edit' : 'New'} team</h3>
            <button onClick={onClose} className="p-1 text-slate-500 hover:text-slate-300 cursor-pointer"><X className="w-4 h-4" /></button>
          </div>
          <div className="p-4 space-y-3">
            {error && <div className="p-3 bg-red-500/10 border border-red-500/20 text-red-400 rounded-lg text-xs">{error}</div>}
            <div className="grid grid-cols-2 gap-2">
              <input value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} placeholder="Name" className={F} />
              <input value={form.code} onChange={(e) => setForm({ ...form, code: e.target.value })} placeholder="Code" className={F} />
            </div>
            <textarea value={form.description} onChange={(e) => setForm({ ...form, description: e.target.value })} rows={2} placeholder="Description" className={F} />
            <div className="grid grid-cols-2 gap-2">
              <select value={form.team_leader_id} disabled={!canManage} onChange={(e) => setForm({ ...form, team_leader_id: e.target.value })} className={`${F} disabled:opacity-50`}>
                <option value="">No leader</option>
                {users.map((u) => <option key={u.id} value={u.id}>{`${u.first_name || ''} ${u.last_name || ''}`.trim() || u.email}</option>)}
              </select>
              <select value={form.department_id} onChange={(e) => setForm({ ...form, department_id: e.target.value })} className={F}>
                <option value="">No department</option>
                {depts.map((d) => <option key={d.id} value={d.id}>{d.name}</option>)}
              </select>
            </div>
            <div className="grid grid-cols-2 gap-2">
              <input type="number" min={1} value={form.capacity} onChange={(e) => setForm({ ...form, capacity: e.target.value })} placeholder="Capacity (max members)" className={F} />
              <input value={form.color} onChange={(e) => setForm({ ...form, color: e.target.value })} placeholder="Color (e.g. #22c55e)" className={F} />
            </div>
            <button onClick={save} disabled={busy} className="w-full inline-flex items-center justify-center gap-2 bg-gradient-to-r from-brand-500 to-indigo-500 text-white font-medium py-2 px-4 rounded-lg text-sm disabled:opacity-40 cursor-pointer">
              {busy ? <Loader2 className="w-4 h-4 animate-spin" /> : <Check className="w-4 h-4" />} {initial ? 'Save' : 'Create'}
            </button>
          </div>
        </div>
      </div>
    );
  };

/* ── Members panel ── */
const MembersPanel: React.FC<{ team: Team; canManage: boolean; users: any[]; onChanged: () => void }> = ({ team, canManage, users, onChanged }) => {
  const [members, setMembers] = useState<TeamMember[]>([]);
  const [adding, setAdding] = useState(false);
  const [pick, setPick] = useState<Set<string>>(new Set());
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(() => { teamApi.members(team.id).then(setMembers).catch(() => {}); }, [team.id]);
  useEffect(() => { load(); }, [load]);

  const memberIds = new Set(members.map((m) => m.id));
  const assignable = users.filter((u) => !memberIds.has(u.id));

  const add = async () => {
    if (!pick.size) return;
    setError(null);
    try { await teamApi.addMembers(team.id, [...pick]); setPick(new Set()); setAdding(false); load(); onChanged(); }
    catch (e: any) { setError(extractErrorMessage(e, 'Failed to add members')); }
  };
  const remove = async (id: string) => {
    setError(null);
    try { await teamApi.removeMembers(team.id, [id]); load(); onChanged(); }
    catch (e: any) { setError(extractErrorMessage(e, 'Failed to remove member')); }
  };

  const pct = team.capacity ? Math.min(100, Math.round((members.length * 100) / team.capacity)) : null;
  return (
    <div className="space-y-3">
      {error && <div className="p-2.5 bg-red-500/10 border border-red-500/20 text-red-400 rounded-lg text-xs">{error}</div>}
      {team.capacity != null && (
        <div>
          <div className="flex items-center justify-between text-[11px] text-slate-400 mb-1">
            <span className="flex items-center gap-1"><Gauge className="w-3.5 h-3.5" /> Capacity</span>
            <span>{members.length}/{team.capacity}</span>
          </div>
          <div className="h-1.5 bg-slate-800 rounded-full overflow-hidden">
            <div className={`h-full ${pct! >= 100 ? 'bg-red-500' : pct! >= 80 ? 'bg-amber-500' : 'bg-emerald-500'}`} style={{ width: `${pct}%` }} />
          </div>
        </div>
      )}
      {canManage && (adding ? (
        <div className="p-2 bg-slate-950/40 border border-slate-800/60 rounded-lg space-y-2">
          <div className="max-h-40 overflow-y-auto space-y-1">
            {assignable.map((u) => (
              <label key={u.id} className="flex items-center gap-2 text-xs text-slate-300 cursor-pointer">
                <input type="checkbox" checked={pick.has(u.id)} onChange={(e) => {
                  const s = new Set(pick); e.target.checked ? s.add(u.id) : s.delete(u.id); setPick(s);
                }} />
                {`${u.first_name || ''} ${u.last_name || ''}`.trim() || u.email}
              </label>
            ))}
            {!assignable.length && <p className="text-xs text-slate-500">Everyone is already on this team.</p>}
          </div>
          <div className="flex gap-2">
            <button onClick={add} className="text-xs text-emerald-400 cursor-pointer">Add {pick.size ? `(${pick.size})` : ''}</button>
            <button onClick={() => { setAdding(false); setPick(new Set()); }} className="text-xs text-slate-500 cursor-pointer">Cancel</button>
          </div>
        </div>
      ) : (
        <button onClick={() => setAdding(true)} className="inline-flex items-center gap-1.5 text-xs text-brand-400 hover:text-brand-300 cursor-pointer"><UserPlus className="w-3.5 h-3.5" /> Add members</button>
      ))}
      <ul className="space-y-1.5">
        {members.map((m) => (
          <li key={m.membership_id} className="flex items-center justify-between p-2 bg-slate-950/40 border border-slate-800/60 rounded-lg">
            <div className="flex items-center gap-2 min-w-0">
              {m.role_in_team === 'leader' && <Crown className="w-3.5 h-3.5 text-amber-400 shrink-0" />}
              <div className="min-w-0">
                <p className="text-xs text-slate-200 truncate">{m.name}</p>
                <p className="text-[10px] text-slate-500 truncate">{m.email} · {m.role}</p>
              </div>
            </div>
            {canManage && m.role_in_team !== 'leader' && (
              <button onClick={() => remove(m.id)} className="p-1 text-slate-600 hover:text-red-400 cursor-pointer"><X className="w-3.5 h-3.5" /></button>
            )}
          </li>
        ))}
        {!members.length && <p className="text-xs text-slate-500">No members yet.</p>}
      </ul>
    </div>
  );
};

/* ── Targets & performance panel ── */
const PerformancePanel: React.FC<{ team: Team; canManage: boolean }> = ({ team, canManage }) => {
  const [perf, setPerf] = useState<TeamPerformance | null>(null);
  const [adding, setAdding] = useState(false);
  const [tform, setTform] = useState({ name: '', metric: 'leads_converted', target_value: '', period: 'monthly' });
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(() => { teamApi.performance(team.id).then(setPerf).catch(() => {}); }, [team.id]);
  useEffect(() => { load(); }, [load]);

  const addTarget = async () => {
    if (!tform.name.trim() || !tform.target_value) { setError('Name and value required'); return; }
    setError(null);
    try {
      await teamApi.createTarget(team.id, { ...tform, target_value: parseFloat(tform.target_value) });
      setTform({ name: '', metric: 'leads_converted', target_value: '', period: 'monthly' });
      setAdding(false); load();
    } catch (e: any) { setError(extractErrorMessage(e, 'Failed to add target')); }
  };

  if (!perf) return <div className="py-4 text-center text-slate-500"><Loader2 className="w-4 h-4 animate-spin inline" /></div>;
  const F = "bg-slate-800/70 border border-slate-700/70 text-slate-200 py-1.5 px-2 rounded-lg text-xs";
  return (
    <div className="space-y-3">
      {error && <div className="p-2.5 bg-red-500/10 border border-red-500/20 text-red-400 rounded-lg text-xs">{error}</div>}
      <div className="grid grid-cols-2 gap-2">
        {(['leads_converted', 'calls_made', 'tasks_completed', 'revenue'] as const).map((k) => (
          <div key={k} className="p-2.5 bg-slate-950/40 border border-slate-800/60 rounded-lg">
            <p className="text-[10px] font-semibold text-slate-500 uppercase tracking-wider">{k.replace(/_/g, ' ')}</p>
            <p className="text-lg font-bold text-slate-100 mt-0.5">{k === 'revenue' ? `₹${Math.round(perf.metrics[k] || 0).toLocaleString()}` : (perf.metrics[k] || 0)}</p>
          </div>
        ))}
      </div>
      <div className="flex items-center justify-between">
        <h4 className="text-xs font-semibold text-slate-300 flex items-center gap-1.5"><Target className="w-3.5 h-3.5 text-brand-400" /> Targets & KPIs</h4>
        {canManage && !adding && <button onClick={() => setAdding(true)} className="text-xs text-brand-400 cursor-pointer">+ Target</button>}
      </div>
      {adding && (
        <div className="p-2 bg-slate-950/40 border border-slate-800/60 rounded-lg grid grid-cols-2 gap-2">
          <input value={tform.name} onChange={(e) => setTform({ ...tform, name: e.target.value })} placeholder="Target name" className={F} />
          <select value={tform.metric} onChange={(e) => setTform({ ...tform, metric: e.target.value })} className={F}>
            {METRICS.map((m) => <option key={m} value={m}>{m}</option>)}
          </select>
          <input type="number" value={tform.target_value} onChange={(e) => setTform({ ...tform, target_value: e.target.value })} placeholder="Value" className={F} />
          <select value={tform.period} onChange={(e) => setTform({ ...tform, period: e.target.value })} className={F}>
            {['daily', 'weekly', 'monthly', 'quarterly', 'yearly'].map((p) => <option key={p} value={p}>{p}</option>)}
          </select>
          <div className="col-span-2 flex gap-2">
            <button onClick={addTarget} className="text-xs text-emerald-400 cursor-pointer">Save</button>
            <button onClick={() => setAdding(false)} className="text-xs text-slate-500 cursor-pointer">Cancel</button>
          </div>
        </div>
      )}
      {perf.kpis.map((k) => (
        <div key={k.target_id} className="p-2 bg-slate-950/40 border border-slate-800/60 rounded-lg">
          <div className="flex items-center justify-between text-xs">
            <span className="text-slate-300">{k.name} <span className="text-slate-600">({k.metric}, {k.period})</span></span>
            <div className="flex items-center gap-2">
              <span className="text-slate-400">{k.actual}/{k.target_value}</span>
              {canManage && <button onClick={async () => { await teamApi.deleteTarget(team.id, k.target_id); load(); }} className="text-slate-600 hover:text-red-400 cursor-pointer"><Trash2 className="w-3 h-3" /></button>}
            </div>
          </div>
          <div className="h-1.5 bg-slate-800 rounded-full overflow-hidden mt-1.5">
            <div className={`h-full ${k.attainment >= 100 ? 'bg-emerald-500' : k.attainment >= 60 ? 'bg-brand-500' : 'bg-amber-500'}`} style={{ width: `${Math.min(100, k.attainment)}%` }} />
          </div>
        </div>
      ))}
      {!perf.kpis.length && !adding && <p className="text-xs text-slate-500">No targets yet.</p>}
      {perf.members.length > 0 && (
        <>
          <h4 className="text-xs font-semibold text-slate-300 flex items-center gap-1.5 pt-1"><TrendingUp className="w-3.5 h-3.5 text-brand-400" /> Member performance</h4>
          <div className="overflow-x-auto">
            <table className="w-full text-xs">
              <thead><tr className="text-left text-[10px] text-slate-500 uppercase">
                <th className="py-1 pr-2">Member</th><th className="py-1 pr-2">Conv.</th><th className="py-1 pr-2">Calls</th><th className="py-1 pr-2">Tasks</th><th className="py-1">Revenue</th>
              </tr></thead>
              <tbody>
                {perf.members.map((m) => (
                  <tr key={m.user_id} className="border-t border-slate-800/50 text-slate-300">
                    <td className="py-1.5 pr-2">{m.name}</td>
                    <td className="py-1.5 pr-2">{m.leads_converted}</td>
                    <td className="py-1.5 pr-2">{m.calls_made}</td>
                    <td className="py-1.5 pr-2">{m.tasks_completed}</td>
                    <td className="py-1.5">₹{Math.round(m.revenue).toLocaleString()}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </>
      )}
    </div>
  );
};

/* ── Team calendar panel (next 7 days) ── */
const CalendarPanel: React.FC<{ team: Team }> = ({ team }) => {
  const [items, setItems] = useState<TeamCalendarItem[] | null>(null);
  useEffect(() => {
    const from = new Date(); const to = new Date(Date.now() + 7 * 86400000);
    teamApi.calendar(team.id, from.toISOString(), to.toISOString()).then(setItems).catch(() => setItems([]));
  }, [team.id]);
  if (!items) return <div className="py-4 text-center text-slate-500"><Loader2 className="w-4 h-4 animate-spin inline" /></div>;
  return (
    <ul className="space-y-1.5">
      {items.map((i) => (
        <li key={`${i.type}-${i.id}`} className="flex items-center justify-between p-2 bg-slate-950/40 border border-slate-800/60 rounded-lg text-xs">
          <div className="min-w-0">
            <p className="text-slate-200 truncate">{i.title}</p>
            <p className="text-[10px] text-slate-500">{i.event_type} · {i.user_name}{i.start ? ` · ${new Date(i.start).toLocaleString()}` : ''}</p>
          </div>
          <StatusChip status={i.status.toLowerCase()} />
        </li>
      ))}
      {!items.length && <p className="text-xs text-slate-500">Nothing scheduled in the next 7 days.</p>}
    </ul>
  );
};

/* ── Assign work modal ── */
const AssignModal: React.FC<{ team: Team; kind: 'leads' | 'tasks'; onClose: () => void }> = ({ team, kind, onClose }) => {
  const [rows, setRows] = useState<any[]>([]);
  const [pick, setPick] = useState<Set<string>>(new Set());
  const [strategy, setStrategy] = useState('round_robin');
  const [busy, setBusy] = useState(false);
  const [done, setDone] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    (kind === 'leads'
      ? leadApi.getLeads({ limit: 100 } as any).then((ls: any[]) => setRows(ls.filter((l) => !l.assigned_user_id)))
      : taskApi.list({ limit: 100 } as any).then((ts: any) => {
          const arr = Array.isArray(ts) ? ts : ts.items || [];
          setRows(arr.filter((t: any) => !t.assigned_user_id && t.status !== 'Done'));
        })
    ).catch(() => setRows([]));
  }, [kind]);

  const run = async () => {
    if (!pick.size) return;
    setBusy(true); setError(null);
    try {
      const res = kind === 'leads'
        ? await teamApi.assignLeads(team.id, [...pick], strategy)
        : await teamApi.assignTasks(team.id, [...pick], strategy);
      setDone(`${res.assigned} ${kind} assigned across ${Object.keys(res.distribution).length} member(s).`);
      setPick(new Set());
    } catch (e: any) { setError(extractErrorMessage(e, 'Assignment failed')); } finally { setBusy(false); }
  };

  return (
    <div className="fixed inset-0 z-40 flex items-center justify-center bg-black/50 backdrop-blur-sm p-4">
      <div className="glass-panel border border-slate-800/85 rounded-2xl w-full max-w-md bg-slate-900 max-h-[85vh] overflow-y-auto">
        <div className="flex items-center justify-between p-4 border-b border-slate-800/60">
          <h3 className="text-sm font-semibold text-slate-200 flex items-center gap-2"><Send className="w-4 h-4 text-brand-400" /> Assign {kind} to {team.name}</h3>
          <button onClick={onClose} className="p-1 text-slate-500 hover:text-slate-300 cursor-pointer"><X className="w-4 h-4" /></button>
        </div>
        <div className="p-4 space-y-3">
          {error && <div className="p-2.5 bg-red-500/10 border border-red-500/20 text-red-400 rounded-lg text-xs">{error}</div>}
          {done && <div className="p-2.5 bg-emerald-500/10 border border-emerald-500/20 text-emerald-400 rounded-lg text-xs">{done}</div>}
          <select value={strategy} onChange={(e) => setStrategy(e.target.value)} className="w-full bg-slate-800/70 border border-slate-700/70 text-slate-200 py-2 px-3 rounded-lg text-sm">
            <option value="round_robin">Round robin (least loaded)</option>
            <option value="leader">All to team leader</option>
          </select>
          <div className="max-h-56 overflow-y-auto space-y-1">
            {rows.map((r) => (
              <label key={r.id} className="flex items-center gap-2 text-xs text-slate-300 cursor-pointer p-1.5 bg-slate-950/40 border border-slate-800/50 rounded-lg">
                <input type="checkbox" checked={pick.has(r.id)} onChange={(e) => {
                  const s = new Set(pick); e.target.checked ? s.add(r.id) : s.delete(r.id); setPick(s);
                }} />
                <span className="truncate">{kind === 'leads' ? (r.title || `${r.first_name || ''} ${r.last_name}`.trim()) : r.title}</span>
              </label>
            ))}
            {!rows.length && <p className="text-xs text-slate-500">No unassigned {kind} found.</p>}
          </div>
          <button onClick={run} disabled={busy || !pick.size} className="w-full inline-flex items-center justify-center gap-2 bg-gradient-to-r from-brand-500 to-indigo-500 text-white font-medium py-2 px-4 rounded-lg text-sm disabled:opacity-40 cursor-pointer">
            {busy ? <Loader2 className="w-4 h-4 animate-spin" /> : <Send className="w-4 h-4" />} Assign {pick.size ? `(${pick.size})` : ''}
          </button>
        </div>
      </div>
    </div>
  );
};

/* ── Page ── */
export const TeamsPage: React.FC = () => {
  const { user } = useAuthStore();
  const canManage = user?.role === 'OrgAdmin' || user?.role === 'Manager';

  const [teams, setTeams] = useState<Team[]>([]);
  const [dash, setDash] = useState<TeamDashboard | null>(null);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState('');
  const [statusFilter, setStatusFilter] = useState('');
  const [selected, setSelected] = useState<Team | null>(null);
  const [tab, setTab] = useState<'members' | 'performance' | 'calendar'>('members');
  const [modal, setModal] = useState<'create' | 'edit' | null>(null);
  const [assign, setAssign] = useState<'leads' | 'tasks' | null>(null);
  const [checked, setChecked] = useState<Set<string>>(new Set());
  const [users, setUsers] = useState<any[]>([]);
  const [depts, setDepts] = useState<Department[]>([]);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const [list, d] = await Promise.all([
        teamApi.list({ search: search || undefined, status: statusFilter || undefined }),
        teamApi.dashboard(),
      ]);
      setTeams(list.items); setDash(d);
      if (selected) {
        const cur = list.items.find((t) => t.id === selected.id);
        setSelected(cur || null);
      }
    } catch (e: any) { setError(extractErrorMessage(e, 'Failed to load teams')); }
    finally { setLoading(false); }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [search, statusFilter]);
  useEffect(() => { load(); }, [load]);
  useEffect(() => {
    if (canManage) {
      userApi.getUsers({ is_active: true, limit: 200 }).then(setUsers).catch(() => {});
      departmentApi.list({}).then((d) => setDepts(d.items)).catch(() => {});
    }
  }, [canManage]);

  const isLeaderOfSelected = selected != null && selected.team_leader_id === user?.id;

  const bulk = async (action: string) => {
    if (!checked.size) return;
    if (action === 'delete' && !window.confirm(`Delete ${checked.size} team(s)?`)) return;
    setError(null);
    try {
      const res = await teamApi.bulk([...checked], action);
      if (res.errors.length) setError(`${res.errors.length} team(s) skipped: ${res.errors.map((e: any) => e.error).join('; ')}`);
      setChecked(new Set()); load();
    } catch (e: any) { setError(extractErrorMessage(e, 'Bulk action failed')); }
  };

  const doExport = async () => {
    const blob = await teamApi.exportCsv();
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url; a.download = 'teams.csv'; a.click();
    URL.revokeObjectURL(url);
  };

  const doImport = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;
    try {
      const res = await teamApi.importCsv(file);
      setError(null);
      window.alert(`Import: ${res.created} created, ${res.updated} updated, ${res.skipped} skipped.`);
      load();
    } catch (err: any) { setError(extractErrorMessage(err, 'Import failed')); }
    e.target.value = '';
  };

  const removeTeam = async (t: Team) => {
    if (!window.confirm(`Delete team "${t.name}"?`)) return;
    try { await teamApi.remove(t.id); setSelected(null); load(); }
    catch (e: any) { setError(extractErrorMessage(e, 'Delete failed')); }
  };

  return (
    <div className="p-4 sm:p-6 space-y-4">
      {/* Header + stats */}
      <div className="flex flex-wrap items-center justify-between gap-3">
        <h1 className="text-lg font-bold text-slate-100 flex items-center gap-2"><Users className="w-5 h-5 text-brand-400" /> Teams</h1>
        <div className="flex items-center gap-2">
          {canManage && (
            <>
              <label className="inline-flex items-center gap-1.5 text-xs text-slate-400 hover:text-slate-200 cursor-pointer px-2.5 py-1.5 border border-slate-800 rounded-lg">
                <Upload className="w-3.5 h-3.5" /> Import
                <input type="file" accept=".csv" onChange={doImport} className="hidden" />
              </label>
              <button onClick={doExport} className="inline-flex items-center gap-1.5 text-xs text-slate-400 hover:text-slate-200 cursor-pointer px-2.5 py-1.5 border border-slate-800 rounded-lg"><Download className="w-3.5 h-3.5" /> Export</button>
              <button onClick={() => setModal('create')} className="inline-flex items-center gap-1.5 bg-gradient-to-r from-brand-500 to-indigo-500 text-white text-xs font-medium py-1.5 px-3 rounded-lg cursor-pointer"><Plus className="w-3.5 h-3.5" /> New team</button>
            </>
          )}
        </div>
      </div>

      {dash && (
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-2">
          {[
            { label: 'Teams', value: `${dash.active}/${dash.total}` },
            { label: 'Members', value: dash.total_members },
            { label: 'Capacity used', value: dash.capacity_utilization != null ? `${dash.capacity_utilization}%` : '—' },
            { label: 'Archived', value: dash.archived },
          ].map((s) => (
            <div key={s.label} className="glass-panel border border-slate-800/85 rounded-xl p-3">
              <p className="text-[10px] font-semibold text-slate-500 uppercase tracking-wider">{s.label}</p>
              <p className="text-xl font-bold text-slate-100 mt-0.5">{s.value}</p>
            </div>
          ))}
        </div>
      )}

      {error && <div className="p-3 bg-red-500/10 border border-red-500/20 text-red-400 rounded-lg text-xs">{error}</div>}

      {/* Toolbar */}
      <div className="flex flex-wrap items-center gap-2">
        <div className="relative">
          <Search className="w-3.5 h-3.5 text-slate-500 absolute left-2.5 top-1/2 -translate-y-1/2" />
          <input value={search} onChange={(e) => setSearch(e.target.value)} placeholder="Search teams…"
                 className="bg-slate-800/70 border border-slate-700/70 text-slate-200 py-1.5 pl-8 pr-3 rounded-lg text-xs w-52" />
        </div>
        <select value={statusFilter} onChange={(e) => setStatusFilter(e.target.value)} className="bg-slate-800/70 border border-slate-700/70 text-slate-200 py-1.5 px-2 rounded-lg text-xs">
          <option value="">All statuses</option>
          <option value="active">Active</option>
          <option value="archived">Archived</option>
        </select>
        {canManage && checked.size > 0 && (
          <div className="flex items-center gap-2 ml-auto">
            <span className="text-[11px] text-slate-500">{checked.size} selected</span>
            <button onClick={() => bulk('archive')} className="text-xs text-amber-400 cursor-pointer inline-flex items-center gap-1"><Archive className="w-3.5 h-3.5" /> Archive</button>
            <button onClick={() => bulk('activate')} className="text-xs text-emerald-400 cursor-pointer inline-flex items-center gap-1"><ArchiveRestore className="w-3.5 h-3.5" /> Activate</button>
            <button onClick={() => bulk('delete')} className="text-xs text-red-400 cursor-pointer inline-flex items-center gap-1"><Trash2 className="w-3.5 h-3.5" /> Delete</button>
          </div>
        )}
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-5 gap-4">
        {/* List */}
        <div className="lg:col-span-2 space-y-2">
          {loading ? (
            <div className="py-8 text-center text-slate-500"><Loader2 className="w-5 h-5 animate-spin inline" /></div>
          ) : teams.length === 0 ? (
            <p className="text-xs text-slate-500 py-6 text-center">No teams found.</p>
          ) : teams.map((t) => (
            <div key={t.id} onClick={() => { setSelected(t); setTab('members'); }}
                 className={`p-3 rounded-xl border cursor-pointer transition ${selected?.id === t.id ? 'border-brand-500/50 bg-brand-500/5' : 'border-slate-800/85 bg-slate-950/30 hover:border-slate-700'}`}>
              <div className="flex items-center justify-between gap-2">
                <div className="flex items-center gap-2 min-w-0">
                  {canManage && (
                    <input type="checkbox" checked={checked.has(t.id)} onClick={(e) => e.stopPropagation()} onChange={(e) => {
                      const s = new Set(checked); e.target.checked ? s.add(t.id) : s.delete(t.id); setChecked(s);
                    }} />
                  )}
                  <span className="w-2 h-2 rounded-full shrink-0" style={{ background: t.color || '#6366f1' }} />
                  <p className="text-sm text-slate-200 font-medium truncate">{t.name}</p>
                  {t.code && <span className="text-[10px] text-slate-600">{t.code}</span>}
                </div>
                <StatusChip status={t.status} />
              </div>
              <p className="text-[11px] text-slate-500 mt-1 flex items-center gap-2">
                <span className="inline-flex items-center gap-1"><Users className="w-3 h-3" /> {t.member_count}{t.capacity ? `/${t.capacity}` : ''}</span>
                {t.leader_name && <span className="inline-flex items-center gap-1"><Crown className="w-3 h-3 text-amber-400/70" /> {t.leader_name}</span>}
                {t.department_name && <span className="truncate">· {t.department_name}</span>}
              </p>
            </div>
          ))}
        </div>

        {/* Detail */}
        <div className="lg:col-span-3">
          {!selected ? (
            <div className="glass-panel border border-slate-800/85 rounded-2xl p-8 text-center text-slate-500 text-sm">Select a team to see members, targets and performance.</div>
          ) : (
            <div className="glass-panel border border-slate-800/85 rounded-2xl p-4 space-y-3">
              <div className="flex flex-wrap items-center justify-between gap-2">
                <div>
                  <h2 className="text-base font-semibold text-slate-100">{selected.name}</h2>
                  {selected.description && <p className="text-xs text-slate-500 mt-0.5">{selected.description}</p>}
                </div>
                <div className="flex items-center gap-1.5">
                  {(canManage || isLeaderOfSelected) && (
                    <>
                      <button onClick={() => setAssign('leads')} title="Assign leads" className="p-1.5 text-slate-400 hover:text-brand-300 cursor-pointer border border-slate-800 rounded-lg text-xs inline-flex items-center gap-1"><Send className="w-3.5 h-3.5" /> Leads</button>
                      <button onClick={() => setAssign('tasks')} title="Assign tasks" className="p-1.5 text-slate-400 hover:text-brand-300 cursor-pointer border border-slate-800 rounded-lg text-xs inline-flex items-center gap-1"><Send className="w-3.5 h-3.5" /> Tasks</button>
                      <button onClick={() => setModal('edit')} className="p-1.5 text-slate-400 hover:text-slate-200 cursor-pointer"><Pencil className="w-4 h-4" /></button>
                    </>
                  )}
                  {canManage && (
                    <>
                      <button onClick={async () => { await teamApi.update(selected.id, { status: selected.status === 'active' ? 'archived' : 'active' }); load(); }}
                              className="p-1.5 text-slate-400 hover:text-amber-300 cursor-pointer">
                        {selected.status === 'active' ? <Archive className="w-4 h-4" /> : <ArchiveRestore className="w-4 h-4" />}
                      </button>
                      <button onClick={() => removeTeam(selected)} className="p-1.5 text-slate-400 hover:text-red-400 cursor-pointer"><Trash2 className="w-4 h-4" /></button>
                    </>
                  )}
                </div>
              </div>
              <div className="flex gap-1 border-b border-slate-800/60">
                {([['members', 'Members', Users], ['performance', 'Performance', TrendingUp], ['calendar', 'Calendar', CalendarDays]] as const).map(([key, label, Icon]) => (
                  <button key={key} onClick={() => setTab(key)}
                          className={`px-3 py-1.5 text-xs font-medium inline-flex items-center gap-1.5 border-b-2 -mb-px cursor-pointer ${tab === key ? 'border-brand-500 text-brand-300' : 'border-transparent text-slate-500 hover:text-slate-300'}`}>
                    <Icon className="w-3.5 h-3.5" /> {label}
                  </button>
                ))}
              </div>
              {tab === 'members' && <MembersPanel team={selected} canManage={canManage || isLeaderOfSelected} users={users} onChanged={load} />}
              {tab === 'performance' && <PerformancePanel team={selected} canManage={canManage || isLeaderOfSelected} />}
              {tab === 'calendar' && <CalendarPanel team={selected} />}
            </div>
          )}
        </div>
      </div>

      {modal && <TeamModal initial={modal === 'edit' ? selected : null} users={users} depts={depts} canManage={canManage}
                           onClose={() => setModal(null)} onSaved={() => { setModal(null); load(); }} />}
      {assign && selected && <AssignModal team={selected} kind={assign} onClose={() => { setAssign(null); load(); }} />}
    </div>
  );
};
