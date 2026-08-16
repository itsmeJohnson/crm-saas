import React, { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { aiAnalyticsApi, AiaDashboard, QUALITY_TONE } from '../../services/aiAnalyticsApi';
import { BarChart3, Gauge, Users, Loader2 } from 'lucide-react';

export const AiAnalyticsWidget: React.FC = () => {
  const [data, setData] = useState<AiaDashboard | null>(null);
  const [loading, setLoading] = useState(true);
  const navigate = useNavigate();

  useEffect(() => {
    aiAnalyticsApi.dashboard(30).then(setData).catch(() => {}).finally(() => setLoading(false));
  }, []);

  return (
    <div className="glass-panel border border-slate-800/85 rounded-2xl p-5">
      <div className="flex items-center justify-between mb-4">
        <h3 className="text-sm font-semibold text-slate-200 flex items-center gap-2"><BarChart3 className="w-4 h-4 text-brand-400" /> AI Analytics</h3>
        <button onClick={() => navigate('/ai-analytics')} className="text-xs text-brand-400 hover:text-brand-300 cursor-pointer">Open</button>
      </div>
      {loading ? (
        <div className="py-6 text-center text-slate-400"><Loader2 className="w-5 h-5 animate-spin inline" /></div>
      ) : !data ? (
        <p className="text-xs text-slate-500">No AI analytics data.</p>
      ) : (
        <div className="grid grid-cols-3 gap-2">
          <div className="p-2.5 bg-slate-950/40 border border-slate-800/60 rounded-lg">
            <p className="text-[10px] font-semibold text-slate-500 uppercase flex items-center gap-1"><Gauge className="w-3 h-3 text-brand-400" /> Quality</p>
            <p className={`text-base font-bold mt-0.5 ${QUALITY_TONE[data.quality_band] || 'text-slate-100'}`}>{data.quality_score}</p>
          </div>
          <div className="p-2.5 bg-slate-950/40 border border-slate-800/60 rounded-lg">
            <p className="text-[10px] font-semibold text-slate-500 uppercase flex items-center gap-1"><Users className="w-3 h-3 text-emerald-400" /> Adoption</p>
            <p className="text-base font-bold text-slate-100 mt-0.5">{data.adoption_rate}%</p>
          </div>
          <div className="p-2.5 bg-slate-950/40 border border-slate-800/60 rounded-lg">
            <p className="text-[10px] font-semibold text-slate-500 uppercase flex items-center gap-1"><BarChart3 className="w-3 h-3 text-sky-400" /> Calls 30d</p>
            <p className="text-base font-bold text-slate-100 mt-0.5">{data.requests}</p>
          </div>
        </div>
      )}
    </div>
  );
};
