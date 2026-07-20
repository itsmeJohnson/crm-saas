import React, { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { financialAnalyticsApi, FinDashboard } from '../../services/financialAnalyticsApi';
import { DollarSign, TrendingUp, Repeat, Wallet, Loader2 } from 'lucide-react';

const cur = (n: any) => (typeof n === 'number' ? `₹${Math.round(n).toLocaleString()}` : '—');

export const FinancialAnalyticsWidget: React.FC = () => {
  const [data, setData] = useState<FinDashboard | null>(null);
  const [loading, setLoading] = useState(true);
  const navigate = useNavigate();

  useEffect(() => {
    financialAnalyticsApi.dashboard().then(setData).catch(() => {}).finally(() => setLoading(false));
  }, []);

  return (
    <div className="glass-panel border border-slate-800/85 rounded-2xl p-5">
      <div className="flex items-center justify-between mb-4">
        <h3 className="text-sm font-semibold text-slate-200 flex items-center gap-2"><DollarSign className="w-4 h-4 text-brand-400" /> Financial Analytics</h3>
        <button onClick={() => navigate('/financial-analytics')} className="text-xs text-brand-400 hover:text-brand-300 cursor-pointer">Open</button>
      </div>
      {loading ? (
        <div className="py-6 text-center text-slate-400"><Loader2 className="w-5 h-5 animate-spin inline" /></div>
      ) : !data ? (
        <p className="text-xs text-slate-500">No financial data.</p>
      ) : (
        <>
          <div className="grid grid-cols-3 gap-2">
            <div className="p-2.5 bg-slate-950/40 border border-slate-800/60 rounded-lg">
              <p className="text-[10px] font-semibold text-slate-500 uppercase flex items-center gap-1"><TrendingUp className="w-3 h-3 text-emerald-400" /> Revenue</p>
              <p className="text-base font-bold text-slate-100 mt-0.5">{cur(data.revenue)}</p>
            </div>
            <div className="p-2.5 bg-slate-950/40 border border-slate-800/60 rounded-lg">
              <p className="text-[10px] font-semibold text-slate-500 uppercase flex items-center gap-1"><Repeat className="w-3 h-3 text-brand-400" /> MRR</p>
              <p className="text-base font-bold text-slate-100 mt-0.5">{cur(data.mrr)}</p>
            </div>
            <div className="p-2.5 bg-slate-950/40 border border-slate-800/60 rounded-lg">
              <p className="text-[10px] font-semibold text-slate-500 uppercase flex items-center gap-1"><Wallet className="w-3 h-3 text-amber-400" /> Outstanding</p>
              <p className="text-base font-bold text-slate-100 mt-0.5">{cur(data.outstanding)}</p>
            </div>
          </div>
          <div className="mt-3 flex items-center justify-between text-xs text-slate-400">
            <span>Profit <span className={data.gross_profit >= 0 ? 'text-emerald-400' : 'text-red-400'}>{cur(data.gross_profit)}</span></span>
            <span>Margin <span className="text-slate-200">{data.profit_margin}%</span></span>
            <span>ARR <span className="text-slate-200">{cur(data.arr)}</span></span>
          </div>
        </>
      )}
    </div>
  );
};
