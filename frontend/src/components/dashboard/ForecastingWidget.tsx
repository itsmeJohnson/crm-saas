import React, { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { forecastingApi, ForecastDashboard } from '../../services/forecastingApi';
import { LineChart, TrendingUp, GitBranch, Loader2 } from 'lucide-react';

const numf = (n: any) => (typeof n === 'number' ? Math.round(n).toLocaleString() : '—');
const arrow = (d: string) => (d === 'up' ? '↑' : d === 'down' ? '↓' : '→');
const tone = (d: string) => (d === 'up' ? 'text-emerald-400' : d === 'down' ? 'text-red-400' : 'text-slate-400');

export const ForecastingWidget: React.FC = () => {
  const [data, setData] = useState<ForecastDashboard | null>(null);
  const [loading, setLoading] = useState(true);
  const navigate = useNavigate();

  useEffect(() => {
    forecastingApi.dashboard().then(setData).catch(() => {}).finally(() => setLoading(false));
  }, []);

  return (
    <div className="glass-panel border border-slate-800/85 rounded-2xl p-5">
      <div className="flex items-center justify-between mb-4">
        <h3 className="text-sm font-semibold text-slate-200 flex items-center gap-2"><LineChart className="w-4 h-4 text-brand-400" /> Forecasting</h3>
        <button onClick={() => navigate('/forecasting')} className="text-xs text-brand-400 hover:text-brand-300 cursor-pointer">Open</button>
      </div>
      {loading ? (
        <div className="py-6 text-center text-slate-400"><Loader2 className="w-5 h-5 animate-spin inline" /></div>
      ) : !data ? (
        <p className="text-xs text-slate-500">No forecast data.</p>
      ) : (
        <>
          <div className="grid grid-cols-3 gap-2">
            <div className="p-2.5 bg-slate-950/40 border border-slate-800/60 rounded-lg">
              <p className="text-[10px] font-semibold text-slate-500 uppercase flex items-center gap-1"><TrendingUp className="w-3 h-3 text-emerald-400" /> Revenue</p>
              <p className="text-base font-bold text-slate-100 mt-0.5">₹{numf(data.revenue.next_month)} <span className={`text-xs ${tone(data.revenue.direction)}`}>{arrow(data.revenue.direction)}</span></p>
            </div>
            <div className="p-2.5 bg-slate-950/40 border border-slate-800/60 rounded-lg">
              <p className="text-[10px] font-semibold text-slate-500 uppercase flex items-center gap-1"><GitBranch className="w-3 h-3 text-brand-400" /> Pipeline</p>
              <p className="text-base font-bold text-slate-100 mt-0.5">₹{numf(data.pipeline_expected_close)}</p>
            </div>
            <div className="p-2.5 bg-slate-950/40 border border-slate-800/60 rounded-lg">
              <p className="text-[10px] font-semibold text-slate-500 uppercase flex items-center gap-1"><LineChart className="w-3 h-3 text-amber-400" /> Goals</p>
              <p className="text-base font-bold text-slate-100 mt-0.5">{data.goals_on_track}/{data.goals_total}</p>
            </div>
          </div>
          <p className="mt-3 text-[11px] text-slate-400">Next-month leads <span className="text-slate-200">{numf(data.leads.next_month)}</span> · collections <span className="text-slate-200">₹{numf(data.collections.next_month)}</span></p>
        </>
      )}
    </div>
  );
};
