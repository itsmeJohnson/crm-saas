import React, { useCallback, useEffect, useRef, useState } from 'react';
import {
  ScanText, Loader2, Download, LayoutDashboard, Search, UploadCloud, FileText,
  Sparkles, Trash2, RefreshCw, Table2, Image as ImageIcon, CheckCircle2, AlertTriangle,
} from 'lucide-react';
import {
  documentIntelligenceApi as api, DiDashboard, DiDocument, DiSearchResult,
} from '../services/documentIntelligenceApi';
import { useAuthStore } from '../store/authStore';
import { extractErrorMessage } from '../utils/errors';

const card = 'glass-panel border border-slate-800/85 rounded-xl p-4';
const F = 'w-full bg-slate-800/70 border border-slate-700/70 text-slate-200 py-1.5 px-2 rounded-lg text-xs';
const BTN = 'px-3 py-1.5 rounded-lg text-xs font-semibold bg-brand-500/20 text-brand-300 hover:bg-brand-500/30 cursor-pointer flex items-center gap-1.5';
const BTN2 = 'px-2 py-1 rounded-lg text-[11px] font-semibold cursor-pointer flex items-center gap-1';

const TYPE_TONE: Record<string, string> = {
  invoice: 'bg-emerald-500/15 text-emerald-300', receipt: 'bg-emerald-500/15 text-emerald-300',
  contract: 'bg-sky-500/15 text-sky-300', identity: 'bg-purple-500/15 text-purple-300',
  resume: 'bg-amber-500/15 text-amber-300', report: 'bg-slate-500/15 text-slate-300',
  letter: 'bg-slate-500/15 text-slate-300', other: 'bg-slate-600/20 text-slate-400',
};

const downloadText = (name: string, text: string) => {
  const a = document.createElement('a');
  a.href = URL.createObjectURL(new Blob([text], { type: 'text/csv' }));
  a.download = name; a.click(); URL.revokeObjectURL(a.href);
};

export const DocumentIntelligencePage: React.FC = () => {
  const { user } = useAuthStore();
  const isManager = user?.role === 'OrgAdmin' || user?.role === 'Manager' || user?.role === 'SuperAdmin';
  const [tab, setTab] = useState<'dashboard' | 'documents' | 'process' | 'search'>('dashboard');
  const [dash, setDash] = useState<DiDashboard | null>(null);
  const [docs, setDocs] = useState<DiDocument[]>([]);
  const [loading, setLoading] = useState(true);
  const [err, setErr] = useState('');
  const [typeFilter, setTypeFilter] = useState('');
  const [q, setQ] = useState('');
  const [detail, setDetail] = useState<DiDocument | null>(null);

  const fileRef = useRef<HTMLInputElement>(null);
  const [pasted, setPasted] = useState('');
  const [busy, setBusy] = useState(false);
  const [lastResult, setLastResult] = useState<DiDocument | null>(null);

  const [searchQ, setSearchQ] = useState('');
  const [results, setResults] = useState<DiSearchResult[] | null>(null);

  const load = useCallback(async () => {
    setLoading(true); setErr('');
    try {
      if (tab === 'dashboard') setDash(await api.dashboard());
      if (tab === 'documents') {
        const params: any = {};
        if (typeFilter) params.doc_type = typeFilter;
        if (q) params.q = q;
        setDocs((await api.documents(params)).items);
      }
    } catch (e) { setErr(extractErrorMessage(e, 'Failed to load document intelligence.')); } finally { setLoading(false); }
  }, [tab, typeFilter, q]);
  useEffect(() => { load(); }, [load]);

  const runProcess = async (fn: () => Promise<DiDocument>) => {
    setBusy(true); setErr('');
    try { const d = await fn(); setLastResult(d); }
    catch (e) { setErr(extractErrorMessage(e, 'Processing failed.')); }
    finally { setBusy(false); }
  };

  const act = async (fn: () => Promise<any>) => {
    try { await fn(); setDetail(null); load(); }
    catch (e) { setErr(extractErrorMessage(e, 'Action failed.')); }
  };

  const openDetail = async (id: string) => {
    try { setDetail(await api.document(id)); }
    catch (e) { setErr(extractErrorMessage(e, 'Failed to open document.')); }
  };

  const renderExtraction = (d: DiDocument) => {
    const typed = Object.entries(d.extraction || {}).filter(([k]) => k !== 'common');
    return (
      <div className="space-y-2">
        {typed.map(([kind, fields]) => (
          <div key={kind} className="p-2 bg-slate-950/40 border border-slate-800/60 rounded-lg">
            <p className="text-[10px] font-bold text-brand-300 uppercase mb-1">{kind} fields</p>
            <div className="grid grid-cols-2 gap-x-4 gap-y-0.5">
              {Object.entries(fields as Record<string, any>).map(([k, v]) => (
                <div key={k} className="text-[11px] flex justify-between gap-2">
                  <span className="text-slate-500">{k}</span>
                  <span className="text-slate-200 text-right truncate">{v == null ? '—' : Array.isArray(v) ? (v.length ? v.map(x => typeof x === 'object' ? Object.values(x).join(' ') : String(x)).join(', ') : '—') : typeof v === 'object' ? JSON.stringify(v) : String(v)}</span>
                </div>
              ))}
            </div>
          </div>
        ))}
        {d.extraction?.common && (
          <div className="p-2 bg-slate-950/40 border border-slate-800/60 rounded-lg">
            <p className="text-[10px] font-bold text-slate-400 uppercase mb-1">Detected entities</p>
            <p className="text-[11px] text-slate-400">
              {['emails', 'phones', 'dates', 'amounts'].map(k => `${k}: ${(d.extraction.common[k] || []).length}`).join(' · ')}
            </p>
          </div>
        )}
      </div>
    );
  };

  return (
    <div className="space-y-5">
      <div className="flex items-center justify-between gap-3 flex-wrap">
        <div>
          <h1 className="text-2xl font-extrabold text-slate-100 flex items-center gap-2"><ScanText className="w-6 h-6 text-brand-400" /> Document Intelligence</h1>
          <p className="text-sm text-slate-500 mt-1">OCR, PDF/DOCX/XLSX parsing, classification, invoice/contract/identity/resume extraction, tables, AI summaries & semantic search.</p>
        </div>
        {isManager && tab === 'dashboard' && (
          <button onClick={async () => { try { downloadText('documents.csv', await api.exportCsv()); } catch (e) { setErr(extractErrorMessage(e, 'Export failed')); } }} className={BTN}><Download className="w-3.5 h-3.5" /> Export CSV</button>
        )}
      </div>

      {err && <div className="text-xs text-red-400 bg-red-500/10 border border-red-500/20 rounded-lg px-3 py-2">{err}</div>}

      <div className="flex items-center gap-1 bg-slate-900/50 border border-slate-800/70 rounded-xl p-1 w-fit">
        {([['dashboard', 'Dashboard', LayoutDashboard], ['documents', 'Documents', FileText], ['process', 'Process', UploadCloud], ['search', 'Search', Search]] as [any, string, any][]).map(([k, l, Icon]) => (
          <button key={k} onClick={() => setTab(k)} className={`px-3 py-1.5 rounded-lg text-xs font-semibold flex items-center gap-1.5 cursor-pointer ${tab === k ? 'bg-brand-500/20 text-brand-300' : 'text-slate-400 hover:text-slate-200'}`}><Icon className="w-3.5 h-3.5" /> {l}</button>
        ))}
      </div>

      {loading && (tab === 'dashboard' || tab === 'documents') ? (
        <div className="py-20 text-center text-slate-400"><Loader2 className="w-6 h-6 animate-spin inline" /></div>
      ) : (
        <>
          {tab === 'dashboard' && dash && (
            <div className="space-y-4">
              <div className="grid grid-cols-2 md:grid-cols-6 gap-3">
                <div className={card}><p className="text-[10px] font-semibold text-slate-500 uppercase">Documents</p><p className="text-xl font-bold text-slate-100 mt-1">{dash.totals.documents}</p></div>
                <div className={card}><p className="text-[10px] font-semibold text-slate-500 uppercase">Pages</p><p className="text-xl font-bold text-slate-100 mt-1">{dash.totals.pages}</p></div>
                <div className={card}><p className="text-[10px] font-semibold text-slate-500 uppercase">OCR Used</p><p className="text-xl font-bold text-sky-400 mt-1">{dash.totals.ocr_used}</p></div>
                <div className={card}><p className="text-[10px] font-semibold text-slate-500 uppercase">With Tables</p><p className="text-xl font-bold text-slate-100 mt-1">{dash.totals.with_tables}</p></div>
                <div className={card}><p className="text-[10px] font-semibold text-slate-500 uppercase">Structured</p><p className="text-xl font-bold text-emerald-400 mt-1">{dash.totals.with_structured_extraction}</p></div>
                <div className={card}>
                  <p className="text-[10px] font-semibold text-slate-500 uppercase">OCR Engine</p>
                  <p className={`text-xl font-bold mt-1 ${dash.capabilities.ocr ? 'text-emerald-400' : 'text-amber-400'}`}>{dash.capabilities.ocr ? 'Ready' : 'Off'}</p>
                </div>
              </div>
              <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
                <div className={card}>
                  <h3 className="text-xs font-bold text-slate-300 mb-2">By Document Type</h3>
                  {Object.keys(dash.totals.by_type).length === 0 ? <p className="text-xs text-slate-500">Nothing processed yet.</p> :
                    Object.entries(dash.totals.by_type).map(([t, n]) => (
                      <div key={t} className="flex justify-between items-center text-xs py-1 border-b border-slate-800/60 last:border-0">
                        <span className={`px-1.5 py-0.5 rounded ${TYPE_TONE[t] || ''}`}>{t}</span><span className="text-slate-300 font-semibold">{n}</span>
                      </div>
                    ))}
                </div>
                <div className={card}>
                  <h3 className="text-xs font-bold text-slate-300 mb-2">Recent Documents</h3>
                  {dash.recent.length === 0 ? <p className="text-xs text-slate-500">Upload or paste a document in the Process tab.</p> :
                    dash.recent.map(d => (
                      <div key={d.id} onClick={() => openDetail(d.id)} className="flex justify-between items-center text-xs py-1 border-b border-slate-800/60 last:border-0 cursor-pointer hover:bg-slate-800/30 rounded px-1">
                        <span className="text-slate-300 truncate pr-2">{d.filename}</span>
                        <span className={`px-1.5 py-0.5 rounded shrink-0 ${TYPE_TONE[d.doc_type] || ''}`}>{d.doc_type}</span>
                      </div>
                    ))}
                </div>
              </div>
              <div className={card}>
                <h3 className="text-xs font-bold text-slate-300 mb-1">Capabilities</h3>
                <p className="text-[11px] text-slate-400">
                  PDF {dash.capabilities.pdf ? '✓' : '✗'} · DOCX {dash.capabilities.docx ? '✓' : '✗'} · XLSX {dash.capabilities.xlsx ? '✓' : '✗'} · Images {dash.capabilities.images ? '✓' : '✗'} · OCR {dash.capabilities.ocr ? '✓ (tesseract)' : '✗ (install tesseract-ocr to enable)'} · Embeddings {dash.capabilities.embedding_model}
                </p>
              </div>
            </div>
          )}

          {tab === 'documents' && (
            <div className="space-y-3">
              <div className="flex items-center gap-2 flex-wrap">
                <input value={q} onChange={e => setQ(e.target.value)} placeholder="Filter by text…" className={`${F} max-w-52`} />
                <select value={typeFilter} onChange={e => setTypeFilter(e.target.value)} className={`${F} max-w-40`}>
                  <option value="">All types</option>
                  {['invoice', 'contract', 'identity', 'resume', 'receipt', 'report', 'letter', 'other'].map(t => <option key={t} value={t}>{t}</option>)}
                </select>
              </div>
              <div className={card}>
                {docs.length === 0 ? <p className="text-xs text-slate-500 py-6 text-center">No documents yet.</p> : (
                  <table className="w-full text-xs">
                    <thead><tr className="text-left text-[10px] uppercase text-slate-500 border-b border-slate-800/70">
                      <th className="py-2 pr-2">File</th><th className="pr-2">Type</th><th className="pr-2">Status</th><th className="pr-2">Pages</th><th className="pr-2">Tables</th><th className="pr-2">OCR</th><th className="pr-2">Confidence</th>
                    </tr></thead>
                    <tbody>
                      {docs.map(d => (
                        <tr key={d.id} onClick={() => openDetail(d.id)} className="border-b border-slate-800/50 last:border-0 hover:bg-slate-800/30 cursor-pointer">
                          <td className="py-2 pr-2 text-slate-200 font-medium">{d.filename}</td>
                          <td className="pr-2"><span className={`px-1.5 py-0.5 rounded ${TYPE_TONE[d.doc_type] || ''}`}>{d.doc_type}</span></td>
                          <td className="pr-2">{d.status === 'processed' ? <CheckCircle2 className="w-3.5 h-3.5 text-emerald-400 inline" /> : <AlertTriangle className="w-3.5 h-3.5 text-amber-400 inline" />} <span className="text-slate-400">{d.status}</span></td>
                          <td className="pr-2 text-slate-400">{d.page_count}</td>
                          <td className="pr-2 text-slate-400">{d.tables.length}</td>
                          <td className="pr-2 text-slate-400">{d.ocr_used ? 'yes' : '—'}</td>
                          <td className="pr-2 text-slate-400">{(d.classification_confidence * 100).toFixed(0)}%</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                )}
              </div>
            </div>
          )}

          {tab === 'process' && (
            <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
              <div className={card}>
                <h3 className="text-xs font-bold text-slate-300 mb-2 flex items-center gap-1.5"><UploadCloud className="w-3.5 h-3.5 text-brand-400" /> Upload a File</h3>
                <p className="text-[11px] text-slate-500 mb-2">PDF, DOCX, XLSX, images (OCR) and text files up to 15 MB.</p>
                <input ref={fileRef} type="file" className="hidden" onChange={e => { const f = e.target.files?.[0]; if (f) runProcess(() => api.upload(f)); e.target.value = ''; }} />
                <button disabled={busy} onClick={() => fileRef.current?.click()} className={BTN}>{busy ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <UploadCloud className="w-3.5 h-3.5" />} Choose file & process</button>
                <h3 className="text-xs font-bold text-slate-300 mt-4 mb-2 flex items-center gap-1.5"><FileText className="w-3.5 h-3.5 text-brand-400" /> Or Paste Text</h3>
                <textarea value={pasted} onChange={e => setPasted(e.target.value)} rows={7} placeholder="Paste an invoice, contract, resume…" className={F} />
                <button disabled={busy || !pasted.trim()} onClick={() => runProcess(() => api.processText(pasted))} className={`${BTN} mt-2`}>{busy ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <Sparkles className="w-3.5 h-3.5" />} Process Text</button>
              </div>
              <div className={card}>
                <h3 className="text-xs font-bold text-slate-300 mb-2">Result</h3>
                {!lastResult ? <p className="text-xs text-slate-500 py-8 text-center">Processed output appears here — classification, extracted fields and tables.</p> : (
                  <div className="space-y-2">
                    <div className="flex items-center gap-2 flex-wrap text-xs">
                      <span className="text-slate-200 font-semibold">{lastResult.filename}</span>
                      <span className={`px-1.5 py-0.5 rounded ${TYPE_TONE[lastResult.doc_type] || ''}`}>{lastResult.doc_type} {(lastResult.classification_confidence * 100).toFixed(0)}%</span>
                      <span className={`px-1.5 py-0.5 rounded ${lastResult.status === 'processed' ? 'bg-emerald-500/15 text-emerald-300' : 'bg-amber-500/15 text-amber-300'}`}>{lastResult.status}</span>
                      {lastResult.ocr_used && <span className="px-1.5 py-0.5 rounded bg-sky-500/15 text-sky-300">OCR</span>}
                    </div>
                    {lastResult.error && <p className="text-[11px] text-amber-300">{lastResult.error}</p>}
                    {renderExtraction(lastResult)}
                    {lastResult.tables.length > 0 && <p className="text-[11px] text-slate-400 flex items-center gap-1"><Table2 className="w-3 h-3" /> {lastResult.tables.length} table(s) extracted</p>}
                    <button onClick={() => openDetail(lastResult.id)} className={BTN}>Open full document</button>
                  </div>
                )}
              </div>
            </div>
          )}

          {tab === 'search' && (
            <div className={card}>
              <h3 className="text-xs font-bold text-slate-300 mb-2 flex items-center gap-1.5"><Search className="w-3.5 h-3.5 text-brand-400" /> Semantic Document Search</h3>
              <div className="flex gap-2">
                <input value={searchQ} onChange={e => setSearchQ(e.target.value)} onKeyDown={async e => { if (e.key === 'Enter' && searchQ.trim()) { try { setResults((await api.search(searchQ)).results); } catch (er) { setErr(extractErrorMessage(er, 'Search failed')); } } }} placeholder="Search across your processed documents…" className={F} />
                <button onClick={async () => { if (searchQ.trim()) try { setResults((await api.search(searchQ)).results); } catch (er) { setErr(extractErrorMessage(er, 'Search failed')); } }} className={BTN}><Search className="w-3.5 h-3.5" /> Search</button>
              </div>
              {results && (results.length === 0 ? <p className="text-xs text-slate-500 mt-3">No matching documents.</p> :
                results.map(r => (
                  <div key={r.id} onClick={() => openDetail(r.id)} className="mt-2 p-2 bg-slate-950/40 border border-slate-800/60 rounded-lg cursor-pointer hover:border-brand-500/40">
                    <div className="flex justify-between text-xs">
                      <span className="text-slate-200 font-semibold">{r.filename}</span>
                      <span className="flex items-center gap-2"><span className={`px-1.5 py-0.5 rounded ${TYPE_TONE[r.doc_type] || ''}`}>{r.doc_type}</span><span className="text-brand-300">{(r.score * 100).toFixed(0)}%</span></span>
                    </div>
                    <p className="text-[11px] text-slate-500 mt-1 line-clamp-2">{r.excerpt}</p>
                  </div>
                )))}
            </div>
          )}
        </>
      )}

      {detail && (
        <div className="fixed inset-0 bg-black/60 flex items-center justify-center z-50 p-4" onClick={() => setDetail(null)}>
          <div className="glass-panel border border-slate-700/70 rounded-2xl p-5 w-full max-w-3xl max-h-[85vh] overflow-y-auto space-y-3" onClick={e => e.stopPropagation()}>
            <div className="flex items-start justify-between gap-3">
              <div>
                <h3 className="text-base font-bold text-slate-100 flex items-center gap-2">
                  {detail.doc_type === 'identity' || detail.image_info?.width ? <ImageIcon className="w-4 h-4 text-brand-400" /> : <FileText className="w-4 h-4 text-brand-400" />}
                  {detail.filename}
                </h3>
                <p className="text-[11px] text-slate-500 mt-0.5">
                  <span className={`px-1.5 py-0.5 rounded mr-2 ${TYPE_TONE[detail.doc_type] || ''}`}>{detail.doc_type} · {(detail.classification_confidence * 100).toFixed(0)}%</span>
                  {detail.status} · {detail.page_count} page(s) · {(detail.size_bytes / 1024).toFixed(1)} KB{detail.ocr_used ? ' · OCR' : ''}
                </p>
              </div>
              <div className="flex items-center gap-1.5">
                <button onClick={() => act(async () => setDetail(await api.reprocess(detail.id)))} className={`${BTN2} bg-slate-700/40 text-slate-300`}><RefreshCw className="w-3 h-3" /> Reprocess</button>
                <button onClick={async () => { try { const s = await api.summarize(detail.id); setDetail({ ...detail, summary: s.summary }); } catch (e) { setErr(extractErrorMessage(e, 'Summarize failed')); } }} className={`${BTN2} bg-brand-500/15 text-brand-300`}><Sparkles className="w-3 h-3" /> AI Summary</button>
                <button onClick={() => act(() => api.deleteDocument(detail.id))} className={`${BTN2} bg-red-500/15 text-red-300`}><Trash2 className="w-3 h-3" /> Delete</button>
              </div>
            </div>
            {detail.error && <p className="text-[11px] text-amber-300 bg-amber-500/10 border border-amber-500/20 rounded-lg px-2 py-1">{detail.error}</p>}
            {detail.summary && (
              <div className="p-2 bg-brand-500/10 border border-brand-500/20 rounded-lg">
                <p className="text-[10px] font-bold text-brand-300 uppercase mb-1">AI Summary</p>
                <p className="text-xs text-slate-200 whitespace-pre-wrap">{detail.summary}</p>
              </div>
            )}
            {renderExtraction(detail)}
            {detail.image_info?.width && (
              <p className="text-[11px] text-slate-400">Image: {detail.image_info.format} {detail.image_info.width}×{detail.image_info.height} ({detail.image_info.megapixels} MP, {detail.image_info.orientation}){detail.image_info.ocr_chars != null ? ` · ${detail.image_info.ocr_chars} chars via OCR` : ''}</p>
            )}
            {(detail.tables || []).map((t, i) => (
              <div key={i} className="overflow-x-auto">
                <p className="text-[10px] font-bold text-slate-400 uppercase mb-1 flex items-center gap-1"><Table2 className="w-3 h-3" /> Table {i + 1} ({t.source})</p>
                <table className="text-[11px] w-full border border-slate-800/70">
                  <thead><tr>{t.headers.map((h, j) => <th key={j} className="text-left px-2 py-1 bg-slate-900/60 text-slate-300 border-b border-slate-800/70">{h}</th>)}</tr></thead>
                  <tbody>{t.rows.slice(0, 8).map((row, ri) => <tr key={ri}>{row.map((c, ci) => <td key={ci} className="px-2 py-1 text-slate-400 border-b border-slate-800/40">{c}</td>)}</tr>)}</tbody>
                </table>
              </div>
            ))}
            {detail.text_content && (
              <details>
                <summary className="text-[11px] text-slate-400 cursor-pointer">Extracted text ({detail.text_content.length} chars)</summary>
                <pre className="text-[11px] text-slate-400 whitespace-pre-wrap mt-1 max-h-60 overflow-y-auto bg-slate-950/40 rounded-lg p-2">{detail.text_content.slice(0, 8000)}</pre>
              </details>
            )}
          </div>
        </div>
      )}
    </div>
  );
};
