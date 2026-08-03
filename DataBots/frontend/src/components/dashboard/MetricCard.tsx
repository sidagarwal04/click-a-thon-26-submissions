import React from 'react';
import { LucideIcon, TrendingUp, TrendingDown, AlertTriangle } from 'lucide-react';

interface MetricCardProps {
  title: string;
  value: string;
  subtext: string;
  trendPct?: number;
  icon: LucideIcon;
  color: 'blue' | 'emerald' | 'amber' | 'red';
  isAnomaly?: boolean;
}

const COLOR_MAP: Record<MetricCardProps['color'], { icon: string; bg: string; border: string; iconBg: string }> = {
  blue:    { icon: 'text-brand-600',   bg: 'bg-brand-50',   border: 'border-brand-200',   iconBg: 'bg-brand-100 border-brand-200' },
  emerald: { icon: 'text-emerald-600', bg: 'bg-emerald-50', border: 'border-emerald-200', iconBg: 'bg-emerald-100 border-emerald-200' },
  amber:   { icon: 'text-amber-600',   bg: 'bg-amber-50',   border: 'border-amber-200',   iconBg: 'bg-amber-100 border-amber-200' },
  red:     { icon: 'text-red-600',     bg: 'bg-red-50',     border: 'border-red-200',     iconBg: 'bg-red-100 border-red-200' },
};

export const MetricCard: React.FC<MetricCardProps> = ({
  title,
  value,
  subtext,
  trendPct,
  icon: Icon,
  color,
  isAnomaly,
}) => {
  const c = COLOR_MAP[color];

  return (
    <div
      className={`relative p-4 rounded-xl bg-white border transition-all duration-150 overflow-hidden hover:shadow-md shadow-sm ${
        isAnomaly ? 'border-red-300 ring-2 ring-red-100' : c.border + ' hover:border-opacity-80'
      }`}
    >
      {/* Background gradient accent */}
      <div className={`absolute -top-4 -right-4 w-20 h-20 bg-gradient-to-br ${c.bg} to-transparent rounded-full blur-xl opacity-50 pointer-events-none`} />

      <div className="relative">
        <div className="flex items-center justify-between mb-3">
          <span className="section-label">{title}</span>
          <div className={`p-2 rounded-lg border ${c.iconBg} ${c.icon}`}>
            <Icon className="w-4 h-4" />
          </div>
        </div>

        <div className="flex items-baseline justify-between gap-2">
          <span className="text-[22px] font-bold text-slate-900 tracking-tight font-mono">{value}</span>
          {trendPct !== undefined && (
            <span className={`flex items-center gap-0.5 text-[11px] font-semibold px-1.5 py-0.5 rounded border ${
              trendPct >= 0
                ? 'bg-emerald-50 text-emerald-700 border-emerald-200'
                : 'bg-red-50 text-red-700 border-red-200'
            }`}>
              {trendPct >= 0 ? <TrendingUp className="w-3 h-3" /> : <TrendingDown className="w-3 h-3" />}
              {Math.abs(trendPct)}%
            </span>
          )}
        </div>

        <p className="mt-2 text-[11px] text-slate-400 flex items-center gap-1.5">
          {isAnomaly && <AlertTriangle className="w-3 h-3 text-red-500 shrink-0" />}
          {subtext}
        </p>
      </div>
    </div>
  );
};
