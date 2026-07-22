import React, { useCallback, useEffect, useState } from 'react';
import {
  Sparkles, Loader2, Download, LayoutDashboard, ThumbsUp, X, Clock, BarChart3,
  Check, Zap, Phone, UserCheck, Package, Workflow, Megaphone, BookOpen, ListChecks, TrendingUp,
} from 'lucide-react';
import {
  recommendationApi as api, RecFeed, RecAnalytics, Recommendation,
} from '../services/recommendationApi';
import { extractErrorMessage } from '../utils/errors';

const card = 'glass-panel border border-slate-800/85 rounded-xl p-4';
const BTN = 'px-3 py-1.5 rounded-lg text-xs font-semibold bg-brand-500/20 text-brand-300 hover:bg-brand-500/30 cursor-pointer flex items-center gap-1.5';
const PRIORITY_TONE: Record<string, string> = {
  high: 'border-l-red-400', medium: 'border-l-amber-400', low: 'border-l-slate-500',
};
const TYPE_ICON: Record<string, any> = {
  next_best_action: Zap, follow_up: Clock, call_time: Phone, agent: UserCheck,
  product: Package, workflow: Workflow, campaign: Megaphone, knowledge: BookOpen,
};
const TYPE_LABEL: Record<string, string> = {
  next_best_action: 'Next Best Action', follow_up: 'Follow-up', call_time: 'Call Time',
  agent: 'Agent', product: 'Product', workflow: 'Workflow', campaign: 'Campaign', knowledge: 'Knowledge',
};

const downloadText = (name: string, text: string) => {
  const a = document.createElement('a');
  a.href = URL.createObjectURL(new Blob([text], { type: 'text/csv' }));
  a.download = name; a.click(); URL.revokeObjectURL(a.href);
};

export const RecommendationsPage: React.FC = () => {
  const [tab, setTab] = useState<'feed' | 'analytics'>('feed');
  const [feed, setFeed] = useState<RecFeed | null>(null);
  const [analytics, setAnalytics] = useState<RecAnalytics | null>(null);
  const [loading, setLoading] = useState(true);
  const [err, setErr] = useState('');
  const [acting, setActing] = useState<string | null>(null);
  const [typeFilter, setTypeFilter] = useState('');

  const load = useCallback(async () => {
    setLoading(true); setErr('');
    try {
      if (tab === 'feed') setFeed(await api.personalized());
      if (tab === 'analytics') setAnalytics(await api.analytics());
    } catch (e) { setErr(extractErrorMessage(e, 'Failed to load recommendations.')); }
    finally { setLoading(false); }
  }, [tab]);
  useEffect(() => { load(); }, [load]);

  const respond = async (rec: Recommendation, action: string, snooze_hours?: number) => {
    setActing(rec.id || rec.rec_key);
    try {
      await api.feedback(rec.id
        ? { action, feedback_id: rec.id, snooze_hours }
        : { action, rec_key: rec.rec_key, rec_type: rec.rec_type, title: rec.title, snooze_hours });
      setFeed(f => f ? { ...f, recommendations: f.recommendations.filter(r => r.rec_key !== rec.rec_key) } : f);
    } catch (e) { setErr(extractErrorMessage(e, 'Action failed.')); }
    finally { setActing(null); }
  };

  const shown = feed?.recommendations.filter(r => !typeFilter || r.rec_type === typeFilter) || [];

  return (
    <div className="space-y-5">
      <div className="flex items-center justify-between gap-3 flex-wrap">
        <div>
          <h1 className="text-2xl font-extrabold text-slate-100 flex items-center gap-2"><Sparkles className="w-6 h-6 text-brand-400" /> Recommendations</h1>
          <p className="text-sm text-slate-500 mt-1">Personalized next best actions, follow-ups, call times, agents, products, workflows, campaigns & knowledge — ranked by your feedback.</p>
        </div>
        <button onClick={async () => { try { downloadText('recommendations.csv', await api.exportCsv()); } catch (e) { setErr(extractErrorMessage(e, 'Export failed')); } }} className={BTN}><Download className="w-3.5 h-3.5" /> Export CSV</button>
      </div>

      {err && <div className="text-xs text-red-400 bg-red-500/10 border border-red-500/20 rounded-lg px-3 py-2">{err}</div>}

      <div className="flex items-center gap-1 bg-slate-900/50 border border-slate-800/70 rounded-xl p-1 w-fit">
        {([['feed', 'My Feed', LayoutDashboard], ['analytics', 'Analytics', BarChart3]] as [any, string, any][]).map(([k, l, Icon]) => (
          <button key={k} onClick={() => setTab(k)} className={`px-3 py-1.5 rounded-lg text-xs font-semibold flex items-center gap-1.5 cursor-pointer ${tab === k ? 'bg-brand-500/20 text-brand-300' : 'text-slate-400 hover:text-slate-200'}`}><Icon className="w-3.5 h-3.5" /> {l}</button>
        ))}
      </div>

      {loading ? <div className="py-20 text-center text-slate-400"><Loader2 className="w-6 h-6 animate-spin inline" /></div> : (
        <>
          {tab === 'feed' && feed && (
            <div className="space-y-3">
              {feed.explanation && (feed.explanation.boosted_types.length > 0 || feed.explanation.muted_types.length > 0) && (
                <div className="text-[11px] text-slate-400 bg-slate-900/40 border border-slate-800/60 rounded-lg px-3 py-2 flex items-center gap-2 flex-wrap">
                  <TrendingUp className="w-3.5 h-3.5 text-brand-400" />
                  {feed.explanation.boosted_types.length > 0 && <span>Boosted: {feed.explanation.boosted_types.map(t => TYPE_LABEL[t] || t).join(', ')}.</span>}
                  {feed.explanation.muted_types.length > 0 && <span className="text-slate-500">Muted: {feed.explanation.muted_types.map(t => TYPE_LABEL[t] || t).join(', ')}.</span>}
                </div>
              )}
              <div className="flex items-center gap-1.5 flex-wrap">
                <button onClick={() => setTypeFilter('')} className={`px-2 py-1 rounded-lg text-[11px] cursor-pointer ${!typeFilter ? 'bg-brand-500/20 text-brand-300' : 'bg-slate-800/50 text-slate-400'}`}>All ({feed.recommendations.length})</button>
                {feed.types_present.map(t => {
                  const Icon = TYPE_ICON[t] || ListChecks;
                  return <button key={t} onClick={() => setTypeFilter(t)} className={`px-2 py-1 rounded-lg text-[11px] cursor-pointer flex items-center gap-1 ${typeFilter === t ? 'bg-brand-500/20 text-brand-300' : 'bg-slate-800/50 text-slate-400'}`}><Icon className="w-3 h-3" /> {TYPE_LABEL[t] || t}</button>;
                })}
              </div>
              {shown.length === 0 ? <div className={`${card} text-center text-xs text-slate-500 py-8`}>No recommendations right now — great, you're caught up.</div> :
                shown.map(rec => {
                  const Icon = TYPE_ICON[rec.rec_type] || ListChecks;
                  const busy = acting === (rec.id || rec.rec_key);
                  return (
                    <div key={rec.rec_key} className={`${card} border-l-2 ${PRIORITY_TONE[rec.priority] || 'border-l-slate-600'} flex items-start justify-between gap-3`}>
                      <div className="min-w-0">
                        <div className="flex items-center gap-2">
                          <Icon className="w-4 h-4 text-brand-400 shrink-0" />
                          <span className="text-sm font-semibold text-slate-100 truncate">{rec.title}</span>
                          <span className="text-[10px] px-1.5 py-0.5 rounded bg-slate-800/60 text-slate-400 shrink-0">{TYPE_LABEL[rec.rec_type] || rec.rec_type}</span>
                        </div>
                        <p className="text-xs text-slate-400 mt-1">{rec.reason}</p>
                      </div>
                      <div className="flex items-center gap-1.5 shrink-0">
                        {busy ? <Loader2 className="w-4 h-4 animate-spin text-slate-400" /> : (
                          <>
                            <button onClick={() => respond(rec, 'accepted')} title="Accept" className="p-1.5 rounded-lg bg-emerald-500/15 text-emerald-300 hover:bg-emerald-500/25 cursor-pointer"><Check className="w-3.5 h-3.5" /></button>
                            <button onClick={() => respond(rec, 'snoozed', 24)} title="Snooze 24h" className="p-1.5 rounded-lg bg-slate-700/40 text-slate-300 hover:bg-slate-700/60 cursor-pointer"><Clock className="w-3.5 h-3.5" /></button>
                            <button onClick={() => respond(rec, 'dismissed')} title="Dismiss" className="p-1.5 rounded-lg bg-red-500/15 text-red-300 hover:bg-red-500/25 cursor-pointer"><X className="w-3.5 h-3.5" /></button>
                          </>
                        )}
                      </div>
                    </div>
                  );
                })}
            </div>
          )}

          {tab === 'analytics' && analytics && (
            <div className="space-y-4">
              <div className="grid grid-cols-2 md:grid-cols-5 gap-3">
                <div className={card}><p className="text-[10px] font-semibold text-slate-500 uppercase">Shown</p><p className="text-xl font-bold text-slate-100 mt-1">{analytics.totals.shown || 0}</p></div>
                <div className={card}><p className="text-[10px] font-semibold text-slate-500 uppercase flex items-center gap-1"><ThumbsUp className="w-3 h-3 text-emerald-400" /> Accepted</p><p className="text-xl font-bold text-emerald-400 mt-1">{analytics.totals.accepted || 0}</p></div>
                <div className={card}><p className="text-[10px] font-semibold text-slate-500 uppercase">Dismissed</p><p className="text-xl font-bold text-red-400 mt-1">{analytics.totals.dismissed || 0}</p></div>
                <div className={card}><p className="text-[10px] font-semibold text-slate-500 uppercase">Pending</p><p className="text-xl font-bold text-slate-100 mt-1">{analytics.totals.pending || 0}</p></div>
                <div className={card}><p className="text-[10px] font-semibold text-slate-500 uppercase">Acceptance</p><p className="text-xl font-bold text-slate-100 mt-1">{analytics.overall_acceptance_rate ?? '—'}{analytics.overall_acceptance_rate != null ? '%' : ''}</p></div>
              </div>
              <div className={card}>
                <h3 className="text-xs font-bold text-slate-300 mb-2">Acceptance by Type</h3>
                {analytics.by_type.length === 0 ? <p className="text-xs text-slate-500">No feedback yet.</p> : (
                  <table className="w-full text-xs">
                    <thead><tr className="text-left text-[10px] uppercase text-slate-500 border-b border-slate-800/70">
                      <th className="py-2 pr-2">Type</th><th className="pr-2">Shown</th><th className="pr-2">Accepted</th><th className="pr-2">Dismissed</th><th className="pr-2">Acceptance</th>
                    </tr></thead>
                    <tbody>
                      {analytics.by_type.map(t => (
                        <tr key={t.rec_type} className="border-b border-slate-800/50 last:border-0">
                          <td className="py-2 pr-2 text-slate-200">{TYPE_LABEL[t.rec_type] || t.rec_type}</td>
                          <td className="pr-2 text-slate-400">{t.shown}</td>
                          <td className="pr-2 text-emerald-400">{t.accepted + t.completed}</td>
                          <td className="pr-2 text-red-400">{t.dismissed}</td>
                          <td className="pr-2 text-slate-300">{t.acceptance_rate != null ? `${t.acceptance_rate}%` : '—'}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                )}
              </div>
              <div className={card}>
                <h3 className="text-xs font-bold text-slate-300 mb-2">Recently Accepted</h3>
                {analytics.top_accepted.length === 0 ? <p className="text-xs text-slate-500">Nothing accepted yet.</p> :
                  analytics.top_accepted.map((a, i) => (
                    <div key={i} className="flex justify-between text-xs py-1 border-b border-slate-800/60 last:border-0">
                      <span className="text-slate-300 truncate pr-2">{a.title}</span>
                      <span className="text-slate-500 shrink-0">{TYPE_LABEL[a.rec_type] || a.rec_type}</span>
                    </div>
                  ))}
              </div>
            </div>
          )}
        </>
      )}
    </div>
  );
};
