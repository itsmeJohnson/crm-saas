import React, { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { vizApi, VizDashboard } from '../../services/vizApi';
import { VizRenderer } from '../viz/VizRenderer';
import { BarChart3, Loader2 } from 'lucide-react';

/** Home-dashboard integration: renders the visualizations pinned in the
 * Visualization Studio (up to two, mini). */
export const VizWidget: React.FC = () => {
  const [data, setData] = useState<VizDashboard | null>(null);
  const [loading, setLoading] = useState(true);
  const navigate = useNavigate();

  useEffect(() => {
    vizApi.dashboard().then(setData).catch(() => {}).finally(() => setLoading(false));
  }, []);

  const pinned = (data?.pinned || []).filter((p) => p.data).slice(0, 2);
  return (
    <div className="glass-panel border border-slate-800/85 rounded-2xl p-5">
      <div className="flex items-center justify-between mb-4">
        <h3 className="text-sm font-semibold text-slate-200 flex items-center gap-2"><BarChart3 className="w-4 h-4 text-brand-400" /> Visualizations</h3>
        <button onClick={() => navigate('/visualizations')} className="text-xs text-brand-400 hover:text-brand-300 cursor-pointer">Open studio</button>
      </div>
      {loading ? (
        <div className="py-6 text-center text-slate-400"><Loader2 className="w-5 h-5 animate-spin inline" /></div>
      ) : pinned.length === 0 ? (
        <p className="text-xs text-slate-500">Pin a visualization in the studio to see it here.</p>
      ) : (
        <div className="space-y-3">
          {pinned.map((v) => (
            <div key={v.id}>
              <p className="text-[11px] text-slate-400 mb-1 truncate">{v.name}</p>
              <VizRenderer vizType={v.viz_type} data={v.data} config={v.config} height={160} />
            </div>
          ))}
        </div>
      )}
    </div>
  );
};
