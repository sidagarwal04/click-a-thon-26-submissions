import React, { useState, useEffect } from 'react';
import { MetricSummary, TimeSeriesPoint, FilterState } from '../../types';
import { MetricCard } from './MetricCard';
import { MetricCharts } from './MetricCharts';
import { FilterBar } from './FilterBar';
import { LiveEventStream } from './LiveEventStream';
import { fetchDashboardSummary, fetchDashboardTimeSeries } from '../../services/api';
import {
  Activity,
  Percent,
  DollarSign,
  TrendingUp,
  AlertTriangle,
  ArrowRight,
  BarChart2,
} from 'lucide-react';

interface DashboardViewProps {
  metrics?: MetricSummary;
  timeSeries?: TimeSeriesPoint[];
  onNavigateToRca: () => void;
  pendingRcaCount: number;
}

export const DashboardView: React.FC<DashboardViewProps> = ({
  metrics: initialMetrics,
  timeSeries: initialTimeSeries,
  onNavigateToRca,
  pendingRcaCount,
}) => {
  const [metrics, setMetrics] = useState<MetricSummary>(
    initialMetrics || { revenue: 2305.72, fillRatePct: 76.2, totalRequests: 1254559, impressions: 956194, clicks: 28685, ctrPct: 3.0, ecpm: 2.82 }
  );
  const [timeSeries, setTimeSeries] = useState<TimeSeriesPoint[]>(initialTimeSeries || []);

  const [filters, setFilters] = useState<FilterState>({
    timeRange: 'last_24h',
    appCategory: 'all',
    vertical: 'all',
    region: 'all',
    adFormat: 'all',
    deviceModel: 'all',
  });

  useEffect(() => {
    fetchDashboardSummary().then((data) => {
      if (data) setMetrics(data);
    });
    fetchDashboardTimeSeries().then((data) => {
      if (data && data.length > 0) setTimeSeries(data);
    });
  }, []);

  const handleResetFilters = () => {
    setFilters({
      timeRange: 'last_24h',
      appCategory: 'all',
      vertical: 'all',
      region: 'all',
      adFormat: 'all',
      deviceModel: 'all',
    });
  };

  return (
    <div className="space-y-5 pb-12">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2.5">
          <div className="p-2 rounded-lg bg-slate-100 border border-slate-200">
            <BarChart2 className="w-4 h-4 text-brand-600" />
          </div>
          <div>
            <h2 className="text-[14px] font-bold text-slate-900 leading-tight">Event Stream Dashboard</h2>
            <p className="text-[11px] text-slate-400 leading-tight">ClickHouse Live Query Dashboard — ad_events Fact Table</p>
          </div>
        </div>
      </div>

      {/* Alert banner if pending RCA review exists */}
      {pendingRcaCount > 0 && (
        <div className="card flex flex-wrap items-center justify-between gap-3 p-3.5 border-amber-300 bg-amber-50">
          <div className="flex items-center gap-2.5">
            <AlertTriangle className="w-4 h-4 text-amber-500 shrink-0" />
            <div>
              <p className="text-[13px] font-semibold text-slate-900 leading-tight">Revenue Spike Incident — Z-Score: +14.2</p>
              <p className="text-[11px] text-slate-500 leading-tight">+10,558.8% Spike at 2026-06-21 · Human-in-the-Loop review required</p>
            </div>
          </div>
          <button
            onClick={onNavigateToRca}
            className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-amber-500 hover:bg-amber-600 text-white font-bold text-[12px] transition-all shrink-0 shadow-sm"
          >
            Review RCA <ArrowRight className="w-3.5 h-3.5" />
          </button>
        </div>
      )}

      {/* Filter Bar */}
      <FilterBar filters={filters} setFilters={setFilters} onReset={handleResetFilters} />

      {/* KPI Metric Cards Grid */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        <MetricCard
          title="Total Window Revenue"
          value={`$${metrics.revenue.toLocaleString()}`}
          subtext="ClickHouse ad_events sum(revenue)"
          trendPct={10558.8}
          icon={DollarSign}
          color="emerald"
          isAnomaly
        />
        <MetricCard
          title="Fill Rate"
          value={`${metrics.fillRatePct}%`}
          subtext="ClickHouse sum(is_filled)/count()"
          trendPct={0.4}
          icon={Percent}
          color="blue"
        />
        <MetricCard
          title="Total Ad Requests"
          value={metrics.totalRequests.toLocaleString()}
          subtext="ClickHouse ad_events count()"
          trendPct={10813.4}
          icon={Activity}
          color="red"
          isAnomaly
        />
        <MetricCard
          title="Average eCPM"
          value={`$${metrics.ecpm.toFixed(2)}`}
          subtext="CPM across impressions"
          trendPct={0.3}
          icon={TrendingUp}
          color="amber"
        />
      </div>

      {/* Recharts Performance Visualizations */}
      <MetricCharts data={timeSeries} onSelectAnomalyTime={onNavigateToRca} />

      {/* Live Stream Table */}
      <LiveEventStream />
    </div>
  );
};
