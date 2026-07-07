import React, { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { salesAnalyticsApi, SalesDashboard } from '../../services/salesAnalyticsApi';
import { TrendingUp, DollarSign, Target, Gauge, Loader2 } from 'lucide-react';

const cur = (n: any) => (typeof n === 'number' ? `₹${Math.round(n).toLocaleString()}` : '—');

export const SalesAnalyticsWidget: React.FC = () => {
  const [data, setData] = useState<SalesDashboard | null>(null);
  const [loading, setLoading] = useState(true);
  const navigate = useNavigate();

  useEffect(() => {
    salesAnalyticsApi.dashboard().then(setData).catch(() => {}).finally(() => setLoading(false));
  }, []);

  return (
    <div className="glass-panel border border-slate-800/85 rounded-2xl p-5">
      <div className="flex items-center justify-between mb-4">
        <h3 className="text-sm font-semibold text-slate-200 flex items-center gap-2"><TrendingUp className="w-4 h-4 text-brand-400" /> Sales Analytics</h3>
        <button onClick={() => navigate('/sales-analytics')} className="text-xs text-brand-400 hover:text-brand-300 cursor-pointer">Open</button>
      </div>
      {loading ? (
        <div className="py-6 text-center text-slate-400"><Loader2 className="w-5 h-5 animate-spin inline" /></div>
      ) : !data ? (
        <p className="text-xs text-slate-500">No sales data.</p>
      ) : (
        <div className="grid grid-cols-3 gap-2">
          <div className="p-2.5 bg-slate-950/40 border border-slate-800/60 rounded-lg">
            <p className="text-[10px] font-semibold text-slate-500 uppercase flex items-center gap-1"><DollarSign className="w-3 h-3 text-emerald-400" /> Revenue</p>
            <p className="text-base font-bold text-slate-100 mt-0.5">{cur(data.revenue)}</p>
          </div>
          <div className="p-2.5 bg-slate-950/40 border border-slate-800/60 rounded-lg">
            <p className="text-[10px] font-semibold text-slate-500 uppercase flex items-center gap-1"><Target className="w-3 h-3 text-brand-400" /> Win rate</p>
            <p className="text-base font-bold text-slate-100 mt-0.5">{data.win_rate}%</p>
          </div>
          <div className="p-2.5 bg-slate-950/40 border border-slate-800/60 rounded-lg">
            <p className="text-[10px] font-semibold text-slate-500 uppercase flex items-center gap-1"><Gauge className="w-3 h-3 text-amber-400" /> Velocity</p>
            <p className="text-base font-bold text-slate-100 mt-0.5">{cur(data.sales_velocity)}</p>
          </div>
        </div>
      )}
    </div>
  );
};
