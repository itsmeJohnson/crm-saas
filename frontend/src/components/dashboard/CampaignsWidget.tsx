import React, { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { campaignApi, CampaignDashboard } from '../../services/campaignApi';
import { Megaphone, Play, Clock, Rocket, TrendingUp, Loader2 } from 'lucide-react';

export const CampaignsWidget: React.FC = () => {
  const [data, setData] = useState<CampaignDashboard | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const navigate = useNavigate();

  useEffect(() => {
    campaignApi.dashboard().then(setData).catch(() => {}).finally(() => setIsLoading(false));
  }, []);

  return (
    <div className="glass-panel border border-slate-800/85 rounded-2xl p-5">
      <div className="flex items-center justify-between mb-4">
        <h3 className="text-sm font-semibold text-slate-200 flex items-center gap-2"><Megaphone className="w-4 h-4 text-brand-400" /> Campaigns</h3>
        <button onClick={() => navigate('/campaigns')} className="text-xs text-brand-400 hover:text-brand-300 cursor-pointer">Open</button>
      </div>
      {isLoading ? (
        <div className="py-6 text-center text-slate-400"><Loader2 className="w-5 h-5 animate-spin inline" /></div>
      ) : !data || data.total === 0 ? (
        <p className="text-xs text-slate-500">No campaigns yet.</p>
      ) : (
        <>
          <div className="grid grid-cols-2 gap-2">
            <div className="p-2.5 bg-slate-950/40 border border-slate-800/60 rounded-lg">
              <p className="text-[10px] font-semibold text-slate-500 uppercase tracking-wider flex items-center gap-1"><Play className="w-3 h-3 text-amber-400" /> Running</p>
              <p className="text-lg font-bold text-slate-100 mt-0.5">{data.running}</p>
            </div>
            <div className="p-2.5 bg-slate-950/40 border border-slate-800/60 rounded-lg">
              <p className="text-[10px] font-semibold text-slate-500 uppercase tracking-wider flex items-center gap-1"><Clock className="w-3 h-3 text-sky-400" /> Scheduled</p>
              <p className="text-lg font-bold text-slate-100 mt-0.5">{data.scheduled}</p>
            </div>
            <div className="p-2.5 bg-slate-950/40 border border-slate-800/60 rounded-lg">
              <p className="text-[10px] font-semibold text-slate-500 uppercase tracking-wider flex items-center gap-1"><Rocket className="w-3 h-3 text-brand-400" /> Sent</p>
              <p className="text-lg font-bold text-slate-100 mt-0.5">{data.total_sent}</p>
            </div>
            <div className="p-2.5 bg-slate-950/40 border border-slate-800/60 rounded-lg">
              <p className="text-[10px] font-semibold text-slate-500 uppercase tracking-wider flex items-center gap-1"><TrendingUp className="w-3 h-3 text-emerald-400" /> ROI</p>
              <p className="text-lg font-bold text-slate-100 mt-0.5">₹{data.total_roi.toFixed(0)}</p>
            </div>
          </div>
        </>
      )}
    </div>
  );
};
