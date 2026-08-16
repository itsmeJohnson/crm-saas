import React, { useCallback, useEffect, useState } from 'react';
import {
  Brain, Loader2, Download, LayoutDashboard, Target, TrendingUp, Clock, Megaphone,
  Gauge, Layers, AlertTriangle, CheckCircle2,
} from 'lucide-react';
import {
  predictionEngineApi as api, PeDashboard, PeAccuracy, PeModel,
  PeTaskPrediction, PeCampaignPrediction,
} from '../services/predictionEngineApi';
import { useAuthStore } from '../store/authStore';
import { extractErrorMessage } from '../utils/errors';

const card = 'glass-panel border border-slate-800/85 rounded-xl p-4';
const BTN = 'px-3 py-1.5 rounded-lg text-xs font-semibold bg-brand-500/20 text-brand-300 hover:bg-brand-500/30 cursor-pointer flex items-center gap-1.5';
const BAND_TONE: Record<string, string> = {
  high: 'bg-emerald-500/15 text-emerald-300', medium: 'bg-amber-500/15 text-amber-300',
  low: 'bg-red-500/15 text-red-300', 'n/a': 'bg-slate-600/20 text-slate-400',
};

const downloadText = (name: string, text: string) => {
  const a = document.createElement('a');
  a.href = URL.createObjectURL(new Blob([text], { type: 'text/csv' }));
  a.download = name; a.click(); URL.revokeObjectURL(a.href);
};

const ConfBar: React.FC<{ value: number }> = ({ value }) => (
  <div className="w-full h-1.5 bg-slate-800 rounded-full overflow-hidden">
    <div className={`h-full ${value >= 70 ? 'bg-emerald-400' : value >= 40 ? 'bg-amber-400' : 'bg-red-400'}`}
         style={{ width: `${value}%` }} />
  </div>
);

export const PredictionEnginePage: React.FC = () => {
  const { user } = useAuthStore();
  const isManager = user?.role === 'OrgAdmin' || user?.role === 'Manager' || user?.role === 'SuperAdmin';
  const [tab, setTab] = useState<'dashboard' | 'tasks' | 'campaigns' | 'accuracy' | 'models'>('dashboard');
  const [dash, setDash] = useState<PeDashboard | null>(null);
  const [tasks, setTasks] = useState<PeTaskPrediction[] | null>(null);
  const [campaigns, setCampaigns] = useState<PeCampaignPrediction[] | null>(null);
  const [accuracy, setAccuracy] = useState<PeAccuracy | null>(null);
  const [models, setModels] = useState<PeModel[] | null>(null);
  const [loading, setLoading] = useState(true);
  const [err, setErr] = useState('');

  const load = useCallback(async () => {
    setLoading(true); setErr('');
    try {
      if (tab === 'dashboard') setDash(await api.dashboard());
      if (tab === 'tasks') setTasks((await api.tasks()).predictions);
      if (tab === 'campaigns') setCampaigns((await api.campaigns()).predictions);
      if (tab === 'accuracy') setAccuracy(await api.accuracy());
      if (tab === 'models') setModels((await api.models()).models);
    } catch (e) { setErr(extractErrorMessage(e, 'Failed to load prediction engine.')); }
    finally { setLoading(false); }
  }, [tab]);
  useEffect(() => { load(); }, [load]);

  if (!isManager) {
    return <div className="text-sm text-slate-400">The Prediction Engine is available to managers and admins.</div>;
  }

  return (
    <div className="space-y-5">
      <div className="flex items-center justify-between gap-3 flex-wrap">
        <div>
          <h1 className="text-2xl font-extrabold text-slate-100 flex items-center gap-2"><Brain className="w-6 h-6 text-brand-400" /> Prediction Engine</h1>
          <p className="text-sm text-slate-500 mt-1">Unified predictions — lead, sales, revenue, churn, collection, task-delay, employee & campaign — each with a confidence score and versioned model.</p>
        </div>
        <button onClick={async () => { try { downloadText('predictions.csv', await api.exportCsv()); } catch (e) { setErr(extractErrorMessage(e, 'Export failed')); } }} className={BTN}><Download className="w-3.5 h-3.5" /> Export CSV</button>
      </div>

      {err && <div className="text-xs text-red-400 bg-red-500/10 border border-red-500/20 rounded-lg px-3 py-2">{err}</div>}

      <div className="flex items-center gap-1 bg-slate-900/50 border border-slate-800/70 rounded-xl p-1 w-fit flex-wrap">
        {([['dashboard', 'Dashboard', LayoutDashboard], ['tasks', 'Task Delay', Clock], ['campaigns', 'Campaigns', Megaphone], ['accuracy', 'Accuracy', Gauge], ['models', 'Models', Layers]] as [any, string, any][]).map(([k, l, Icon]) => (
          <button key={k} onClick={() => setTab(k)} className={`px-3 py-1.5 rounded-lg text-xs font-semibold flex items-center gap-1.5 cursor-pointer ${tab === k ? 'bg-brand-500/20 text-brand-300' : 'text-slate-400 hover:text-slate-200'}`}><Icon className="w-3.5 h-3.5" /> {l}</button>
        ))}
      </div>

      {loading ? <div className="py-20 text-center text-slate-400"><Loader2 className="w-6 h-6 animate-spin inline" /></div> : (
        <>
          {tab === 'dashboard' && dash && (
            <div className="space-y-4">
              <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
                <div className={card}>
                  <p className="text-[10px] font-semibold text-slate-500 uppercase flex items-center gap-1"><Target className="w-3 h-3 text-brand-400" /> Weighted Pipeline</p>
                  <p className="text-xl font-bold text-slate-100 mt-1">₹{dash.sales.weighted_expected_value.toLocaleString()}</p>
                  <p className="text-[11px] text-slate-500">{dash.sales.open_deals} open deals · win rate {dash.sales.win_rate}%</p>
                  <div className="mt-2"><ConfBar value={dash.sales.confidence} /><p className="text-[10px] text-slate-500 mt-0.5">confidence {dash.sales.confidence}%</p></div>
                </div>
                <div className={card}>
                  <p className="text-[10px] font-semibold text-slate-500 uppercase flex items-center gap-1"><TrendingUp className="w-3 h-3 text-emerald-400" /> Revenue Forecast</p>
                  <p className="text-xl font-bold text-slate-100 mt-1">₹{(dash.revenue.total_forecast || 0).toLocaleString()}</p>
                  <p className="text-[11px] text-slate-500">trend {dash.revenue.trend} · backtest {dash.revenue.backtest_accuracy ?? '—'}%</p>
                  <div className="mt-2"><ConfBar value={dash.revenue.confidence} /><p className="text-[10px] text-slate-500 mt-0.5">confidence {dash.revenue.confidence}%</p></div>
                </div>
                <div className={card}>
                  <p className="text-[10px] font-semibold text-slate-500 uppercase flex items-center gap-1"><Clock className="w-3 h-3 text-amber-400" /> Tasks at Risk</p>
                  <p className="text-xl font-bold text-amber-400 mt-1">{dash.tasks.at_risk} <span className="text-sm text-slate-500">/ {dash.tasks.open}</span></p>
                  <p className="text-[11px] text-slate-500">open tasks predicted to slip</p>
                </div>
              </div>
              <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
                <div className={card}>
                  <h3 className="text-xs font-bold text-slate-300 mb-2">Highest Task Delay Risk</h3>
                  {dash.tasks.top.length === 0 ? <p className="text-xs text-slate-500">No open tasks.</p> :
                    dash.tasks.top.map((t: any) => (
                      <div key={t.task_id} className="flex justify-between items-center text-xs py-1 border-b border-slate-800/60 last:border-0">
                        <span className="text-slate-300 truncate pr-2">{t.title}</span>
                        <span className={`px-1.5 py-0.5 rounded shrink-0 ${BAND_TONE[t.band] || ''}`}>{t.delay_risk}%</span>
                      </div>
                    ))}
                </div>
                <div className={card}>
                  <h3 className="text-xs font-bold text-slate-300 mb-2">Customers at Churn Risk</h3>
                  {dash.customers_at_risk.length === 0 ? <p className="text-xs text-slate-500">No order-to-cash customers yet.</p> :
                    dash.customers_at_risk.map(c => (
                      <div key={c.customer_id} className="flex justify-between items-center text-xs py-1 border-b border-slate-800/60 last:border-0">
                        <span className="text-slate-300 truncate pr-2">{c.customer_name}</span>
                        <span className={`px-1.5 py-0.5 rounded shrink-0 ${c.churn_risk >= 60 ? BAND_TONE.low : c.churn_risk >= 30 ? BAND_TONE.medium : BAND_TONE.high}`}>{c.churn_risk}%</span>
                      </div>
                    ))}
                </div>
              </div>
            </div>
          )}

          {tab === 'tasks' && tasks && (
            <div className={card}>
              {tasks.length === 0 ? <p className="text-xs text-slate-500 py-6 text-center">No open tasks to predict.</p> : (
                <table className="w-full text-xs">
                  <thead><tr className="text-left text-[10px] uppercase text-slate-500 border-b border-slate-800/70">
                    <th className="py-2 pr-2">Task</th><th className="pr-2">Status</th><th className="pr-2">Due in (h)</th><th className="pr-2">Delay Risk</th><th className="pr-2">Top factor</th>
                  </tr></thead>
                  <tbody>
                    {tasks.map(t => (
                      <tr key={t.task_id} className="border-b border-slate-800/50 last:border-0">
                        <td className="py-2 pr-2 text-slate-200 font-medium">{t.title}{t.predicted_late && <AlertTriangle className="w-3 h-3 text-amber-400 inline ml-1" />}</td>
                        <td className="pr-2 text-slate-400">{t.status}</td>
                        <td className="pr-2 text-slate-400">{t.hours_to_due ?? '—'}</td>
                        <td className="pr-2"><span className={`px-1.5 py-0.5 rounded ${BAND_TONE[t.band] || ''}`}>{t.delay_risk}%</span></td>
                        <td className="pr-2 text-slate-500 truncate max-w-[220px]">{t.factors[0]?.factor || '—'}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              )}
            </div>
          )}

          {tab === 'campaigns' && campaigns && (
            <div className={card}>
              {campaigns.length === 0 ? <p className="text-xs text-slate-500 py-6 text-center">No pending campaigns to predict. Create a draft/scheduled campaign.</p> : (
                <table className="w-full text-xs">
                  <thead><tr className="text-left text-[10px] uppercase text-slate-500 border-b border-slate-800/70">
                    <th className="py-2 pr-2">Campaign</th><th className="pr-2">Channel</th><th className="pr-2">Audience</th><th className="pr-2">Exp. Conv.</th><th className="pr-2">Exp. Revenue</th><th className="pr-2">ROI</th><th className="pr-2">Basis</th>
                  </tr></thead>
                  <tbody>
                    {campaigns.map(c => (
                      <tr key={c.campaign_id} className="border-b border-slate-800/50 last:border-0">
                        <td className="py-2 pr-2 text-slate-200 font-medium">{c.name}</td>
                        <td className="pr-2 text-slate-400">{c.channel}</td>
                        <td className="pr-2 text-slate-400">{c.audience_size}</td>
                        <td className="pr-2 text-slate-400">{c.predicted.converted}</td>
                        <td className="pr-2 text-slate-400">₹{c.predicted.revenue.toLocaleString()}</td>
                        <td className="pr-2"><span className={c.predicted.roi_pct != null && c.predicted.roi_pct >= 0 ? 'text-emerald-400' : 'text-red-400'}>{c.predicted.roi_pct != null ? `${c.predicted.roi_pct}%` : '—'}</span></td>
                        <td className="pr-2 text-slate-500">{c.benchmark_source}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              )}
            </div>
          )}

          {tab === 'accuracy' && accuracy && (
            <div className="space-y-4">
              <div className={card}>
                <div className="flex items-center justify-between">
                  <h3 className="text-xs font-bold text-slate-300">Overall Accuracy</h3>
                  <span className="text-2xl font-bold text-slate-100">{accuracy.overall_accuracy ?? '—'}{accuracy.overall_accuracy != null ? '%' : ''}</span>
                </div>
              </div>
              <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
                <div className={card}>
                  <h3 className="text-xs font-bold text-slate-300 mb-2">Regression (holdout backtest / MAPE)</h3>
                  {accuracy.regression.map(r => (
                    <div key={r.model} className="flex justify-between items-center text-xs py-1 border-b border-slate-800/60 last:border-0">
                      <span className="text-slate-300">{r.model} <span className="text-slate-500">({r.metric})</span></span>
                      <span className="text-slate-400">{r.accuracy != null ? `${r.accuracy}% (MAPE ${r.mape})` : 'insufficient history'}</span>
                    </div>
                  ))}
                </div>
                <div className={card}>
                  <h3 className="text-xs font-bold text-slate-300 mb-2">Classification (calibration on labelled data)</h3>
                  {accuracy.classification.map(c => (
                    <div key={c.model} className="flex justify-between items-center text-xs py-1 border-b border-slate-800/60 last:border-0">
                      <span className="text-slate-300">{c.model} <span className="text-slate-500">({c.samples} samples)</span></span>
                      <span className="text-slate-400">{c.accuracy != null ? `${c.accuracy}% · Brier ${c.brier}` : 'insufficient data'}</span>
                    </div>
                  ))}
                </div>
              </div>
            </div>
          )}

          {tab === 'models' && models && (
            <div className={card}>
              <table className="w-full text-xs">
                <thead><tr className="text-left text-[10px] uppercase text-slate-500 border-b border-slate-800/70">
                  <th className="py-2 pr-2">Model</th><th className="pr-2">Version</th><th className="pr-2">Type</th><th className="pr-2">Target</th><th className="pr-2">Status</th>
                </tr></thead>
                <tbody>
                  {models.map(m => (
                    <tr key={m.key} className="border-b border-slate-800/50 last:border-0">
                      <td className="py-2 pr-2 text-slate-200 font-medium">{m.name}</td>
                      <td className="pr-2"><span className="px-1.5 py-0.5 rounded bg-slate-700/40 text-slate-300 font-mono">v{m.version}</span></td>
                      <td className="pr-2 text-slate-400">{m.type}</td>
                      <td className="pr-2 text-slate-500 truncate max-w-[280px]">{m.target}</td>
                      <td className="pr-2"><span className="text-emerald-400 flex items-center gap-1"><CheckCircle2 className="w-3 h-3" /> {m.status}</span></td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </>
      )}
    </div>
  );
};
