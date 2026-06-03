import React from 'react';
import { ResponsiveContainer, PieChart, Pie, Cell, Tooltip, Legend } from 'recharts';
import { DashboardSummaryResponse } from '../../services/dashboardApi';

interface LeadStatusChartProps {
  summary: DashboardSummaryResponse | null;
  isLoading: boolean;
}

const COLORS: Record<string, string> = {
  New: '#94a3b8', // slate-400
  Contacted: '#38bdf8', // sky-400
  Qualified: '#10b981', // emerald-500
  Nurturing: '#6366f1', // indigo-500
  Lost: '#f43f5e', // rose-500
  Unknown: '#64748b' // slate-500
};

export const LeadStatusChart: React.FC<LeadStatusChartProps> = ({ summary, isLoading }) => {
  if (isLoading) {
    return (
      <div className="glass-panel p-6 rounded-2xl border border-slate-800/80 h-80 flex flex-col items-center justify-center bg-slate-950/20">
        <div className="w-10 h-10 border-4 border-slate-800 border-t-brand-500 rounded-full animate-spin"></div>
        <p className="text-sm text-slate-400 mt-6 animate-pulse">Loading chart...</p>
      </div>
    );
  }

  const rawData = summary?.leads_by_status ?? {};
  const data = Object.entries(rawData).map(([name, value]) => ({
    name,
    value,
    color: COLORS[name] || COLORS.Unknown
  }));

  const totalLeads = summary?.total_leads ?? 0;

  if (totalLeads === 0) {
    return (
      <div className="glass-panel p-6 rounded-2xl border border-slate-800/80 h-80 flex flex-col items-center justify-center bg-slate-950/20 text-slate-500">
        <p className="text-sm font-medium">No lead data to display</p>
        <p className="text-xs text-slate-600 mt-1">Create a lead to view status distribution</p>
      </div>
    );
  }

  const CustomTooltip = ({ active, payload }: any) => {
    if (active && payload && payload.length) {
      const data = payload[0].payload;
      const percentage = totalLeads ? ((data.value / totalLeads) * 100).toFixed(1) : 0;
      return (
        <div className="bg-slate-900/95 border border-slate-800 p-2.5 rounded-xl shadow-xl text-xs font-semibold text-slate-200">
          <p className="font-bold flex items-center gap-1.5">
            <span className="w-2.5 h-2.5 rounded-full" style={{ backgroundColor: data.color }}></span>
            {data.name}: {data.value}
          </p>
          <p className="text-slate-400 mt-0.5">{percentage}% of total leads</p>
        </div>
      );
    }
    return null;
  };

  return (
    <div className="glass-panel p-6 rounded-2xl border border-slate-800/80 bg-slate-950/20 h-80 flex flex-col justify-between">
      <div>
        <h3 className="text-sm font-semibold text-slate-300">Lead Status Distribution</h3>
        <p className="text-xs text-slate-500 mt-0.5">Distribution of all active leads across statuses</p>
      </div>

      <div className="flex-1 min-h-[180px] relative">
        <ResponsiveContainer width="100%" height="100%">
          <PieChart>
            <Pie
              data={data}
              cx="50%"
              cy="50%"
              innerRadius={50}
              outerRadius={75}
              paddingAngle={4}
              dataKey="value"
            >
              {data.map((entry, index) => (
                <Cell key={`cell-${index}`} fill={entry.color} />
              ))}
            </Pie>
            <Tooltip content={<CustomTooltip />} />
            <Legend
              verticalAlign="bottom"
              height={36}
              iconSize={10}
              iconType="circle"
              formatter={(value) => <span className="text-xs text-slate-400">{value}</span>}
            />
          </PieChart>
        </ResponsiveContainer>
        <div className="absolute top-[41%] left-1/2 -translate-x-1/2 -translate-y-1/2 text-center pointer-events-none">
          <p className="text-2xl font-bold text-slate-200">{totalLeads}</p>
          <p className="text-[10px] text-slate-500 uppercase tracking-wider font-semibold">Total</p>
        </div>
      </div>
    </div>
  );
};
