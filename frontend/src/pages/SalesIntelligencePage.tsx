import React, { useCallback, useEffect, useState } from 'react';
import {
  Briefcase, Loader2, Download, LayoutDashboard, ListChecks, Swords, TrendingUp, X,
  Sparkles, MessageSquareWarning, FileText, Receipt, GraduationCap, ArrowUpRight,
} from 'lucide-react';
import {
  salesIntelligenceApi as api, SalesIntelDashboard, DealIntelligence, CompetitorAnalysis, UpsellResult,
} from '../services/salesIntelligenceApi';
import { extractErrorMessage } from '../utils/errors';

const card = 'glass-panel border border-slate-800/85 rounded-xl p-4';
const F = 'bg-slate-800/70 border border-slate-700/70 text-slate-200 py-1.5 px-2 rounded-lg text-xs';
const BTN = 'px-3 py-1.5 rounded-lg text-xs font-semibold bg-brand-500/20 text-brand-300 hover:bg-brand-500/30 cursor-pointer flex items-center gap-1.5';
const HEALTH_TONE: Record<string, string> = { strong: 'text-emerald-400', moderate: 'text-amber-400', at_risk: 'text-red-400' };

const downloadText = (name: string, text: string) => {
  const a = document.createElement('a');
  a.href = URL.createObjectURL(new Blob([text], { type: 'text/csv' }));
  a.download = name; a.click(); URL.revokeObjectURL(a.href);
};
const inr = (n: number) => `₹${Math.round(n).toLocaleString()}`;

export const SalesIntelligencePage: React.FC = () => {
  const [tab, setTab] = useState<'dashboard' | 'deals' | 'competitors' | 'upsell'>('dashboard');
  const [dash, setDash] = useState<SalesIntelDashboard | null>(null);
  const [deals, setDeals] = useState<DealIntelligence[]>([]);
  const [comp, setComp] = useState<CompetitorAnalysis | null>(null);
  const [upsell, setUpsell] = useState<UpsellResult | null>(null);
  const [sort, setSort] = useState('expected_value');
  const [detail, setDetail] = useState<DealIntelligence | null>(null);
  const [loading, setLoading] = useState(true);
  const [err, setErr] = useState('');

  const load = useCallback(async () => {
    setLoading(true); setErr('');
    try {
      if (tab === 'dashboard') setDash(await api.dashboard());
      else if (tab === 'deals') setDeals((await api.deals({ sort })).rows);
      else if (tab === 'competitors') setComp(await api.competitorAnalysis());
      else setUpsell(await api.upsell());
    } catch (e) { setErr(extractErrorMessage(e, 'Failed to load sales intelligence.')); } finally { setLoading(false); }
  }, [tab, sort]);
  useEffect(() => { load(); }, [load]);

  return (
    <div className="space-y-5">
      <div className="flex items-center justify-between gap-3 flex-wrap">
        <div>
          <h1 className="text-2xl font-extrabold text-slate-100 flex items-center gap-2"><Briefcase className="w-6 h-6 text-brand-400" /> Sales Intelligence</h1>
          <p className="text-sm text-slate-500 mt-1">Win probability, deal risk, revenue prediction, coaching, proposals & competitor analysis.</p>
        </div>
        {tab === 'dashboard' && <button onClick={async () => { try { downloadText('sales-intelligence.csv', await api.exportCsv()); } catch (e) { setErr(extractErrorMessage(e, 'Export failed')); } }} className={BTN}><Download className="w-3.5 h-3.5" /> Export CSV</button>}
      </div>

      {err && <div className="text-xs text-red-400 bg-red-500/10 border border-red-500/20 rounded-lg px-3 py-2">{err}</div>}

      <div className="flex items-center gap-1 bg-slate-900/50 border border-slate-800/70 rounded-xl p-1 w-fit flex-wrap">
        {([['dashboard', 'Dashboard', LayoutDashboard], ['deals', 'Deals', ListChecks], ['competitors', 'Competitors', Swords], ['upsell', 'Upsell / Cross-sell', ArrowUpRight]] as [any, string, any][]).map(([k, l, Icon]) => (
          <button key={k} onClick={() => setTab(k)} className={`px-3 py-1.5 rounded-lg text-xs font-semibold flex items-center gap-1.5 cursor-pointer ${tab === k ? 'bg-brand-500/20 text-brand-300' : 'text-slate-400 hover:text-slate-200'}`}><Icon className="w-3.5 h-3.5" /> {l}</button>
        ))}
      </div>

      {loading ? (
        <div className="py-20 text-center text-slate-400"><Loader2 className="w-6 h-6 animate-spin inline" /></div>
      ) : tab === 'dashboard' && dash ? (
        <div className="space-y-4">
          <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
            <div className={card}><p className="text-[10px] font-semibold text-slate-500 uppercase">Open deals</p><p className="text-xl font-bold text-slate-100 mt-1">{dash.open_deals}</p></div>
            <div className={card}><p className="text-[10px] font-semibold text-slate-500 uppercase">Pipeline value</p><p className="text-xl font-bold text-slate-100 mt-1">{inr(dash.open_pipeline_value)}</p></div>
            <div className={card}><p className="text-[10px] font-semibold text-slate-500 uppercase flex items-center gap-1"><TrendingUp className="w-3 h-3 text-emerald-400" /> Weighted</p><p className="text-xl font-bold text-emerald-400 mt-1">{inr(dash.weighted_pipeline_value)}</p></div>
            <div className={card}><p className="text-[10px] font-semibold text-slate-500 uppercase">Avg win prob</p><p className="text-xl font-bold text-slate-100 mt-1">{dash.avg_win_probability}%</p></div>
          </div>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
            <div className={card}>
              <p className="text-xs font-semibold text-slate-400 uppercase mb-2">Top deals</p>
              {dash.top_deals.map((d) => <DealMini key={d.lead_id} d={d} onOpen={() => setDetail(d)} />)}
              {dash.top_deals.length === 0 && <p className="text-xs text-slate-500">No open deals.</p>}
            </div>
            <div className={card}>
              <p className="text-xs font-semibold text-slate-400 uppercase mb-2">At-risk deals</p>
              {dash.at_risk_deals.map((d) => <DealMini key={d.lead_id} d={d} onOpen={() => setDetail(d)} />)}
              {dash.at_risk_deals.length === 0 && <p className="text-xs text-slate-500">Nothing at risk.</p>}
            </div>
          </div>
          <div className={card}>
            <p className="text-xs font-semibold text-slate-400 uppercase mb-2">Revenue forecast (next 3)</p>
            <div className="flex items-end gap-3">
              {dash.revenue_forecast_next3.map((b) => (
                <div key={b.bucket} className="text-center">
                  <p className="text-sm font-bold text-slate-100">{inr(b.value)}</p>
                  <p className="text-[10px] text-slate-500">{b.bucket}</p>
                </div>
              ))}
              {dash.revenue_forecast_next3.length === 0 && <p className="text-xs text-slate-500">Not enough history.</p>}
            </div>
          </div>
        </div>
      ) : tab === 'deals' ? (
        <div className="space-y-3">
          <select value={sort} onChange={(e) => setSort(e.target.value)} className={F}>
            <option value="expected_value">Sort: expected value</option>
            <option value="win">Sort: win probability</option>
            <option value="risk">Sort: sales risk</option>
            <option value="value">Sort: deal value</option>
          </select>
          {deals.length === 0 && <p className="text-sm text-slate-500">No open deals.</p>}
          {deals.map((d) => (
            <button key={d.lead_id} onClick={() => setDetail(d)} className="w-full glass-panel border border-slate-800/85 rounded-xl p-3 flex items-center gap-3 text-left cursor-pointer hover:border-brand-500/30">
              <div className="flex flex-col items-center w-16 shrink-0">
                <span className="text-lg font-extrabold text-emerald-400">{d.win_probability}%</span>
                <span className="text-[9px] text-slate-500 uppercase">win</span>
              </div>
              <div className="flex-1 min-w-0">
                <div className="flex items-center gap-2 flex-wrap">
                  <span className="text-sm font-semibold text-slate-100 truncate">{d.name}</span>
                  <span className={`text-[11px] font-semibold ${HEALTH_TONE[d.health]}`}>{d.health.replace('_', ' ')}</span>
                  <span className="text-[10px] text-slate-500">{inr(d.value)} · exp {inr(d.expected_value)}</span>
                </div>
                <p className="text-[11px] text-slate-500 mt-0.5">risk {d.sales_risk} · loss {d.loss_risk}% · {d.recommended_action.action}</p>
              </div>
            </button>
          ))}
        </div>
      ) : tab === 'competitors' && comp ? (
        <div className={card}>
          <p className="text-xs font-semibold text-slate-400 uppercase mb-2">Competitor analysis <span className="text-slate-500">· {comp.lost_to_competitor} deals lost to competitors of {comp.total_analyzed} analyzed</span></p>
          {comp.competitors.length === 0 ? <p className="text-sm text-slate-500">No competitor mentions found.</p> : (
            <table className="w-full text-[11px]">
              <thead><tr className="text-slate-400 border-b border-slate-800"><th className="text-left py-1.5">Competitor</th><th className="text-right py-1.5">Mentions</th><th className="text-right py-1.5">Lost to</th><th className="text-right py-1.5">Won against</th></tr></thead>
              <tbody>
                {comp.competitors.map((c) => (
                  <tr key={c.competitor} className="border-b border-slate-800/50">
                    <td className="py-1.5 text-slate-200">{c.competitor}</td>
                    <td className="py-1.5 text-right text-slate-300">{c.mentions}</td>
                    <td className="py-1.5 text-right text-red-400">{c.lost_to}</td>
                    <td className="py-1.5 text-right text-emerald-400">{c.won_against}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>
      ) : tab === 'upsell' && upsell ? (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
          <div className={card}>
            <p className="text-xs font-semibold text-slate-400 uppercase mb-2 flex items-center gap-1.5"><ArrowUpRight className="w-3.5 h-3.5 text-emerald-400" /> Upsell ({upsell.upsell.length})</p>
            {upsell.upsell.map((u) => (
              <div key={u.customer_id} className="py-1.5 border-b border-slate-800/50 last:border-0">
                <p className="text-sm text-slate-200">{u.customer_name} <span className="text-[10px] text-slate-500">{inr(u.total_paid)}</span></p>
                <p className="text-[11px] text-slate-500">{u.reason}</p>
              </div>
            ))}
            {upsell.upsell.length === 0 && <p className="text-xs text-slate-500">No upsell candidates.</p>}
          </div>
          <div className={card}>
            <p className="text-xs font-semibold text-slate-400 uppercase mb-2">Cross-sell ({upsell.cross_sell.length})</p>
            {upsell.cross_sell.map((u) => (
              <div key={u.customer_id} className="py-1.5 border-b border-slate-800/50 last:border-0">
                <p className="text-sm text-slate-200">{u.customer_name}</p>
                <p className="text-[11px] text-slate-500">{u.reason}</p>
              </div>
            ))}
            {upsell.cross_sell.length === 0 && <p className="text-xs text-slate-500">No cross-sell candidates.</p>}
          </div>
        </div>
      ) : null}

      {detail && <DealModal deal={detail} onClose={() => setDetail(null)} setErr={setErr} />}
    </div>
  );
};

const DealMini: React.FC<{ d: DealIntelligence; onOpen: () => void }> = ({ d, onOpen }) => (
  <button onClick={onOpen} className="w-full text-left flex items-center justify-between py-1.5 border-b border-slate-800/50 last:border-0 cursor-pointer">
    <div className="min-w-0"><p className="text-sm text-slate-200 truncate">{d.name}</p><p className="text-[10px] text-slate-500">{inr(d.value)} · <span className={HEALTH_TONE[d.health]}>{d.health.replace('_', ' ')}</span></p></div>
    <span className="text-emerald-400 font-bold text-sm shrink-0">{d.win_probability}%</span>
  </button>
);

const DealModal: React.FC<{ deal: DealIntelligence; onClose: () => void; setErr: (s: string) => void }> = ({ deal, onClose, setErr }) => {
  const [tool, setTool] = useState<string | null>(null);
  const [output, setOutput] = useState<any>(null);
  const [objection, setObjection] = useState('');
  const [busy, setBusy] = useState(false);

  const run = async (kind: string) => {
    setBusy(true); setTool(kind); setOutput(null); setErr('');
    try {
      if (kind === 'summary') setOutput({ text: (await api.summary(deal.lead_id)).text });
      else if (kind === 'coaching') setOutput({ text: (await api.coaching(deal.lead_id)).text });
      else if (kind === 'proposal') setOutput({ text: (await api.proposal(deal.lead_id)).text });
      else if (kind === 'quotation') setOutput({ quote: await api.quotation(deal.lead_id) });
      else if (kind === 'objection') {
        if (!objection.trim()) { setErr('Enter the objection first'); setBusy(false); return; }
        setOutput({ text: (await api.objection(deal.lead_id, objection)).text });
      }
    } catch (e) { setErr(extractErrorMessage(e, 'Request failed')); } finally { setBusy(false); }
  };

  return (
    <div className="fixed inset-0 z-50 bg-black/60 flex items-center justify-center p-4" onClick={onClose}>
      <div className="glass-panel border border-slate-800 rounded-2xl w-full max-w-2xl max-h-[90vh] overflow-y-auto p-5 bg-slate-900" onClick={(e) => e.stopPropagation()}>
        <div className="flex items-center justify-between mb-3">
          <h3 className="text-sm font-bold text-slate-100 flex items-center gap-2"><Briefcase className="w-4 h-4 text-brand-400" /> {deal.name}
            <span className={`text-[11px] font-semibold ${HEALTH_TONE[deal.health]}`}>{deal.health.replace('_', ' ')}</span></h3>
          <button onClick={onClose} className="text-slate-500 hover:text-slate-300 cursor-pointer"><X className="w-4 h-4" /></button>
        </div>
        <div className="grid grid-cols-2 md:grid-cols-4 gap-3 mb-3">
          {[['Win', `${deal.win_probability}%`], ['Loss risk', `${deal.loss_risk}%`], ['Expected', inr(deal.expected_value)], ['Sales risk', deal.sales_risk]].map(([l, v]) => (
            <div key={l as string} className="bg-slate-950/40 border border-slate-800/60 rounded-lg p-2.5"><p className="text-[10px] text-slate-500 uppercase font-semibold">{l}</p><p className="text-lg font-bold text-slate-100">{v}</p></div>
          ))}
        </div>
        {deal.competitors && deal.competitors.length > 0 && (
          <p className="text-[11px] text-slate-400 mb-2">Competitors mentioned: <span className="text-red-300">{deal.competitors.join(', ')}</span></p>
        )}

        <div className="flex flex-wrap gap-2 mb-3">
          {[['summary', 'Deal summary', Sparkles], ['coaching', 'Coaching', GraduationCap], ['proposal', 'Proposal', FileText], ['quotation', 'Quotation', Receipt], ['objection', 'Objection', MessageSquareWarning]].map(([k, l, Icon]: any) => (
            <button key={k} onClick={() => k === 'objection' ? setTool('objection') : run(k)} className="px-2.5 py-1.5 rounded-lg text-[11px] font-semibold bg-slate-800/70 hover:bg-slate-700/70 text-slate-200 cursor-pointer flex items-center gap-1"><Icon className="w-3.5 h-3.5" /> {l}</button>
          ))}
        </div>

        {tool === 'objection' && !output && (
          <div className="flex items-center gap-2 mb-3">
            <input value={objection} onChange={(e) => setObjection(e.target.value)} placeholder="What did the prospect object to?" className={`${F} w-full`} />
            <button onClick={() => run('objection')} className={`${BTN} shrink-0`}>Respond</button>
          </div>
        )}

        {busy && <div className="py-6 text-center text-slate-400"><Loader2 className="w-5 h-5 animate-spin inline" /></div>}
        {output?.text && <div className={card}><p className="text-sm text-slate-200 whitespace-pre-wrap">{output.text}</p></div>}
        {output?.quote && (
          <div className={card}>
            <table className="w-full text-[11px] mb-2">
              <thead><tr className="text-slate-400 border-b border-slate-800"><th className="text-left py-1">Item</th><th className="text-right py-1">Qty</th><th className="text-right py-1">Amount</th></tr></thead>
              <tbody>{output.quote.line_items.map((li: any, i: number) => (
                <tr key={i} className="border-b border-slate-800/50"><td className="py-1 text-slate-300">{li.description}</td><td className="py-1 text-right text-slate-400">{li.qty}</td><td className="py-1 text-right text-slate-200">{inr(li.amount)}</td></tr>
              ))}</tbody>
            </table>
            <div className="text-[11px] text-slate-400 space-y-0.5">
              <p className="flex justify-between"><span>Subtotal</span><span>{inr(output.quote.subtotal)}</span></p>
              <p className="flex justify-between"><span>Tax (18%)</span><span>{inr(output.quote.tax)}</span></p>
              <p className="flex justify-between text-slate-100 font-semibold"><span>Total</span><span>{inr(output.quote.total)}</span></p>
            </div>
            <p className="text-[11px] text-slate-300 mt-2 italic">{output.quote.cover_note}</p>
          </div>
        )}
      </div>
    </div>
  );
};
