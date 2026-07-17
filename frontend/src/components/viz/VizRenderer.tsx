import React from 'react';
import {
  ResponsiveContainer, BarChart, Bar, LineChart, Line, AreaChart, Area, PieChart, Pie, Cell,
  Treemap, RadialBarChart, RadialBar, XAxis, YAxis, CartesianGrid, Tooltip, PolarAngleAxis,
} from 'recharts';

export const VIZ_COLORS = ['#818cf8', '#34d399', '#fbbf24', '#f87171', '#22d3ee', '#a78bfa', '#fb923c', '#4ade80', '#e879f9', '#94a3b8'];

const AXIS = { stroke: '#64748b', fontSize: 11 };
const TOOLTIP_STYLE = { backgroundColor: '#0f172a', border: '1px solid #334155', borderRadius: 8, fontSize: 12, color: '#e2e8f0' };

export interface VizRendererProps {
  vizType: string;
  data: any;
  config?: any;
  height?: number;
  /** invoked when the user clicks a datum (field, value) — powers drill-down */
  onDrill?: (field: string, value: any) => void;
}

/** One renderer for every visualization type. Recharts (inside
 * ResponsiveContainer → responsive) for charts, styled HTML for
 * table/pivot/heatmap/geo. Clicks call onDrill with the underlying value. */
export const VizRenderer: React.FC<VizRendererProps> = ({ vizType, data, config = {}, height = 280, onDrill }) => {
  if (!data) return <p className="text-xs text-slate-500 py-6 text-center">No data.</p>;
  const drillDim = (v: any) => onDrill && config.dimension && onDrill(config.dimension, v);

  if (vizType === 'bar') {
    return (
      <ResponsiveContainer width="100%" height={height}>
        <BarChart data={data.points} margin={{ top: 5, right: 10, left: -15, bottom: 5 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="#1e293b" />
          <XAxis dataKey="label" {...AXIS} /><YAxis {...AXIS} />
          <Tooltip contentStyle={TOOLTIP_STYLE} cursor={{ fill: '#1e293b66' }} />
          <Bar dataKey="value" radius={[4, 4, 0, 0]} onClick={(p: any) => drillDim(p?.label)} cursor={onDrill ? 'pointer' : undefined}>
            {data.points.map((_: any, i: number) => <Cell key={i} fill={VIZ_COLORS[i % VIZ_COLORS.length]} />)}
          </Bar>
        </BarChart>
      </ResponsiveContainer>
    );
  }

  if (vizType === 'line' || vizType === 'area' || vizType === 'timeline') {
    const points = vizType === 'timeline' ? data.points : data.points;
    const xKey = vizType === 'timeline' ? 'period' : 'label';
    const Chart: any = vizType === 'area' ? AreaChart : LineChart;
    return (
      <ResponsiveContainer width="100%" height={height}>
        <Chart data={points} margin={{ top: 5, right: 10, left: -15, bottom: 5 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="#1e293b" />
          <XAxis dataKey={xKey} {...AXIS} /><YAxis {...AXIS} />
          <Tooltip contentStyle={TOOLTIP_STYLE} />
          {vizType === 'area'
            ? <Area type="monotone" dataKey="value" stroke="#818cf8" fill="#818cf833" strokeWidth={2} />
            : <Line type="monotone" dataKey="value" stroke="#818cf8" strokeWidth={2} dot={{ r: 3 }} />}
        </Chart>
      </ResponsiveContainer>
    );
  }

  if (vizType === 'pie') {
    return (
      <ResponsiveContainer width="100%" height={height}>
        <PieChart>
          <Tooltip contentStyle={TOOLTIP_STYLE} />
          <Pie data={data.points} dataKey="value" nameKey="label" innerRadius="45%" outerRadius="80%"
               paddingAngle={2} onClick={(p: any) => drillDim(p?.label)} cursor={onDrill ? 'pointer' : undefined}>
            {data.points.map((_: any, i: number) => <Cell key={i} fill={VIZ_COLORS[i % VIZ_COLORS.length]} stroke="#0f172a" />)}
          </Pie>
        </PieChart>
      </ResponsiveContainer>
    );
  }

  if (vizType === 'treemap') {
    return (
      <ResponsiveContainer width="100%" height={height}>
        <Treemap data={data.nodes} dataKey="value" nameKey="name" stroke="#0f172a" fill="#818cf8"
                 onClick={(n: any) => drillDim(n?.name)}
                 content={<TreemapCell colors={VIZ_COLORS} />}>
          <Tooltip contentStyle={TOOLTIP_STYLE} />
        </Treemap>
      </ResponsiveContainer>
    );
  }

  if (vizType === 'funnel') {
    const stages = data.stages || [];
    const max = stages[0]?.value || 1;
    return (
      <div className="space-y-1.5 py-2">
        {stages.map((s: any, i: number) => (
          <button key={s.label} onClick={() => drillDim(s.label)} disabled={!onDrill}
                  className="w-full flex items-center gap-2 cursor-pointer disabled:cursor-default">
            <span className="text-[11px] text-slate-400 w-24 text-right truncate shrink-0">{s.label}</span>
            <div className="flex-1 h-7 bg-slate-800/40 rounded overflow-hidden">
              <div className="h-7 rounded flex items-center px-2 transition-all"
                   style={{ width: `${Math.max(4, (s.value * 100) / max)}%`, backgroundColor: `${VIZ_COLORS[i % VIZ_COLORS.length]}55`, borderLeft: `3px solid ${VIZ_COLORS[i % VIZ_COLORS.length]}` }}>
                <span className="text-[11px] font-semibold text-slate-100">{s.value.toLocaleString()}</span>
              </div>
            </div>
            <span className="text-[10px] text-slate-500 w-20 shrink-0 text-left">{s.pct_of_first}%{i > 0 && s.drop_pct > 0 ? ` · −${s.drop_pct}%` : ''}</span>
          </button>
        ))}
        {stages.length === 0 && <p className="text-xs text-slate-500 text-center py-4">No stages.</p>}
      </div>
    );
  }

  if (vizType === 'gauge') {
    const pct = Math.min(100, data.pct || 0);
    const tone = pct >= 100 ? '#34d399' : pct >= 60 ? '#818cf8' : pct >= 30 ? '#fbbf24' : '#f87171';
    return (
      <div className="relative">
        <ResponsiveContainer width="100%" height={height}>
          <RadialBarChart innerRadius="70%" outerRadius="95%" startAngle={210} endAngle={-30}
                          data={[{ name: 'pct', value: pct, fill: tone }]}>
            <PolarAngleAxis type="number" domain={[0, 100]} tick={false} />
            <RadialBar dataKey="value" cornerRadius={8} background={{ fill: '#1e293b' }} />
          </RadialBarChart>
        </ResponsiveContainer>
        <div className="absolute inset-0 flex flex-col items-center justify-center pointer-events-none">
          <p className="text-3xl font-extrabold" style={{ color: tone }}>{data.pct}%</p>
          <p className="text-[11px] text-slate-500 mt-1">{data.value?.toLocaleString()} / {data.target?.toLocaleString()}</p>
        </div>
      </div>
    );
  }

  if (vizType === 'heatmap') {
    const mx = data.max || 1;
    return (
      <div className="overflow-x-auto">
        <table className="text-[11px] border-separate" style={{ borderSpacing: 2 }}>
          <thead><tr><th />{data.cols.map((c: string) => <th key={c} className="text-slate-400 font-medium px-1.5 pb-1 whitespace-nowrap">{c}</th>)}</tr></thead>
          <tbody>
            {data.rows.map((r: string, i: number) => (
              <tr key={r}>
                <td className="text-slate-400 pr-2 whitespace-nowrap text-right">{r}</td>
                {data.cells[i].map((v: number, j: number) => (
                  <td key={j} title={`${r} × ${data.cols[j]}: ${v}`}
                      className="rounded text-center text-slate-100 font-semibold"
                      style={{ minWidth: 40, height: 28, backgroundColor: v ? `rgba(129,140,248,${0.15 + 0.75 * (v / mx)})` : '#1e293b55' }}>
                    {v || ''}
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    );
  }

  if (vizType === 'geo') {
    const max = Math.max(...data.regions.map((r: any) => r.value), 1);
    return (
      <div className="grid grid-cols-2 md:grid-cols-3 gap-2 py-1">
        {data.regions.map((r: any) => (
          <button key={r.region} disabled={!onDrill || data.field === 'pin_code'}
                  onClick={() => onDrill && data.field !== 'pin_code' && onDrill(data.field, r.region)}
                  className="rounded-lg p-2.5 text-left border border-slate-800/60 cursor-pointer disabled:cursor-default"
                  style={{ backgroundColor: `rgba(129,140,248,${0.08 + 0.5 * (r.value / max)})` }}>
            <p className="text-[11px] text-slate-300 truncate" title={r.region}>{r.region}</p>
            <p className="text-sm font-bold text-slate-100">{r.value.toLocaleString()} <span className="text-[10px] font-normal text-slate-400">({r.pct}%)</span></p>
          </button>
        ))}
        {data.regions.length === 0 && <p className="text-xs text-slate-500 col-span-3 text-center py-4">No location data.</p>}
      </div>
    );
  }

  if (vizType === 'comparison') {
    const up = data.delta >= 0;
    return (
      <div className="space-y-3 py-1">
        <div className="flex items-end gap-4">
          <div><p className="text-[10px] text-slate-500 uppercase font-semibold">Current {data.window_days}d</p><p className="text-2xl font-extrabold text-slate-100">{data.current.toLocaleString()}</p></div>
          <div><p className="text-[10px] text-slate-500 uppercase font-semibold">Previous {data.window_days}d</p><p className="text-2xl font-extrabold text-slate-500">{data.previous.toLocaleString()}</p></div>
          <span className={`text-sm font-bold ${up ? 'text-emerald-400' : 'text-red-400'}`}>{up ? '▲' : '▼'} {Math.abs(data.delta_pct)}%</span>
        </div>
        {data.by_dimension?.length > 0 && (
          <div className="space-y-1">
            {data.by_dimension.map((r: any) => {
              const m = Math.max(r.current, r.previous, 1);
              return (
                <div key={r.label} className="flex items-center gap-2 text-[11px]">
                  <span className="w-24 text-right text-slate-400 truncate shrink-0">{r.label}</span>
                  <div className="flex-1 space-y-0.5">
                    <div className="h-2.5 rounded bg-brand-500/70" style={{ width: `${(r.current * 100) / m}%` }} />
                    <div className="h-2.5 rounded bg-slate-600/60" style={{ width: `${(r.previous * 100) / m}%` }} />
                  </div>
                  <span className="w-20 text-slate-300 shrink-0">{r.current} <span className="text-slate-600">vs {r.previous}</span></span>
                </div>
              );
            })}
          </div>
        )}
      </div>
    );
  }

  if (vizType === 'pivot') {
    return (
      <div className="overflow-x-auto">
        <table className="w-full text-[11px]">
          <thead><tr className="text-slate-400 border-b border-slate-800"><th className="text-left py-1.5 pr-2">{data.row_field}</th>{data.columns.map((c: string) => <th key={c} className="text-right py-1.5 px-2">{c}</th>)}</tr></thead>
          <tbody>
            {data.rows.map((r: any, i: number) => (
              <tr key={i} className="border-b border-slate-800/50">
                <td className="py-1.5 pr-2 text-slate-300">{String(r.__row ?? '—')}</td>
                {data.columns.map((c: string) => <td key={c} className="text-right py-1.5 px-2 text-slate-100">{r[c] ?? 0}</td>)}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    );
  }

  // table (default)
  return (
    <div className="overflow-x-auto">
      <table className="w-full text-[11px]">
        <thead><tr className="text-slate-400 border-b border-slate-800">{data.columns.map((c: any) => <th key={c.key} className="text-left py-1.5 px-2">{c.label}</th>)}</tr></thead>
        <tbody>
          {data.rows.map((r: any, i: number) => (
            <tr key={i} className="border-b border-slate-800/50">
              {data.columns.map((c: any) => <td key={c.key} className="py-1.5 px-2 text-slate-200 whitespace-nowrap max-w-[220px] truncate">{r[c.key] == null ? '—' : String(r[c.key])}</td>)}
            </tr>
          ))}
        </tbody>
      </table>
      {data.rows.length === 0 && <p className="text-xs text-slate-500 text-center py-4">No rows.</p>}
    </div>
  );
};

/** Custom treemap cell so every node gets a palette color + readable label. */
const TreemapCell: React.FC<any> = ({ x, y, width, height, index, name, colors }) => {
  if (width < 4 || height < 4) return null;
  const fill = colors[(index || 0) % colors.length];
  return (
    <g>
      <rect x={x} y={y} width={width} height={height} rx={4} fill={`${fill}44`} stroke={fill} strokeWidth={1.5} />
      {width > 60 && height > 24 && (
        <text x={x + 6} y={y + 16} fill="#e2e8f0" fontSize={11} fontWeight={600}>{name}</text>
      )}
    </g>
  );
};
