import React, { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { predictionEngineApi, PeDashboard } from '../../services/predictionEngineApi';
import { Brain, Target, Clock, Gauge, Loader2 } from 'lucide-react';

export const PredictionEngineWidget: React.FC = () => {
  const [data, setData] = useState<PeDashboard | null>(null);
  const [loading, setLoading] = useState(true);
  const navigate = useNavigate();

  useEffect(() => {
    predictionEngineApi.dashboard().then(setData).catch(() => {}).finally(() => setLoading(false));
  }, []);

  return (
    <div className="glass-panel border border-slate-800/85 rounded-2xl p-5">
      <div className="flex items-center justify-between mb-4">
        <h3 className="text-sm font-semibold text-slate-200 flex items-center gap-2"><Brain className="w-4 h-4 text-brand-400" /> Prediction Engine</h3>
        <button onClick={() => navigate('/prediction-engine')} className="text-xs text-brand-400 hover:text-brand-300 cursor-pointer">Open</button>
      </div>
      {loading ? (
        <div className="py-6 text-center text-slate-400"><Loader2 className="w-5 h-5 animate-spin inline" /></div>
      ) : !data ? (
        <p className="text-xs text-slate-500">No prediction data.</p>
      ) : (
        <div className="grid grid-cols-3 gap-2">
          <div className="p-2.5 bg-slate-950/40 border border-slate-800/60 rounded-lg">
            <p className="text-[10px] font-semibold text-slate-500 uppercase flex items-center gap-1"><Target className="w-3 h-3 text-brand-400" /> Pipeline</p>
            <p className="text-base font-bold text-slate-100 mt-0.5">₹{Math.round(data.sales.weighted_expected_value / 1000)}k</p>
          </div>
          <div className="p-2.5 bg-slate-950/40 border border-slate-800/60 rounded-lg">
            <p className="text-[10px] font-semibold text-slate-500 uppercase flex items-center gap-1"><Clock className="w-3 h-3 text-amber-400" /> At Risk</p>
            <p className="text-base font-bold text-slate-100 mt-0.5">{data.tasks.at_risk}</p>
          </div>
          <div className="p-2.5 bg-slate-950/40 border border-slate-800/60 rounded-lg">
            <p className="text-[10px] font-semibold text-slate-500 uppercase flex items-center gap-1"><Gauge className="w-3 h-3 text-sky-400" /> Rev Conf</p>
            <p className="text-base font-bold text-slate-100 mt-0.5">{data.revenue.confidence}%</p>
          </div>
        </div>
      )}
    </div>
  );
};
