import React, { useCallback, useEffect, useState } from 'react';
import {
  BrainCircuit, Loader2, Download, LayoutDashboard, Database, Lightbulb, Flame, AlertTriangle,
} from 'lucide-react';
import {
  predictiveApi as api, PredCatalog, PredDashboard, PredDatasetResult, Recommendation,
} from '../services/predictiveApi';
import { extractErrorMessage } from '../utils/errors';

const F = 'w-full bg-slate-800/70 border border-slate-700/70 text-slate-200 py-1.5 px-2 rounded-lg text-xs';
const card = 'glass-panel border border-slate-800/85 rounded-xl p-4';
const PRIORITY_TONE: Record<string, string> = {
  high: 'bg-red-500/10 text-red-300', medium: 'bg-amber-500/10 text-amber-300', low: 'bg-slate-700/40 text-slate-400',
};

const saveBlob = (blob: Blob, name: string) => {
  const a = document.createElement('a');
  a.href = URL.createObjectURL(blob);
  a.download = name;
  a.click();
  URL.revokeObjectURL(a.href);
};

export const PredictivePage: React.FC = () => {
  const [tab, setTab] = useState<'dashboard' | 'datasets' | 'recommendations'>('dashboard');
  const [catalog, setCatalog] = useState<PredCatalog | null>(null);
  const [dash, setDash] = useState<PredDashboard | null>(null);
  const [dsKey, setDsKey] = useState('lead_conversion');
  const [dataset, setDataset] = useState<PredDatasetResult | null>(null);
  const [recs, setRecs] = useState<Recommendation[]>([]);
  const [scope, setScope] = useState('all');
  const [loading, setLoading] = useState(true);
  const [err, setErr] = useState('');

  const load = useCallback(async () => {
    setLoading(true); setErr('');
    try {
      if (!catalog) setCatalog(await api.catalog());
      if (tab === 'dashboard') setDash(await api.dashboard());
      else if (tab === 'datasets') setDataset(await api.dataset(dsKey, 100));
      else setRecs(await api.recommendations(scope));
    } catch (e) { setErr(extractErrorMessage(e, 'Failed to load predictive data.')); } finally { setLoading(false); }
  }, [tab, catalog, dsKey, scope]);
  useEffect(() => { load(); }, [load]);

  const exportDs = async (fmt: 'csv' | 'json') => {
    try { saveBlob(await api.exportDataset(dsKey, fmt), `${dsKey}.${fmt}`); }
    catch (e) { setErr(extractErrorMessage(e, 'Export failed')); }
  };

  const meta = catalog?.datasets.find((d) => d.key === dsKey);
  return (
    <div className="space-y-5">
      <div>
        <h1 className="text-2xl font-extrabold text-slate-100 flex items-center gap-2"><BrainCircuit className="w-6 h-6 text-brand-400" /> Predictive Analytics</h1>
        <p className="text-sm text-slate-500 mt-1">Training-ready feature datasets and transparent heuristic scores — deterministic rules today, model-ready contracts for tomorrow. No AI involved.</p>
      </div>

      {err && <div className="text-xs text-red-400 bg-red-500/10 border border-red-500/20 rounded-lg px-3 py-2">{err}</div>}

      <div className="flex items-center gap-1 bg-slate-900/50 border border-slate-800/70 rounded-xl p-1 w-fit">
        {([['dashboard', 'Dashboard', LayoutDashboard], ['datasets', 'Datasets & Features', Database], ['recommendations', 'Recommendations', Lightbulb]] as [any, string, any][]).map(([k, l, Icon]) => (
          <button key={k} onClick={() => setTab(k)} className={`px-3 py-1.5 rounded-lg text-xs font-semibold flex items-center gap-1.5 cursor-pointer ${tab === k ? 'bg-brand-500/20 text-brand-300' : 'text-slate-400 hover:text-slate-200'}`}><Icon className="w-3.5 h-3.5" /> {l}</button>
        ))}
      </div>

      {loading ? (
        <div className="py-20 text-center text-slate-400"><Loader2 className="w-6 h-6 animate-spin inline" /></div>
      ) : tab === 'dashboard' && dash ? (
        <div className="space-y-4">
          <div className="grid grid-cols-2 md:grid-cols-5 gap-3">
            <div className={card}><p className="text-[10px] font-semibold text-slate-500 uppercase">Open leads</p><p className="text-xl font-bold text-slate-100 mt-1">{dash.open_leads}</p></div>
            <div className={card}><p className="text-[10px] font-semibold text-slate-500 uppercase">Expected pipeline</p><p className="text-xl font-bold text-emerald-400 mt-1">₹{Math.round(dash.expected_pipeline_value).toLocaleString()}</p></div>
            <div className={card}><p className="text-[10px] font-semibold text-slate-500 uppercase">High churn risk</p><p className="text-xl font-bold text-red-400 mt-1">{dash.customers_at_high_churn_risk}/{dash.customers_tracked}</p></div>
            <div className={card}><p className="text-[10px] font-semibold text-slate-500 uppercase">Collection risk</p><p className="text-xl font-bold text-amber-400 mt-1">{dash.invoices_at_collection_risk}/{dash.open_invoices}</p></div>
            <div className={card}><p className="text-[10px] font-semibold text-slate-500 uppercase">Recommendations</p><p className="text-xl font-bold text-slate-100 mt-1">{dash.recommendations}</p></div>
          </div>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
            <div className={card}>
              <p className="text-xs font-semibold text-slate-400 uppercase tracking-wider mb-2 flex items-center gap-1.5"><Flame className="w-3.5 h-3.5 text-orange-400" /> Hottest open leads</p>
              {dash.hot_leads.map((l) => (
                <div key={l.lead_id} className="flex items-center justify-between py-1.5 border-b border-slate-800/50 last:border-0 text-sm">
                  <div className="min-w-0"><p className="text-slate-200 truncate">{l.name}</p><p className="text-[10px] text-slate-500">₹{Math.round(l.value).toLocaleString()} · expected ₹{Math.round(l.expected_value || 0).toLocaleString()}</p></div>
                  <span className="text-emerald-400 font-bold text-sm shrink-0">{l.conversion_probability}%</span>
                </div>
              ))}
              {dash.hot_leads.length === 0 && <p className="text-xs text-slate-500">No open leads.</p>}
            </div>
            <div className={card}>
              <p className="text-xs font-semibold text-slate-400 uppercase tracking-wider mb-2 flex items-center gap-1.5"><AlertTriangle className="w-3.5 h-3.5 text-red-400" /> Churn-risk customers</p>
              {dash.at_risk_customers.map((c) => (
                <div key={c.customer_id} className="flex items-center justify-between py-1.5 border-b border-slate-800/50 last:border-0 text-sm">
                  <div className="min-w-0"><p className="text-slate-200 truncate">{c.customer_name}</p><p className="text-[10px] text-slate-500">last order {c.last_order_days ?? '—'}d ago · {c.active_contracts} active contract(s)</p></div>
                  <span className={`font-bold text-sm shrink-0 ${c.churn_risk >= 60 ? 'text-red-400' : 'text-amber-400'}`}>{c.churn_risk}</span>
                </div>
              ))}
              {dash.at_risk_customers.length === 0 && <p className="text-xs text-slate-500">No customers tracked yet.</p>}
            </div>
            <div className={card}>
              <p className="text-xs font-semibold text-slate-400 uppercase tracking-wider mb-2 flex items-center gap-1.5"><Lightbulb className="w-3.5 h-3.5 text-brand-400" /> Next best actions</p>
              {dash.top_recommendations.map((r, i) => (
                <div key={i} className="py-1.5 border-b border-slate-800/50 last:border-0">
                  <p className="text-sm text-slate-200">{r.action} <span className={`text-[9px] px-1 py-0.5 rounded ${PRIORITY_TONE[r.priority]}`}>{r.priority}</span></p>
                  <p className="text-[10px] text-slate-500 truncate">{r.entity_name} — {r.reason}</p>
                </div>
              ))}
              {dash.top_recommendations.length === 0 && <p className="text-xs text-slate-500">Nothing to recommend right now.</p>}
            </div>
          </div>
        </div>
      ) : tab === 'datasets' && catalog ? (
        <div className="space-y-3">
          <div className="flex items-center gap-2 flex-wrap">
            <select value={dsKey} onChange={(e) => setDsKey(e.target.value)} className={`${F} !w-72`}>
              {catalog.datasets.map((d) => <option key={d.key} value={d.key}>{d.label} ({d.key})</option>)}
            </select>
            <button onClick={() => exportDs('csv')} className="px-3 py-1.5 rounded-lg text-xs font-semibold bg-brand-500/20 text-brand-300 hover:bg-brand-500/30 cursor-pointer flex items-center gap-1.5"><Download className="w-3.5 h-3.5" /> Training CSV</button>
            <button onClick={() => exportDs('json')} className="px-3 py-1.5 rounded-lg text-xs font-semibold bg-slate-800/70 hover:bg-slate-700/70 text-slate-200 cursor-pointer flex items-center gap-1.5"><Download className="w-3.5 h-3.5" /> JSON</button>
          </div>
          {meta && (
            <div className={card}>
              <p className="text-sm font-semibold text-slate-100">{meta.label} <span className="text-[10px] text-slate-500">· entity: {meta.entity} · target: {meta.target}</span></p>
              <p className="text-[11px] text-slate-500 mt-0.5">{meta.description}</p>
              <div className="flex flex-wrap gap-1 mt-2">
                {meta.features.map((f) => <code key={f} className="text-[10px] bg-slate-950/50 text-brand-300 px-1.5 py-0.5 rounded">{f}</code>)}
              </div>
            </div>
          )}
          {dataset && (
            <div className={card}>
              <p className="text-[11px] text-slate-500 mb-2">{dataset.count} row(s) · generated {new Date(dataset.generated_at).toLocaleString()}</p>
              <div className="overflow-x-auto max-h-[480px] overflow-y-auto">
                <table className="w-full text-[11px]">
                  <thead><tr className="text-slate-400 border-b border-slate-800">{dataset.columns.map((c) => <th key={c} className="text-left py-1.5 px-2 whitespace-nowrap sticky top-0 bg-slate-900">{c}</th>)}</tr></thead>
                  <tbody>
                    {dataset.rows.map((r, i) => (
                      <tr key={i} className="border-b border-slate-800/50">
                        {dataset.columns.map((c) => <td key={c} className="py-1 px-2 text-slate-300 whitespace-nowrap max-w-[200px] truncate">{r[c] == null ? '—' : String(r[c])}</td>)}
                      </tr>
                    ))}
                  </tbody>
                </table>
                {dataset.rows.length === 0 && <p className="text-sm text-slate-500 py-8 text-center">No rows yet — this dataset fills as CRM data accumulates.</p>}
              </div>
            </div>
          )}
        </div>
      ) : tab === 'recommendations' ? (
        <div className="space-y-3">
          <div className="flex items-center gap-2">
            {['all', 'leads', 'customers'].map((s) => (
              <button key={s} onClick={() => setScope(s)} className={`px-3 py-1.5 rounded-lg text-xs font-semibold cursor-pointer capitalize ${scope === s ? 'bg-brand-500/20 text-brand-300' : 'bg-slate-800/60 text-slate-400 hover:text-slate-200'}`}>{s}</button>
            ))}
          </div>
          {recs.length === 0 && <p className="text-sm text-slate-500">No recommendations — everything looks handled.</p>}
          {recs.map((r, i) => (
            <div key={i} className="glass-panel border border-slate-800/85 rounded-xl p-3 flex items-center gap-3">
              <span className={`text-[10px] px-1.5 py-0.5 rounded shrink-0 ${PRIORITY_TONE[r.priority]}`}>{r.priority}</span>
              <div className="flex-1 min-w-0">
                <p className="text-sm text-slate-200">{r.action} <span className="text-[10px] text-slate-500">· {r.entity_type}</span></p>
                <p className="text-[11px] text-slate-500 truncate">{r.entity_name} — {r.reason}</p>
              </div>
            </div>
          ))}
        </div>
      ) : null}
    </div>
  );
};
