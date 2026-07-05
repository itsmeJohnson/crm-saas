import React, { useCallback, useEffect, useState } from 'react';
import {
  Trophy, Target, Award, Plus, Loader2, X, Check, Trash2, Pencil, BarChart3, Gauge,
  Medal, TrendingUp, Sparkles,
} from 'lucide-react';
import {
  performanceApi, KPI, Goal, Scorecard, LeaderboardRow, Achievement, PerformanceDashboard,
  PerformanceReport, PERFORMANCE_METRICS,
} from '../services/performanceApi';
import { userApi } from '../services/userApi';
import { useAuthStore } from '../store/authStore';
import { extractErrorMessage } from '../utils/errors';

const F = "w-full bg-slate-800/70 border border-slate-700/70 text-slate-200 py-2 px-3 rounded-lg text-sm";
const label = (m: string) => m.replace(/_/g, ' ');
const fmt = (v: number, unit?: string | null) => unit === 'currency' ? `₹${Math.round(v).toLocaleString()}` : unit === 'percent' ? `${v}%` : `${v}`;
const badgeTone = (b: string | null) => b === 'Gold' ? 'text-amber-400' : b === 'Silver' ? 'text-slate-300' : 'text-orange-400';

/* ── KPI modal ── */
const KpiModal: React.FC<{ initial?: KPI | null; onClose: () => void; onSaved: () => void }> = ({ initial, onClose, onSaved }) => {
  const [f, setF] = useState<any>(initial ? { ...initial } : { name: '', code: '', metric: 'sales_revenue', weight: 1, higher_is_better: true, status: 'active' });
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const save = async () => {
    if (!f.name?.trim()) { setError('Name is required'); return; }
    setBusy(true); setError(null);
    try {
      const payload = { name: f.name, code: f.code || undefined, metric: f.metric, weight: Number(f.weight) || 1, higher_is_better: !!f.higher_is_better, status: f.status };
      if (initial) await performanceApi.updateKpi(initial.id, payload);
      else await performanceApi.createKpi(payload);
      onSaved();
    } catch (e: any) { setError(extractErrorMessage(e, 'Failed to save')); } finally { setBusy(false); }
  };
  return (
    <div className="fixed inset-0 z-40 flex items-center justify-center bg-black/50 backdrop-blur-sm p-4">
      <div className="glass-panel border border-slate-800/85 rounded-2xl w-full max-w-md bg-slate-900">
        <div className="flex items-center justify-between p-4 border-b border-slate-800/60">
          <h3 className="text-sm font-semibold text-slate-200 flex items-center gap-2"><Gauge className="w-4 h-4 text-brand-400" /> {initial ? 'Edit' : 'New'} KPI</h3>
          <button onClick={onClose} className="p-1 text-slate-500 hover:text-slate-300 cursor-pointer"><X className="w-4 h-4" /></button>
        </div>
        <div className="p-4 space-y-3">
          {error && <div className="p-2.5 bg-red-500/10 border border-red-500/20 text-red-400 rounded-lg text-xs">{error}</div>}
          <div className="grid grid-cols-2 gap-2">
            <input value={f.name} onChange={(e) => setF({ ...f, name: e.target.value })} placeholder="Name" className={F} />
            <input value={f.code || ''} onChange={(e) => setF({ ...f, code: e.target.value })} placeholder="Code" className={F} />
          </div>
          <select value={f.metric} onChange={(e) => setF({ ...f, metric: e.target.value })} className={F}>
            {PERFORMANCE_METRICS.map((m) => <option key={m} value={m}>{label(m)}</option>)}
          </select>
          <label className="text-xs text-slate-400 block">Weight (composite score)<input type="number" step="0.5" value={f.weight} onChange={(e) => setF({ ...f, weight: e.target.value })} className={F} /></label>
          <button onClick={save} disabled={busy} className="w-full inline-flex items-center justify-center gap-2 bg-gradient-to-r from-brand-500 to-indigo-500 text-white font-medium py-2 px-4 rounded-lg text-sm disabled:opacity-40 cursor-pointer">
            {busy ? <Loader2 className="w-4 h-4 animate-spin" /> : <Check className="w-4 h-4" />} {initial ? 'Save' : 'Create'}
          </button>
        </div>
      </div>
    </div>
  );
};

/* ── Goal modal ── */
const GoalModal: React.FC<{ kpis: KPI[]; users: any[]; onClose: () => void; onSaved: () => void }> = ({ kpis, users, onClose, onSaved }) => {
  const [f, setF] = useState<any>({ user_id: '', kpi_id: kpis[0]?.id || '', period: 'monthly', target_value: '', start_date: '', end_date: '' });
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const save = async () => {
    if (!f.user_id || !f.kpi_id || !f.target_value || !f.start_date || !f.end_date) { setError('All fields are required'); return; }
    setBusy(true); setError(null);
    try {
      await performanceApi.createGoal({ user_id: f.user_id, kpi_id: f.kpi_id, period: f.period, target_value: Number(f.target_value), start_date: f.start_date, end_date: f.end_date });
      onSaved();
    } catch (e: any) { setError(extractErrorMessage(e, 'Failed to set goal')); } finally { setBusy(false); }
  };
  return (
    <div className="fixed inset-0 z-40 flex items-center justify-center bg-black/50 backdrop-blur-sm p-4">
      <div className="glass-panel border border-slate-800/85 rounded-2xl w-full max-w-md bg-slate-900 max-h-[90vh] overflow-y-auto">
        <div className="flex items-center justify-between p-4 border-b border-slate-800/60">
          <h3 className="text-sm font-semibold text-slate-200 flex items-center gap-2"><Target className="w-4 h-4 text-brand-400" /> Set performance goal</h3>
          <button onClick={onClose} className="p-1 text-slate-500 hover:text-slate-300 cursor-pointer"><X className="w-4 h-4" /></button>
        </div>
        <div className="p-4 space-y-3">
          {error && <div className="p-2.5 bg-red-500/10 border border-red-500/20 text-red-400 rounded-lg text-xs">{error}</div>}
          <select value={f.user_id} onChange={(e) => setF({ ...f, user_id: e.target.value })} className={F}>
            <option value="">Select user…</option>
            {users.map((u) => <option key={u.id} value={u.id}>{`${u.first_name || ''} ${u.last_name || ''}`.trim() || u.email}</option>)}
          </select>
          <select value={f.kpi_id} onChange={(e) => setF({ ...f, kpi_id: e.target.value })} className={F}>
            {kpis.map((k) => <option key={k.id} value={k.id}>{k.name}</option>)}
          </select>
          <div className="grid grid-cols-2 gap-2">
            <select value={f.period} onChange={(e) => setF({ ...f, period: e.target.value })} className={F}>
              {['daily', 'weekly', 'monthly', 'quarterly', 'yearly'].map((p) => <option key={p} value={p}>{p}</option>)}
            </select>
            <input type="number" value={f.target_value} onChange={(e) => setF({ ...f, target_value: e.target.value })} placeholder="Target" className={F} />
          </div>
          <div className="grid grid-cols-2 gap-2">
            <label className="text-xs text-slate-400">Start<input type="date" value={f.start_date} onChange={(e) => setF({ ...f, start_date: e.target.value })} className={F} /></label>
            <label className="text-xs text-slate-400">End<input type="date" value={f.end_date} onChange={(e) => setF({ ...f, end_date: e.target.value })} className={F} /></label>
          </div>
          <button onClick={save} disabled={busy} className="w-full inline-flex items-center justify-center gap-2 bg-gradient-to-r from-brand-500 to-indigo-500 text-white font-medium py-2 px-4 rounded-lg text-sm disabled:opacity-40 cursor-pointer">
            {busy ? <Loader2 className="w-4 h-4 animate-spin" /> : <Check className="w-4 h-4" />} Set goal
          </button>
        </div>
      </div>
    </div>
  );
};

/* ── Page ── */
export const PerformancePage: React.FC = () => {
  const { user } = useAuthStore();
  const isManager = user?.role === 'OrgAdmin' || user?.role === 'Manager';
  const isAdmin = user?.role === 'OrgAdmin';

  const [tab, setTab] = useState<'scorecard' | 'leaderboard' | 'goals' | 'achievements' | 'kpis' | 'reports'>('scorecard');
  const [dash, setDash] = useState<PerformanceDashboard | null>(null);
  const [score, setScore] = useState<Scorecard | null>(null);
  const [board, setBoard] = useState<LeaderboardRow[]>([]);
  const [boardMetric, setBoardMetric] = useState('sales_revenue');
  const [goals, setGoals] = useState<Goal[]>([]);
  const [achievements, setAchievements] = useState<Achievement[]>([]);
  const [kpis, setKpis] = useState<KPI[]>([]);
  const [report, setReport] = useState<PerformanceReport | null>(null);
  const [users, setUsers] = useState<any[]>([]);
  const [kpiModal, setKpiModal] = useState<KPI | null | 'new'>(null);
  const [goalOpen, setGoalOpen] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const loadDash = useCallback(() => { performanceApi.dashboard().then(setDash).catch(() => {}); }, []);
  useEffect(() => { loadDash(); performanceApi.listKpis({ status: 'active' }).then(setKpis).catch(() => {}); }, [loadDash]);
  useEffect(() => { if (isManager) userApi.getUsers({ is_active: true, limit: 200 }).then(setUsers).catch(() => {}); }, [isManager]);

  const loadTab = useCallback(() => {
    setError(null);
    if (tab === 'scorecard') performanceApi.scorecard().then(setScore).catch((e) => setError(extractErrorMessage(e, 'Failed')));
    if (tab === 'leaderboard') performanceApi.leaderboard({ metric: boardMetric }).then(setBoard).catch(() => {});
    if (tab === 'goals') performanceApi.listGoals({}).then(setGoals).catch(() => {});
    if (tab === 'achievements') performanceApi.listAchievements({}).then(setAchievements).catch(() => {});
    if (tab === 'kpis') performanceApi.listKpis({}).then(setKpis).catch(() => {});
    if (tab === 'reports') performanceApi.report({}).then(setReport).catch(() => {});
  }, [tab, boardMetric]);
  useEffect(() => { loadTab(); }, [loadTab]);

  const evaluate = async () => {
    try { const r = await performanceApi.evaluate(); window.alert(`${r.awarded} achievement(s) awarded.`); loadTab(); loadDash(); }
    catch (e: any) { setError(extractErrorMessage(e, 'Failed')); }
  };
  const removeGoal = async (g: Goal) => {
    if (!window.confirm('Delete this goal?')) return;
    try { await performanceApi.deleteGoal(g.id); loadTab(); } catch (e: any) { setError(extractErrorMessage(e, 'Delete failed')); }
  };
  const removeKpi = async (k: KPI) => {
    if (!window.confirm(`Delete KPI "${k.name}"?`)) return;
    try { await performanceApi.deleteKpi(k.id); loadTab(); } catch (e: any) { setError(extractErrorMessage(e, 'Delete failed')); }
  };
  const seed = async () => {
    try { const r = await performanceApi.seedKpis(); window.alert(`${r.created} KPI(s) created.`); loadTab(); }
    catch (e: any) { setError(extractErrorMessage(e, 'Failed')); }
  };

  return (
    <div className="p-4 sm:p-6 space-y-4">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <h1 className="text-lg font-bold text-slate-100 flex items-center gap-2"><Trophy className="w-5 h-5 text-brand-400" /> Performance</h1>
      </div>

      {dash && (
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-2">
          {[
            { label: 'My score', value: dash.my_composite_score != null ? `${dash.my_composite_score}%` : '—', icon: Gauge },
            { label: 'Revenue (mo)', value: `₹${Math.round(dash.my_metrics.sales_revenue || 0).toLocaleString()}`, icon: TrendingUp },
            { label: 'Open goals', value: dash.my_open_goals, icon: Target },
            { label: 'Achievements', value: dash.my_achievements, icon: Award },
          ].map((s) => (
            <div key={s.label} className="glass-panel border border-slate-800/85 rounded-xl p-3">
              <p className="text-[10px] font-semibold text-slate-500 uppercase tracking-wider flex items-center gap-1"><s.icon className="w-3 h-3 text-brand-400" /> {s.label}</p>
              <p className="text-lg font-bold text-slate-100 mt-0.5 truncate">{s.value}</p>
            </div>
          ))}
        </div>
      )}

      {error && <div className="p-3 bg-red-500/10 border border-red-500/20 text-red-400 rounded-lg text-xs">{error}</div>}

      <div className="flex gap-1 border-b border-slate-800/60 flex-wrap">
        {([['scorecard', 'My Scorecard', Gauge], ['leaderboard', 'Leaderboards', Medal], ['goals', 'Goals & Targets', Target], ['achievements', 'Achievements', Award], ...(isAdmin ? [['kpis', 'KPIs', Sparkles]] as const : []), ...(isManager ? [['reports', 'Reports', BarChart3]] as const : [])] as const).map(([key, lbl, Icon]) => (
          <button key={key} onClick={() => setTab(key as any)} className={`px-3 py-1.5 text-xs font-medium inline-flex items-center gap-1.5 border-b-2 -mb-px cursor-pointer ${tab === key ? 'border-brand-500 text-brand-300' : 'border-transparent text-slate-500 hover:text-slate-300'}`}>
            <Icon className="w-3.5 h-3.5" /> {lbl}
          </button>
        ))}
      </div>

      {tab === 'scorecard' && score && (
        <div className="space-y-3">
          <div className="glass-panel border border-slate-800/85 rounded-2xl p-4">
            <div className="flex items-center justify-between">
              <p className="text-sm text-slate-300">Composite score <span className="text-slate-500">({score.date_from} → {score.date_to})</span></p>
              <p className="text-2xl font-bold text-brand-300">{score.composite_score != null ? `${score.composite_score}%` : '—'}</p>
            </div>
          </div>
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-2">
            {score.kpis.map((k) => (
              <div key={k.kpi_id} className="glass-panel border border-slate-800/85 rounded-xl p-3">
                <p className="text-xs font-semibold text-slate-200">{k.name}</p>
                <p className="text-xl font-bold text-slate-100 mt-1">{fmt(k.actual, k.unit)}{k.target != null && <span className="text-xs text-slate-500"> / {fmt(k.target, k.unit)}</span>}</p>
                {k.attainment != null && (
                  <div className="h-1.5 bg-slate-800 rounded-full overflow-hidden mt-1.5">
                    <div className={`h-full ${k.attainment >= 100 ? 'bg-emerald-500' : k.attainment >= 60 ? 'bg-brand-500' : 'bg-amber-500'}`} style={{ width: `${Math.min(100, k.attainment)}%` }} />
                  </div>
                )}
              </div>
            ))}
          </div>
        </div>
      )}

      {tab === 'leaderboard' && (
        <div className="space-y-3">
          <select value={boardMetric} onChange={(e) => setBoardMetric(e.target.value)} className="bg-slate-800/70 border border-slate-700/70 text-slate-200 py-1.5 px-2 rounded-lg text-xs w-56">
            {PERFORMANCE_METRICS.map((m) => <option key={m} value={m}>{label(m)}</option>)}
          </select>
          <div className="space-y-1.5">
            {board.map((r) => (
              <div key={r.user_id} className="flex items-center justify-between p-2.5 bg-slate-950/40 border border-slate-800/60 rounded-lg">
                <div className="flex items-center gap-3">
                  <span className={`w-6 text-center font-bold ${r.rank === 1 ? 'text-amber-400' : r.rank === 2 ? 'text-slate-300' : r.rank === 3 ? 'text-orange-400' : 'text-slate-500'}`}>#{r.rank}</span>
                  <span className="text-sm text-slate-200">{r.name}</span>
                </div>
                <span className="text-sm font-semibold text-slate-100">{boardMetric.includes('revenue') || boardMetric.includes('recovery') ? `₹${Math.round(r.value).toLocaleString()}` : boardMetric.includes('rate') || boardMetric.includes('score') ? `${r.value}%` : r.value}</span>
              </div>
            ))}
            {!board.length && <p className="text-xs text-slate-500 py-6 text-center">No data yet.</p>}
          </div>
        </div>
      )}

      {tab === 'goals' && (
        <div className="space-y-3">
          {isManager && <button onClick={() => setGoalOpen(true)} className="inline-flex items-center gap-1.5 bg-gradient-to-r from-brand-500 to-indigo-500 text-white text-xs font-medium py-1.5 px-3 rounded-lg cursor-pointer"><Plus className="w-3.5 h-3.5" /> Set goal</button>}
          <div className="space-y-2">
            {goals.map((g) => (
              <div key={g.id} className="p-3 rounded-xl border border-slate-800/85 bg-slate-950/30">
                <div className="flex items-center justify-between gap-2">
                  <div className="min-w-0">
                    <p className="text-sm text-slate-200 truncate">{g.user_name} · <span className="text-slate-400">{g.kpi_name}</span></p>
                    <p className="text-[11px] text-slate-500">{g.period} · {g.start_date} → {g.end_date}</p>
                  </div>
                  <div className="flex items-center gap-2 shrink-0">
                    <span className="text-xs text-slate-300">{fmt(g.actual, g.unit)}/{fmt(g.target_value, g.unit)} · {g.attainment}%</span>
                    {isManager && <button onClick={() => removeGoal(g)} className="text-slate-600 hover:text-red-400 cursor-pointer"><Trash2 className="w-3.5 h-3.5" /></button>}
                  </div>
                </div>
                <div className="h-1.5 bg-slate-800 rounded-full overflow-hidden mt-2">
                  <div className={`h-full ${g.attainment >= 100 ? 'bg-emerald-500' : g.attainment >= 60 ? 'bg-brand-500' : 'bg-amber-500'}`} style={{ width: `${Math.min(100, g.attainment)}%` }} />
                </div>
              </div>
            ))}
            {!goals.length && <p className="text-xs text-slate-500 py-6 text-center">No goals set.</p>}
          </div>
        </div>
      )}

      {tab === 'achievements' && (
        <div className="space-y-3">
          {isManager && <button onClick={evaluate} className="inline-flex items-center gap-1.5 border border-slate-800 text-slate-300 text-xs py-1.5 px-3 rounded-lg cursor-pointer"><Sparkles className="w-3.5 h-3.5" /> Evaluate goals now</button>}
          <div className="space-y-2">
            {achievements.map((a) => (
              <div key={a.id} className="flex items-center justify-between p-3 rounded-xl border border-slate-800/85 bg-slate-950/30">
                <div className="flex items-center gap-3">
                  <Medal className={`w-5 h-5 ${badgeTone(a.badge)}`} />
                  <div>
                    <p className="text-sm text-slate-200">{a.user_name} · {a.title}</p>
                    <p className="text-[11px] text-slate-500">{a.badge} · {a.attainment}% · {a.period_label}</p>
                  </div>
                </div>
                <span className="text-[11px] text-slate-500">{new Date(a.awarded_at).toLocaleDateString()}</span>
              </div>
            ))}
            {!achievements.length && <p className="text-xs text-slate-500 py-6 text-center">No achievements yet.</p>}
          </div>
        </div>
      )}

      {tab === 'kpis' && isAdmin && (
        <div className="space-y-3">
          <div className="flex items-center gap-2">
            <button onClick={() => setKpiModal('new')} className="inline-flex items-center gap-1.5 bg-gradient-to-r from-brand-500 to-indigo-500 text-white text-xs font-medium py-1.5 px-3 rounded-lg cursor-pointer"><Plus className="w-3.5 h-3.5" /> New KPI</button>
            <button onClick={seed} className="inline-flex items-center gap-1.5 border border-slate-800 text-slate-300 text-xs py-1.5 px-3 rounded-lg cursor-pointer"><Sparkles className="w-3.5 h-3.5" /> Seed default KPIs</button>
          </div>
          <div className="space-y-2">
            {kpis.map((k) => (
              <div key={k.id} className="p-3 rounded-xl border border-slate-800/85 bg-slate-950/30 flex items-center justify-between gap-2">
                <div>
                  <p className="text-sm text-slate-200 font-medium">{k.name} {k.code && <span className="text-[10px] text-slate-600">{k.code}</span>}</p>
                  <p className="text-[11px] text-slate-500 mt-0.5">metric: {label(k.metric)} · {k.unit} · weight {k.weight} · {k.status}</p>
                </div>
                <div className="flex items-center gap-1">
                  <button onClick={() => setKpiModal(k)} className="p-1.5 text-slate-500 hover:text-slate-300 cursor-pointer"><Pencil className="w-4 h-4" /></button>
                  <button onClick={() => removeKpi(k)} className="p-1.5 text-slate-500 hover:text-red-400 cursor-pointer"><Trash2 className="w-4 h-4" /></button>
                </div>
              </div>
            ))}
            {!kpis.length && <p className="text-xs text-slate-500 py-6 text-center">No KPIs yet — seed the defaults to start.</p>}
          </div>
        </div>
      )}

      {tab === 'reports' && isManager && report && (
        <div className="overflow-x-auto">
          <table className="w-full text-xs">
            <thead><tr className="text-left text-[10px] text-slate-500 uppercase">
              <th className="py-2 pr-2">User</th><th className="py-2 pr-2">Calls</th><th className="py-2 pr-2">Conv.</th><th className="py-2 pr-2">CVR</th><th className="py-2 pr-2">Sales</th><th className="py-2 pr-2">Recovery</th><th className="py-2 pr-2">Tasks</th><th className="py-2">Att.</th>
            </tr></thead>
            <tbody>
              {report.rows.map((r) => (
                <tr key={r.user_id} className="border-t border-slate-800/50 text-slate-300">
                  <td className="py-1.5 pr-2">{r.name}</td>
                  <td className="py-1.5 pr-2">{r.calls_made}</td>
                  <td className="py-1.5 pr-2">{r.leads_converted}</td>
                  <td className="py-1.5 pr-2">{r.conversion_rate}%</td>
                  <td className="py-1.5 pr-2">₹{Math.round(r.sales_revenue).toLocaleString()}</td>
                  <td className="py-1.5 pr-2">₹{Math.round(r.recovery_amount).toLocaleString()}</td>
                  <td className="py-1.5 pr-2">{r.tasks_completed}</td>
                  <td className="py-1.5">{r.attendance_score}%</td>
                </tr>
              ))}
            </tbody>
          </table>
          {!report.rows.length && <p className="text-xs text-slate-500 py-6 text-center">No data for this period.</p>}
        </div>
      )}

      {kpiModal && <KpiModal initial={kpiModal === 'new' ? null : kpiModal} onClose={() => setKpiModal(null)} onSaved={() => { setKpiModal(null); loadTab(); }} />}
      {goalOpen && <GoalModal kpis={kpis} users={users} onClose={() => setGoalOpen(false)} onSaved={() => { setGoalOpen(false); loadTab(); loadDash(); }} />}
    </div>
  );
};
