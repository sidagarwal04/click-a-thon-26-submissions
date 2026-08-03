import React from 'react';
import {
  ResponsiveContainer,
  AreaChart,
  Area,
  XAxis,
  YAxis,
  Tooltip,
  CartesianGrid,
  Legend,
} from 'recharts';
import { TimeSeriesPoint } from '../../types';
import { AlertCircle, TrendingDown } from 'lucide-react';

interface MetricChartsProps {
  data: TimeSeriesPoint[];
  onSelectAnomalyTime?: (time: string) => void;
}

export const MetricCharts: React.FC<MetricChartsProps> = ({ data, onSelectAnomalyTime }) => {
  return (
    <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
      {/* Chart 1: Fill Rate % (Actual vs Baseline) */}
      <div className="p-6 rounded-2xl bg-white border border-slate-200 shadow-sm">
        <div className="flex items-center justify-between mb-4">
          <div>
            <h3 className="text-base font-bold text-slate-900 flex items-center gap-2">
              Fill Rate % vs Baseline (Hourly)
              <span className="text-xs font-medium px-2 py-0.5 rounded bg-red-50 text-red-700 border border-red-200">
                Incident at 14:00
              </span>
            </h3>
            <p className="text-xs text-slate-400">Comparing current hourly fill rate against trailing baseline</p>
          </div>
          {onSelectAnomalyTime && (
            <button
              onClick={() => onSelectAnomalyTime('14:00')}
              className="flex items-center gap-1 text-xs font-semibold px-3 py-1.5 rounded-lg bg-red-50 text-red-700 hover:bg-red-100 border border-red-200 transition-colors"
            >
              <AlertCircle className="w-3.5 h-3.5" /> Inspect RCA
            </button>
          )}
        </div>

        <div className="h-64 w-full">
          <ResponsiveContainer width="100%" height="100%">
            <AreaChart data={data} margin={{ top: 10, right: 10, left: -20, bottom: 0 }}>
              <defs>
                <linearGradient id="fillRateActual" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="5%" stopColor="#f43f5e" stopOpacity={0.25} />
                  <stop offset="95%" stopColor="#f43f5e" stopOpacity={0.0} />
                </linearGradient>
                <linearGradient id="fillRateBaseline" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="5%" stopColor="#6366f1" stopOpacity={0.15} />
                  <stop offset="95%" stopColor="#6366f1" stopOpacity={0.0} />
                </linearGradient>
              </defs>
              <CartesianGrid strokeDasharray="3 3" stroke="#f1f5f9" />
              <XAxis dataKey="time" stroke="#94a3b8" fontSize={11} />
              <YAxis stroke="#94a3b8" fontSize={11} domain={[40, 90]} />
              <Tooltip
                contentStyle={{ backgroundColor: '#fff', borderColor: '#e2e8f0', borderRadius: '12px', color: '#0f172a', boxShadow: '0 4px 6px rgba(0,0,0,0.07)' }}
                formatter={(val: any) => [`${val}%`, '']}
              />
              <Legend wrapperStyle={{ fontSize: '12px', color: '#64748b' }} />
              <Area type="monotone" dataKey="actualFillRate" name="Actual Fill Rate %" stroke="#f43f5e" strokeWidth={2.5} fillOpacity={1} fill="url(#fillRateActual)" />
              <Area type="monotone" dataKey="baselineFillRate" name="Baseline Fill Rate %" stroke="#6366f1" strokeWidth={2} strokeDasharray="4 4" fillOpacity={1} fill="url(#fillRateBaseline)" />
            </AreaChart>
          </ResponsiveContainer>
        </div>
      </div>

      {/* Chart 2: Revenue ($) Trend */}
      <div className="p-6 rounded-2xl bg-white border border-slate-200 shadow-sm">
        <div className="flex items-center justify-between mb-4">
          <div>
            <h3 className="text-base font-bold text-slate-900 flex items-center gap-2">
              Hourly Revenue ($)
            </h3>
            <p className="text-xs text-slate-400">Net revenue aggregate across 9M ad events</p>
          </div>
          <span className="flex items-center gap-1 text-xs font-semibold px-2.5 py-1 rounded bg-amber-50 text-amber-700 border border-amber-200">
            <TrendingDown className="w-3.5 h-3.5" /> -28.4% Delta
          </span>
        </div>

        <div className="h-64 w-full">
          <ResponsiveContainer width="100%" height="100%">
            <AreaChart data={data} margin={{ top: 10, right: 10, left: -10, bottom: 0 }}>
              <defs>
                <linearGradient id="revActual" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="5%" stopColor="#10b981" stopOpacity={0.25} />
                  <stop offset="95%" stopColor="#10b981" stopOpacity={0.0} />
                </linearGradient>
                <linearGradient id="revBaseline" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="5%" stopColor="#818cf8" stopOpacity={0.15} />
                  <stop offset="95%" stopColor="#818cf8" stopOpacity={0.0} />
                </linearGradient>
              </defs>
              <CartesianGrid strokeDasharray="3 3" stroke="#f1f5f9" />
              <XAxis dataKey="time" stroke="#94a3b8" fontSize={11} />
              <YAxis stroke="#94a3b8" fontSize={11} />
              <Tooltip
                contentStyle={{ backgroundColor: '#fff', borderColor: '#e2e8f0', borderRadius: '12px', color: '#0f172a', boxShadow: '0 4px 6px rgba(0,0,0,0.07)' }}
                formatter={(val: any) => [`$${Number(val).toLocaleString()}`, '']}
              />
              <Legend wrapperStyle={{ fontSize: '12px', color: '#64748b' }} />
              <Area type="monotone" dataKey="actualRevenue" name="Actual Revenue ($)" stroke="#10b981" strokeWidth={2.5} fillOpacity={1} fill="url(#revActual)" />
              <Area type="monotone" dataKey="baselineRevenue" name="Baseline Revenue ($)" stroke="#818cf8" strokeWidth={2} strokeDasharray="4 4" fillOpacity={1} fill="url(#revBaseline)" />
            </AreaChart>
          </ResponsiveContainer>
        </div>
      </div>
    </div>
  );
};
