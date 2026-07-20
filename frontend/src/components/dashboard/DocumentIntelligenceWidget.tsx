import React, { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { documentIntelligenceApi, DiDashboard } from '../../services/documentIntelligenceApi';
import { ScanText, FileText, Table2, Loader2, Eye } from 'lucide-react';

export const DocumentIntelligenceWidget: React.FC = () => {
  const [data, setData] = useState<DiDashboard | null>(null);
  const [loading, setLoading] = useState(true);
  const navigate = useNavigate();

  useEffect(() => {
    documentIntelligenceApi.dashboard().then(setData).catch(() => {}).finally(() => setLoading(false));
  }, []);

  return (
    <div className="glass-panel border border-slate-800/85 rounded-2xl p-5">
      <div className="flex items-center justify-between mb-4">
        <h3 className="text-sm font-semibold text-slate-200 flex items-center gap-2"><ScanText className="w-4 h-4 text-brand-400" /> Document Intelligence</h3>
        <button onClick={() => navigate('/document-intelligence')} className="text-xs text-brand-400 hover:text-brand-300 cursor-pointer">Open</button>
      </div>
      {loading ? (
        <div className="py-6 text-center text-slate-400"><Loader2 className="w-5 h-5 animate-spin inline" /></div>
      ) : !data ? (
        <p className="text-xs text-slate-500">No document data.</p>
      ) : (
        <div className="grid grid-cols-3 gap-2">
          <div className="p-2.5 bg-slate-950/40 border border-slate-800/60 rounded-lg">
            <p className="text-[10px] font-semibold text-slate-500 uppercase flex items-center gap-1"><FileText className="w-3 h-3 text-brand-400" /> Docs</p>
            <p className="text-base font-bold text-slate-100 mt-0.5">{data.totals.documents}</p>
          </div>
          <div className="p-2.5 bg-slate-950/40 border border-slate-800/60 rounded-lg">
            <p className="text-[10px] font-semibold text-slate-500 uppercase flex items-center gap-1"><Eye className="w-3 h-3 text-sky-400" /> OCR</p>
            <p className="text-base font-bold text-slate-100 mt-0.5">{data.capabilities.ocr ? data.totals.ocr_used : 'Off'}</p>
          </div>
          <div className="p-2.5 bg-slate-950/40 border border-slate-800/60 rounded-lg">
            <p className="text-[10px] font-semibold text-slate-500 uppercase flex items-center gap-1"><Table2 className="w-3 h-3 text-emerald-400" /> Tables</p>
            <p className="text-base font-bold text-slate-100 mt-0.5">{data.totals.with_tables}</p>
          </div>
        </div>
      )}
    </div>
  );
};
