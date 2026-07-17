import React, { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { predictiveApi, PredDashboard } from '../../services/predictiveApi';
import { BrainCircuit, Flame, AlertTriangle, Lightbulb, Loader2 } from 'lucide-react';

export const PredictiveWidget: React.FC = () => {
  const [data, setData] = useState<PredDashboard | null>(null);
  const [loading, setLoading] = useState(true);
  const navigate = useNavigate();

  useEffect(() => {
    predictiveApi.dashboard().then(setData).catch(() => {}).finally(() => setLoading(false));
  }, []);

  return (
    <div className="glass-panel border border-slate-800/85 rounded-2xl p-5">
      <div className="flex items-center justify-between mb-4">
        <h3 className="text-sm font-semibold text-slate-200 flex items-center gap-2"><BrainCircuit className="w-4 h-4 text-brand-400" /> Predictive Analytics</h3>
        <button onClick={() => navigate('/predictive')} className="text-xs text-brand-400 hover:text-brand-300 cursor-pointer">Open</button>
      </div>
      {loading ? (
        <div className="py-6 text-center text-slate-400"><Loader2 className="w-5 h-5 animate-spin inline" /></div>
      ) : !data ? (
        <p className="text-xs text-slate-500">No data.</p>
      ) : (
        <div className="grid grid-cols-3 gap-2">
          <div className="p-2.5 bg-slate-950/40 border border-slate-800/60 rounded-lg">
            <p className="text-[10px] font-semibold text-slate-500 uppercase flex items-center gap-1"><Flame className="w-3 h-3 text-orange-400" /> Pipeline</p>
            <p className="text-base font-bold text-slate-100 mt-0.5">₹{Math.round(data.expected_pipeline_value).toLocaleString()}</p>
          </div>
          <div className="p-2.5 bg-slate-950/40 border border-slate-800/60 rounded-lg">
            <p className="text-[10px] font-semibold text-slate-500 uppercase flex items-center gap-1"><AlertTriangle className="w-3 h-3 text-red-400" /> Churn risk</p>
            <p className="text-base font-bold text-slate-100 mt-0.5">{data.customers_at_high_churn_risk}</p>
          </div>
          <div className="p-2.5 bg-slate-950/40 border border-slate-800/60 rounded-lg">
            <p className="text-[10px] font-semibold text-slate-500 uppercase flex items-center gap-1"><Lightbulb className="w-3 h-3 text-brand-400" /> Actions</p>
            <p className="text-base font-bold text-slate-100 mt-0.5">{data.recommendations}</p>
          </div>
        </div>
      )}
    </div>
  );
};
