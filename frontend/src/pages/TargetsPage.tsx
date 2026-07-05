import React, { useCallback, useEffect, useState } from 'react';
import {
  Target, Plus, Loader2, X, Check, User as UserIcon, Users, Building2, Gauge, BarChart3,
} from 'lucide-react';
import { targetApi, TargetRow, TargetDashboard, TARGET_SCOPES, TARGET_PERIODS } from '../services/targetApi';
import { performanceApi, KPI } from '../services/performanceApi';
import { teamApi } from '../services/teamApi';
import { departmentApi } from '../services/departmentApi';
import { userApi } from '../services/userApi';
import { useAuthStore } from '../store/authStore';
import { extractErrorMessage } from '../utils/errors';

const F = "w-full bg-slate-800/70 border border-slate-700/70 text-slate-200 py-2 px-3 rounded-lg text-sm";
const TEAM_METRICS = ['leads_converted', 'calls_made', 'tasks_completed', 'revenue', 'activities'];
const label = (m: string | null) => (m || '').replace(/_/g, ' ');
const fmtVal = (v: number, unit: string) => unit === 'currency' ? `₹${Math.round(v).toLocaleString()}` : unit === 'percent' ? `${v}%` : `${v}`;

const scopeIcon = (s: string) => s === 'individual' ? <UserIcon className="w-3.5 h-3.5 text-brand-400" />
  : s === 'team' ? <Users className="w-3.5 h-3.5 text-emerald-400" />
    : <Building2 className="w-3.5 h-3.5 text-indigo-300" />;

const StatusChip: React.FC<{ s: string }> = ({ s }) => {
  const tone = s === 'achieved' ? 'bg-emerald-500/10 text-emerald-400 border-emerald-500/20'
    : s === 'on_track' ? 'bg-brand-500/10 text-brand-300 border-brand-500/20'
      : s === 'at_risk' ? 'bg-amber-500/10 text-amber-400 border-amber-500/20'
        : 'bg-red-500/10 text-red-400 border-red-500/20';
  return <span className={`px-2 py-0.5 text-[10px] font-semibold rounded-md border ${tone}`}>{s.replace('_', ' ')}</span>;
};

/* ── Create modal (delegates by scope) ── */
const CreateModal: React.FC<{ kpis: KPI[]; users: any[]; teams: any[]; depts: any[]; onClose: () => void; onSaved: () => void }> =
  ({ kpis, users, teams, depts, onClose, onSaved }) => {
    const [f, setF] = useState<any>({
      scope: 'individual', period: 'monthly', target_value: '', start_date: '', end_date: '',
      user_id: '', kpi_id: kpis[0]?.id || '', team_id: '', department_id: '', name: '', metric: 'leads_converted',
    });
    const [busy, setBusy] = useState(false);
    const [error, setError] = useState<string | null>(null);
    const save = async () => {
      if (!f.target_value) { setError('Target value is required'); return; }
      setBusy(true); setError(null);
      try {
        const base: any = { scope: f.scope, period: f.period, target_value: Number(f.target_value), start_date: f.start_date || undefined, end_date: f.end_date || undefined };
        if (f.scope === 'individual') { base.user_id = f.user_id; base.kpi_id = f.kpi_id; }
        else if (f.scope === 'team') { base.team_id = f.team_id; base.name = f.name; base.metric = f.metric; }
        else { base.department_id = f.department_id; base.name = f.name; base.metric = f.metric; }
        await targetApi.create(base);
        onSaved();
      } catch (e: any) { setError(extractErrorMessage(e, 'Failed to create')); } finally { setBusy(false); }
    };
    return (
      <div className="fixed inset-0 z-40 flex items-center justify-center bg-black/50 backdrop-blur-sm p-4">
        <div className="glass-panel border border-slate-800/85 rounded-2xl w-full max-w-md bg-slate-900 max-h-[90vh] overflow-y-auto">
          <div className="flex items-center justify-between p-4 border-b border-slate-800/60">
            <h3 className="text-sm font-semibold text-slate-200 flex items-center gap-2"><Target className="w-4 h-4 text-brand-400" /> New target</h3>
            <button onClick={onClose} className="p-1 text-slate-500 hover:text-slate-300 cursor-pointer"><X className="w-4 h-4" /></button>
          </div>
          <div className="p-4 space-y-3">
            {error && <div className="p-2.5 bg-red-500/10 border border-red-500/20 text-red-400 rounded-lg text-xs">{error}</div>}
            <div className="flex gap-2">
              {TARGET_SCOPES.map((s) => (
                <button key={s} onClick={() => setF({ ...f, scope: s })} className={`flex-1 py-1.5 text-xs rounded-lg border cursor-pointer capitalize inline-flex items-center justify-center gap-1.5 ${f.scope === s ? 'bg-brand-500/15 text-brand-300 border-brand-500/30' : 'bg-slate-800/40 text-slate-400 border-slate-700/40'}`}>{scopeIcon(s)} {s}</button>
              ))}
            </div>
            {f.scope === 'individual' && (
              <>
                <select value={f.user_id} onChange={(e) => setF({ ...f, user_id: e.target.value })} className={F}>
                  <option value="">Select user…</option>
                  {users.map((u) => <option key={u.id} value={u.id}>{`${u.first_name || ''} ${u.last_name || ''}`.trim() || u.email}</option>)}
                </select>
                <select value={f.kpi_id} onChange={(e) => setF({ ...f, kpi_id: e.target.value })} className={F}>
                  <option value="">Select KPI…</option>
                  {kpis.map((k) => <option key={k.id} value={k.id}>{k.name}</option>)}
                </select>
              </>
            )}
            {f.scope === 'team' && (
              <>
                <select value={f.team_id} onChange={(e) => setF({ ...f, team_id: e.target.value })} className={F}>
                  <option value="">Select team…</option>
                  {teams.map((t) => <option key={t.id} value={t.id}>{t.name}</option>)}
                </select>
                <input value={f.name} onChange={(e) => setF({ ...f, name: e.target.value })} placeholder="Target name" className={F} />
                <select value={f.metric} onChange={(e) => setF({ ...f, metric: e.target.value })} className={F}>
                  {TEAM_METRICS.map((m) => <option key={m} value={m}>{label(m)}</option>)}
                </select>
              </>
            )}
            {f.scope === 'department' && (
              <>
                <select value={f.department_id} onChange={(e) => setF({ ...f, department_id: e.target.value })} className={F}>
                  <option value="">Select department…</option>
                  {depts.map((d) => <option key={d.id} value={d.id}>{d.name}</option>)}
                </select>
                <input value={f.name} onChange={(e) => setF({ ...f, name: e.target.value })} placeholder="Target name" className={F} />
                <select value={f.metric} onChange={(e) => setF({ ...f, metric: e.target.value })} className={F}>
                  {TEAM_METRICS.map((m) => <option key={m} value={m}>{label(m)}</option>)}
                </select>
              </>
            )}
            <div className="grid grid-cols-2 gap-2">
              <select value={f.period} onChange={(e) => setF({ ...f, period: e.target.value })} className={F}>
                {TARGET_PERIODS.map((p) => <option key={p} value={p}>{p}</option>)}
              </select>
              <input type="number" value={f.target_value} onChange={(e) => setF({ ...f, target_value: e.target.value })} placeholder="Target value" className={F} />
            </div>
            <div className="grid grid-cols-2 gap-2">
              <label className="text-xs text-slate-400">Start (optional)<input type="date" value={f.start_date} onChange={(e) => setF({ ...f, start_date: e.target.value })} className={F} /></label>
              <label className="text-xs text-slate-400">End (optional)<input type="date" value={f.end_date} onChange={(e) => setF({ ...f, end_date: e.target.value })} className={F} /></label>
            </div>
            <button onClick={save} disabled={busy} className="w-full inline-flex items-center justify-center gap-2 bg-gradient-to-r from-brand-500 to-indigo-500 text-white font-medium py-2 px-4 rounded-lg text-sm disabled:opacity-40 cursor-pointer">
              {busy ? <Loader2 className="w-4 h-4 animate-spin" /> : <Check className="w-4 h-4" />} Create
            </button>
          </div>
        </div>
      </div>
    );
  };

/* ── Page ── */
export const TargetsPage: React.FC = () => {
  const { user } = useAuthStore();
  const isManager = user?.role === 'OrgAdmin' || user?.role === 'Manager';

  const [dash, setDash] = useState<TargetDashboard | null>(null);
  const [rows, setRows] = useState<TargetRow[]>([]);
  const [scope, setScope] = useState('');
  const [period, setPeriod] = useState('');
  const [createOpen, setCreateOpen] = useState(false);
  const [kpis, setKpis] = useState<KPI[]>([]);
  const [users, setUsers] = useState<any[]>([]);
  const [teams, setTeams] = useState<any[]>([]);
  const [depts, setDepts] = useState<any[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  const loadDash = useCallback(() => { targetApi.dashboard().then(setDash).catch(() => {}); }, []);
  const load = useCallback(async () => {
    setLoading(true); setError(null);
    try { setRows(await targetApi.list({ scope: scope || undefined, period: period || undefined })); }
    catch (e: any) { setError(extractErrorMessage(e, 'Failed to load targets')); } finally { setLoading(false); }
  }, [scope, period]);
  useEffect(() => { load(); }, [load]);
  useEffect(() => { loadDash(); }, [loadDash]);
  useEffect(() => {
    if (isManager) {
      performanceApi.listKpis({ status: 'active' }).then(setKpis).catch(() => {});
      userApi.getUsers({ is_active: true, limit: 200 }).then(setUsers).catch(() => {});
      teamApi.list({}).then((t) => setTeams(t.items)).catch(() => {});
      departmentApi.list({}).then((d) => setDepts(d.items)).catch(() => {});
    }
  }, [isManager]);

  return (
    <div className="p-4 sm:p-6 space-y-4">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <h1 className="text-lg font-bold text-slate-100 flex items-center gap-2"><Target className="w-5 h-5 text-brand-400" /> Targets</h1>
        {isManager && <button onClick={() => setCreateOpen(true)} className="inline-flex items-center gap-1.5 bg-gradient-to-r from-brand-500 to-indigo-500 text-white text-xs font-medium py-1.5 px-3 rounded-lg cursor-pointer"><Plus className="w-3.5 h-3.5" /> New target</button>}
      </div>

      {dash && (
        <div className="grid grid-cols-3 sm:grid-cols-6 gap-2">
          {[
            { label: 'Total', value: dash.total, icon: Target },
            { label: 'Achieved', value: dash.achieved, icon: Check },
            { label: 'On track', value: dash.on_track, icon: BarChart3 },
            { label: 'At risk', value: dash.at_risk, icon: Gauge },
            { label: 'Missed', value: dash.missed, icon: X },
            { label: 'Avg attain.', value: `${dash.avg_attainment}%`, icon: Gauge },
          ].map((s) => (
            <div key={s.label} className="glass-panel border border-slate-800/85 rounded-xl p-3">
              <p className="text-[10px] font-semibold text-slate-500 uppercase tracking-wider flex items-center gap-1"><s.icon className="w-3 h-3 text-brand-400" /> {s.label}</p>
              <p className="text-lg font-bold text-slate-100 mt-0.5">{s.value}</p>
            </div>
          ))}
        </div>
      )}

      {error && <div className="p-3 bg-red-500/10 border border-red-500/20 text-red-400 rounded-lg text-xs">{error}</div>}

      <div className="flex items-center gap-2 flex-wrap">
        <select value={scope} onChange={(e) => setScope(e.target.value)} className="bg-slate-800/70 border border-slate-700/70 text-slate-200 py-1.5 px-2 rounded-lg text-xs">
          <option value="">All scopes</option>
          {TARGET_SCOPES.map((s) => <option key={s} value={s} className="capitalize">{s}</option>)}
        </select>
        <select value={period} onChange={(e) => setPeriod(e.target.value)} className="bg-slate-800/70 border border-slate-700/70 text-slate-200 py-1.5 px-2 rounded-lg text-xs">
          <option value="">All periods</option>
          {TARGET_PERIODS.map((p) => <option key={p} value={p}>{p}</option>)}
        </select>
      </div>

      {loading ? (
        <div className="py-8 text-center text-slate-500"><Loader2 className="w-5 h-5 animate-spin inline" /></div>
      ) : (
        <div className="space-y-2">
          {rows.map((r) => (
            <div key={`${r.scope}-${r.id}`} className="p-3 rounded-xl border border-slate-800/85 bg-slate-950/30">
              <div className="flex items-center justify-between gap-2">
                <div className="flex items-center gap-2 min-w-0">
                  {scopeIcon(r.scope)}
                  <p className="text-sm text-slate-200 truncate">{r.scope_name} · <span className="text-slate-400">{r.name}</span></p>
                  <span className="text-[10px] text-slate-600">{r.period}</span>
                </div>
                <div className="flex items-center gap-2 shrink-0">
                  <span className="text-xs text-slate-300">{fmtVal(r.actual, r.unit)}/{fmtVal(r.target_value, r.unit)} · {r.attainment}%</span>
                  <StatusChip s={r.status_label} />
                </div>
              </div>
              <div className="h-1.5 bg-slate-800 rounded-full overflow-hidden mt-2">
                <div className={`h-full ${r.achieved ? 'bg-emerald-500' : r.status_label === 'on_track' ? 'bg-brand-500' : r.status_label === 'at_risk' ? 'bg-amber-500' : 'bg-red-500'}`} style={{ width: `${Math.min(100, r.attainment)}%` }} />
              </div>
              <p className="text-[10px] text-slate-600 mt-1">{label(r.metric)} · {r.start_date} → {r.end_date}</p>
            </div>
          ))}
          {!rows.length && <p className="text-xs text-slate-500 py-8 text-center">No targets found. {isManager ? 'Create one, or set individual goals in Performance, team targets in Teams, and department targets in Departments.' : ''}</p>}
        </div>
      )}

      {createOpen && <CreateModal kpis={kpis} users={users} teams={teams} depts={depts} onClose={() => setCreateOpen(false)} onSaved={() => { setCreateOpen(false); load(); loadDash(); }} />}
    </div>
  );
};
