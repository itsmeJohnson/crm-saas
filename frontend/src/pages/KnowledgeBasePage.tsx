import React, { useCallback, useEffect, useState } from 'react';
import {
  BookOpen, Loader2, Download, LayoutDashboard, Search, MessageCircleQuestion,
  Sparkles, Plus, CheckCircle2, XCircle, Send, Archive, History, ThumbsUp,
  ThumbsDown, FolderTree, RefreshCw, Eye,
} from 'lucide-react';
import {
  knowledgeApi as api, KbArticle, KbCategory, KbDashboard, KbFaq, KbSearchResult, KbAskResult,
} from '../services/knowledgeApi';
import { useAuthStore } from '../store/authStore';
import { extractErrorMessage } from '../utils/errors';

const card = 'glass-panel border border-slate-800/85 rounded-xl p-4';
const F = 'w-full bg-slate-800/70 border border-slate-700/70 text-slate-200 py-1.5 px-2 rounded-lg text-xs';
const BTN = 'px-3 py-1.5 rounded-lg text-xs font-semibold bg-brand-500/20 text-brand-300 hover:bg-brand-500/30 cursor-pointer flex items-center gap-1.5';
const BTN2 = 'px-2 py-1 rounded-lg text-[11px] font-semibold cursor-pointer flex items-center gap-1';

const STATUS_TONE: Record<string, string> = {
  draft: 'bg-slate-500/15 text-slate-300', pending_review: 'bg-amber-500/15 text-amber-300',
  published: 'bg-emerald-500/15 text-emerald-300', rejected: 'bg-red-500/15 text-red-300',
  archived: 'bg-slate-600/20 text-slate-400',
};

const downloadText = (name: string, text: string) => {
  const a = document.createElement('a');
  a.href = URL.createObjectURL(new Blob([text], { type: 'text/csv' }));
  a.download = name; a.click(); URL.revokeObjectURL(a.href);
};

const emptyForm = { title: '', content: '', summary: '', article_type: 'article', category_id: '', tags: '', visibility: 'all' };

export const KnowledgeBasePage: React.FC = () => {
  const { user } = useAuthStore();
  const isManager = user?.role === 'OrgAdmin' || user?.role === 'Manager' || user?.role === 'SuperAdmin';
  const [tab, setTab] = useState<'dashboard' | 'articles' | 'faq' | 'ask'>('dashboard');
  const [dash, setDash] = useState<KbDashboard | null>(null);
  const [articles, setArticles] = useState<KbArticle[]>([]);
  const [cats, setCats] = useState<KbCategory[]>([]);
  const [faqs, setFaqs] = useState<KbFaq[]>([]);
  const [loading, setLoading] = useState(true);
  const [err, setErr] = useState('');
  const [statusFilter, setStatusFilter] = useState('');
  const [typeFilter, setTypeFilter] = useState('');
  const [q, setQ] = useState('');

  const [showForm, setShowForm] = useState(false);
  const [form, setForm] = useState<any>(emptyForm);
  const [editId, setEditId] = useState<string | null>(null);
  const [detail, setDetail] = useState<KbArticle | null>(null);
  const [versions, setVersions] = useState<any[] | null>(null);
  const [newCat, setNewCat] = useState('');

  const [searchQ, setSearchQ] = useState('');
  const [results, setResults] = useState<KbSearchResult[] | null>(null);
  const [question, setQuestion] = useState('');
  const [answer, setAnswer] = useState<KbAskResult | null>(null);
  const [asking, setAsking] = useState(false);

  const load = useCallback(async () => {
    setLoading(true); setErr('');
    try {
      if (tab === 'dashboard') setDash(await api.dashboard());
      if (tab === 'articles') {
        const params: any = {};
        if (statusFilter) params.status = statusFilter;
        if (typeFilter) params.article_type = typeFilter;
        if (q) params.q = q;
        const [list, categories] = await Promise.all([api.articles(params), api.categories()]);
        setArticles(list.items); setCats(categories);
      }
      if (tab === 'faq') setFaqs(await api.faq());
    } catch (e) { setErr(extractErrorMessage(e, 'Failed to load knowledge base.')); } finally { setLoading(false); }
  }, [tab, statusFilter, typeFilter, q]);
  useEffect(() => { load(); }, [load]);

  const saveArticle = async () => {
    try {
      const payload: any = { ...form, category_id: form.category_id || null, tags: form.tags ? form.tags.split(',').map((t: string) => t.trim()).filter(Boolean) : [] };
      if (editId) await api.updateArticle(editId, payload); else await api.createArticle(payload);
      setShowForm(false); setForm(emptyForm); setEditId(null); load();
    } catch (e) { setErr(extractErrorMessage(e, 'Failed to save article.')); }
  };

  const act = async (fn: () => Promise<any>) => {
    try { await fn(); setDetail(null); setVersions(null); load(); }
    catch (e) { setErr(extractErrorMessage(e, 'Action failed.')); }
  };

  const openDetail = async (id: string) => {
    try { setDetail(await api.article(id)); setVersions(null); }
    catch (e) { setErr(extractErrorMessage(e, 'Failed to open article.')); }
  };

  const catName = (id: string | null) => cats.find(c => c.id === id)?.name || '—';

  return (
    <div className="space-y-5">
      <div className="flex items-center justify-between gap-3 flex-wrap">
        <div>
          <h1 className="text-2xl font-extrabold text-slate-100 flex items-center gap-2"><BookOpen className="w-6 h-6 text-brand-400" /> Knowledge Base</h1>
          <p className="text-sm text-slate-500 mt-1">Articles, FAQ & documents with semantic search, approval workflow and AI answers grounded in your knowledge.</p>
        </div>
        <div className="flex items-center gap-2">
          {isManager && tab === 'dashboard' && (
            <>
              <button onClick={() => act(() => api.reindex())} className={BTN}><RefreshCw className="w-3.5 h-3.5" /> Reindex</button>
              <button onClick={async () => { try { downloadText('knowledge-base.csv', await api.exportCsv()); } catch (e) { setErr(extractErrorMessage(e, 'Export failed')); } }} className={BTN}><Download className="w-3.5 h-3.5" /> Export CSV</button>
            </>
          )}
          {tab === 'articles' && <button onClick={() => { setForm(emptyForm); setEditId(null); setShowForm(true); }} className={BTN}><Plus className="w-3.5 h-3.5" /> New Article</button>}
        </div>
      </div>

      {err && <div className="text-xs text-red-400 bg-red-500/10 border border-red-500/20 rounded-lg px-3 py-2">{err}</div>}

      <div className="flex items-center gap-1 bg-slate-900/50 border border-slate-800/70 rounded-xl p-1 w-fit">
        {([['dashboard', 'Dashboard', LayoutDashboard], ['articles', 'Articles', BookOpen], ['faq', 'FAQ', MessageCircleQuestion], ['ask', 'Search & Ask AI', Sparkles]] as [any, string, any][]).map(([k, l, Icon]) => (
          <button key={k} onClick={() => setTab(k)} className={`px-3 py-1.5 rounded-lg text-xs font-semibold flex items-center gap-1.5 cursor-pointer ${tab === k ? 'bg-brand-500/20 text-brand-300' : 'text-slate-400 hover:text-slate-200'}`}><Icon className="w-3.5 h-3.5" /> {l}</button>
        ))}
      </div>

      {loading && tab !== 'ask' ? <div className="py-20 text-center text-slate-400"><Loader2 className="w-6 h-6 animate-spin inline" /></div> : (
        <>
          {tab === 'dashboard' && dash && (
            <div className="space-y-4">
              <div className="grid grid-cols-2 md:grid-cols-6 gap-3">
                <div className={card}><p className="text-[10px] font-semibold text-slate-500 uppercase">Articles</p><p className="text-xl font-bold text-slate-100 mt-1">{dash.totals.articles}</p></div>
                <div className={card}><p className="text-[10px] font-semibold text-slate-500 uppercase">Published</p><p className="text-xl font-bold text-emerald-400 mt-1">{dash.totals.by_status.published || 0}</p></div>
                <div className={card}><p className="text-[10px] font-semibold text-slate-500 uppercase">Pending Review</p><p className="text-xl font-bold text-amber-400 mt-1">{dash.totals.by_status.pending_review || 0}</p></div>
                <div className={card}><p className="text-[10px] font-semibold text-slate-500 uppercase">Categories</p><p className="text-xl font-bold text-slate-100 mt-1">{dash.totals.categories}</p></div>
                <div className={card}><p className="text-[10px] font-semibold text-slate-500 uppercase">Indexed</p><p className="text-xl font-bold text-sky-400 mt-1">{dash.totals.indexed_pct}%</p><p className="text-[10px] text-slate-500">{dash.totals.chunks} chunks</p></div>
                <div className={card}><p className="text-[10px] font-semibold text-slate-500 uppercase">Helpful Rate</p><p className="text-xl font-bold text-slate-100 mt-1">{dash.helpful_rate ?? '—'}{dash.helpful_rate != null ? '%' : ''}</p></div>
              </div>
              <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
                <div className={card}>
                  <h3 className="text-xs font-bold text-slate-300 mb-2 flex items-center gap-1.5"><Eye className="w-3.5 h-3.5 text-brand-400" /> Top Articles</h3>
                  {dash.top_articles.length === 0 ? <p className="text-xs text-slate-500">No published articles yet.</p> :
                    dash.top_articles.map(a => <div key={a.id} className="flex justify-between text-xs py-1 border-b border-slate-800/60 last:border-0"><span className="text-slate-300 truncate pr-2">{a.title}</span><span className="text-slate-500 shrink-0">{a.views} views · {a.helpful} 👍</span></div>)}
                </div>
                <div className={card}>
                  <h3 className="text-xs font-bold text-slate-300 mb-2 flex items-center gap-1.5"><Search className="w-3.5 h-3.5 text-brand-400" /> Recent Searches</h3>
                  {dash.recent_searches.length === 0 ? <p className="text-xs text-slate-500">No searches yet.</p> :
                    dash.recent_searches.map((s, i) => <div key={i} className="flex justify-between text-xs py-1 border-b border-slate-800/60 last:border-0"><span className="text-slate-300 truncate pr-2">{s.query}</span><span className={`shrink-0 ${(s.results || 0) === 0 ? 'text-red-400' : 'text-slate-500'}`}>{s.results ?? 0} hits</span></div>)}
                </div>
                <div className={card}>
                  <h3 className="text-xs font-bold text-slate-300 mb-2">Knowledge Gaps (0-result queries)</h3>
                  {dash.unanswered_queries.length === 0 ? <p className="text-xs text-slate-500">No gaps detected.</p> :
                    dash.unanswered_queries.map((u, i) => <div key={i} className="flex justify-between text-xs py-1 border-b border-slate-800/60 last:border-0"><span className="text-amber-300 truncate pr-2">{u.query}</span><span className="text-slate-500 shrink-0">×{u.count}</span></div>)}
                </div>
              </div>
            </div>
          )}

          {tab === 'articles' && (
            <div className="space-y-3">
              <div className="flex items-center gap-2 flex-wrap">
                <input value={q} onChange={e => setQ(e.target.value)} placeholder="Filter by text…" className={`${F} max-w-52`} />
                <select value={statusFilter} onChange={e => setStatusFilter(e.target.value)} className={`${F} max-w-40`}>
                  <option value="">All statuses</option>
                  {['draft', 'pending_review', 'published', 'rejected', 'archived'].map(s => <option key={s} value={s}>{s}</option>)}
                </select>
                <select value={typeFilter} onChange={e => setTypeFilter(e.target.value)} className={`${F} max-w-40`}>
                  <option value="">All types</option>
                  {['article', 'faq', 'document'].map(t => <option key={t} value={t}>{t}</option>)}
                </select>
                {isManager && (
                  <div className="flex items-center gap-1 ml-auto">
                    <input value={newCat} onChange={e => setNewCat(e.target.value)} placeholder="New category…" className={`${F} max-w-40`} />
                    <button onClick={() => newCat.trim() && act(async () => { await api.createCategory({ name: newCat.trim() }); setNewCat(''); })} className={BTN}><FolderTree className="w-3.5 h-3.5" /> Add</button>
                  </div>
                )}
              </div>
              <div className={card}>
                {articles.length === 0 ? <p className="text-xs text-slate-500 py-6 text-center">No articles yet. Create the first one.</p> : (
                  <table className="w-full text-xs">
                    <thead><tr className="text-left text-[10px] uppercase text-slate-500 border-b border-slate-800/70">
                      <th className="py-2 pr-2">Title</th><th className="pr-2">Type</th><th className="pr-2">Category</th><th className="pr-2">Status</th><th className="pr-2">v</th><th className="pr-2">Views</th><th className="pr-2">Indexed</th>
                    </tr></thead>
                    <tbody>
                      {articles.map(a => (
                        <tr key={a.id} onClick={() => openDetail(a.id)} className="border-b border-slate-800/50 last:border-0 hover:bg-slate-800/30 cursor-pointer">
                          <td className="py-2 pr-2 text-slate-200 font-medium">{a.title}</td>
                          <td className="pr-2 text-slate-400">{a.article_type}</td>
                          <td className="pr-2 text-slate-400">{catName(a.category_id)}</td>
                          <td className="pr-2"><span className={`px-1.5 py-0.5 rounded ${STATUS_TONE[a.status] || ''}`}>{a.status}</span></td>
                          <td className="pr-2 text-slate-400">{a.version}</td>
                          <td className="pr-2 text-slate-400">{a.view_count}</td>
                          <td className="pr-2">{a.is_indexed ? <span className="text-emerald-400">{a.chunk_count} chunks</span> : <span className="text-slate-500">no</span>}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                )}
              </div>
            </div>
          )}

          {tab === 'faq' && (
            <div className={card}>
              {faqs.length === 0 ? <p className="text-xs text-slate-500 py-6 text-center">No published FAQs yet. Create an article with type "faq" and publish it.</p> :
                faqs.map(f => (
                  <details key={f.id} className="border-b border-slate-800/60 last:border-0 py-2">
                    <summary className="text-sm text-slate-200 font-semibold cursor-pointer">{f.question}</summary>
                    <p className="text-xs text-slate-400 mt-2 whitespace-pre-wrap">{f.answer}</p>
                    <p className="text-[10px] text-slate-500 mt-1">{f.category || 'Uncategorized'} · {f.views} views</p>
                  </details>
                ))}
            </div>
          )}

          {tab === 'ask' && (
            <div className="space-y-4">
              <div className={card}>
                <h3 className="text-xs font-bold text-slate-300 mb-2 flex items-center gap-1.5"><Search className="w-3.5 h-3.5 text-brand-400" /> Semantic Search</h3>
                <div className="flex gap-2">
                  <input value={searchQ} onChange={e => setSearchQ(e.target.value)} onKeyDown={async e => { if (e.key === 'Enter' && searchQ.trim()) { try { setResults((await api.search(searchQ)).results); } catch (er) { setErr(extractErrorMessage(er, 'Search failed')); } } }} placeholder="Search the knowledge base…" className={F} />
                  <button onClick={async () => { if (searchQ.trim()) try { setResults((await api.search(searchQ)).results); } catch (er) { setErr(extractErrorMessage(er, 'Search failed')); } }} className={BTN}><Search className="w-3.5 h-3.5" /> Search</button>
                </div>
                {results && (results.length === 0 ? <p className="text-xs text-slate-500 mt-3">No matches — this query will show up as a knowledge gap.</p> :
                  results.map(r => (
                    <div key={r.article_id} onClick={() => openDetail(r.article_id)} className="mt-2 p-2 bg-slate-950/40 border border-slate-800/60 rounded-lg cursor-pointer hover:border-brand-500/40">
                      <div className="flex justify-between text-xs"><span className="text-slate-200 font-semibold">{r.title}</span><span className="text-brand-300">{(r.score * 100).toFixed(0)}%</span></div>
                      <p className="text-[11px] text-slate-500 mt-1 line-clamp-2">{r.excerpt}</p>
                    </div>
                  )))}
              </div>
              <div className={card}>
                <h3 className="text-xs font-bold text-slate-300 mb-2 flex items-center gap-1.5"><Sparkles className="w-3.5 h-3.5 text-brand-400" /> Ask AI (RAG)</h3>
                <div className="flex gap-2">
                  <input value={question} onChange={e => setQuestion(e.target.value)} onKeyDown={e => { if (e.key === 'Enter') document.getElementById('kb-ask-btn')?.click(); }} placeholder="Ask a question — the answer is grounded in your published knowledge…" className={F} />
                  <button id="kb-ask-btn" disabled={asking} onClick={async () => { if (!question.trim()) return; setAsking(true); try { setAnswer(await api.ask(question)); } catch (er) { setErr(extractErrorMessage(er, 'Ask failed')); } finally { setAsking(false); } }} className={BTN}>{asking ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <Send className="w-3.5 h-3.5" />} Ask</button>
                </div>
                {answer && (
                  <div className="mt-3 p-3 bg-slate-950/40 border border-slate-800/60 rounded-lg">
                    <p className="text-xs text-slate-200 whitespace-pre-wrap">{answer.answer}</p>
                    <div className="flex items-center gap-2 mt-2 flex-wrap text-[10px] text-slate-500">
                      <span className={`px-1.5 py-0.5 rounded ${answer.grounded ? 'bg-emerald-500/15 text-emerald-300' : 'bg-amber-500/15 text-amber-300'}`}>{answer.grounded ? 'Grounded in KB' : 'No KB match — general answer'}</span>
                      <span>{answer.provider} / {answer.model}</span>
                      {answer.sources.map(s => <button key={s.article_id} onClick={() => openDetail(s.article_id)} className="px-1.5 py-0.5 rounded bg-brand-500/15 text-brand-300 cursor-pointer">{s.title}</button>)}
                    </div>
                  </div>
                )}
              </div>
            </div>
          )}
        </>
      )}

      {showForm && (
        <div className="fixed inset-0 bg-black/60 flex items-center justify-center z-50 p-4" onClick={() => setShowForm(false)}>
          <div className="glass-panel border border-slate-700/70 rounded-2xl p-5 w-full max-w-2xl space-y-3" onClick={e => e.stopPropagation()}>
            <h3 className="text-sm font-bold text-slate-100">{editId ? 'Edit Article' : 'New Article'}</h3>
            <input value={form.title} onChange={e => setForm({ ...form, title: e.target.value })} placeholder="Title (or FAQ question)" className={F} />
            <textarea value={form.content} onChange={e => setForm({ ...form, content: e.target.value })} placeholder="Content (or FAQ answer) — plain text or pasted document" rows={8} className={F} />
            <input value={form.summary} onChange={e => setForm({ ...form, summary: e.target.value })} placeholder="Short summary (optional)" className={F} />
            <div className="grid grid-cols-2 md:grid-cols-4 gap-2">
              <select value={form.article_type} onChange={e => setForm({ ...form, article_type: e.target.value })} className={F}>
                {['article', 'faq', 'document'].map(t => <option key={t} value={t}>{t}</option>)}
              </select>
              <select value={form.category_id} onChange={e => setForm({ ...form, category_id: e.target.value })} className={F}>
                <option value="">No category</option>
                {cats.map(c => <option key={c.id} value={c.id}>{c.name}</option>)}
              </select>
              <select value={form.visibility} onChange={e => setForm({ ...form, visibility: e.target.value })} className={F}>
                <option value="all">Everyone</option><option value="managers">Managers+</option><option value="admins">Admins only</option>
              </select>
              <input value={form.tags} onChange={e => setForm({ ...form, tags: e.target.value })} placeholder="tags, comma, separated" className={F} />
            </div>
            <div className="flex justify-end gap-2">
              <button onClick={() => setShowForm(false)} className="px-3 py-1.5 rounded-lg text-xs text-slate-400 hover:text-slate-200 cursor-pointer">Cancel</button>
              <button onClick={saveArticle} className={BTN}>{editId ? 'Save' : 'Create Draft'}</button>
            </div>
          </div>
        </div>
      )}

      {detail && (
        <div className="fixed inset-0 bg-black/60 flex items-center justify-center z-50 p-4" onClick={() => { setDetail(null); setVersions(null); }}>
          <div className="glass-panel border border-slate-700/70 rounded-2xl p-5 w-full max-w-3xl max-h-[85vh] overflow-y-auto space-y-3" onClick={e => e.stopPropagation()}>
            <div className="flex items-start justify-between gap-3">
              <div>
                <h3 className="text-base font-bold text-slate-100">{detail.title}</h3>
                <p className="text-[11px] text-slate-500 mt-0.5">
                  <span className={`px-1.5 py-0.5 rounded mr-2 ${STATUS_TONE[detail.status] || ''}`}>{detail.status}</span>
                  {detail.article_type} · v{detail.version} · {detail.view_count} views · {detail.chunk_count} chunks indexed
                </p>
              </div>
              <div className="flex items-center gap-1.5 flex-wrap justify-end">
                <button onClick={() => { setForm({ title: detail.title, content: detail.content || '', summary: detail.summary || '', article_type: detail.article_type, category_id: detail.category_id || '', tags: (detail.tags || []).join(', '), visibility: detail.visibility }); setEditId(detail.id); setDetail(null); setShowForm(true); }} className={`${BTN2} bg-slate-700/40 text-slate-300 hover:bg-slate-700/60`}>Edit</button>
                {(detail.status === 'draft' || detail.status === 'rejected') && <button onClick={() => act(() => api.submit(detail.id))} className={`${BTN2} bg-sky-500/15 text-sky-300`}><Send className="w-3 h-3" /> Submit</button>}
                {isManager && (detail.status === 'draft' || detail.status === 'pending_review') && <button onClick={() => act(() => api.approve(detail.id))} className={`${BTN2} bg-emerald-500/15 text-emerald-300`}><CheckCircle2 className="w-3 h-3" /> Approve & Publish</button>}
                {isManager && detail.status === 'pending_review' && <button onClick={() => act(() => api.reject(detail.id, 'Needs changes'))} className={`${BTN2} bg-red-500/15 text-red-300`}><XCircle className="w-3 h-3" /> Reject</button>}
                {detail.status !== 'archived' && <button onClick={() => act(() => api.archive(detail.id))} className={`${BTN2} bg-slate-700/40 text-slate-400`}><Archive className="w-3 h-3" /> Archive</button>}
                <button onClick={async () => setVersions(await api.versions(detail.id))} className={`${BTN2} bg-slate-700/40 text-slate-400`}><History className="w-3 h-3" /> Versions</button>
              </div>
            </div>
            {detail.review_note && <p className="text-[11px] text-amber-300 bg-amber-500/10 border border-amber-500/20 rounded-lg px-2 py-1">Review note: {detail.review_note}</p>}
            <p className="text-xs text-slate-300 whitespace-pre-wrap">{detail.content}</p>
            <div className="flex items-center gap-2 pt-2 border-t border-slate-800/60">
              <span className="text-[10px] text-slate-500">Was this helpful?</span>
              <button onClick={() => act(() => api.feedback(detail.id, true))} className={`${BTN2} bg-emerald-500/15 text-emerald-300`}><ThumbsUp className="w-3 h-3" /> {detail.helpful_count}</button>
              <button onClick={() => act(() => api.feedback(detail.id, false))} className={`${BTN2} bg-red-500/15 text-red-300`}><ThumbsDown className="w-3 h-3" /> {detail.not_helpful_count}</button>
            </div>
            {versions && (
              <div className="border-t border-slate-800/60 pt-2 space-y-1.5">
                <h4 className="text-xs font-bold text-slate-300">Version History</h4>
                {versions.length === 0 ? <p className="text-[11px] text-slate-500">No prior versions.</p> :
                  versions.map(v => (
                    <div key={v.version} className="flex items-center justify-between text-[11px] bg-slate-950/40 border border-slate-800/60 rounded-lg px-2 py-1.5">
                      <span className="text-slate-300">v{v.version} — {v.title}{v.change_note ? ` · ${v.change_note}` : ''}</span>
                      <button onClick={() => act(() => api.restoreVersion(detail.id, v.version))} className="text-brand-300 cursor-pointer">Restore</button>
                    </div>
                  ))}
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
};
