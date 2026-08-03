import React from 'react';
import { FactorDecomposition, SegmentDriver, RuledOutCause } from '../../types';
import { CheckCircle2, AlertTriangle, Activity, GitBranch, Database } from 'lucide-react';

interface MetricTreeProps {
  metric: string;
  factorDecomp?: FactorDecomposition;
  topSegments: SegmentDriver[];
  ruledOut: RuledOutCause[];
}

type NodeStatus = {
  border: string;
  bg: string;
  label: string;
  labelColor: string;
  icon: React.ReactNode;
  valueColor: string;
};

export const MetricTreeVisualizer: React.FC<MetricTreeProps> = ({
  metric,
  factorDecomp,
  topSegments = [],
  ruledOut = [],
}) => {
  const primaryDriver = factorDecomp?.primary_driver_factor || 'fill_rate';

  const getStatus = (nodeMetric: string): NodeStatus => {
    if (primaryDriver === nodeMetric || metric === nodeMetric) {
      return {
        border: 'border-red-200',
        bg: 'bg-red-50',
        label: 'CRITICAL',
        labelColor: 'text-red-600',
        icon: <AlertTriangle className="w-3.5 h-3.5 text-red-500" />,
        valueColor: 'text-red-600',
      };
    }
    const cleared = ruledOut.some(
      (r) => r.dimension.includes(nodeMetric) || nodeMetric.includes(r.dimension)
    );
    if (cleared) {
      return {
        border: 'border-emerald-200',
        bg: 'bg-emerald-50',
        label: 'CLEARED',
        labelColor: 'text-emerald-600',
        icon: <CheckCircle2 className="w-3.5 h-3.5 text-emerald-500" />,
        valueColor: 'text-emerald-600',
      };
    }
    return {
      border: 'border-slate-200',
      bg: 'bg-slate-50',
      label: 'NORMAL',
      labelColor: 'text-slate-500',
      icon: <Activity className="w-3.5 h-3.5 text-slate-400" />,
      valueColor: 'text-slate-700',
    };
  };

  const reqChange    = factorDecomp?.requests_delta_pct    ?? 0.3;
  const fillChange   = factorDecomp?.fill_rate_delta_pct   ?? -28.1;
  const renderChange = factorDecomp?.render_rate_delta_pct ?? 0.1;
  const ecpmChange   = factorDecomp?.ecpm_delta_pct        ?? 0.0;

  const nodes = [
    { key: 'requests',   label: 'Requests',   change: reqChange },
    { key: 'fill_rate',  label: 'Fill Rate',  change: fillChange },
    { key: 'render_rate',label: 'Render Rate',change: renderChange },
    { key: 'ecpm',       label: 'eCPM',       change: ecpmChange },
  ];

  const fmt = (v: number) => (v > 0 ? `+${v}%` : `${v}%`);

  return (
    <div>
      {/* Header */}
      <div className="flex items-center justify-between mb-2.5">
        <div className="flex items-center gap-2">
          <GitBranch className="w-3.5 h-3.5 text-brand-500" />
          <h4 className="text-[12px] font-semibold text-slate-800">Revenue Identity Decomposition</h4>
        </div>
        <span className="flex items-center gap-1 mono-pill">
          <Database className="w-2.5 h-2.5 text-brand-500" /> ClickHouse
        </span>
      </div>

      {/* Equation row */}
      <div className="flex items-center gap-1.5 mb-3 p-2.5 rounded-lg bg-slate-50 border border-slate-200 font-mono text-[11px] overflow-x-auto">
        <span className="text-slate-400 shrink-0">Revenue =</span>
        {nodes.map((n, i) => {
          const s = getStatus(n.key);
          return (
            <React.Fragment key={n.key}>
              <span className={`px-2 py-0.5 rounded border ${s.bg} ${s.border} ${s.valueColor} shrink-0`}>
                {n.label} ({fmt(n.change)})
              </span>
              {i < nodes.length - 1 && <span className="text-slate-300 shrink-0">×</span>}
            </React.Fragment>
          );
        })}
      </div>

      {/* Node grid */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-2 mb-3">
        {nodes.map((n) => {
          const s = getStatus(n.key);
          return (
            <div key={n.key} className={`p-3 rounded-lg border ${s.bg} ${s.border} space-y-1.5`}>
              <div className="flex items-center justify-between">
                {s.icon}
                <span className={`text-[10px] font-semibold uppercase ${s.labelColor}`}>{s.label}</span>
              </div>
              <div className={`text-[17px] font-bold font-mono ${s.valueColor}`}>{fmt(n.change)}</div>
              <div className="text-[11px] text-slate-500 font-medium">{n.label}</div>
            </div>
          );
        })}
      </div>

      {/* Top segment mini-list */}
      {topSegments.length > 0 && (
        <div className="p-3 rounded-lg bg-slate-50 border border-slate-200 space-y-2">
          <p className="section-label">Top Localized Segments</p>
          <div className="grid grid-cols-1 sm:grid-cols-3 gap-2">
            {topSegments.slice(0, 3).map((seg, i) => (
              <div key={i} className="p-2.5 rounded-lg bg-white border border-slate-200 space-y-1.5 shadow-sm">
                <div className="flex items-center justify-between text-[11px]">
                  <span className="text-slate-400 capitalize">{seg.dimension}</span>
                  <span className="font-mono font-bold text-amber-600">{(seg.share_of_delta * 100).toFixed(1)}%</span>
                </div>
                <div className="font-semibold text-[13px] text-slate-900 truncate">{seg.value}</div>
                <div className="w-full bg-slate-100 h-1 rounded-full overflow-hidden">
                  <div
                    className="bg-gradient-to-r from-amber-400 to-red-400 h-full rounded-full"
                    style={{ width: `${Math.min(100, seg.share_of_delta * 100)}%` }}
                  />
                </div>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
};
